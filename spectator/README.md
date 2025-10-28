# Spectator Displays

This directory contains apps used to visualize tournament tables. Currently we ship a macOS SwiftUI app.

## macOS SwiftUI App
- Source: `PokerArenaDisplay/`
- Project file: `PokerArenaDisplay.xcodeproj`

### Build & Run
1. Open `PokerArenaDisplay.xcodeproj` in Xcode 15 or later.
2. Choose the `PokerArenaDisplay` target and run.
3. Connect to a tournament host or practice server using the control panel at the top-left. The app requests `mode="presentation"` by default for paced animations.

### Features
- Animated felt with seat pads, community cards, and pot summaries.
- Manual **Force Skip** button for tournament operators.
- Works best when the host runs with `--presentation` and `--manual-control` flags.

Feel free to build additional spectator clients inside this folder (e.g., web or mobile dashboards).
