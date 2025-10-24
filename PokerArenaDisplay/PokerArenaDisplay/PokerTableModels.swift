import Foundation
import SwiftUI

enum TablePhase: String, CaseIterable {
    case preFlop = "PRE_FLOP"
    case flop = "FLOP"
    case turn = "TURN"
    case river = "RIVER"
    case showdown = "SHOWDOWN"

    var displayName: String {
        switch self {
        case .preFlop: return "Pre-Flop"
        case .flop: return "Flop"
        case .turn: return "Turn"
        case .river: return "River"
        case .showdown: return "Showdown"
        }
    }
}

struct CardModel: Identifiable, Hashable {
    let id = UUID()
    let rank: String
    let suit: Suit

    init(rank: String, suit: Suit) {
        self.rank = rank
        self.suit = suit
    }

    init?(label: String) {
        guard label.count == 2 else { return nil }
        let components = Array(label)
        guard let suit = Suit(character: components[1]) else { return nil }
        self.rank = String(components[0])
        self.suit = suit
    }

    enum Suit: String {
        case hearts
        case diamonds
        case clubs
        case spades

        init?(character: Character) {
            switch character {
            case "h": self = .hearts
            case "d": self = .diamonds
            case "c": self = .clubs
            case "s": self = .spades
            default: return nil
            }
        }

        var symbol: String {
            switch self {
            case .hearts: return "♥︎"
            case .diamonds: return "♦︎"
            case .clubs: return "♣︎"
            case .spades: return "♠︎"
            }
        }

        var textColor: Color {
            switch self {
            case .hearts, .diamonds:
                return .red
            case .clubs, .spades:
                return .black
            }
        }
    }
}

struct PlayerSeatModel: Identifiable {
    let id = UUID()
    let seatIndex: Int
    let name: String
    let stack: Int
    let committed: Int
    let totalInPot: Int
    let status: Status
    let isButton: Bool
    let isActing: Bool
    let connected: Bool
    let recentActions: [String]

    enum Status: String {
        case active
        case folded
        case busted
        case disconnected
    }
}

struct EventLog: Identifiable {
    let id = UUID()
    let icon: String
    let message: String
    let timestamp: Date
}

struct TableState {
    // Snapshot of everything the UI needs—no networking required here.
    var handID: String?
    var phase: TablePhase = .preFlop
    var pot: Int = 0
    var sidePots: [Int] = []
    var community: [CardModel] = []
    var seats: [PlayerSeatModel] = []
    var logs: [EventLog] = []
    var actingSeat: Int?
    var smallBlind: Int = 0
    var bigBlind: Int = 0
    var lastUpdated: Date = Date()

    static let sample: TableState = {
        let seats: [PlayerSeatModel] = [
            PlayerSeatModel(
                seatIndex: 0,
                name: "Alpha",
                stack: 4820,
                committed: 80,
                totalInPot: 180,
                status: .active,
                isButton: true,
                isActing: false,
                connected: true,
                recentActions: ["Raise 120", "Bet 220"]
            ),
            PlayerSeatModel(
                seatIndex: 1,
                name: "Bravo",
                stack: 3140,
                committed: 220,
                totalInPot: 220,
                status: .active,
                isButton: false,
                isActing: true,
                connected: true,
                recentActions: ["Call 220", "Check"]
            ),
            PlayerSeatModel(
                seatIndex: 2,
                name: "Charlie",
                stack: 915,
                committed: 0,
                totalInPot: 120,
                status: .folded,
                isButton: false,
                isActing: false,
                connected: true,
                recentActions: ["Fold"]
            ),
            PlayerSeatModel(
                seatIndex: 3,
                name: "Delta",
                stack: 7600,
                committed: 220,
                totalInPot: 220,
                status: .active,
                isButton: false,
                isActing: false,
                connected: true,
                recentActions: ["Call 220"]
            ),
            PlayerSeatModel(
                seatIndex: 4,
                name: "Echo",
                stack: 5400,
                committed: 0,
                totalInPot: 0,
                status: .active,
                isButton: false,
                isActing: false,
                connected: false,
                recentActions: []
            ),
            PlayerSeatModel(
                seatIndex: 5,
                name: "Foxtrot",
                stack: 0,
                committed: 0,
                totalInPot: 0,
                status: .busted,
                isButton: false,
                isActing: false,
                connected: false,
                recentActions: ["Eliminated"]
            ),
        ]

        let community: [CardModel] = [
            CardModel(rank: "A", suit: .spades),
            CardModel(rank: "K", suit: .hearts),
            CardModel(rank: "Q", suit: .clubs),
            CardModel(rank: "T", suit: .diamonds),
        ]

        let logs = [
            EventLog(icon: "bolt.fill", message: "Alpha raised to 120", timestamp: Date().addingTimeInterval(-60)),
            EventLog(icon: "xmark.circle.fill", message: "Charlie folded", timestamp: Date().addingTimeInterval(-45)),
            EventLog(icon: "drop.fill", message: "Pot is now 960", timestamp: Date().addingTimeInterval(-30)),
            EventLog(icon: "sparkles", message: "Turn dealt: ♦︎T", timestamp: Date().addingTimeInterval(-10)),
        ]

        var state = TableState()
        state.handID = "H-20251022-00421"
        state.phase = .turn
        state.pot = 1240
        state.sidePots = [400, 300]
        state.community = community
        state.seats = seats
        state.logs = logs
        state.actingSeat = 1
        state.smallBlind = 10
        state.bigBlind = 20
        state.lastUpdated = Date()
        return state
    }()

    static var placeholder: TableState {
        TableState()
    }
}
