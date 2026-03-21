# Board Game Engine

A framework for building digital implementations of board games with a shared WebSocket server, per-game engine architecture, and React-based clients. Add a new game by implementing a `GameEngine` subclass (server-side logic) and a single-file React client (UI) — the framework handles rooms, networking, reconnection, spectators, and player management.

For the full integration guide, see [CLAUDE.md](CLAUDE.md).

## Supported Games

### The GIPF Project (2-player abstract strategy)

| Game | Description |
|------|-------------|
| GIPF | Push pieces from the edge, capture rows of 4 |
| TAMSK | Race against hourglass timers on a hex board |
| ZERTZ | Shrinking board with mandatory marble captures |
| DVONN | Stack pieces, stay connected to DVONN stones |
| YINSH | Move rings, flip markers, form rows of 5 |
| PUNCT | Connect opposite sides with tri-hex pieces |
| TZAAR | Capture and stack — protect all three types |
| LYNGK | Claim colors, build stacks of 5 unique colors |

### Classic Games

| Game | Players | Description |
|------|---------|-------------|
| Battle Line | 2 | Poker-like card formations across 9 flags |
| Arboretum | 2–4 | Plant trees in paths, score with hand management |
| Lost Cities | 2 | Expedition card game — invest wisely in 5 suits |
| In the Year of the Dragon | 2–5 | Survive disasters in medieval China |
| Caylus | 2–5 | Build a castle for the king, manage workers |

## How It Works

- **Server** (`server/`): A game-agnostic WebSocket server handles rooms, authentication, spectators, and broadcasting. Each game provides a `GameEngine` subclass that owns all game logic.
- **Client** (`client/`): A React app with a game selector menu. Each game is a single self-contained JSX file in `client/games/`.
- **Rules** (`server/<game>/rules/`): Game rulebooks and reference materials live alongside each game's engine code.

## Project Structure

```
board_game_engine/
├── run_server.py                 # Server entry point
├── CLAUDE.md                     # Integration guide
├── server/
│   ├── game_engine.py            # Abstract GameEngine base class
│   ├── server.py                 # WebSocket server + room management
│   └── <game>/                   # One directory per game
│       ├── engine.py             # GameEngine subclass
│       ├── state.py              # Constants, helpers, board/deck setup
│       └── rules/                # Rulebooks (PDF, markdown, images)
│           └── rules.pdf
├── client/
│   ├── main.jsx                  # Game selector + room browser
│   ├── PROTOCOL.md               # WebSocket protocol spec
│   └── games/                    # One JSX file per game
│       ├── BattleLine_MP.jsx
│       ├── Tamsk_MP.jsx
│       └── ...
├── tests/                        # Engine tests
├── legacy/                       # Old single-screen prototypes
└── tools/                        # Utilities (card ingest, etc.)
```

## Running Locally

This is intended to be hosted locally on a LAN or single machine.

```bash
# Start the WebSocket server
python run_server.py

# In a separate terminal, start the client dev server
cd client && npm install && npm run dev
```

Server runs on `ws://localhost:8765`, client on `http://localhost:5173`.

## Adding a New Game

1. Create `server/<game>/` with `engine.py`, `state.py`, and `__init__.py`
2. Put the game rules in `server/<game>/rules/rules.pdf` (or `.md`/`.txt`)
3. Implement the `GameEngine` interface (6 abstract methods — see [CLAUDE.md](CLAUDE.md))
4. Register the engine in `server/server.py`
5. Create `client/games/<Game>_MP.jsx` with a `useGameConnection` hook
6. Add the game to the `GAMES` array in `client/main.jsx`
7. Test with 2+ browser tabs

## Features

- Room creation with shareable codes
- Room browser — see and join open games
- Spectator mode — watch games in progress
- Host controls — kick players, lock rooms
- Token-based auto-reconnection
- Per-player views with hidden information
- Server-validated moves
