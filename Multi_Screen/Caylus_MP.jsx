import { useState, useRef, useCallback, useEffect } from "react";

const WS_URL = `ws://${window.location.hostname}:8765`;

// ============================================================
// CONSTANTS (mirrored from server/caylus/state.py)
// ============================================================

const PLAYER_COLORS_LIST = [
  { key: "blue", bg: "#2563eb", light: "#93c5fd", name: "Blue" },
  { key: "red", bg: "#dc2626", light: "#fca5a5", name: "Red" },
  { key: "green", bg: "#16a34a", light: "#86efac", name: "Green" },
  { key: "orange", bg: "#ea580c", light: "#fdba74", name: "Orange" },
  { key: "black", bg: "#374151", light: "#9ca3af", name: "Black" },
];

const RESOURCE_ICONS = {
  food: { color: "#e85d75", label: "Food", symbol: "🌾" },
  wood: { color: "#92400e", label: "Wood", symbol: "🪵" },
  stone: { color: "#6b7280", label: "Stone", symbol: "🪨" },
  cloth: { color: "#7c3aed", label: "Cloth", symbol: "🧵" },
  gold: { color: "#eab308", label: "Gold", symbol: "✦" },
};

const CASTLE_SECTIONS = {
  dungeon: { name: "Dungeon", capacity: 6, vpPerBatch: 5 },
  walls: { name: "Walls", capacity: 10, vpPerBatch: 4 },
  towers: { name: "Towers", capacity: 14, vpPerBatch: 3 },
};

const FAVOR_TRACKS = {
  prestige: { name: "Prestige", icon: "⭐", levels: ["1VP","2VP","3VP","4VP","5VP"] },
  deniers: { name: "Deniers", icon: "💰", levels: ["3$","4$","5$","6$","7$"] },
  resources: { name: "Resources", icon: "📦", levels: ["1🌾","🪵/🪨","1🧵","swap","1✦"] },
  buildings: { name: "Buildings", icon: "🏗️", levels: ["—","Carp-1","Mason-1","Lawyer","Archi-1"] },
};

const PHASES = [
  { id: "income", name: "1. Income" },
  { id: "workers", name: "2. Workers" },
  { id: "special", name: "3. Special" },
  { id: "provost", name: "4. Provost" },
  { id: "activate", name: "5. Activate" },
  { id: "castle", name: "6. Castle" },
  { id: "end_turn", name: "7. End Turn" },
];

const TC = {
  neutral: { bg: "#f5d0c5", border: "#d4a089" },
  basic: { bg: "#f5d0c5", border: "#d4a089" },
  wood: { bg: "#d4a574", border: "#92400e" },
  stone: { bg: "#b8b8b8", border: "#6b7280" },
  prestige: { bg: "#93c5fd", border: "#2563eb" },
  residential: { bg: "#86efac", border: "#16a34a" },
  empty: { bg: "#e8dcc8", border: "#c4b59a" },
};

// ============================================================
// WEBSOCKET CONNECTION HOOK
// ============================================================

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

  const createRoom = (name) => connect(() => send({ type: "create", game: "caylus", name }));
  const joinRoom = (code, name) => connect(() => send({ type: "join", room_code: code.toUpperCase(), name }));
  const startGame = () => send({ type: "start" });
  const submitAction = (action) => send({ type: "action", action });

  return {
    connected, roomCode, playerId, token, isHost, lobby,
    gameStarted, gameState, phaseInfo, yourTurn, waitingFor,
    gameLogs, gameOver, error,
    createRoom, joinRoom, startGame, submitAction,
  };
}

// ============================================================
// SMALL UI COMPONENTS
// ============================================================

function ResourceBadge({ type, count, small }) {
  const r = RESOURCE_ICONS[type];
  if (!r) return null;
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 2,
      background: r.color + "22", border: `1px solid ${r.color}55`,
      borderRadius: 4, padding: small ? "0 3px" : "1px 5px",
      fontSize: small ? 11 : 13, color: r.color, fontWeight: 600,
    }}>
      <span>{r.symbol}</span>{count > 0 && <span>{count}</span>}
    </span>
  );
}

function PlayerToken({ color, size = 16 }) {
  if (!color) return null;
  return (
    <span style={{
      display: "inline-block", width: size, height: size, borderRadius: "50%",
      background: color.bg, border: `2px solid ${color.light}`,
      boxShadow: `0 1px 3px ${color.bg}66`, flexShrink: 0,
    }} />
  );
}

function WorkerCylinder({ color, size = 14 }) {
  if (!color) return null;
  return (
    <span style={{
      display: "inline-block", width: size, height: size * 1.3,
      borderRadius: `${size / 2}px ${size / 2}px 2px 2px`,
      background: `linear-gradient(135deg, ${color.light}, ${color.bg})`,
      border: `1.5px solid ${color.bg}`, flexShrink: 0,
    }} />
  );
}

function Btn({ children, onClick, disabled, variant = "primary", small, style: xs }) {
  const V = {
    primary: { bg: "linear-gradient(135deg,#92400e,#78350f)", color: "#fef3c7", border: "1px solid #78350f" },
    secondary: { bg: "#fef3c7", color: "#78350f", border: "1px solid #d4a574" },
    danger: { bg: "#fee2e2", color: "#dc2626", border: "1px solid #fca5a5" },
    success: { bg: "#dcfce7", color: "#16a34a", border: "1px solid #86efac" },
  };
  const s = V[variant];
  return (
    <button
      onClick={onClick} disabled={disabled}
      style={{
        background: disabled ? "#e8dcc8" : s.bg, color: disabled ? "#a08060" : s.color,
        border: disabled ? "1px solid #c4b59a" : s.border, borderRadius: 6,
        padding: small ? "3px 8px" : "6px 14px", fontSize: small ? 11 : 13,
        fontWeight: 700, cursor: disabled ? "not-allowed" : "pointer",
        opacity: disabled ? 0.6 : 1, fontFamily: "inherit", ...xs,
      }}
    >{children}</button>
  );
}

// ============================================================
// LOBBY
// ============================================================

function Lobby({ game }) {
  const [name, setName] = useState("");
  const [joinCode, setJoinCode] = useState("");
  const [mode, setMode] = useState(null);

  return (
    <div style={{
      minHeight: "100vh",
      background: "linear-gradient(160deg,#faf5eb 0%,#f0e6d2 50%,#e8dcc8 100%)",
      fontFamily: "'Crimson Text','Georgia',serif", color: "#3d2a14",
    }}>
      <div style={{ maxWidth: 500, margin: "0 auto", padding: "40px 16px", textAlign: "center" }}>
        <div style={{ fontSize: 48, marginBottom: 8 }}>🏰</div>
        <h1 style={{
          fontFamily: "'Cinzel','Palatino Linotype',serif", fontSize: 40, color: "#78350f",
          margin: "0 0 4px", textShadow: "0 2px 4px rgba(120,80,40,0.15)",
        }}>CAYLUS</h1>
        <p style={{ fontSize: 15, color: "#92400e", fontStyle: "italic", margin: "0 0 28px" }}>
          Build the King's castle and earn his favor
        </p>

        {!game.roomCode ? (
          <div style={{
            background: "#faf5eb", border: "2px solid #d4a574", borderRadius: 12, padding: 20,
          }}>
            <input
              value={name} onChange={(e) => setName(e.target.value)}
              placeholder="Your name" maxLength={20}
              style={{
                width: "100%", padding: "10px 14px", borderRadius: 8, border: "2px solid #d4a574",
                background: "#fef3c7", fontSize: 15, fontFamily: "inherit", marginBottom: 12, color: "#78350f",
              }}
            />
            {!mode && (
              <div style={{ display: "flex", gap: 8 }}>
                <Btn onClick={() => setMode("create")} style={{ flex: 1 }}>Create Room</Btn>
                <Btn onClick={() => setMode("join")} variant="secondary" style={{ flex: 1 }}>Join Room</Btn>
              </div>
            )}
            {mode === "create" && (
              <Btn onClick={() => name && game.createRoom(name)} disabled={!name} style={{ width: "100%" }}>
                Create Room
              </Btn>
            )}
            {mode === "join" && (
              <div style={{ display: "flex", gap: 8 }}>
                <input
                  value={joinCode} onChange={(e) => setJoinCode(e.target.value.toUpperCase())}
                  placeholder="Room code" maxLength={6}
                  style={{
                    flex: 1, padding: "10px 14px", borderRadius: 8, border: "2px solid #d4a574",
                    background: "#fef3c7", fontSize: 15, fontFamily: "inherit", color: "#78350f",
                    textTransform: "uppercase", letterSpacing: 3, textAlign: "center",
                  }}
                />
                <Btn onClick={() => name && joinCode && game.joinRoom(joinCode, name)} disabled={!name || !joinCode}>
                  Join
                </Btn>
              </div>
            )}
            {game.error && <div style={{ color: "#dc2626", marginTop: 8, fontSize: 13 }}>{game.error}</div>}
          </div>
        ) : (
          <div style={{
            background: "#faf5eb", border: "2px solid #d4a574", borderRadius: 12, padding: 20,
          }}>
            <div style={{ fontSize: 12, color: "#92400e", marginBottom: 4 }}>ROOM CODE</div>
            <div style={{
              fontSize: 32, fontWeight: 800, color: "#78350f", letterSpacing: 6, marginBottom: 16,
              fontFamily: "'Cinzel',serif",
            }}>{game.roomCode}</div>

            <div style={{ marginBottom: 16 }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: "#92400e88", marginBottom: 6 }}>PLAYERS</div>
              {game.lobby.map((p) => (
                <div key={p.id} style={{
                  display: "flex", alignItems: "center", gap: 8, padding: "4px 8px",
                  background: "#fef3c7", borderRadius: 6, marginBottom: 4,
                  border: p.id === game.playerId ? "2px solid #92400e" : "1px solid #d4a574",
                }}>
                  <span style={{ fontWeight: 700, color: "#78350f", flex: 1 }}>{p.name}</span>
                  {p.is_host && <span style={{ fontSize: 10, background: "#92400e", color: "#fef3c7", borderRadius: 4, padding: "1px 6px" }}>HOST</span>}
                </div>
              ))}
            </div>

            {game.isHost && game.lobby.length >= 2 && (
              <Btn onClick={game.startGame} style={{ width: "100%" }}>
                Start Game ({game.lobby.length} players)
              </Btn>
            )}
            {game.isHost && game.lobby.length < 2 && (
              <div style={{ fontSize: 13, color: "#92400e" }}>Waiting for players... (need at least 2)</div>
            )}
            {!game.isHost && (
              <div style={{ fontSize: 13, color: "#92400e" }}>Waiting for host to start...</div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ============================================================
// PHASE TRACKER
// ============================================================

function PhaseTracker({ currentPhase }) {
  return (
    <div style={{ display: "flex", gap: 2, flexWrap: "wrap" }}>
      {PHASES.map((ph, i) => (
        <div key={ph.id} style={{
          padding: "2px 6px", borderRadius: 4, fontSize: 10, fontWeight: 700,
          background: i === currentPhase ? "#92400e" : "#fef3c7",
          color: i === currentPhase ? "#fef3c7" : "#92400e88",
          border: i === currentPhase ? "1px solid #78350f" : "1px solid #d4a57444",
        }}>{ph.name}</div>
      ))}
    </div>
  );
}

// ============================================================
// ACTION PANEL — dynamic from valid_actions
// ============================================================

function ActionPanel({ game, gs, submitAction }) {
  const actions = gs.valid_actions || [];
  const yourTurn = game.yourTurn;
  const myIdx = gs.your_player_idx;
  const myPlayer = gs.players.find((p) => p.index === myIdx);
  const myColor = myPlayer?.color;

  if (gs.game_over) {
    const sorted = [...gs.players].sort((a, b) => b.score - a.score);
    return (
      <div style={{ background: "#fef3c7", border: "2px solid #d97706", borderRadius: 10, padding: 16, textAlign: "center" }}>
        <div style={{ fontSize: 24, fontWeight: 800, color: "#78350f" }}>Game Over!</div>
        {sorted.map((pl, i) => (
          <div key={pl.index} style={{
            display: "flex", alignItems: "center", gap: 8, justifyContent: "center",
            padding: 3, fontWeight: i === 0 ? 800 : 400, fontSize: i === 0 ? 18 : 14,
            color: pl.color.bg,
          }}>
            <PlayerToken color={pl.color} size={i === 0 ? 22 : 16} />
            {pl.name}: {pl.score}VP {i === 0 && "👑"}
          </div>
        ))}
      </div>
    );
  }

  if (!yourTurn || actions.length === 0) {
    const waitNames = (game.waitingFor || []).map((pid) => {
      const wp = gs.players.find((p) => p.player_id === pid);
      return wp ? wp.name : pid;
    });
    return (
      <div style={{
        background: "#faf5eb", border: "1px solid #d4a574", borderRadius: 10, padding: 12,
        textAlign: "center", color: "#92400e",
      }}>
        Waiting for {waitNames.join(", ") || "other players"}...
      </div>
    );
  }

  // Group actions by kind for cleaner UI
  const roadActions = actions.filter((a) => a.kind === "place_worker");
  const specialActions = actions.filter((a) => a.kind === "place_special");
  const castleAction = actions.find((a) => a.kind === "place_castle");
  const passAction = actions.find((a) => a.kind === "pass");
  const incomeAction = actions.find((a) => a.kind === "collect_income");

  // Generic action list for non-placement phases
  const otherActions = actions.filter((a) =>
    !["place_worker", "place_special", "place_castle", "pass", "collect_income"].includes(a.kind)
  );

  const borderColor = myColor ? myColor.bg : "#d4a574";

  return (
    <div style={{
      background: myColor ? `${myColor.bg}10` : "#faf5eb",
      border: `2px solid ${borderColor}`,
      borderRadius: 10, padding: 12,
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
        {myColor && <PlayerToken color={myColor} size={22} />}
        <span style={{ fontWeight: 800, fontSize: 16, color: borderColor }}>Your Turn</span>
        {game.phaseInfo && <span style={{ fontSize: 12, color: "#78350f" }}>{game.phaseInfo.description}</span>}
      </div>

      {incomeAction && (
        <Btn onClick={() => submitAction({ kind: "collect_income" })}>
          Collect Income for All Players
        </Btn>
      )}

      {roadActions.length > 0 && (
        <div style={{ marginBottom: 6 }}>
          <div style={{ fontSize: 11, color: "#92400e88", fontWeight: 600, marginBottom: 3 }}>
            ROAD BUILDINGS (click to place worker)
          </div>
          <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
            {roadActions.map((a) => (
              <Btn key={a.road_index} onClick={() => submitAction(a)} small variant={a.is_own ? "success" : "secondary"}>
                {a.building_name} ({a.cost}$)
              </Btn>
            ))}
          </div>
        </div>
      )}

      {specialActions.length > 0 && (
        <div style={{ marginBottom: 6 }}>
          <div style={{ fontSize: 11, color: "#92400e88", fontWeight: 600, marginBottom: 3 }}>SPECIAL BUILDINGS</div>
          <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
            {specialActions.map((a) => (
              <Btn key={a.special_id} onClick={() => submitAction(a)} small variant="secondary">
                {a.description}
              </Btn>
            ))}
          </div>
        </div>
      )}

      {castleAction && (
        <div style={{ marginBottom: 6 }}>
          <Btn onClick={() => submitAction(castleAction)} small variant="secondary">
            {castleAction.description}
          </Btn>
        </div>
      )}

      {otherActions.length > 0 && (
        <div style={{ display: "flex", gap: 4, flexWrap: "wrap", marginBottom: 6 }}>
          {otherActions.map((a, i) => (
            <Btn
              key={`${a.kind}_${a.choice_id || a.track || a.delta || a.res1 || i}`}
              onClick={() => submitAction(a)} small
              variant={a.kind === "castle_skip" || a.choice_id === "skip" ? "danger" : "success"}
            >
              {a.description || a.label || a.kind}
            </Btn>
          ))}
        </div>
      )}

      {passAction && (
        <Btn onClick={() => submitAction({ kind: "pass" })} variant="danger" small>
          Pass
        </Btn>
      )}

      {game.error && <div style={{ color: "#dc2626", fontSize: 12, marginTop: 4 }}>{game.error}</div>}
    </div>
  );
}

// ============================================================
// ROAD PANEL
// ============================================================

function RoadPanel({ gs }) {
  return (
    <div style={{ background: "rgba(120,80,40,0.06)", borderRadius: 10, padding: 10, border: "1px solid #d4a57444" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
        <span style={{ fontSize: 12, fontWeight: 700, color: "#78350f", letterSpacing: 1 }}>ROAD</span>
        <span style={{ fontSize: 10, color: "#92400e88" }}>
          Bailiff: {gs.bailiff_position + 1} | Provost: {gs.provost_position + 1}
        </span>
      </div>
      <div style={{ display: "flex", gap: 3, flexWrap: "wrap" }}>
        {gs.road.map((slot, i) => {
          const b = slot.building;
          const bType = b ? b.type : "empty";
          const tc = TC[bType] || TC.empty;
          const isBailiff = i === gs.bailiff_position;
          const isProvost = i === gs.provost_position;
          const beyondProvost = i > gs.provost_position;
          const ownerColor = slot.house !== null && slot.house !== undefined ? gs.players.find((p) => p.index === slot.house)?.color : null;
          const workerColor = slot.worker !== null && slot.worker !== undefined ? gs.players.find((p) => p.index === slot.worker)?.color : null;

          return (
            <div key={i} style={{
              width: 56, minHeight: 60, borderRadius: 5,
              background: beyondProvost ? "#e8dcc855" : tc.bg,
              border: isBailiff || isProvost ? `2px solid ${isBailiff ? "#dc2626" : "#2563eb"}` : `1px solid ${tc.border}`,
              padding: 2, fontSize: 9, textAlign: "center",
              opacity: beyondProvost ? 0.5 : 1, position: "relative",
            }}>
              <div style={{ fontWeight: 700, color: "#3d2a14", lineHeight: 1.1, minHeight: 18 }}>
                {b ? b.name : "—"}
              </div>
              <div style={{ fontSize: 8, color: "#78350f88" }}>{i + 1}</div>
              {ownerColor && (
                <div style={{ width: 8, height: 8, borderRadius: "50%", background: ownerColor.bg, margin: "1px auto", border: `1px solid ${ownerColor.light}` }} />
              )}
              {workerColor && (
                <div style={{ position: "absolute", top: 1, right: 1 }}>
                  <WorkerCylinder color={workerColor} size={8} />
                </div>
              )}
              {(isBailiff || isProvost) && (
                <div style={{ fontSize: 7, fontWeight: 800, color: isBailiff ? "#dc2626" : "#2563eb" }}>
                  {isBailiff && "B"}{isBailiff && isProvost && "+"}{isProvost && "P"}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ============================================================
// SPECIAL BUILDINGS PANEL
// ============================================================

function SpecialBuildingsPanel({ gs }) {
  const specials = [
    { id: "gate", name: "Gate" },
    { id: "trading_post", name: "Trading Post" },
    { id: "merchants_guild", name: "Merchants' Guild" },
    { id: "joust_field", name: "Joust Field" },
    { id: "stables", name: "Stables" },
    { id: "inn", name: "Inn" },
  ];
  const ss = gs.special_state;

  return (
    <div style={{ background: "rgba(120,80,40,0.06)", borderRadius: 10, padding: 10, border: "1px solid #d4a57444" }}>
      <div style={{ fontSize: 12, fontWeight: 700, color: "#78350f", marginBottom: 4, letterSpacing: 1 }}>SPECIAL BUILDINGS</div>
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
        {specials.map((sp) => {
          let occupants = [];
          if (sp.id === "stables") {
            occupants = (ss.stables || []).filter((x) => x !== null).map((idx) => gs.players.find((p) => p.index === idx)?.color);
          } else if (sp.id === "inn") {
            if (ss.inn?.left !== null && ss.inn?.left !== undefined)
              occupants.push(gs.players.find((p) => p.index === ss.inn.left)?.color);
            if (ss.inn?.right !== null && ss.inn?.right !== undefined)
              occupants.push(gs.players.find((p) => p.index === ss.inn.right)?.color);
          } else {
            const w = ss[sp.id]?.worker;
            if (w !== null && w !== undefined)
              occupants.push(gs.players.find((p) => p.index === w)?.color);
          }

          return (
            <div key={sp.id} style={{
              background: "#fef3c7", border: "1px solid #d4a574", borderRadius: 6, padding: "4px 8px",
              fontSize: 11, fontWeight: 600, color: "#78350f", display: "flex", alignItems: "center", gap: 4,
            }}>
              <span>{sp.name}</span>
              {occupants.map((c, i) => c && <WorkerCylinder key={i} color={c} size={9} />)}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ============================================================
// CASTLE PANEL
// ============================================================

function CastlePanel({ gs }) {
  const secs = [
    { key: "dungeon", ...CASTLE_SECTIONS.dungeon, parts: gs.castle.dungeon, counted: gs.castle.dungeon_counted },
    { key: "walls", ...CASTLE_SECTIONS.walls, parts: gs.castle.walls, counted: gs.castle.walls_counted },
    { key: "towers", ...CASTLE_SECTIONS.towers, parts: gs.castle.towers, counted: gs.castle.towers_counted },
  ];

  return (
    <div style={{ background: "rgba(120,80,40,0.06)", borderRadius: 10, padding: 10, border: "1px solid #d4a57444" }}>
      <div style={{ fontSize: 12, fontWeight: 700, color: "#78350f", marginBottom: 6, letterSpacing: 1 }}>CASTLE</div>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        {secs.map((s) => (
          <div key={s.key} style={{
            background: s.key === gs.castle.current_section ? "#fef3c7" : "#f5ead6",
            border: s.key === gs.castle.current_section ? "2px solid #d97706" : "1px solid #d4a57444",
            borderRadius: 8, padding: 6, minWidth: 100,
          }}>
            <div style={{ fontWeight: 700, fontSize: 11, color: "#78350f", marginBottom: 3, textAlign: "center" }}>
              {s.name} ({s.parts.filter((x) => x !== null).length}/{s.capacity})
              {s.counted && <span style={{ color: "#16a34a", marginLeft: 3 }}>✓</span>}
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 2, justifyContent: "center" }}>
              {s.parts.map((pt, i) => {
                const c = pt !== null ? gs.players.find((p) => p.index === pt)?.color : null;
                return (
                  <div key={i} style={{
                    width: 14, height: 14, borderRadius: 3,
                    border: c ? "none" : "1px dashed #c4995a55",
                    background: c ? c.bg : "transparent",
                  }} />
                );
              })}
            </div>
            <div style={{ fontSize: 9, color: "#92400e88", textAlign: "center", marginTop: 2 }}>+{s.vpPerBatch}VP/batch</div>
          </div>
        ))}
      </div>
      {gs.castle.workers.length > 0 && (
        <div style={{ marginTop: 4, fontSize: 10, color: "#78350f", display: "flex", gap: 3, alignItems: "center" }}>
          Workers: {gs.castle.workers.map((w, i) => {
            const c = gs.players.find((p) => p.index === w)?.color;
            return <WorkerCylinder key={i} color={c} size={9} />;
          })}
        </div>
      )}
    </div>
  );
}

// ============================================================
// PLAYER PANELS
// ============================================================

function PlayerPanel({ player, isActive, isYou }) {
  const c = player.color;
  const avail = player.workers_total - player.workers_placed;
  return (
    <div style={{
      background: isActive ? `${c.bg}12` : "#faf5eb",
      border: isYou ? `2px solid ${c.bg}` : isActive ? `2px solid ${c.bg}66` : "1px solid #d4a57444",
      borderRadius: 8, padding: 8, minWidth: 160, flex: "1 1 160px",
      boxShadow: isActive ? `0 0 10px ${c.bg}33` : "none",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 5, marginBottom: 4 }}>
        <PlayerToken color={c} size={18} />
        <span style={{ fontWeight: 800, color: c.bg, fontSize: 13 }}>{player.name}</span>
        {isYou && <span style={{ fontSize: 9, background: "#dbeafe", color: "#2563eb", borderRadius: 3, padding: "0 3px", fontWeight: 700 }}>YOU</span>}
        {player.passed && <span style={{ fontSize: 9, background: "#fee2e2", color: "#dc2626", borderRadius: 3, padding: "0 3px", fontWeight: 700 }}>PASS</span>}
        {player.inn_occupant && <span style={{ fontSize: 9, background: "#dbeafe", color: "#2563eb", borderRadius: 3, padding: "0 3px", fontWeight: 700 }}>INN</span>}
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 4, marginBottom: 3 }}>
        <span style={{ fontWeight: 800, fontSize: 16, color: "#78350f", background: "#fef3c7", borderRadius: 4, padding: "1px 6px" }}>{player.score}VP</span>
        <span style={{ fontWeight: 700, fontSize: 13, color: "#92400e", background: "#fef3c7", borderRadius: 4, padding: "1px 5px", border: "1px solid #f59e0b55" }}>💰{player.deniers}</span>
      </div>
      <div style={{ display: "flex", gap: 2, flexWrap: "wrap", marginBottom: 3 }}>
        {Object.entries(player.resources).map(([r, ct]) => <ResourceBadge key={r} type={r} count={ct} small />)}
      </div>
      <div style={{ fontSize: 10, color: "#78350f", display: "flex", gap: 2, alignItems: "center" }}>
        Workers: {Array.from({ length: avail }).map((_, i) => <WorkerCylinder key={i} color={c} size={7} />)}
        {avail === 0 && <span style={{ color: "#92400e88" }}>none</span>}
      </div>
    </div>
  );
}

// ============================================================
// FAVOR TABLE
// ============================================================

function FavorTablePanel({ gs }) {
  const fca = gs.favor_columns_available;
  return (
    <div style={{ background: "rgba(120,80,40,0.06)", borderRadius: 10, padding: 10, border: "1px solid #d4a57444" }}>
      <div style={{ fontSize: 12, fontWeight: 700, color: "#78350f", marginBottom: 4 }}>ROYAL FAVORS</div>
      <table style={{ borderCollapse: "collapse", fontSize: 10, width: "100%" }}>
        <thead>
          <tr>
            <th style={{ textAlign: "left", padding: "2px 4px", color: "#78350f" }}>Track</th>
            {[1, 2, 3, 4, 5].map((n) => (
              <th key={n} style={{
                padding: "2px 4px", color: "#78350f", textAlign: "center",
                opacity: n <= fca ? 1 : 0.25,
                background: n <= fca ? "#fef3c7" : "transparent", borderRadius: 3,
              }}>{n}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {Object.entries(FAVOR_TRACKS).map(([k, t]) => (
            <tr key={k}>
              <td style={{ padding: "2px 4px", fontWeight: 600, color: "#78350f" }}>{t.icon} {t.name}</td>
              {t.levels.map((l, i) => (
                <td key={i} style={{ padding: "2px 4px", textAlign: "center", opacity: i < fca ? 1 : 0.25, color: "#5c3a1e" }}>
                  <div>{l}</div>
                  <div style={{ display: "flex", gap: 1, justifyContent: "center", marginTop: 1 }}>
                    {gs.players.filter((p) => p.favors[k] === i + 1).map((p) => (
                      <div key={p.index} style={{
                        width: 8, height: 8, borderRadius: "50%",
                        background: p.color.bg, border: `1px solid ${p.color.light}`,
                      }} />
                    ))}
                  </div>
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ============================================================
// BUILDING STOCK
// ============================================================

function BuildingStockPanel({ buildingStock }) {
  return (
    <div style={{ background: "rgba(120,80,40,0.06)", borderRadius: 10, padding: 10, border: "1px solid #d4a57444" }}>
      <div style={{ fontSize: 12, fontWeight: 700, color: "#78350f", marginBottom: 4 }}>BUILDING STOCK</div>
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
        {Object.entries(buildingStock).map(([type, buildings]) => (
          <div key={type}>
            <div style={{
              fontSize: 10, fontWeight: 700, color: (TC[type] || TC.empty).border,
              marginBottom: 2, textTransform: "capitalize",
            }}>{type} ({buildings.length})</div>
            <div style={{ display: "flex", gap: 2, flexWrap: "wrap", maxWidth: 260 }}>
              {buildings.map((b) => (
                <div key={b.id} title={b.description || b.name} style={{
                  background: (TC[type] || TC.empty).bg, border: `1px solid ${(TC[type] || TC.empty).border}`,
                  borderRadius: 3, padding: "1px 4px", fontSize: 9, fontWeight: 600, color: "#3d2a14",
                }}>{b.name}</div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ============================================================
// GAME LOG
// ============================================================

function GameLog({ logs }) {
  const ref = useRef(null);
  useEffect(() => {
    if (ref.current) ref.current.scrollTop = ref.current.scrollHeight;
  }, [logs]);

  return (
    <div style={{ background: "rgba(120,80,40,0.06)", borderRadius: 10, padding: 10, border: "1px solid #d4a57444" }}>
      <div style={{ fontSize: 12, fontWeight: 700, color: "#78350f", marginBottom: 4 }}>LOG</div>
      <div ref={ref} style={{ maxHeight: 200, overflowY: "auto", fontSize: 11, color: "#5c3a1e", lineHeight: 1.4 }}>
        {logs.map((e, i) => (
          <div key={i} style={{
            borderBottom: "1px solid #d4a57411", padding: "1px 0",
            fontWeight: e.startsWith("Turn") || e.startsWith("FINAL") || e.startsWith("Counting") ? 700 : 400,
            color: e.startsWith("Turn") ? "#78350f" : e.startsWith("—") ? "#92400e" : "#5c3a1e",
          }}>{e}</div>
        ))}
      </div>
    </div>
  );
}

// ============================================================
// PASSING SCALE
// ============================================================

function PassingScale({ gs }) {
  return (
    <div style={{ display: "flex", gap: 3, alignItems: "center", padding: "2px 8px", fontSize: 11, color: "#78350f" }}>
      <span style={{ fontWeight: 700, marginRight: 3 }}>Pass:</span>
      {gs.passing_scale.map((ps, i) => {
        const c = ps !== null ? gs.players.find((p) => p.index === ps)?.color : null;
        return (
          <div key={i} style={{
            width: 24, height: 24, borderRadius: 5,
            border: c ? `2px solid ${c.bg}` : "1.5px dashed #c4995a44",
            background: c ? `${c.bg}22` : "transparent",
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 10, fontWeight: 700, color: "#92400e",
          }}>
            {c ? <PlayerToken color={c} size={12} /> : i + 1}
          </div>
        );
      })}
    </div>
  );
}

// ============================================================
// MAIN GAME BOARD
// ============================================================

function GameBoard({ game }) {
  const gs = game.gameState;
  if (!gs) return <div style={{ textAlign: "center", padding: 40, color: "#78350f" }}>Loading game state...</div>;

  const myIdx = gs.your_player_idx;

  // Determine who is "active" (whose turn it is)
  let activeIdx = null;
  if (gs.pending_favors) {
    activeIdx = gs.pending_favors.queue[gs.pending_favors.queue_index]?.player_idx;
  } else if (gs.pending_gate) {
    activeIdx = gs.pending_gate.player_idx;
  } else if (gs.pending_provost) {
    activeIdx = gs.pending_provost.player_idx;
  } else if (gs.pending_activation) {
    activeIdx = gs.pending_activation.worker_idx;
  } else if (gs.pending_castle) {
    activeIdx = gs.pending_castle.player_idx;
  } else if (gs.pending_owner_bonus) {
    activeIdx = gs.pending_owner_bonus.owner_idx;
  } else if (gs.pending_inn) {
    activeIdx = gs.pending_inn.player_idx;
  } else {
    activeIdx = gs.current_player_idx;
  }

  return (
    <div style={{
      minHeight: "100vh",
      background: "linear-gradient(160deg,#faf5eb 0%,#f0e6d2 50%,#e8dcc8 100%)",
      fontFamily: "'Crimson Text','Georgia',serif", color: "#3d2a14",
    }}>
      <style>{`@import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@400;600;800&family=Crimson+Text:ital,wght@0,400;0,600;0,700;1,400&display=swap');*{box-sizing:border-box;}::-webkit-scrollbar{height:5px;width:5px;}::-webkit-scrollbar-track{background:transparent;}::-webkit-scrollbar-thumb{background:#c4995a55;border-radius:3px;}`}</style>
      <div style={{ maxWidth: 1100, margin: "0 auto", padding: "12px 10px" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 6 }}>
            <div>
              <h1 style={{ fontFamily: "'Cinzel','Palatino Linotype',serif", fontSize: 22, color: "#78350f", margin: 0 }}>CAYLUS</h1>
              <span style={{ fontSize: 11, color: "#92400e88" }}>Turn {gs.turn} | Room: {game.roomCode}</span>
            </div>
            <PhaseTracker currentPhase={gs.current_phase} />
          </div>

          <ActionPanel game={game} gs={gs} submitAction={game.submitAction} />
          <PassingScale gs={gs} />

          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            {gs.players.map((pl) => (
              <PlayerPanel key={pl.index} player={pl} isActive={pl.index === activeIdx} isYou={pl.index === myIdx} />
            ))}
          </div>

          <SpecialBuildingsPanel gs={gs} />
          <RoadPanel gs={gs} />
          <CastlePanel gs={gs} />

          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <div style={{ flex: "1 1 300px" }}><FavorTablePanel gs={gs} /></div>
            <div style={{ flex: "1 1 300px" }}><BuildingStockPanel buildingStock={gs.building_stock} /></div>
          </div>

          <GameLog logs={game.gameLogs} />
        </div>
      </div>
    </div>
  );
}

// ============================================================
// APP
// ============================================================

export default function App() {
  const game = useGameConnection();

  if (!game.gameStarted) return <Lobby game={game} />;
  return <GameBoard game={game} />;
}
