import SwiftUI

// Pure rendering layer. Takes a TableState snapshot and draws the table.
struct PokerTableView: View {
    var state: TableState

    var body: some View {
        GeometryReader { proxy in
            ZStack {
                backgroundView
                VStack(spacing: 28) {
                    tableHeader
                    Spacer(minLength: 20)
                    tableSurface(size: proxy.size)
                    Spacer(minLength: 16)
                    potFooter
                }
                .padding(.horizontal, 48)
                .padding(.vertical, 36)
            }
        }
        .ignoresSafeArea()
    }

    private var backgroundView: some View {
        LinearGradient(
            colors: [
                Color(red: 0.04, green: 0.14, blue: 0.26),
                Color(red: 0.02, green: 0.09, blue: 0.17)
            ],
            startPoint: .topLeading,
            endPoint: .bottomTrailing
        )
        .overlay(
            RadialGradient(
                colors: [Color.white.opacity(0.18), Color.clear],
                center: .center,
                startRadius: 40,
                endRadius: 520
            )
            .blendMode(.screen)
            .opacity(0.7)
        )
        .overlay(Color.black.opacity(0.15))
    }

    private var tableHeader: some View {
        VStack(spacing: 12) {
            Text("Poker Bot Arena")
                .font(.title2.weight(.semibold))
                .foregroundStyle(.white.opacity(0.92))
                .textCase(.uppercase)
                .tracking(2)

            HStack(alignment: .firstTextBaseline, spacing: 18) {
                Label(state.phase.displayName, systemImage: "square.grid.3x3.fill")
                    .font(.callout.weight(.medium))
                    .foregroundStyle(.white.opacity(0.75))

                if let handID = state.handID {
                    Label(handID, systemImage: "number.circle")
                        .font(.caption)
                        .foregroundStyle(.white.opacity(0.55))
                }

                Spacer()

                Label("SB \(state.smallBlind)", systemImage: "arrowtriangle.down.fill")
                    .font(.caption)
                    .foregroundStyle(.white.opacity(0.65))

                Label("BB \(state.bigBlind)", systemImage: "arrowtriangle.up.fill")
                    .font(.caption)
                    .foregroundStyle(.white.opacity(0.65))
            }
        }
        .padding(.horizontal, 32)
        .padding(.vertical, 16)
        .background(
            RoundedRectangle(cornerRadius: 28, style: .continuous)
                .fill(.regularMaterial)
                .opacity(0.55)
        )
        .overlay(
            RoundedRectangle(cornerRadius: 28, style: .continuous)
                .stroke(Color.white.opacity(0.1), lineWidth: 1)
        )
    }

    private func tableSurface(size: CGSize) -> some View {
        let width = min(size.width * 0.85, 1100)
        let height = width * 0.55
        let tableSize = CGSize(width: width, height: height)

        return ZStack {
            Capsule()
                .fill(
                    LinearGradient(
                        colors: [
                            Color(red: 0.41, green: 0.07, blue: 0.15),
                            Color(red: 0.21, green: 0.01, blue: 0.06)
                        ],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    )
                )
                .shadow(color: .black.opacity(0.45), radius: 40, y: 30)
                .overlay(
                    Capsule()
                        .stroke(LinearGradient(colors: [Color.white.opacity(0.35), Color.white.opacity(0.12)], startPoint: .topLeading, endPoint: .bottomTrailing), lineWidth: 2)
                        .blur(radius: 0.2)
                )
                .overlay(
                    Capsule()
                        .stroke(Color.black.opacity(0.55), lineWidth: 8)
                        .offset(y: 4)
                        .blur(radius: 6)
                        .opacity(0.6)
                )

            communityTray

            ForEach(state.seats) { seat in
                PlayerSeatView(seat: seat)
                    .frame(width: 220)
                    .position(position(for: seat.seatIndex, tableSize: tableSize))
            }
        }
        .frame(width: width, height: height)
    }

    private var communityTray: some View {
        VStack(spacing: 14) {
            Text(state.phase.displayName.uppercased())
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(.white.opacity(0.8))

            HStack(spacing: 18) {
                ForEach(state.community) { card in
                    CardView(card: card)
                }
                if state.community.count < 5 {
                    ForEach(state.community.count..<5, id: \.self) { _ in
                        PlaceholderCard()
                    }
                }
            }

            ChipRow()
        }
        .padding(.horizontal, 36)
        .padding(.vertical, 22)
        .background(
            RoundedRectangle(cornerRadius: 30, style: .continuous)
                .fill(.ultraThinMaterial)
                .opacity(0.7)
        )
        .overlay(
            RoundedRectangle(cornerRadius: 30, style: .continuous)
                .stroke(Color.white.opacity(0.12), lineWidth: 1)
        )
    }

    private var potFooter: some View {
        VStack(spacing: 10) {
            Text("Pot Summary")
                .font(.footnote.weight(.medium))
                .foregroundStyle(.white.opacity(0.55))

            HStack(spacing: 20) {
                PotChipBadge(title: "Main Pot", amount: state.pot, accent: .orange)

                if !state.sidePots.isEmpty {
                    ForEach(Array(state.sidePots.enumerated()), id: \.offset) { index, amount in
                        PotChipBadge(title: "Side Pot \(index + 1)", amount: amount, accent: .cyan)
                    }
                }
            }
        }
    }

    private func position(for seat: Int, tableSize: CGSize) -> CGPoint {
        let seatCount = max(state.seats.count, 1)
        let angleOffset = -Double.pi / 2
        let angle = angleOffset + (Double(seat) / Double(seatCount)) * (2 * Double.pi)
        let radiusX = Double(tableSize.width / 2 - 130)
        let radiusY = Double(tableSize.height / 2 - 90)
        let centerX = Double(tableSize.width / 2)
        let centerY = Double(tableSize.height / 2)
        return CGPoint(
            x: centerX + cos(angle) * radiusX,
            y: centerY + sin(angle) * radiusY
        )
    }
}

private struct PlayerSeatView: View {
    let seat: PlayerSeatModel

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(alignment: .center, spacing: 10) {
                Circle()
                    .fill(LinearGradient(colors: [Color.white.opacity(0.6), Color.white.opacity(0.2)], startPoint: .top, endPoint: .bottom))
                    .overlay(Text("\(seat.seatIndex + 1)").font(.caption.weight(.semibold)).foregroundStyle(.black.opacity(0.7)))
                    .frame(width: 28, height: 28)
                VStack(alignment: .leading, spacing: 2) {
                    Text(seat.name)
                        .font(.headline)
                        .foregroundStyle(.white)
                    Text(statusText)
                        .font(.caption)
                        .foregroundStyle(statusColor.opacity(0.85))
                }
                Spacer()
                if seat.isButton {
                    Text("BTN")
                        .font(.caption2.weight(.bold))
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(Color.yellow.opacity(0.9), in: Capsule())
                        .foregroundStyle(.black.opacity(0.8))
                }
                if seat.isActing {
                    Circle()
                        .fill(Color.cyan)
                        .frame(width: 10, height: 10)
                        .shadow(color: .cyan.opacity(0.7), radius: 6)
                }
            }

            VStack(alignment: .leading, spacing: 4) {
                HStack {
                    Text("Stack")
                        .font(.caption)
                        .foregroundStyle(.white.opacity(0.6))
                    Spacer()
                    Text("\(seat.stack)")
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(.white)
                }

                ProgressView(value: progressValue)
                    .tint(Color.orange)
                    .frame(maxWidth: .infinity)
            }

            HStack {
                Text("Committed")
                    .font(.caption)
                    .foregroundStyle(.white.opacity(0.6))
                Spacer()
                Text("\(seat.committed)")
                    .font(.caption.weight(.medium))
                    .foregroundStyle(.white.opacity(0.85))
            }

            if !seat.recentActions.isEmpty {
                HStack(spacing: 6) {
                    ForEach(seat.recentActions.prefix(2), id: \.self) { action in
                        Text(action)
                            .font(.caption2.weight(.semibold))
                            .padding(.horizontal, 8)
                            .padding(.vertical, 4)
                            .background(Color.white.opacity(0.08), in: Capsule())
                            .foregroundStyle(.white.opacity(0.9))
                    }
                }
            }
        }
        .padding(16)
        .background(backgroundStyle)
        .overlay(
            RoundedRectangle(cornerRadius: 24, style: .continuous)
                .stroke(Color.white.opacity(0.08), lineWidth: 1)
        )
        .clipShape(RoundedRectangle(cornerRadius: 24, style: .continuous))
        .shadow(color: .black.opacity(0.25), radius: 10, y: 6)
    }

    private var progressValue: Double {
        let total = max(Double(seat.stack + seat.totalInPot), 1)
        return Double(seat.totalInPot) / total
    }

    private var statusText: String {
        switch seat.status {
        case .active:
            return seat.isActing ? "In Action" : (seat.connected ? "Active" : "Idle")
        case .folded:
            return "Folded"
        case .busted:
            return "Eliminated"
        case .disconnected:
            return "Disconnected"
        }
    }

    private var statusColor: Color {
        switch seat.status {
        case .active:
            return seat.isActing ? .cyan : .green
        case .folded:
            return .orange
        case .busted:
            return .red
        case .disconnected:
            return .yellow
        }
    }

    private var backgroundStyle: some ShapeStyle {
        switch seat.status {
        case .active:
            return AnyShapeStyle(.ultraThinMaterial)
        case .folded:
            return AnyShapeStyle(Color.gray.opacity(0.35))
        case .busted:
            return AnyShapeStyle(Color.black.opacity(0.45))
        case .disconnected:
            return AnyShapeStyle(Color.orange.opacity(0.35))
        }
    }
}

private struct CardView: View {
    let card: CardModel

    var body: some View {
        RoundedRectangle(cornerRadius: 18, style: .continuous)
            .fill(
                LinearGradient(
                    colors: [Color.white, Color(red: 0.96, green: 0.97, blue: 1.0)],
                    startPoint: .topLeading,
                    endPoint: .bottomTrailing
                )
            )
            .frame(width: 82, height: 110)
            .shadow(color: .black.opacity(0.25), radius: 12, y: 8)
            .overlay(
                VStack(alignment: .leading, spacing: 0) {
                    Text(card.rank)
                        .font(.title.weight(.bold))
                    Text(card.suit.symbol)
                        .font(.title2)
                }
                .foregroundStyle(card.suit.textColor)
                .padding(14)
            )
    }
}

private struct PlaceholderCard: View {
    var body: some View {
        RoundedRectangle(cornerRadius: 18, style: .continuous)
            .strokeBorder(style: StrokeStyle(lineWidth: 1.2, dash: [6, 6]))
            .foregroundStyle(Color.white.opacity(0.18))
            .frame(width: 82, height: 110)
            .overlay(
                Image(systemName: "questionmark")
                    .font(.title3.weight(.bold))
                    .foregroundStyle(.white.opacity(0.25))
            )
    }
}

private struct ChipRow: View {
    var body: some View {
        HStack(spacing: 6) {
            Capsule().fill(Color.orange.opacity(0.9)).frame(width: 26, height: 10)
            Capsule().fill(Color.cyan.opacity(0.85)).frame(width: 30, height: 10)
            Capsule().fill(Color.pink.opacity(0.85)).frame(width: 34, height: 10)
        }
        .overlay(
            Capsule().stroke(Color.white.opacity(0.2), lineWidth: 0.6)
        )
    }
}

private struct PotChipBadge: View {
    let title: String
    let amount: Int
    let accent: Color

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title.uppercased())
                .font(.caption2.weight(.semibold))
                .foregroundStyle(.white.opacity(0.6))
            Text("\(amount) chips")
                .font(.headline)
                .foregroundStyle(.white)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
        .background(
            RoundedRectangle(cornerRadius: 18, style: .continuous)
                .fill(.ultraThinMaterial)
                .overlay(
                    RoundedRectangle(cornerRadius: 18, style: .continuous)
                        .stroke(accent.opacity(0.5), lineWidth: 1)
                )
        )
    }
}
