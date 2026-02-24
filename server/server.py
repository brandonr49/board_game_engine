"""
Generic WebSocket game server.

Handles lobby management, player connections, and routing commands
to pluggable game engines. Knows nothing about specific game rules.
"""

import asyncio
import json
import secrets
import time
from dataclasses import dataclass, field

import websockets

from server.game_engine import GameEngine


def generate_room_code():
    """Generate a short, human-friendly room code."""
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no I/O/0/1 for clarity
    return "".join(secrets.choice(chars) for _ in range(5))


def generate_token():
    return secrets.token_urlsafe(24)


@dataclass
class Player:
    player_id: str
    name: str
    token: str
    websocket: object = None
    connected: bool = False


@dataclass
class Room:
    code: str
    host_id: str
    engine: GameEngine
    players: dict = field(default_factory=dict)       # player_id -> Player
    game_state: dict = None
    started: bool = False
    created_at: float = field(default_factory=time.time)
    game_name: str = "unknown"

    @property
    def player_list(self):
        return [
            {"player_id": p.player_id, "name": p.name, "connected": p.connected}
            for p in self.players.values()
        ]


class GameServer:
    """
    Manages rooms, player connections, and message routing.
    Game-agnostic — delegates all game logic to the engine.
    """

    def __init__(self):
        self.rooms: dict[str, Room] = {}               # code -> Room
        self.tokens: dict[str, tuple[str, str]] = {}    # token -> (room_code, player_id)
        self.engines: dict[str, type] = {}              # game_name -> GameEngine class

    def register_engine(self, game_name, engine_class):
        """Register a game engine class by name."""
        self.engines[game_name] = engine_class

    # ── Room Management ──────────────────────────────────────────────

    def create_room(self, game_name, host_name):
        if game_name not in self.engines:
            raise ValueError(f"Unknown game: {game_name}. Available: {list(self.engines.keys())}")

        code = generate_room_code()
        while code in self.rooms:
            code = generate_room_code()

        engine = self.engines[game_name]()
        player_id = f"p_{generate_token()[:8]}"
        token = generate_token()
        host = Player(player_id=player_id, name=host_name, token=token)

        room = Room(code=code, host_id=player_id, engine=engine, game_name=game_name)
        room.players[player_id] = host

        self.rooms[code] = room
        self.tokens[token] = (code, player_id)

        return code, player_id, token

    def join_room(self, code, name):
        room = self.rooms.get(code)
        if room is None:
            raise ValueError(f"Room {code} not found")
        if room.started:
            raise ValueError("Game already in progress")
        max_players = room.engine.player_count_range[1]
        if len(room.players) >= max_players:
            raise ValueError("Room is full")

        player_id = f"p_{generate_token()[:8]}"
        token = generate_token()
        player = Player(player_id=player_id, name=name, token=token)
        room.players[player_id] = player
        self.tokens[token] = (code, player_id)

        return player_id, token

    def start_game(self, code, requester_id):
        room = self.rooms.get(code)
        if room is None:
            raise ValueError("Room not found")
        if room.host_id != requester_id:
            raise ValueError("Only the host can start the game")
        if room.started:
            raise ValueError("Game already started")
        min_players = room.engine.player_count_range[0]
        if len(room.players) < min_players:
            raise ValueError(f"Need at least {min_players} players")

        player_ids = list(room.players.keys())
        player_names = [room.players[pid].name for pid in player_ids]

        room.game_state = room.engine.initial_state(player_ids, player_names)
        room.started = True

        return room.game_state

    # ── WebSocket Handler ────────────────────────────────────────────

    async def handle_connection(self, websocket):
        """Main handler for a single WebSocket connection."""
        room_code = None
        player_id = None

        try:
            async for raw in websocket:
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    await self._send(websocket, {"type": "error", "message": "Invalid JSON"})
                    continue

                msg_type = msg.get("type")

                # ── Pre-auth messages ────────────────────────────
                if msg_type == "create":
                    await self._handle_create(websocket, msg)
                    continue

                if msg_type == "join":
                    await self._handle_join(websocket, msg)
                    continue

                if msg_type == "reconnect":
                    result = await self._handle_reconnect(websocket, msg)
                    if result:
                        room_code, player_id = result
                    continue

                if msg_type == "auth":
                    result = await self._handle_auth(websocket, msg)
                    if result:
                        room_code, player_id = result
                    continue

                # ── Authenticated messages ───────────────────────
                if not room_code or not player_id:
                    await self._send(websocket, {"type": "error", "message": "Not authenticated. Send 'auth' first."})
                    continue

                room = self.rooms.get(room_code)
                if not room:
                    await self._send(websocket, {"type": "error", "message": "Room no longer exists"})
                    continue

                if msg_type == "start":
                    await self._handle_start(room, player_id)

                elif msg_type == "action":
                    await self._handle_action(room, player_id, msg.get("action", {}))

                elif msg_type == "get_state":
                    await self._send_game_state(room, player_id)

                elif msg_type == "chat":
                    await self._broadcast(room, {
                        "type": "chat",
                        "from": room.players[player_id].name,
                        "message": msg.get("message", ""),
                    })

                else:
                    await self._send(websocket, {"type": "error", "message": f"Unknown message type: {msg_type}"})

        except websockets.ConnectionClosed:
            pass
        finally:
            # Mark player as disconnected
            if room_code and player_id:
                room = self.rooms.get(room_code)
                if room and player_id in room.players:
                    room.players[player_id].connected = False
                    room.players[player_id].websocket = None
                    await self._broadcast(room, {
                        "type": "lobby_update",
                        "players": room.player_list,
                        "reason": f"{room.players[player_id].name} disconnected",
                    })

    # ── Message Handlers ─────────────────────────────────────────────

    async def _handle_create(self, websocket, msg):
        game_name = msg.get("game", "dragon")
        host_name = msg.get("name", "Host")
        try:
            code, player_id, token = self.create_room(game_name, host_name)
            await self._send(websocket, {
                "type": "created",
                "room_code": code,
                "player_id": player_id,
                "token": token,
                "game": game_name,
            })
        except ValueError as e:
            await self._send(websocket, {"type": "error", "message": str(e)})

    async def _handle_join(self, websocket, msg):
        code = msg.get("room_code", "").upper()
        name = msg.get("name", "Player")
        try:
            player_id, token = self.join_room(code, name)
            await self._send(websocket, {
                "type": "joined",
                "room_code": code,
                "player_id": player_id,
                "token": token,
            })
        except ValueError as e:
            await self._send(websocket, {"type": "error", "message": str(e)})

    async def _handle_auth(self, websocket, msg):
        """Authenticate with a token and bind this websocket to a room/player."""
        token = msg.get("token")
        if not token or token not in self.tokens:
            await self._send(websocket, {"type": "error", "message": "Invalid token"})
            return None

        room_code, player_id = self.tokens[token]
        room = self.rooms.get(room_code)
        if not room or player_id not in room.players:
            await self._send(websocket, {"type": "error", "message": "Room or player not found"})
            return None

        player = room.players[player_id]
        player.websocket = websocket
        player.connected = True

        await self._send(websocket, {
            "type": "authenticated",
            "room_code": room_code,
            "player_id": player_id,
            "name": player.name,
            "is_host": player_id == room.host_id,
            "game_started": room.started,
        })

        # Broadcast updated player list
        await self._broadcast(room, {
            "type": "lobby_update",
            "players": room.player_list,
            "game_started": room.started,
        })

        # If game is in progress, send current state
        if room.started:
            await self._send_game_state(room, player_id)

        return room_code, player_id

    async def _handle_reconnect(self, websocket, msg):
        """Reconnect with a token — same as auth but semantically different."""
        return await self._handle_auth(websocket, msg)

    async def _handle_start(self, room, player_id):
        try:
            self.start_game(room.code, player_id)
            await self._broadcast(room, {
                "type": "game_started",
                "message": "Game has begun!",
            })
            # Send each player their personalized view
            await self._broadcast_game_state(room)
        except ValueError as e:
            player = room.players.get(player_id)
            if player and player.websocket:
                await self._send(player.websocket, {"type": "error", "message": str(e)})

    async def _handle_action(self, room, player_id, action):
        if not room.started or not room.game_state:
            player = room.players.get(player_id)
            if player and player.websocket:
                await self._send(player.websocket, {"type": "error", "message": "Game not started"})
            return

        try:
            result = room.engine.apply_action(room.game_state, player_id, action)
            room.game_state = result.new_state

            # Broadcast log to everyone
            if result.log:
                await self._broadcast(room, {
                    "type": "game_log",
                    "messages": result.log,
                })

            # Send updated state to each player
            await self._broadcast_game_state(room)

            if result.game_over:
                await self._broadcast(room, {"type": "game_over"})

        except ValueError as e:
            player = room.players.get(player_id)
            if player and player.websocket:
                await self._send(player.websocket, {"type": "action_error", "message": str(e)})

    # ── Broadcasting ─────────────────────────────────────────────────

    async def _send(self, websocket, data):
        try:
            await websocket.send(json.dumps(data))
        except websockets.ConnectionClosed:
            pass

    async def _broadcast(self, room, data):
        """Send the same message to all connected players in a room."""
        for player in room.players.values():
            if player.connected and player.websocket:
                await self._send(player.websocket, data)

    async def _send_game_state(self, room, player_id):
        """Send personalized game view to one player."""
        player = room.players.get(player_id)
        if not player or not player.websocket or not room.game_state:
            return

        view = room.engine.get_player_view(room.game_state, player_id)
        phase_info = room.engine.get_phase_info(room.game_state)
        waiting_for = room.engine.get_waiting_for(room.game_state)

        await self._send(player.websocket, {
            "type": "game_state",
            "state": view,
            "phase_info": phase_info,
            "waiting_for": waiting_for,
            "your_turn": player_id in waiting_for,
        })

    async def _broadcast_game_state(self, room):
        """Send personalized game view to each connected player."""
        for player_id in room.players:
            await self._send_game_state(room, player_id)


# ── Server Entry Point ───────────────────────────────────────────────

async def run_server(host="0.0.0.0", port=8765):
    from server.dragon.engine import DragonEngine
    from server.battleline.engine import BattleLineEngine
    from server.arboretum.engine import ArboretumEngine

    server = GameServer()
    server.register_engine("dragon", DragonEngine)
    server.register_engine("battleline", BattleLineEngine)
    server.register_engine("arboretum", ArboretumEngine)

    print(f"Game server starting on ws://{host}:{port}")
    print(f"Registered games: {list(server.engines.keys())}")

    async with websockets.serve(server.handle_connection, host, port):
        print("Server running. Ctrl+C to stop.")
        await asyncio.Future()  # run forever


def main():
    asyncio.run(run_server())


if __name__ == "__main__":
    main()
