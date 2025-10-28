//
//  ContentView.swift
//  PokerArenaDisplay
//
//  Created by Andres Antillon on 2025-10-22.
//

import SwiftUI

// Main window: overlays connection controls on top of the rendered table.
struct ContentView: View {
    @StateObject private var viewModel = TableViewModel()
    @FocusState private var isHostFieldFocused: Bool

    var body: some View {
        ZStack(alignment: .topLeading) {
            PokerTableView(state: viewModel.state)
            controlPanel
        }
        .onAppear {
            viewModel.autoConnectIfNeeded()
        }
    }

    private var controlPanel: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Spectator Connection")
                .font(.caption.weight(.semibold))
                .foregroundStyle(.white.opacity(0.75))

            HStack(spacing: 10) {
                TextField("ws://127.0.0.1:8765/ws", text: $viewModel.hostURLString)
                    .textFieldStyle(.roundedBorder)
                    .focused($isHostFieldFocused)
                    .frame(minWidth: 260, maxWidth: 340)

                Button(action: viewModel.connect) {
                    Label("Connect", systemImage: "antenna.radiowaves.left.and.right")
                        .labelStyle(.titleAndIcon)
                }
                .buttonStyle(.borderedProminent)
                .tint(.accentColor)
                .disabled(isConnecting)

                Button(action: viewModel.disconnect) {
                    Label("Disconnect", systemImage: "xmark.octagon.fill")
                }
                .buttonStyle(.bordered)
                .disabled(!isConnected && !isConnecting)
            }

            statusMessage

            if viewModel.canSkipCurrentTurn, let actor = viewModel.currentActorDescription {
                Divider().background(Color.white.opacity(0.15))
                Button {
                    viewModel.skipCurrentTurn()
                } label: {
                    Label("Force Skip (\(actor))", systemImage: "forward.fill")
                        .labelStyle(.titleAndIcon)
                }
                .buttonStyle(.borderedProminent)
                .tint(.orange)
            }
        }
        .padding(20)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 22, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 22, style: .continuous)
                .stroke(Color.white.opacity(0.12), lineWidth: 1)
        )
        .padding(.leading, 32)
        .padding(.top, 32)
    }

    @ViewBuilder
    private var statusMessage: some View {
        switch viewModel.connectionStatus {
        case .failed(let message):
            Text(message)
                .font(.caption)
                .foregroundStyle(Color.red)
        case .connected:
            Text("Connected")
                .font(.caption)
                .foregroundStyle(Color.green)
        case .connecting:
            Text("Connecting…")
                .font(.caption)
                .foregroundStyle(Color.yellow)
        case .disconnected:
            Text("Disconnected")
                .font(.caption)
                .foregroundStyle(.white.opacity(0.6))
        }
    }

    private var isConnecting: Bool {
        if case .connecting = viewModel.connectionStatus {
            return true
        }
        return false
    }

    private var isConnected: Bool {
        if case .connected = viewModel.connectionStatus {
            return true
        }
        return false
    }
}

#Preview {
    ContentView()
        .frame(width: 1280, height: 720)
}
