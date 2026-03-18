# Board Game Engine

A framework for building digital implementations of board games with a shared WebSocket server, per-game engine architecture, and React-based clients. The goal is to make it easy to add new games by implementing a `GameEngine` subclass (server-side logic) and a single-file React client (UI), with the framework handling rooms, networking, reconnection, and player management.

For implementation details, see the [Integration Guide](CLAUDE.md).

## Supported Games

| Game | Players | Single-Screen | Network Play |
|------|---------|---------------|--------------|
| Battle Line | 2 | — | ✓ |
| Arboretum | 2–4 | — | ✓ |
| Lost Cities | 2 | — | ✓ |
| In the Year of the Dragon | 2–5 | ✓ | ✓ |

## How It Works

- **Server** (`server/`): A game-agnostic WebSocket server handles rooms, authentication, and broadcasting. Each game provides a `GameEngine` subclass that owns all game logic — state initialization, player views, action validation, and state transitions.
- **Multi-Screen clients** (`Multi_Screen/`): One React JSX file per game connects to the server via WebSocket for network play. Each player opens the app on their own device.
- **Single-Screen clients** (`Single_Screen/`): Hot-seat mode for local play on a single device. Useful for prototyping or games where shared-screen play is fine.

## Running Locally

This is intended to be hosted locally on a LAN or single machine.

```bash
# Start the WebSocket server
python run_server.py

# In a separate terminal, start the client dev server
cd Multi_Screen && npm run dev
```

Server runs on `ws://localhost:8765`, client on `http://localhost:5173`.

For single-screen games, open `Single_Screen/index.html` directly or serve it locally.

## TODO

- **Game action logging & status**: Add server-side logging of all game actions with timestamps and player info, plus a status API to inspect active games and room state.
- **Card parser library**: Build a shared utility for defining card games with structured data (card definitions, deck composition, hand management) to reduce boilerplate when implementing new card-based games.
