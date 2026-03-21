# Board Game Engine — Integration Guide

## Quick Start: Adding a New Game

1. Create `server/<game_name>/` with `engine.py`, `state.py`, and `__init__.py`
2. Add rules to `server/<game_name>/rules/` (PDF, markdown, or text — named `rules.pdf`, `rules.md`, etc.)
3. Subclass `GameEngine` from `server/game_engine.py` — implement all 6 abstract methods
4. Register the engine in `server/server.py` `run_server()`
5. Create `client/games/<GameName>_MP.jsx` — the React multiplayer client
6. Add the game to the `GAMES` array in `client/main.jsx`
7. Test with 2+ browser tabs

---

## Architecture Overview

```
server/
  game_engine.py          # Abstract GameEngine base class + ActionResult
  server.py               # WebSocket server, rooms, player management
  <game>/
    engine.py             # GameEngine subclass (all game logic)
    state.py              # Constants, deck/board generation, helpers
    rules/                # Game rules (PDF, markdown, images)
      rules.pdf           # Original rulebook
      rules.md            # Markdown summary (optional)
    (scoring.py etc.)     # Optional: complex subsystems

client/
  main.jsx                # Entry point — game selector, room browser
  PROTOCOL.md             # Full WebSocket message spec
  games/
    <GameName>_MP.jsx     # React single-file multiplayer client (one per game)

legacy/                   # Old single-screen / hot-seat prototypes
tests/                    # Game engine tests
tools/                    # Utilities (card ingest, etc.)
run_server.py             # Server entry point: `python run_server.py`
```

The server is game-agnostic. It handles rooms, WebSockets, authentication, reconnection, spectators, and broadcasting. Game logic lives entirely in the engine subclass. The client is a single React JSX file per game.

---

## Server Side: Implementing `GameEngine`

### The Abstract Interface (`server/game_engine.py`)

```python
from server.game_engine import GameEngine, ActionResult

class MyGameEngine(GameEngine):
    player_count_range = (2, 4)  # Override from default (2, 5)

    def initial_state(self, player_ids, player_names) -> dict:
        """Return a plain dict with the full starting game state."""

    def get_player_view(self, state, player_id) -> dict:
        """Return a filtered copy of state for this player.
        Must add 'your_player_id' and typically 'valid_actions'."""

    def get_valid_actions(self, state, player_id) -> list[dict]:
        """Return list of action dicts this player can currently submit.
        Empty list = not their turn."""

    def apply_action(self, state, player_id, action) -> ActionResult:
        """Validate & execute action. Raise ValueError on invalid.
        Return ActionResult(new_state, log=[], game_over=False)."""

    def get_waiting_for(self, state) -> list[str]:
        """Return player_ids who must act before game can proceed."""

    def get_phase_info(self, state) -> dict:
        """Return {phase, round, description, ...} for the UI."""

    # Optional override (has default implementation):
    def get_spectator_view(self, state) -> dict:
        """Return a view for spectators (non-players).
        Default: full state with valid_actions=[] and your_player_id=None.
        Override for games with hidden info to control what spectators see."""
```

### Key Patterns

**State is always a plain dict** — JSON-serializable, no classes. The server stores and broadcasts it directly.

**Always deepcopy at the start of `apply_action`:**
```python
from copy import deepcopy

def apply_action(self, state, player_id, action):
    state = deepcopy(state)
    kind = action.get("kind")
    if kind == "play_card":
        return self._apply_play_card(state, player_id, action)
    # ...
    raise ValueError(f"Unknown action kind: {kind}")
```

**Dispatch on `action["kind"]`** — every action dict has a `"kind"` field. Route to private `_apply_*` methods.

**Validate before mutating** — raise `ValueError("message")` for illegal moves. The server catches this and sends an `action_error` to the player.

**Phase state machine** — use `state["phase"]` (and optionally `state["sub_phase"]`) to track game flow. Advance phases at the end of action handlers.

**`get_player_view` must hide secrets:**
```python
def get_player_view(self, state, player_id):
    view = deepcopy(state)
    view["your_player_id"] = player_id
    # Hide other players' hands
    for p in view["players"]:
        if p["player_id"] != player_id:
            p["hand"] = len(p["hand"])  # Show count only
    # Hide deck contents
    view.pop("draw_pile", None)
    view["draw_pile_count"] = len(state.get("draw_pile", []))
    view["valid_actions"] = self.get_valid_actions(state, player_id)
    return view
```

### State Structure Convention

All games follow this common skeleton:
```python
{
    "game": "my_game",
    "player_ids": ["p_abc", "p_def"],
    "player_count": 2,
    "players": [
        {"index": 0, "player_id": "p_abc", "name": "Alice", ...},
        {"index": 1, "player_id": "p_def", "name": "Bob", ...},
    ],
    "current_player": 0,    # Index into players list
    "phase": "play",
    "sub_phase": None,
    # ... game-specific state
}
```

### `state.py` Convention

Put constants, deck/board generators, and helper functions here:
- Card/piece definitions
- `create_player(index, player_id, name)` helper
- `generate_deck(player_count)` or similar setup functions
- Action execution helpers (keep `engine.py` focused on flow)

### Rules Files Convention

Each game keeps its rules in `server/<game>/rules/`:
- `rules.pdf` — Original rulebook PDF (renamed from whatever the source was)
- `rules.md` — Markdown summary of key rules (optional but helpful)
- `rules.txt` — Plain text rules if no PDF available
- Additional images or reference cards can go here too

Use generic filenames (`rules.pdf`, not `PUNCT_english.pdf`) since the directory already identifies the game.

### Registering the Engine

In `server/server.py` inside `run_server()`, add the import and registration:
```python
from server.my_game.engine import MyGameEngine
server.register_engine("my_game", MyGameEngine)
```

The string key (e.g. `"my_game"`) is what clients pass in the `create` message.

---

## Client Side: React Client

Each game is a single `client/games/<GameName>_MP.jsx` file. No shared component library — each game is self-contained with inline styles.

### Skeleton

```jsx
import { useState, useRef, useCallback, useEffect } from "react";

const WS_URL = "ws://localhost:8765";

// Mirror key server constants here (card types, colors, etc.)
const CARD_TYPES = { ... };

// ── WebSocket Connection Hook ──────────────────────────
function useGameConnection() {
  const [connected, setConnected] = useState(false);
  const [roomCode, setRoomCode] = useState(null);
  const [playerId, setPlayerId] = useState(null);
  const [token, setToken] = useState(null);
  const [isHost, setIsHost] = useState(false);
  const [lobby, setLobby] = useState([]);
  const [gameStarted, setGameStarted] = useState(false);
  const [gameState, setGameState] = useState(null);
  const [phaseInfo, setPhaseInfo] = useState(null);
  const [yourTurn, setYourTurn] = useState(false);
  const [waitingFor, setWaitingFor] = useState([]);
  const [gameLogs, setGameLogs] = useState([]);
  const [gameOver, setGameOver] = useState(false);
  const [error, setError] = useState(null);

  const wsRef = useRef(null);
  const tokenRef = useRef(null);

  const send = useCallback((msg) => {
    if (wsRef.current?.readyState === WebSocket.OPEN)
      wsRef.current.send(JSON.stringify(msg));
  }, []);

  const connect = useCallback((onOpen) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) { onOpen?.(); return; }
    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      setError(null);
      if (tokenRef.current)
        ws.send(JSON.stringify({ type: "reconnect", token: tokenRef.current }));
      onOpen?.();
    };

    ws.onmessage = (evt) => {
      const msg = JSON.parse(evt.data);
      switch (msg.type) {
        case "created":
        case "joined":
          setRoomCode(msg.room_code);
          setPlayerId(msg.player_id);
          setToken(msg.token);
          tokenRef.current = msg.token;
          ws.send(JSON.stringify({ type: "auth", token: msg.token }));
          break;
        case "authenticated":
          setIsHost(msg.is_host);
          setGameStarted(msg.game_started);
          break;
        case "lobby_update":
          setLobby(msg.players);
          if (msg.game_started !== undefined) setGameStarted(msg.game_started);
          break;
        case "game_started":
          setGameStarted(true);
          break;
        case "game_state":
          setGameState(msg.state);
          setPhaseInfo(msg.phase_info);
          setYourTurn(msg.your_turn);
          setWaitingFor(msg.waiting_for || []);
          break;
        case "game_log":
          setGameLogs((prev) => [...prev, ...msg.messages]);
          break;
        case "game_over":
          setGameOver(true);
          break;
        case "action_error":
          setError(msg.message);
          break;
        case "error":
          setError(msg.message);
          break;
      }
    };

    ws.onclose = () => {
      setConnected(false);
      setTimeout(() => { if (tokenRef.current) connect(); }, 2000);
    };
  }, []);

  const createRoom = (name) => {
    connect(() => send({ type: "create", game: "my_game", name }));
  };
  const joinRoom = (code, name) => {
    connect(() => send({ type: "join", room_code: code.toUpperCase(), name }));
  };
  const startGame = () => send({ type: "start" });
  const submitAction = (action) => send({ type: "action", action });

  return {
    connected, roomCode, playerId, token, isHost, lobby,
    gameStarted, gameState, phaseInfo, yourTurn, waitingFor,
    gameLogs, gameOver, error,
    createRoom, joinRoom, startGame, submitAction,
  };
}

// ── Main App Component ─────────────────────────────────
export default function App() {
  const game = useGameConnection();

  if (!game.gameStarted) return <Lobby game={game} />;
  return <GameBoard game={game} />;
}

function Lobby({ game }) { /* Room code entry, player list, start button */ }
function GameBoard({ game }) { /* Render game.gameState, handle actions */ }
```

### Client Conventions

- **`game: "my_game"`** in `createRoom` must match the engine registration key
- **`submitAction(action)`** sends `{type: "action", action: {...}}` — the action object goes directly to `engine.apply_action`
- **`gameState`** is the player-filtered view from `get_player_view`
- **`gameState.valid_actions`** lists what the current player can do — build UI dynamically from this
- **Inline CSS-in-JS styles** — each game defines its own `styles` object
- **No external UI libraries** — just React + inline styles

**Guard against null `gameState` in `GameBoard`.** There is a race condition between the `game_started` and `game_state` WebSocket messages. When `game_started` arrives, the App component switches from `<Lobby>` to `<GameBoard>`, but `gameState` may still be `null` because the `game_state` message hasn't arrived yet. You must add a null guard — but **all React hooks must come before any early return** (React rules of hooks). The correct pattern:
```jsx
function GameBoard({ game }) {
  const { gameState: state, gameLogs, submitAction } = game;
  const [selection, setSelection] = useState(null);
  const logRef = useRef(null);

  // ALL hooks BEFORE any early return
  useEffect(() => { setSelection(null); }, [state?.current_player, state?.phase]);

  // NOW the guard
  if (!state || !state.players) {
    return <div>Loading game...</div>;
  }

  // Safe to access state.players, state.board, etc.
}
```

### Adding a Game to the Menu

In `client/main.jsx`, add an import and a `GAMES` entry:
```jsx
import MyGameApp from "./games/MyGame_MP.jsx";

// In the GAMES array:
{ id: "my_game", name: "My Game", players: "2–4", component: MyGameApp, series: "other", desc: "Short description" },
```

---

## WebSocket Protocol Summary

See `client/PROTOCOL.md` for the full spec. Key messages:

| Client → Server | Purpose |
|---|---|
| `{type: "create", game: "...", name: "..."}` | Create room |
| `{type: "join", room_code: "...", name: "..."}` | Join room |
| `{type: "auth", token: "..."}` | Authenticate |
| `{type: "reconnect", token: "..."}` | Reconnect |
| `{type: "start"}` | Host starts game |
| `{type: "action", action: {...}}` | Submit game action |
| `{type: "list_rooms", game: "..."}` | Browse open rooms |
| `{type: "spectate", room_code: "..."}` | Watch a game |
| `{type: "kick", player_id: "..."}` | Host kicks player |
| `{type: "lock_room"}` / `{type: "unlock_room"}` | Host locks/unlocks room |
| `{type: "chat", message: "..."}` | Chat message |

| Server → Client | Purpose |
|---|---|
| `created` / `joined` | Room/player info + token |
| `authenticated` | Auth confirmation |
| `lobby_update` | Player list changes |
| `game_started` | Game begins |
| `game_state` | Personalized state + valid_actions + phase_info |
| `game_log` | Broadcast action log messages |
| `game_over` | Game ended |
| `room_list` | Available rooms for browsing |
| `spectating` | Spectator mode confirmed |
| `action_error` / `error` | Validation or protocol errors |

---

## Running & Testing

```bash
# Start server
python run_server.py

# Start client (separate terminal)
cd client && npm run dev

# Run tests
python -m pytest tests/ -v
```

Server runs on `ws://localhost:8765`, client on `http://localhost:5173` (Vite default).

---

## Checklist for a New Game

- [ ] `server/<game>/engine.py` — GameEngine subclass with all 6 methods
- [ ] `server/<game>/state.py` — Constants and helpers
- [ ] `server/<game>/__init__.py` — Empty init file
- [ ] `server/<game>/rules/rules.pdf` — Rulebook (or .md/.txt)
- [ ] Register in `server/server.py` `run_server()`
- [ ] `client/games/<Game>_MP.jsx` — React client with useGameConnection hook
- [ ] Add to `GAMES` array in `client/main.jsx`
- [ ] Test with 2+ browser tabs
