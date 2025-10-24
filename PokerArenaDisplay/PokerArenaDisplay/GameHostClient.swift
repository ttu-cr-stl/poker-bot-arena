import Foundation

// Lightweight wrapper around URLSessionWebSocketTask so the view model only
// deals with Swift structs instead of raw JSON strings.

struct HostEnvelope: Decodable {
    let type: String
}

struct SpectatorSnapshot: Decodable {
    struct Config: Decodable {
        let variant: String
        let seats: Int
        let sb: Int
        let bb: Int
    }

    struct Seat: Decodable {
        let seat: Int
        let team: String
        let stack: Int
        let committed: Int
        let totalInPot: Int
        let hasFolded: Bool
        let status: String
        let connected: Bool
        let isButton: Bool
        let isActing: Bool
    }

    struct Hand: Decodable {
        let handId: String
        let phase: String
        let button: Int
        let actingSeat: Int?
        let currentBet: Int
        let minRaiseIncrement: Int
        let pot: Int
        let sidePots: [Int]
        let community: [String]
        let seats: [Seat]
    }

    struct Lobby: Decodable {
        struct Player: Decodable {
            let seat: Int
            let team: String
            let connected: Bool
            let stack: Int
        }

        let players: [Player]
    }

    let hand: Hand?
    let config: Config
    let lobby: Lobby
    let timestamp: Double
}

struct SpectatorWelcome: Decodable {
    struct Config: Decodable {
        let variant: String
        let seats: Int
        let startingStack: Int
        let sb: Int
        let bb: Int
        let moveTimeMs: Int
    }

    let tableId: String
    let config: Config
}

struct TableEventMessage: Decodable {
    let ev: String
    let seat: Int?
    let amount: Int?
    let cards: [String]?
    let card: String?
    let rank: String?
    let sbSeat: Int?
    let bbSeat: Int?
    let sb: Int?
    let bb: Int?
}

struct StartHandMessage: Decodable {
    struct StackEntry: Decodable {
        let seat: Int
        let stack: Int
    }

    let handId: String
    let button: Int
    let stacks: [StackEntry]
}

struct EndHandMessage: Decodable {
    struct StackEntry: Decodable {
        let seat: Int
        let stack: Int
    }

    let handId: String
    let stacks: [StackEntry]
}

struct MatchEndMessage: Decodable {
    struct Winner: Decodable {
        let seat: Int
        let team: String
    }

    struct FinalStack: Decodable {
        let seat: Int
        let team: String
        let stack: Int
    }

    let winner: Winner?
    let finalStacks: [FinalStack]
}

struct LobbyMessage: Decodable {
    struct Player: Decodable {
        let seat: Int
        let team: String
        let connected: Bool
        let stack: Int
    }

    let players: [Player]
}

struct AdminMessage: Decodable {
    let event: String
    let seat: Int?
}

final class GameHostClient {
    private let url: URL
    private let session: URLSession
    private var task: URLSessionWebSocketTask?
    private var isShuttingDown = false

    var onConnected: (() -> Void)?
    var onDisconnected: (() -> Void)?
    var onSnapshot: ((SpectatorSnapshot) -> Void)?
    var onEvent: ((TableEventMessage) -> Void)?
    var onStartHand: ((StartHandMessage) -> Void)?
    var onEndHand: ((EndHandMessage) -> Void)?
    var onMatchEnd: ((MatchEndMessage) -> Void)?
    var onLobby: ((LobbyMessage) -> Void)?
    var onError: ((Error) -> Void)?
    var onAdmin: ((AdminMessage) -> Void)?

    private let decoder: JSONDecoder = {
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        return decoder
    }()

    init(url: URL, session: URLSession = .shared) {
        self.url = url
        self.session = session
    }

    func connect() {
        disconnect()
        isShuttingDown = false
        let task = session.webSocketTask(with: url)
        self.task = task
        task.resume()
        sendHello()
        listen()
    }

    func disconnect() {
        isShuttingDown = true
        task?.cancel(with: .goingAway, reason: nil)
        task = nil
    }

    private func sendHello() {
        // Spectators identify themselves; default to presentation mode.
        let payload: [String: Any] = [
            "type": "hello",
            "v": 1,
            "role": "spectator",
            "mode": "presentation",
        ]
        guard let data = try? JSONSerialization.data(withJSONObject: payload, options: []),
              let string = String(data: data, encoding: .utf8)
        else {
            return
        }

        task?.send(.string(string)) { [weak self] error in
            if let error {
                self?.handleError(error)
            }
        }
    }

    private func listen() {
        task?.receive { [weak self] result in
            guard let self else { return }
            switch result {
            case .failure(let error):
                self.handleError(error)
            case .success(let message):
                switch message {
                case .string(let text):
                    self.handle(text: text)
                case .data(let data):
                    if let text = String(data: data, encoding: .utf8) {
                        self.handle(text: text)
                    }
                @unknown default:
                    break
                }
                self.listen()
            }
        }
    }

    private func handle(text: String) {
        guard let data = text.data(using: .utf8),
              let envelope = try? decoder.decode(HostEnvelope.self, from: data)
        else {
            return
        }

        switch envelope.type {
        case "spectator_welcome":
            DispatchQueue.main.async { [weak self] in
                self?.onConnected?()
            }
        case "spectator_snapshot":
            if let snapshot = try? decoder.decode(SpectatorSnapshot.self, from: data) {
                DispatchQueue.main.async { [weak self] in
                    self?.onSnapshot?(snapshot)
                }
            }
        case "event":
            if let event = try? decoder.decode(TableEventMessage.self, from: data) {
                DispatchQueue.main.async { [weak self] in
                    self?.onEvent?(event)
                }
            }
        case "start_hand":
            if let startHand = try? decoder.decode(StartHandMessage.self, from: data) {
                DispatchQueue.main.async { [weak self] in
                    self?.onStartHand?(startHand)
                }
            }
        case "end_hand":
            if let endHand = try? decoder.decode(EndHandMessage.self, from: data) {
                DispatchQueue.main.async { [weak self] in
                    self?.onEndHand?(endHand)
                }
            }
        case "match_end":
            if let match = try? decoder.decode(MatchEndMessage.self, from: data) {
                DispatchQueue.main.async { [weak self] in
                    self?.onMatchEnd?(match)
                }
            }
        case "lobby":
            if let lobby = try? decoder.decode(LobbyMessage.self, from: data) {
                DispatchQueue.main.async { [weak self] in
                    self?.onLobby?(lobby)
                }
            }
        case "admin":
            if let admin = try? decoder.decode(AdminMessage.self, from: data) {
                DispatchQueue.main.async { [weak self] in
                    self?.onAdmin?(admin)
                }
            }
        default:
            break
        }
    }

    func send(command: [String: Any]) {
        guard !isShuttingDown, let task else { return }
        guard let data = try? JSONSerialization.data(withJSONObject: command, options: []),
              let string = String(data: data, encoding: .utf8) else {
            return
        }

        task.send(.string(string)) { [weak self] error in
            if let error {
                self?.handleError(error)
            }
        }
    }

    private func handleError(_ error: Error) {
        guard !isShuttingDown else { return }
        DispatchQueue.main.async { [weak self] in
            self?.onError?(error)
            self?.onDisconnected?()
        }
    }
}
