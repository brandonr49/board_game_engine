# Multiplayer Board Game Server

A WebSocket-based game server with a pluggable engine architecture. Currently includes **In the Year of the Dragon** as the first game implementation.

## Architecture

```
┌──────────────┐     WebSocket      ┌──────────────────┐
│  React Client │◄──────────────────►│   Game Server     │
│  (per player) │     JSON msgs      │   (generic)       │
└──────────────┘                     │                   │
                                     │  ┌─────────────┐  │
                                     │  │ Dragon      │  │
                                     │  │ Engine      │  │
                                     │  └─────────────┘  │
                                     │  ┌─────────────┐  │
                                     │  │ Future Game │  │
                                     │  │ Engine      │  │
                                     │  └─────────────┘  │
                                     └──────────────────┘
```

### Three Layers

1. **`server/game_engine.py`** — Abstract interface that any game must implement:
   - `initial_state()` — create starting state
   - `get_player_view()` — per-player filtered view
   - `get_valid_actions()` — what can a player do right now?
   - `apply_action()` — validate & execute a player action
   - `get_waiting_for()` — who needs to act?

2. **`server/server.py`** — Generic WebSocket server handling:
   - Room creation/joining with codes (e.g., "F6PYC")
   - Token-based auth with reconnection support
   - Action routing to the game engine
   - Per-player state broadcasting

3. **`server/dragon/`** — Game-specific implementation:
   - `state.py` — Constants, tile generation, action execution
   - `engine.py` — State machine implementing the GameEngine interface

## Quick Start

```bash
pip install -r requirements.txt
python run_server.py
# Server starts on ws://localhost:8765
```

## Adding a New Game

1. Create a new directory under `server/` (e.g., `server/mygame/`)
2. Implement a class that inherits from `GameEngine`
3. Register it in `server.py`:
   ```python
   server.register_engine("mygame", MyGameEngine)
   ```
4. Clients create rooms with `{"type": "create", "game": "mygame", "name": "Host"}`

## File Structure

```
├── run_server.py              # Entry point
├── requirements.txt
├── PROTOCOL.md                # Full WebSocket protocol reference
├── server/
│   ├── game_engine.py         # Abstract GameEngine interface
│   ├── server.py              # WebSocket server + room management
│   └── dragon/
│       ├── state.py           # Constants, utilities, action execution
│       └── engine.py          # Dragon GameEngine implementation
├── test_engine.py             # Engine unit/integration test
└── test_websocket.py          # Full WebSocket flow test
```

## Protocol Overview

See [PROTOCOL.md](PROTOCOL.md) for the full reference. Key flow:

```
create room → join room → auth with token → start game → exchange actions
```

Each player gets a personalized `game_state` message with their view of the board,
a `your_turn` flag, and a `valid_actions` list describing what they can do.

## Next Steps

- [ ] React client refactor (strip game logic, add WebSocket connection)
- [ ] Per-player views in the UI (each player sees their own browser tab)
- [ ] Persistent game state (save/load to disk or DB)
- [ ] Spectator mode
- [ ] Game timer/timeout handling
