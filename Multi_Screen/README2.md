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
├── client/
│   └── InTheYearOfTheDragon_MP.jsx   # Multiplayer React client
├── test_engine.py             # Engine unit/integration test
└── test_websocket.py          # Full WebSocket flow test
```

## Running the Game

### 1. Start the server
```bash
pip install -r requirements.txt
python run_server.py
# → Server starts on ws://localhost:8765
```

### 2. Open the client
The client (`client/InTheYearOfTheDragon_MP.jsx`) is a React component that 
connects to `ws://localhost:8765`. It can be loaded in any React environment
(Vite, CRA, etc.) or adapted to your hosting setup.

The `WS_URL` constant at the top of the file controls the server address.

### 3. Play
1. **Player 1** opens the client → clicks "Create Room" → enters name → gets a 5-character room code
2. **Other players** open the client → click "Join Room" → enter the room code + their name
3. **Player 1** (host) clicks "Start Game" when everyone has joined
4. Each player sees their own personalized view — hidden cards, turn indicators, action menus
5. When it's your turn, the UI enables your controls; when waiting, you see an animated indicator

### Client Features

Compared to the original hot-seat version:

| Feature | Hot-Seat | Multiplayer |
|---------|----------|-------------|
| Browser tabs | 1 shared | 1 per player |
| Game logic | Client-side React state | Server-side Python engine |
| Card visibility | Everyone sees everything | Your cards hidden from others |
| Turn control | Honor system | Server-enforced |
| Reconnection | N/A | Token-based auto-reconnect |
| Action validation | Client-only | Server-validated |

## Protocol Overview

See [PROTOCOL.md](PROTOCOL.md) for the full reference. Key flow:

```
create room → join room → auth with token → start game → exchange actions
```

Each player gets a personalized `game_state` message with their view of the board,
a `your_turn` flag, and a `valid_actions` list describing what they can do.

## Next Steps

- [ ] Serve the React client from the Python server (static file serving)
- [ ] Persistent game state (save/load to disk or DB)
- [ ] Spectator mode
- [ ] Game timer/timeout handling
- [ ] Additional game engines
