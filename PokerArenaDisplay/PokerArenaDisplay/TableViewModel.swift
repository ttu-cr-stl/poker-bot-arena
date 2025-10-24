import Foundation
import SwiftUI
import Combine

// Acts as the brains for the macOS dashboard: keeps a TableState in sync,
// transforms host messages, and exposes simple actions for the UI.

@MainActor
final class TableViewModel: ObservableObject {
    enum ConnectionStatus {
        case disconnected
        case connecting
        case connected
        case failed(String)

        var label: String {
            switch self {
            case .disconnected:
                return "Disconnected"
            case .connecting:
                return "Connecting…"
            case .connected:
                return "Connected"
            case .failed(let message):
                return "Error: \(message)"
            }
        }

        var tint: Color {
            switch self {
            case .disconnected:
                return .gray
            case .connecting:
                return .yellow
            case .connected:
                return .green
            case .failed:
                return .red
            }
        }
    }

    @Published var state: TableState = .placeholder
    @Published var connectionStatus: ConnectionStatus = .disconnected
    @Published var hostURLString: String = "ws://127.0.0.1:8765/ws"

    private var client: GameHostClient?
    private var recentActionsBySeat: [Int: [String]] = [:]
    private let logLimit = 12

    func connect() {
        guard let url = URL(string: hostURLString) else {
            connectionStatus = .failed("Invalid URL")
            return
        }

        connectionStatus = .connecting
        recentActionsBySeat.removeAll()

        let client = GameHostClient(url: url)
        configure(client: client)
        client.connect()
        self.client = client
    }

    func disconnect() {
        client?.disconnect()
        client = nil
        connectionStatus = .disconnected
    }

    func autoConnectIfNeeded() {
        guard case .disconnected = connectionStatus else { return }
        connect()
    }

    var canSkipCurrentTurn: Bool {
        guard case .connected = connectionStatus else { return false }
        return state.actingSeat != nil
    }

    var currentActorDescription: String? {
        guard let seat = state.actingSeat else { return nil }
        return name(for: seat) ?? "Seat \(seat + 1)"
    }

    func skipCurrentTurn() {
        guard let client, canSkipCurrentTurn else { return }
        // Send a tiny JSON command; host decides which action to apply.
        client.send(command: ["type": "skip"])
    }

    private func configure(client: GameHostClient) {
        client.onConnected = { [weak self] in
            self?.connectionStatus = .connected
        }

        client.onDisconnected = { [weak self] in
            guard let self else { return }
            if case .failed = self.connectionStatus {
                return
            }
            self.connectionStatus = .disconnected
        }

        client.onError = { [weak self] error in
            self?.connectionStatus = .failed(error.localizedDescription)
        }

        client.onSnapshot = { [weak self] snapshot in
            self?.apply(snapshot: snapshot)
        }

        client.onEvent = { [weak self] event in
            self?.handle(event: event)
        }

        client.onStartHand = { [weak self] message in
            self?.handleStartHand(message)
        }

        client.onEndHand = { [weak self] message in
            self?.handleEndHand(message)
        }

        client.onMatchEnd = { [weak self] message in
            self?.handleMatchEnd(message)
        }

        client.onLobby = { [weak self] message in
            self?.handleLobby(message)
        }

        client.onAdmin = { [weak self] admin in
            self?.handleAdmin(admin)
        }
    }

    private func apply(snapshot: SpectatorSnapshot) {
        var updated = state
        updated.smallBlind = snapshot.config.sb
        updated.bigBlind = snapshot.config.bb
        updated.lastUpdated = Date()

        if let hand = snapshot.hand {
            updated.handID = hand.handId
            updated.phase = TablePhase(rawValue: hand.phase) ?? .preFlop
            updated.pot = hand.pot
            updated.sidePots = hand.sidePots
            updated.community = hand.community.compactMap(CardModel.init)
            updated.actingSeat = hand.actingSeat
            updated.seats = hand.seats
                .sorted(by: { $0.seat < $1.seat })
                .map { seatSnapshot in
                    var status = PlayerSeatModel.Status.from(snapshot: seatSnapshot.status)
                    if !seatSnapshot.connected {
                        status = .disconnected
                    }
                    return PlayerSeatModel(
                        seatIndex: seatSnapshot.seat,
                        name: seatSnapshot.team,
                        stack: seatSnapshot.stack,
                        committed: seatSnapshot.committed,
                        totalInPot: seatSnapshot.totalInPot,
                        status: status,
                        isButton: seatSnapshot.isButton,
                        isActing: seatSnapshot.isActing,
                        connected: seatSnapshot.connected,
                        recentActions: recentActionsBySeat[seatSnapshot.seat] ?? []
                    )
                }
        } else {
            updated.handID = nil
            updated.phase = .preFlop
            updated.pot = 0
            updated.community = []
            updated.sidePots = []
            updated.actingSeat = nil
            updated.seats = snapshot.lobby.players
                .sorted(by: { $0.seat < $1.seat })
                .map { player in
                    let status: PlayerSeatModel.Status = player.stack > 0 ? .active : .busted
                    return PlayerSeatModel(
                        seatIndex: player.seat,
                        name: player.team,
                        stack: player.stack,
                        committed: 0,
                        totalInPot: 0,
                        status: player.connected ? status : .disconnected,
                        isButton: false,
                        isActing: false,
                        connected: player.connected,
                        recentActions: recentActionsBySeat[player.seat] ?? []
                    )
                }
        }

        updated.logs = state.logs
        state = updated
    }

    private func handle(event: TableEventMessage) {
        let seatName = name(for: event.seat)
        let icon: String
        let message: String

        switch event.ev {
        case "POST_BLINDS":
            icon = "banknote.fill"
            if let sbSeat = event.sbSeat, let bbSeat = event.bbSeat, let sb = event.sb, let bb = event.bb {
                let sbName = name(for: sbSeat) ?? "Seat \(sbSeat)"
                let bbName = name(for: bbSeat) ?? "Seat \(bbSeat)"
                message = "\(sbName) posted \(sb), \(bbName) posted \(bb)"
                pushAction("Posted \(sb)", for: sbSeat)
                pushAction("Posted \(bb)", for: bbSeat)
            } else {
                message = "Blinds posted"
            }
        case "BET":
            icon = "flame.fill"
            if let seat = event.seat, let amount = event.amount {
                message = "\(seatName ?? "Seat \(seat)") bet \(amount)"
                pushAction("Bet \(amount)", for: seat)
            } else {
                message = "Bet placed"
            }
        case "CALL":
            icon = "phone.fill"
            if let seat = event.seat, let amount = event.amount {
                message = "\(seatName ?? "Seat \(seat)") called \(amount)"
                pushAction("Call \(amount)", for: seat)
            } else {
                message = "Call"
            }
        case "CHECK":
            icon = "checkmark.circle"
            if let seat = event.seat {
                message = "\(seatName ?? "Seat \(seat)") checked"
                pushAction("Checked", for: seat)
            } else {
                message = "Check"
            }
        case "FOLD":
            icon = "xmark.circle.fill"
            if let seat = event.seat {
                message = "\(seatName ?? "Seat \(seat)") folded"
                pushAction("Folded", for: seat)
            } else {
                message = "Fold"
            }
        case "SHOWDOWN":
            icon = "sparkles"
            if let seat = event.seat, let rank = event.rank {
                message = "\(seatName ?? "Seat \(seat)") showed \(rank.replacingOccurrences(of: "_", with: " "))"
                pushAction("Showed \(rank)", for: seat)
            } else {
                message = "Showdown"
            }
        case "POT_AWARD":
            icon = "trophy.fill"
            if let seat = event.seat, let amount = event.amount {
                message = "\(seatName ?? "Seat \(seat)") won \(amount)"
                pushAction("Won \(amount)", for: seat)
            } else {
                message = "Pot awarded"
            }
        case "ELIMINATED":
            icon = "skull.fill"
            if let seat = event.seat {
                message = "\(seatName ?? "Seat \(seat)") eliminated"
                pushAction("Eliminated", for: seat)
            } else {
                message = "Player eliminated"
            }
        case "FLOP":
            icon = "rectangle.grid.3x2.fill"
            if let cards = event.cards {
                message = "Flop: \(cards.joined(separator: " "))"
            } else {
                message = "Flop dealt"
            }
        case "TURN":
            icon = "arrow.triangle.2.circlepath"
            if let card = event.card {
                message = "Turn: \(card)"
            } else {
                message = "Turn dealt"
            }
        case "RIVER":
            icon = "drop.fill"
            if let card = event.card {
                message = "River: \(card)"
            } else {
                message = "River dealt"
            }
        default:
            icon = "questionmark.circle"
            message = event.ev.capitalized
        }

        appendLog(icon: icon, message: message)
        refreshSeatActions()
    }

    private func handleStartHand(_ message: StartHandMessage) {
        recentActionsBySeat.removeAll()
        appendLog(icon: "play.fill", message: "Hand \(message.handId) started")
    }

    private func handleEndHand(_ message: EndHandMessage) {
        appendLog(icon: "flag.checkered", message: "Hand \(message.handId) completed")
    }

    private func handleMatchEnd(_ message: MatchEndMessage) {
        if let winner = message.winner {
            appendLog(icon: "crown.fill", message: "\(winner.team) wins the match")
        } else {
            appendLog(icon: "crown.fill", message: "Match complete")
        }
    }

    private func handleLobby(_ message: LobbyMessage) {
        var updated = state
        let connections = Dictionary(uniqueKeysWithValues: message.players.map { ($0.seat, $0.connected) })
        updated.seats = updated.seats.map { seat in
            let isConnected = connections[seat.seatIndex] ?? seat.connected
            let status: PlayerSeatModel.Status
            if !isConnected {
                status = .disconnected
            } else if case .busted = seat.status {
                status = .busted
            } else if case .folded = seat.status {
                status = .folded
            } else {
                status = .active
            }
            return PlayerSeatModel(
                seatIndex: seat.seatIndex,
                name: seat.name,
                stack: seat.stack,
                committed: seat.committed,
                totalInPot: seat.totalInPot,
                status: status,
                isButton: seat.isButton,
                isActing: seat.isActing,
                connected: isConnected,
                recentActions: recentActionsBySeat[seat.seatIndex] ?? seat.recentActions
            )
        }
        state = updated
    }

    private func handleAdmin(_ message: AdminMessage) {
        guard message.event.uppercased() == "SKIP" else { return }
        if let seat = message.seat {
            let label = name(for: seat) ?? "Seat \(seat)"
            pushAction("Skipped", for: seat)
            appendLog(icon: "forward.fill", message: "Manual skip applied to \(label)")
        } else {
            appendLog(icon: "forward.fill", message: "Manual skip applied")
        }
        refreshSeatActions()
    }

    private func appendLog(icon: String, message: String) {
        var updated = state
        updated.logs.insert(EventLog(icon: icon, message: message, timestamp: Date()), at: 0)
        if updated.logs.count > logLimit {
            updated.logs = Array(updated.logs.prefix(logLimit))
        }
        state = updated
    }

    private func name(for seat: Int?) -> String? {
        guard let seat else { return nil }
        return state.seats.first(where: { $0.seatIndex == seat })?.name
    }

    private func pushAction(_ text: String, for seat: Int) {
        var actions = recentActionsBySeat[seat] ?? []
        actions.insert(text, at: 0)
        if actions.count > 3 {
            actions = Array(actions.prefix(3))
        }
        recentActionsBySeat[seat] = actions
    }

    private func refreshSeatActions() {
        var updated = state
        updated.seats = updated.seats.map { seat in
            PlayerSeatModel(
                seatIndex: seat.seatIndex,
                name: seat.name,
                stack: seat.stack,
                committed: seat.committed,
                totalInPot: seat.totalInPot,
                status: seat.status,
                isButton: seat.isButton,
                isActing: seat.isActing,
                connected: seat.connected,
                recentActions: recentActionsBySeat[seat.seatIndex] ?? seat.recentActions
            )
        }
        state = updated
    }
}

private extension PlayerSeatModel.Status {
    static func from(snapshot status: String) -> PlayerSeatModel.Status {
        switch status.uppercased() {
        case "FOLDED":
            return .folded
        case "BUSTED":
            return .busted
        case "DISCONNECTED":
            return .disconnected
        default:
            return .active
        }
    }
}
