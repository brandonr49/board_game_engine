import { useState, useMemo } from "react";

// ─── PERSON TYPE CONFIGURATION ──────────────────────────────────────
// symbols = resource icons on the tile (action bonuses)
// value   = person track movement when placed

const PERSON_TYPES = {
  monk: {
    name: "Monk", color: "#8B4513", icon: "☸️",
    resource: "buddha", resourceIcon: "☸️",
    young: { symbols: 1, value: 6 },
    old:   { symbols: 2, value: 2 },
  },
  healer: {
    name: "Healer", color: "#3498db", icon: "⚕️",
    resource: "mortar", resourceIcon: "⚗️",
    young: { symbols: 1, value: 4 },
    old:   { symbols: 2, value: 1 },
  },
  pyrotechnist: {
    name: "Pyrotechnist", color: "#8e44ad", icon: "🎆",
    resource: "rocket", resourceIcon: "🚀",
    young: { symbols: 1, value: 5 },
    old:   { symbols: 2, value: 3 },
  },
  craftsman: {
    name: "Craftsman", color: "#d4a574", icon: "🔨",
    resource: "hammer", resourceIcon: "🔨",
    youngOnly: true,
    young: { symbols: 1, value: 2 },
    old: null,
  },
  courtLady: {
    name: "Court Lady", color: "#d4a017", icon: "🪭",
    resource: "dragon", resourceIcon: "🐉",
    youngOnly: true,
    young: { symbols: 1, value: 1 },
    old: null,
  },
  taxCollector: {
    name: "Tax Collector", color: "#f1c40f", icon: "💰",
    resource: "coin", resourceIcon: "🪙",
    youngOnly: true,
    young: { symbols: 3, value: 3 },
    old: null,
  },
  warrior: {
    name: "Warrior", color: "#c0392b", icon: "⚔️",
    resource: "helmet", resourceIcon: "🪖",
    young: { symbols: 1, value: 5 },
    old:   { symbols: 2, value: 3 },
  },
  scholar: {
    name: "Scholar", color: "#ecf0f1", icon: "📜",
    resource: "book", resourceIcon: "📖",
    young: { symbols: 2, value: 4 },
    old:   { symbols: 3, value: 2 },
  },
  farmer: {
    name: "Farmer", color: "#27ae60", icon: "🌾",
    resource: "rice", resourceIcon: "🌾",
    young: { symbols: 1, value: 4 },
    old:   { symbols: 2, value: 1 },
  },
};

// Action card descriptions for display
const ACTION_INFO = {
  taxes:     { name: "Taxes",            icon: "💰", desc: "Collect 2 yuan, +1 per tax collector coin symbol",     bonus: "taxCollector", unit: "¥" },
  build:     { name: "Build",            icon: "🏗️", desc: "Gain 1 palace floor, +1 per craftsman hammer symbol",  bonus: "craftsman",    unit: "floors" },
  harvest:   { name: "Harvest",          icon: "🌾", desc: "Gain 1 rice tile, +1 per farmer rice symbol",          bonus: "farmer",       unit: "rice" },
  fireworks: { name: "Fireworks Display", icon: "🎆", desc: "Gain 1 firework, +1 per pyrotechnist rocket symbol", bonus: "pyrotechnist", unit: "fireworks" },
  military:  { name: "Military Parade",  icon: "⚔️", desc: "Advance 1 on person track, +1 per warrior helmet",    bonus: "warrior",      unit: "steps" },
  research:  { name: "Research",         icon: "📜", desc: "Score 1 VP, +1 per scholar book symbol",               bonus: "scholar",      unit: "VP" },
  privilege: { name: "Privilege",        icon: "🏅", desc: "Buy a privilege: small (2¥, 1🐉) or large (7¥, 2🐉)", bonus: null,           unit: "" },
};

const EVENT_TYPES = [
  { id: "peace",           name: "Peace",           icon: "☮️",  color: "#27ae60" },
  { id: "drought",         name: "Drought",         icon: "☀️",  color: "#e67e22" },
  { id: "contagion",       name: "Contagion",       icon: "☠️",  color: "#8e44ad" },
  { id: "mongolInvasion",  name: "Mongol Invasion", icon: "🏇",  color: "#c0392b" },
  { id: "imperialTribute", name: "Imperial Tribute", icon: "👑", color: "#f1c40f" },
  { id: "dragonFestival",  name: "Dragon Festival", icon: "🐉",  color: "#e74c3c" },
];

const ACTION_TYPES = [
  { id: "taxes" }, { id: "build" }, { id: "harvest" }, { id: "fireworks" },
  { id: "military" }, { id: "research" }, { id: "privilege" },
];

const PLAYER_COLORS = [
  { name: "Red",    primary: "#b33025", light: "#e8453a", dark: "#7a1f17" },
  { name: "Blue",   primary: "#2563a8", light: "#3b82d6", dark: "#1a4270" },
  { name: "Green",  primary: "#1d8348", light: "#28a85c", dark: "#145a32" },
  { name: "Yellow", primary: "#c49000", light: "#e8ad10", dark: "#8a6500" },
  { name: "Purple", primary: "#7b3fa0", light: "#9b59b6", dark: "#5b2d75" },
];

// ─── UTILITIES ──────────────────────────────────────────────────────

function shuffle(arr) {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

function deepClonePlayer(p) {
  return {
    ...p,
    palaces: p.palaces.map(pal => ({ ...pal, persons: [...pal.persons] })),
    privileges: { ...p.privileges },
    cards: [...p.cards],
  };
}

function deepClonePlayers(players) { return players.map(deepClonePlayer); }

function countSymbols(player, typeId) {
  let total = 0;
  player.palaces.forEach(pal => pal.persons.forEach(per => {
    if (per.typeId === typeId) total += per.symbols;
  }));
  return total;
}

function generateEventTiles() {
  const events = [{ ...EVENT_TYPES[0], slot: 0 }, { ...EVENT_TYPES[0], slot: 1 }];
  const nonPeace = EVENT_TYPES.slice(1);
  let pool = [];
  nonPeace.forEach(e => { pool.push({ ...e }); pool.push({ ...e }); });
  pool = shuffle(pool);
  const placed = [], deferred = [];
  for (const tile of pool) {
    if (placed.length > 0 && placed[placed.length - 1].id === tile.id) deferred.push(tile);
    else placed.push(tile);
  }
  for (const tile of deferred) {
    let ins = false;
    for (let i = 0; i <= placed.length; i++) {
      const prev = i > 0 ? placed[i-1].id : null;
      const next = i < placed.length ? placed[i].id : null;
      if (prev !== tile.id && next !== tile.id) { placed.splice(i, 0, tile); ins = true; break; }
    }
    if (!ins) placed.push(tile);
  }
  placed.forEach((t, i) => events.push({ ...t, slot: i + 2 }));
  return events;
}

function generatePersonTiles(playerCount) {
  const tiles = [];
  Object.entries(PERSON_TYPES).forEach(([typeId, type]) => {
    if (type.youngOnly) {
      for (let i = 0; i < playerCount * 2; i++)
        tiles.push({ id: `${typeId}-young-${i}`, typeId, experience: "young", symbols: type.young.symbols, value: type.young.value });
    } else {
      const oc = Math.max(0, 4 - (5 - playerCount)), yc = Math.max(0, 6 - (5 - playerCount));
      for (let i = 0; i < oc; i++)
        tiles.push({ id: `${typeId}-old-${i}`, typeId, experience: "old", symbols: type.old.symbols, value: type.old.value });
      for (let i = 0; i < yc; i++)
        tiles.push({ id: `${typeId}-young-${i}`, typeId, experience: "young", symbols: type.young.symbols, value: type.young.value });
    }
  });
  return tiles;
}

function createPlayer(index, colorObj, name) {
  const cards = Object.keys(PERSON_TYPES).map(typeId => ({ typeId, isWild: false }));
  cards.push({ typeId: null, isWild: true }, { typeId: null, isWild: true });
  return {
    index, color: colorObj, name,
    palaces: [{ floors: 2, persons: [] }, { floors: 2, persons: [] }],
    yuan: 6, rice: 0, fireworks: 0,
    privileges: { small: 0, large: 0 },
    personTrack: 0, scoringTrack: 0, cards,
  };
}

function comboKey(a, b) { return [a, b].sort().join("+"); }

function getPersonTrackOrder(players) {
  return [...Array(players.length).keys()].sort((a, b) => {
    if (players[b].personTrack !== players[a].personTrack) return players[b].personTrack - players[a].personTrack;
    return b - a;
  });
}

function dealActionGroups(playerCount) {
  const shuffled = shuffle(ACTION_TYPES);
  const groups = Array.from({ length: playerCount }, () => []);
  shuffled.forEach((card, i) => { groups[i % playerCount].push(card); });
  return groups;
}

// ─── ACTION EXECUTION ───────────────────────────────────────────────

function executeTaxes(p) {
  const b = countSymbols(p, "taxCollector"), t = 2 + b;
  p.yuan += t;
  return `Collected ${t}¥ (2 base + ${b} tax collectors). Now ${p.yuan}¥.`;
}
function executeHarvest(p) {
  const b = countSymbols(p, "farmer"), t = 1 + b;
  p.rice += t;
  return `Harvested ${t} rice (1 base + ${b} farmers). Now ${p.rice} rice.`;
}
function executeFireworks(p) {
  const b = countSymbols(p, "pyrotechnist"), t = 1 + b;
  p.fireworks += t;
  return `Gained ${t} fireworks (1 base + ${b} pyrotechnists). Now ${p.fireworks}.`;
}
function executeMilitary(p) {
  const b = countSymbols(p, "warrior"), t = 1 + b;
  p.personTrack += t;
  return `Advanced ${t} steps (1 base + ${b} warriors). Now at ${p.personTrack}.`;
}
function executeResearch(p) {
  const b = countSymbols(p, "scholar"), t = 1 + b;
  p.scoringTrack += t;
  return `Gained ${t} VP (1 base + ${b} scholars). Now ${p.scoringTrack} VP.`;
}
function executeBuild(p) {
  const b = countSymbols(p, "craftsman"), t = 1 + b;
  let rem = t;
  for (let i = 0; i < p.palaces.length && rem > 0; i++) {
    const add = Math.min(3 - p.palaces[i].floors, rem);
    p.palaces[i].floors += add; rem -= add;
  }
  while (rem > 0) { const f = Math.min(3, rem); p.palaces.push({ floors: f, persons: [] }); rem -= f; }
  return `Built ${t} floor(s) (1 base + ${b} craftsmen).`;
}
function executePrivilege(p, size) {
  if (size === "small") { p.yuan -= 2; p.privileges.small += 1; return `Bought small privilege (2¥). ${p.yuan}¥ left.`; }
  p.yuan -= 7; p.privileges.large += 1; return `Bought large privilege (7¥). ${p.yuan}¥ left.`;
}

// ─── STYLES ─────────────────────────────────────────────────────────

const font = `'Palatino Linotype', 'Book Antiqua', Palatino, Georgia, serif`;

const S = {
  app: {
    fontFamily: font, minHeight: "100vh",
    background: "linear-gradient(160deg, #1a0a00 0%, #2d1810 30%, #1a0a00 100%)",
    color: "#f0e6d3", position: "relative", overflow: "hidden",
  },
  overlay: {
    position: "fixed", inset: 0, pointerEvents: "none", zIndex: 0,
    backgroundImage: `repeating-linear-gradient(45deg, transparent, transparent 35px, rgba(139,69,19,0.03) 35px, rgba(139,69,19,0.03) 70px)`,
  },
  content: { position: "relative", zIndex: 1, maxWidth: 1200, margin: "0 auto", padding: "20px" },
  card: {
    background: "linear-gradient(135deg, rgba(45,24,16,0.9) 0%, rgba(30,15,8,0.95) 100%)",
    border: "1px solid #5a3a20", borderRadius: 8, padding: 24, marginBottom: 20,
    boxShadow: "0 4px 20px rgba(0,0,0,0.4)",
  },
  cardTitle: {
    fontFamily: font, fontSize: 22, color: "#d4a017",
    marginBottom: 16, borderBottom: "1px solid #5a3a20", paddingBottom: 8,
  },
  btn: {
    fontFamily: font, fontSize: 15, padding: "10px 24px", borderRadius: 6,
    border: "1px solid #8B4513",
    background: "linear-gradient(135deg, #5a3a20 0%, #3d2510 100%)",
    color: "#f0e6d3", cursor: "pointer", transition: "all 0.2s", fontWeight: 600,
  },
  btnP: { background: "linear-gradient(135deg, #8B4513 0%, #5a3a20 100%)", border: "1px solid #d4a017" },
  dis: { opacity: 0.4, cursor: "not-allowed" },
  title: {
    fontFamily: font, fontSize: 42, fontWeight: 700, color: "#d4a017",
    textShadow: "0 2px 8px rgba(0,0,0,0.5)", margin: 0, letterSpacing: 2,
  },
};

function bs(primary, disabled) { return { ...S.btn, ...(primary ? S.btnP : {}), ...(disabled ? S.dis : {}) }; }

// ─── RESOURCE BADGE ─────────────────────────────────────────────────

function ResourceBadge({ icon, label, value, highlight }) {
  return (
    <div style={{
      display: "inline-flex", alignItems: "center", gap: 6,
      background: highlight ? "rgba(212,160,23,0.12)" : "rgba(0,0,0,0.2)",
      border: highlight ? "1px solid #d4a01744" : "1px solid #5a3a2044",
      borderRadius: 6, padding: "4px 10px",
    }}>
      <span style={{ fontSize: 14 }}>{icon}</span>
      <div style={{ display: "flex", flexDirection: "column" }}>
        <span style={{ fontSize: 9, color: "#806040", lineHeight: 1, textTransform: "uppercase", letterSpacing: 0.5 }}>{label}</span>
        <span style={{ fontSize: 15, fontWeight: 700, color: highlight ? "#d4a017" : "#c0a070", lineHeight: 1.2 }}>{value}</span>
      </div>
    </div>
  );
}

// ─── PALACE DISPLAY (redesigned) ────────────────────────────────────

function PalaceDisplay({ palace, palaceIndex }) {
  const emptySlots = palace.floors - palace.persons.length;
  return (
    <div style={{
      background: "rgba(0,0,0,0.2)", border: "1px solid #5a3a2066",
      borderRadius: 8, padding: 10, minWidth: 110,
    }}>
      {/* Roof indicator */}
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        marginBottom: 6, paddingBottom: 4, borderBottom: "1px solid #5a3a2044",
      }}>
        <span style={{ fontSize: 10, color: "#a08060", fontWeight: 600 }}>Palace {palaceIndex + 1}</span>
        <div style={{ display: "flex", gap: 2 }}>
          {Array.from({ length: palace.floors }).map((_, i) => (
            <div key={i} style={{
              width: 8, height: 10,
              background: i < palace.persons.length ? "#d4a017" : "#5a3a2088",
              borderRadius: 1, border: "1px solid #8B451366",
            }} />
          ))}
        </div>
      </div>
      {/* Person slots */}
      <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
        {palace.persons.map((person, i) => {
          const t = PERSON_TYPES[person.typeId];
          return (
            <div key={i} style={{
              display: "flex", alignItems: "center", gap: 6,
              background: `${t.color}15`, border: `1px solid ${t.color}44`,
              borderRadius: 5, padding: "3px 8px",
            }}>
              <span style={{ fontSize: 14 }}>{t.icon}</span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 10, color: t.color, fontWeight: 600, lineHeight: 1.2 }}>{t.name}</div>
                <div style={{ display: "flex", gap: 2, alignItems: "center" }}>
                  {Array.from({ length: person.symbols }).map((_, j) => (
                    <span key={j} style={{ fontSize: 9 }}>{t.resourceIcon}</span>
                  ))}
                  <span style={{ fontSize: 8, color: "#80604088", marginLeft: 2 }}>
                    {person.experience === "old" ? "exp" : ""}
                  </span>
                </div>
              </div>
            </div>
          );
        })}
        {Array.from({ length: emptySlots }).map((_, i) => (
          <div key={`empty-${i}`} style={{
            display: "flex", alignItems: "center", justifyContent: "center",
            border: "1px dashed #5a3a2044", borderRadius: 5, padding: "3px 8px",
            height: 28,
          }}>
            <span style={{ fontSize: 9, color: "#5a3a2066" }}>empty</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── PERSON TILE (for selection UIs) ────────────────────────────────

function PersonTileDisplay({ tile, onClick, selected, small, disabled }) {
  const t = PERSON_TYPES[tile.typeId];
  return (
    <div onClick={disabled ? undefined : onClick} style={{
      width: small ? 72 : 90, minHeight: small ? 82 : 100,
      background: selected ? `linear-gradient(135deg, ${t.color}44, ${t.color}22)`
        : "linear-gradient(135deg, rgba(50,30,20,0.9), rgba(35,20,12,0.95))",
      border: selected ? `2px solid ${t.color}` : "1px solid #5a3a2088",
      borderRadius: 6, padding: small ? 6 : 8,
      cursor: disabled ? "default" : "pointer",
      display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 2,
      transition: "all 0.15s", opacity: disabled ? 0.35 : 1,
      boxShadow: selected ? `0 0 12px ${t.color}44` : "0 2px 6px rgba(0,0,0,0.3)",
    }}>
      <span style={{ fontSize: small ? 20 : 26 }}>{t.icon}</span>
      <span style={{ fontSize: small ? 9 : 11, color: t.color, fontWeight: 600, textAlign: "center" }}>{t.name}</span>
      <span style={{ fontSize: small ? 8 : 10, color: "#a08060" }}>
        {tile.experience === "old" ? "Experienced" : "Young"}
      </span>
      <div style={{ display: "flex", gap: 2, marginTop: 2 }}>
        {Array.from({ length: tile.symbols }).map((_, i) => (
          <span key={i} style={{ fontSize: small ? 10 : 12 }}>{t.resourceIcon}</span>
        ))}
      </div>
      <span style={{
        fontSize: small ? 10 : 12, fontWeight: 700, color: "#d4a017", marginTop: 2,
        background: "rgba(0,0,0,0.3)", borderRadius: 4, padding: "1px 6px",
      }}>+{tile.value}</span>
    </div>
  );
}

// ─── PLAYER AREA ────────────────────────────────────────────────────

function PlayerArea({ player, isActive }) {
  const totalDragons = player.privileges.small + player.privileges.large * 2;
  return (
    <div style={{
      ...S.card, padding: 14,
      border: isActive ? `2px solid ${player.color.primary}` : S.card.border,
      boxShadow: isActive ? `0 0 20px ${player.color.primary}44, 0 4px 20px rgba(0,0,0,0.4)` : S.card.boxShadow,
    }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
        <div style={{
          width: 18, height: 18, borderRadius: "50%",
          background: player.color.primary, boxShadow: `0 0 6px ${player.color.primary}88`,
        }} />
        <span style={{ fontFamily: font, fontSize: 17, color: player.color.light, fontWeight: 700, flex: 1 }}>
          {player.name}
        </span>
        {isActive && (
          <span style={{
            fontSize: 10, color: "#1a0a00", background: player.color.primary,
            padding: "2px 10px", borderRadius: 10, fontWeight: 700,
          }}>⬤ TURN</span>
        )}
      </div>

      {/* Resources row */}
      <div style={{ display: "flex", gap: 6, marginBottom: 10, flexWrap: "wrap" }}>
        <ResourceBadge icon="💰" label="Yuan" value={player.yuan} />
        <ResourceBadge icon="🌾" label="Rice" value={player.rice} />
        <ResourceBadge icon="🎆" label="Fireworks" value={player.fireworks} />
        {(player.privileges.small > 0 || player.privileges.large > 0) && (
          <div style={{
            display: "inline-flex", alignItems: "center", gap: 6,
            background: "rgba(0,0,0,0.2)", border: "1px solid #5a3a2044",
            borderRadius: 6, padding: "4px 10px",
          }}>
            <span style={{ fontSize: 14 }}>🐉</span>
            <div style={{ display: "flex", flexDirection: "column" }}>
              <span style={{ fontSize: 9, color: "#806040", lineHeight: 1, textTransform: "uppercase", letterSpacing: 0.5 }}>Privileges</span>
              <div style={{ display: "flex", gap: 4, alignItems: "center" }}>
                {player.privileges.small > 0 && (
                  <span style={{ fontSize: 12, color: "#c0a070" }}>{player.privileges.small}×🐉</span>
                )}
                {player.privileges.large > 0 && (
                  <span style={{ fontSize: 12, color: "#d4a017" }}>{player.privileges.large}×🐉🐉</span>
                )}
                <span style={{ fontSize: 10, color: "#806040" }}>= {totalDragons}/round</span>
              </div>
            </div>
          </div>
        )}
        <ResourceBadge icon="👤" label="Person Track" value={player.personTrack} highlight />
        <ResourceBadge icon="⭐" label="Score" value={player.scoringTrack} highlight />
      </div>

      {/* Palaces */}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        {player.palaces.map((palace, i) => (
          <PalaceDisplay key={i} palace={palace} palaceIndex={i} />
        ))}
      </div>
    </div>
  );
}

// ─── PLAYER AREAS GRID ──────────────────────────────────────────────

function PlayerAreasGrid({ players, activePlayerIdx }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: 12, marginTop: 16 }}>
      {players.map((p, i) => (
        <PlayerArea key={i} player={p} isActive={i === activePlayerIdx} />
      ))}
    </div>
  );
}

// ─── PHASE TRACKER ──────────────────────────────────────────────────

const PHASES = [
  { id: "action",  name: "Action",  icon: "⚡" },
  { id: "person",  name: "Person",  icon: "👤" },
  { id: "event",   name: "Event",   icon: "📜" },
  { id: "scoring", name: "Scoring", icon: "⭐" },
];

function PhaseTracker({ currentPhase }) {
  const curIdx = PHASES.findIndex(p => p.id === currentPhase);
  return (
    <div style={{ display: "flex", gap: 3, alignItems: "center" }}>
      {PHASES.map((phase, i) => {
        const isPast = i < curIdx;
        const isCurrent = i === curIdx;
        return (
          <div key={phase.id} style={{ display: "flex", alignItems: "center", gap: 3 }}>
            <div style={{
              padding: "4px 12px", borderRadius: 6,
              background: isCurrent ? "rgba(212,160,23,0.2)" : isPast ? "rgba(30,15,8,0.5)" : "rgba(45,24,16,0.6)",
              border: isCurrent ? "2px solid #d4a017" : "1px solid #5a3a2066",
              opacity: isPast ? 0.45 : 1,
              display: "flex", alignItems: "center", gap: 5,
            }}>
              <span style={{ fontSize: 13 }}>{phase.icon}</span>
              <span style={{ fontSize: 11, fontWeight: isCurrent ? 700 : 400, color: isCurrent ? "#d4a017" : "#a08060" }}>
                {phase.name}
              </span>
            </div>
            {i < PHASES.length - 1 && (
              <span style={{ color: isPast ? "#5a3a2044" : "#5a3a2088", fontSize: 10 }}>›</span>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ─── TURN ORDER BAR ─────────────────────────────────────────────────

function TurnOrderBar({ players, turnOrder, currentOrderIdx, phaseName }) {
  if (!turnOrder || turnOrder.length === 0) return null;
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap",
      padding: "8px 12px", marginBottom: 10, background: "rgba(0,0,0,0.15)", borderRadius: 6,
    }}>
      <span style={{ fontSize: 11, color: "#806040", fontWeight: 600, whiteSpace: "nowrap" }}>
        {phaseName} order:
      </span>
      {turnOrder.map((pIdx, i) => {
        const p = players[pIdx];
        const isCurrent = i === currentOrderIdx;
        const isDone = i < currentOrderIdx;
        return (
          <div key={i} style={{ display: "flex", alignItems: "center", gap: 3 }}>
            {i > 0 && <span style={{ color: "#5a3a2066", fontSize: 10 }}>→</span>}
            <div style={{
              display: "flex", alignItems: "center", gap: 5,
              padding: "3px 10px", borderRadius: 10,
              background: isCurrent ? `${p.color.primary}33` : "transparent",
              border: isCurrent ? `2px solid ${p.color.primary}` : "1px solid transparent",
              opacity: isDone ? 0.4 : 1,
            }}>
              <div style={{
                width: 10, height: 10, borderRadius: "50%",
                background: p.color.primary,
                boxShadow: isCurrent ? `0 0 6px ${p.color.primary}` : "none",
              }} />
              <span style={{
                fontSize: 11, color: isCurrent ? p.color.light : "#a08060",
                fontWeight: isCurrent ? 700 : 400,
                textDecoration: isDone ? "line-through" : "none",
              }}>
                {p.name}
              </span>
              {isCurrent && <span style={{ fontSize: 9, color: p.color.primary }}>◄</span>}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ─── EVENT TRACK ────────────────────────────────────────────────────

function EventTrack({ events, currentRound }) {
  return (
    <div style={{ display: "flex", gap: 4, flexWrap: "wrap", padding: "8px 0" }}>
      {events.map((event, i) => (
        <div key={i} style={{
          width: 72, height: 52,
          background: i < currentRound ? "rgba(30,15,8,0.6)"
            : i === currentRound ? `linear-gradient(135deg, ${event.color}33, ${event.color}11)`
            : "rgba(45,24,16,0.7)",
          border: i === currentRound ? `2px solid ${event.color}` : "1px solid #5a3a2066",
          borderRadius: 6, display: "flex", flexDirection: "column",
          alignItems: "center", justifyContent: "center", gap: 2,
          opacity: i < currentRound ? 0.4 : 1,
        }}>
          <span style={{ fontSize: 16 }}>{event.icon}</span>
          <span style={{ fontSize: 8, color: "#a08060", textAlign: "center" }}>{event.name}</span>
          <span style={{ fontSize: 8, color: "#705030" }}>Month {i + 1}</span>
        </div>
      ))}
    </div>
  );
}

// ─── ACTION CARD DISPLAY ────────────────────────────────────────────

function ActionCard({ actionId, selected, onClick, disabled, player }) {
  const info = ACTION_INFO[actionId];
  if (!info) return null;
  const bonus = info.bonus ? countSymbols(player, info.bonus) : 0;
  const previewTotal = info.bonus ? (actionId === "taxes" ? 2 + bonus : 1 + bonus) : null;

  return (
    <div onClick={disabled ? undefined : onClick} style={{
      width: 130, padding: 10, borderRadius: 8, cursor: disabled ? "default" : "pointer",
      background: selected
        ? "linear-gradient(135deg, rgba(212,160,23,0.15), rgba(139,69,19,0.2))"
        : "linear-gradient(135deg, rgba(40,22,12,0.95), rgba(25,12,6,0.95))",
      border: selected ? "2px solid #d4a017" : "1px solid #5a3a2088",
      boxShadow: selected ? "0 0 12px rgba(212,160,23,0.2)" : "0 2px 6px rgba(0,0,0,0.3)",
      transition: "all 0.15s", opacity: disabled ? 0.5 : 1,
      display: "flex", flexDirection: "column", gap: 4,
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        <span style={{ fontSize: 20 }}>{info.icon}</span>
        <span style={{ fontSize: 12, fontWeight: 700, color: selected ? "#d4a017" : "#c0a070" }}>{info.name}</span>
      </div>
      <div style={{ fontSize: 9, color: "#907050", lineHeight: 1.3 }}>{info.desc}</div>
      {previewTotal !== null && (
        <div style={{
          fontSize: 10, color: "#d4a017", background: "rgba(0,0,0,0.25)",
          borderRadius: 4, padding: "2px 6px", marginTop: 2,
        }}>
          → {previewTotal} {info.unit}
        </div>
      )}
    </div>
  );
}

// ─── SETUP ──────────────────────────────────────────────────────────

function SetupScreen({ onStart }) {
  const [pc, setPc] = useState(3);
  const [names, setNames] = useState(["", "", "", "", ""]);

  const updateName = (i, val) => {
    const n = [...names]; n[i] = val; setNames(n);
  };

  const finalNames = Array.from({ length: pc }, (_, i) => names[i].trim() || `Player ${i + 1}`);

  return (
    <div style={S.content}>
      <div style={{ textAlign: "center", padding: "30px 0 20px", borderBottom: "2px solid #8B4513", marginBottom: 30 }}>
        <h1 style={S.title}>🐉 In the Year of the Dragon 🐉</h1>
        <p style={{ fontSize: 14, color: "#a08060", marginTop: 6, fontStyle: "italic" }}>
          A game of foresight and survival in ancient China, 1000 A.D.
        </p>
      </div>
      <div style={{ ...S.card, maxWidth: 520, margin: "40px auto", textAlign: "center" }}>
        <h2 style={S.cardTitle}>New Game</h2>
        <p style={{ color: "#c0a070", marginBottom: 20, lineHeight: 1.6 }}>
          Navigate 12 months of hazardous events with the help of your loyal courtiers.
        </p>
        <div style={{ marginBottom: 24 }}>
          <label style={{ color: "#d4a017", fontSize: 15, display: "block", marginBottom: 12 }}>Number of Players</label>
          <div style={{ display: "flex", gap: 8, justifyContent: "center" }}>
            {[2, 3, 4, 5].map(n => (
              <button key={n} onClick={() => setPc(n)} style={{
                ...S.btn, ...(pc === n ? S.btnP : {}),
                width: 50, height: 50, fontSize: 20, padding: 0,
                display: "flex", alignItems: "center", justifyContent: "center",
              }}>{n}</button>
            ))}
          </div>
        </div>

        {/* Player name inputs */}
        <div style={{ marginBottom: 24, textAlign: "left" }}>
          <label style={{ color: "#d4a017", fontSize: 15, display: "block", marginBottom: 12, textAlign: "center" }}>Player Names</label>
          {Array.from({ length: pc }).map((_, i) => (
            <div key={i} style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
              <div style={{
                width: 16, height: 16, borderRadius: "50%", flexShrink: 0,
                background: PLAYER_COLORS[i].primary, boxShadow: `0 0 4px ${PLAYER_COLORS[i].primary}66`,
              }} />
              <input
                type="text"
                placeholder={`Player ${i + 1}`}
                value={names[i]}
                onChange={(e) => updateName(i, e.target.value)}
                style={{
                  flex: 1, fontFamily: font, fontSize: 14, padding: "8px 12px",
                  borderRadius: 6, border: "1px solid #5a3a20",
                  background: "rgba(0,0,0,0.3)", color: "#f0e6d3",
                  outline: "none",
                }}
              />
              <span style={{ fontSize: 11, color: PLAYER_COLORS[i].light, width: 50 }}>{PLAYER_COLORS[i].name}</span>
            </div>
          ))}
        </div>

        <button onClick={() => onStart(pc, finalNames)} style={{ ...S.btn, ...S.btnP, fontSize: 18, padding: "14px 40px" }}>
          Start Game
        </button>
      </div>
    </div>
  );
}

// ─── DRAFT ──────────────────────────────────────────────────────────

function DraftScreen({ players, personTiles, events, onCompleteDraft }) {
  const [curIdx, setCurIdx] = useState(0);
  const [sels, setSels] = useState([]);
  const [dPlayers, setDPlayers] = useState(players);
  const [remTiles, setRemTiles] = useState(personTiles);
  const [usedCombos, setUsedCombos] = useState(new Set());

  const young = remTiles.filter(t => t.experience === "young");
  const byType = {};
  young.forEach(t => { if (!byType[t.typeId]) byType[t.typeId] = []; byType[t.typeId].push(t); });

  const cur = dPlayers[curIdx];
  const canSel = (tile) => {
    if (sels.length >= 2 || sels.find(s => s.id === tile.id)) return false;
    if (sels.length === 1 && sels[0].typeId === tile.typeId) return false;
    if (sels.length === 1 && usedCombos.has(comboKey(sels[0].typeId, tile.typeId))) return false;
    return true;
  };
  const toggle = (tile) => {
    if (sels.find(s => s.id === tile.id)) setSels(sels.filter(s => s.id !== tile.id));
    else if (canSel(tile)) setSels([...sels, tile]);
  };
  const confirm = () => {
    if (sels.length !== 2) return;
    const nc = new Set(usedCombos); nc.add(comboKey(sels[0].typeId, sels[1].typeId));
    const up = [...dPlayers]; const p = deepClonePlayer(up[curIdx]);
    p.palaces[0].persons = [sels[0]]; p.palaces[1].persons = [sels[1]];
    p.personTrack = sels[0].value + sels[1].value; up[curIdx] = p;
    const nt = remTiles.filter(t => t.id !== sels[0].id && t.id !== sels[1].id);
    setDPlayers(up); setRemTiles(nt); setUsedCombos(nc); setSels([]);
    if (curIdx + 1 < players.length) setCurIdx(curIdx + 1); else onCompleteDraft(up, nt);
  };

  return (
    <div style={S.content}>
      <div style={{ textAlign: "center", padding: "20px 0 16px", borderBottom: "2px solid #8B4513", marginBottom: 20 }}>
        <h1 style={{ ...S.title, fontSize: 32 }}>🐉 Initial Draft</h1>
      </div>
      <div style={{ ...S.card, padding: 12 }}>
        <div style={{ fontSize: 12, color: "#d4a017", marginBottom: 6 }}>Event Track — Plan ahead!</div>
        <EventTrack events={events} currentRound={-1} />
      </div>
      <div style={S.card}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
          <div style={{ width: 20, height: 20, borderRadius: "50%", background: cur.color.primary }} />
          <h2 style={{ ...S.cardTitle, margin: 0, border: "none", padding: 0 }}>
            {cur.name} ({cur.color.name}) — Pick 2 different young courtiers
          </h2>
        </div>
        {usedCombos.size > 0 && (
          <p style={{ fontSize: 12, color: "#a08060", marginBottom: 12 }}>
            Forbidden: {Array.from(usedCombos).map(c => { const [a,b]=c.split("+"); return `${PERSON_TYPES[a]?.name} + ${PERSON_TYPES[b]?.name}`; }).join(", ")}
          </p>
        )}
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 20 }}>
          {Object.entries(byType).map(([tid, tiles]) => (
            <div key={tid} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
              {tiles.length > 0 && <PersonTileDisplay tile={tiles[0]} onClick={() => toggle(tiles[0])}
                selected={!!sels.find(s => s.id === tiles[0].id)}
                disabled={!canSel(tiles[0]) && !sels.find(s => s.id === tiles[0].id)} />}
              <span style={{ fontSize: 10, color: "#705030" }}>×{tiles.length}</span>
            </div>
          ))}
        </div>
        {sels.length > 0 && (
          <div style={{ marginBottom: 16 }}>
            <span style={{ color: "#d4a017", fontSize: 13 }}>Selected: </span>
            {sels.map(s => (
              <span key={s.id} style={{
                display: "inline-block", background: `${PERSON_TYPES[s.typeId].color}22`,
                border: `1px solid ${PERSON_TYPES[s.typeId].color}`,
                borderRadius: 6, padding: "3px 10px", fontSize: 12,
                color: PERSON_TYPES[s.typeId].color, marginRight: 6,
              }}>{PERSON_TYPES[s.typeId].icon} {PERSON_TYPES[s.typeId].name} (+{s.value})</span>
            ))}
          </div>
        )}
        <button onClick={confirm} disabled={sels.length !== 2} style={bs(true, sels.length !== 2)}>Confirm</button>
      </div>
      <PlayerAreasGrid players={dPlayers} activePlayerIdx={curIdx} />
    </div>
  );
}

// ─── ACTION PHASE ───────────────────────────────────────────────────

function BuildPlacementUI({ totalFloors, initialPalaces, onConfirm, onCancel, playerName }) {
  // Working copy of palaces the player can modify
  const [palaces, setPalaces] = useState(initialPalaces.map(p => ({ ...p, persons: [...p.persons] })));
  const [remaining, setRemaining] = useState(totalFloors);

  const addFloor = (palaceIdx) => {
    if (remaining <= 0) return;
    if (palaces[palaceIdx].floors >= 3) return;
    const np = palaces.map((p, i) => i === palaceIdx ? { ...p, floors: p.floors + 1 } : p);
    setPalaces(np);
    setRemaining(remaining - 1);
  };

  const addNewPalace = () => {
    if (remaining <= 0) return;
    setPalaces([...palaces, { floors: 1, persons: [] }]);
    setRemaining(remaining - 1);
  };

  const resetBuild = () => {
    setPalaces(initialPalaces.map(p => ({ ...p, persons: [...p.persons] })));
    setRemaining(totalFloors);
  };

  return (
    <div style={{ padding: 16, background: "rgba(139,105,20,0.08)", border: "1px solid #8B691444", borderRadius: 8, marginBottom: 16 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
        <h3 style={{ color: "#d4a017", fontSize: 16, margin: 0 }}>
          🏗️ {playerName}: Place {totalFloors} floor(s)
        </h3>
        <span style={{
          fontSize: 14, fontWeight: 700, padding: "4px 14px", borderRadius: 12,
          background: remaining === 0 ? "rgba(39,174,96,0.2)" : "rgba(212,160,23,0.2)",
          color: remaining === 0 ? "#27ae60" : "#d4a017",
          border: remaining === 0 ? "1px solid #27ae6044" : "1px solid #d4a01744",
        }}>
          {remaining === 0 ? "✓ All placed" : `${remaining} remaining`}
        </span>
      </div>

      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: 16 }}>
        {palaces.map((pal, i) => {
          const canAdd = remaining > 0 && pal.floors < 3;
          return (
            <div key={i} style={{
              background: "rgba(0,0,0,0.15)", border: "1px solid #5a3a2066",
              borderRadius: 8, padding: 10, minWidth: 120, textAlign: "center",
            }}>
              <PalaceDisplay palace={pal} palaceIndex={i} />
              <button onClick={() => addFloor(i)} disabled={!canAdd}
                style={{ ...bs(false, !canAdd), fontSize: 11, padding: "4px 10px", marginTop: 6, width: "100%" }}>
                + Add Floor
              </button>
            </div>
          );
        })}

        {/* New palace button */}
        {remaining > 0 && (
          <div onClick={addNewPalace} style={{
            background: "rgba(0,0,0,0.1)", border: "2px dashed #5a3a2066",
            borderRadius: 8, padding: 10, minWidth: 120, minHeight: 100,
            display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
            cursor: "pointer", gap: 6,
          }}>
            <span style={{ fontSize: 24, color: "#5a3a20" }}>+</span>
            <span style={{ fontSize: 11, color: "#806040" }}>New Palace</span>
          </div>
        )}
      </div>

      <div style={{ display: "flex", gap: 10 }}>
        <button onClick={() => onConfirm(palaces)} disabled={remaining > 0}
          style={bs(true, remaining > 0)}>
          Confirm Build
        </button>
        <button onClick={resetBuild} style={bs(false)}>Reset</button>
        <button onClick={onCancel} style={bs(false)}>Cancel</button>
      </div>
    </div>
  );
}

function ActionPhase({ gameState, onCompleteAction }) {
  const { players, actionGroups, personTrackOrder } = gameState;
  const [orderIdx, setOrderIdx] = useState(0);
  const [selGroup, setSelGroup] = useState(null);
  const [selAction, setSelAction] = useState(null);
  const [uPlayers, setUPlayers] = useState(players);
  const [dragons, setDragons] = useState(actionGroups.map(() => []));
  const [done, setDone] = useState(false);
  const [privChoice, setPrivChoice] = useState(null);
  const [log, setLog] = useState(null);
  // Build sub-phase
  const [buildMode, setBuildMode] = useState(null); // null | { totalFloors, allPlayers, groupIdx }

  const curPIdx = personTrackOrder[orderIdx];
  const curP = uPlayers[curPIdx];
  const gCost = (g) => dragons[g].length > 0 ? 3 : 0;
  const canAfford = (g) => dragons[g].length === 0 || curP.yuan >= 3;

  const advance = (np, lg) => {
    setUPlayers(np); setLog(lg);
    setSelGroup(null); setSelAction(null); setPrivChoice(null); setBuildMode(null);
    if (orderIdx + 1 < personTrackOrder.length) setOrderIdx(orderIdx + 1);
    else setDone(true);
  };

  const handleConfirm = () => {
    if (selGroup === null || selAction === null) return;
    if (selAction === "privilege" && !privChoice) return;

    const ap = deepClonePlayers(uPlayers); const p = ap[curPIdx];
    const cost = gCost(selGroup);
    if (cost > 0) p.yuan -= cost;
    const nd = dragons.map(g => [...g]); nd[selGroup].push(curPIdx); setDragons(nd);

    // Build action: enter build sub-phase instead of auto-executing
    if (selAction === "build") {
      const bonus = countSymbols(p, "craftsman");
      const totalFloors = 1 + bonus;
      // Save the partially-updated players (group cost paid) for build mode
      setUPlayers(ap);
      setBuildMode({ totalFloors, groupIdx: selGroup, costPaid: cost });
      return;
    }

    let lg = "";
    switch (selAction) {
      case "taxes": lg = executeTaxes(p); break;
      case "harvest": lg = executeHarvest(p); break;
      case "fireworks": lg = executeFireworks(p); break;
      case "military": lg = executeMilitary(p); break;
      case "research": lg = executeResearch(p); break;
      case "privilege": lg = executePrivilege(p, privChoice); break;
    }
    if (cost > 0) lg = `Paid ${cost}¥ for occupied group. ` + lg;
    advance(ap, lg);
  };

  const handleBuildConfirm = (newPalaces) => {
    const ap = deepClonePlayers(uPlayers);
    ap[curPIdx].palaces = newPalaces;
    const bonus = countSymbols(curP, "craftsman");
    let lg = `Built ${buildMode.totalFloors} floor(s) (1 base + ${bonus} craftsmen).`;
    if (buildMode.costPaid > 0) lg = `Paid ${buildMode.costPaid}¥ for occupied group. ` + lg;
    advance(ap, lg);
  };

  const handleBuildCancel = () => {
    // Refund the exact cost that was paid
    const restored = deepClonePlayers(uPlayers);
    restored[curPIdx].yuan += buildMode.costPaid;
    setUPlayers(restored);
    // Remove dragon from group
    const nd = dragons.map(g => [...g]);
    const idx = nd[buildMode.groupIdx].indexOf(curPIdx);
    if (idx >= 0) nd[buildMode.groupIdx].splice(idx, 1);
    setDragons(nd);
    setBuildMode(null);
  };

  const handleSkip = () => {
    const ap = deepClonePlayers(uPlayers); const p = ap[curPIdx];
    const need = Math.max(0, 3 - p.yuan); p.yuan += need;
    advance(ap, `Skipped. Took ${need}¥ (now ${p.yuan}¥).`);
  };

  if (done) {
    return (
      <>
        <div style={S.card}>
          <h2 style={S.cardTitle}>Action Phase Complete</h2>
          {log && <p style={{ fontSize: 13, color: "#c0a070", marginBottom: 12 }}>Last: {log}</p>}
          <button onClick={() => onCompleteAction(uPlayers)} style={bs(true)}>Continue to Person Phase →</button>
        </div>
        <PlayerAreasGrid players={uPlayers} activePlayerIdx={-1} />
      </>
    );
  }

  // Build sub-phase
  if (buildMode) {
    return (
      <>
        <TurnOrderBar players={uPlayers} turnOrder={personTrackOrder}
          currentOrderIdx={orderIdx} phaseName="Action" />
        <div style={S.card}>
          <BuildPlacementUI
            totalFloors={buildMode.totalFloors}
            initialPalaces={curP.palaces}
            onConfirm={handleBuildConfirm}
            onCancel={handleBuildCancel}
            playerName={curP.name}
          />
        </div>
        <PlayerAreasGrid players={uPlayers} activePlayerIdx={curPIdx} />
      </>
    );
  }

  const yuanAfter = selGroup !== null ? curP.yuan - gCost(selGroup) : 0;

  return (
    <>
      <TurnOrderBar players={uPlayers} turnOrder={personTrackOrder}
        currentOrderIdx={orderIdx} phaseName="Action" />
      <div style={S.card}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
          <div style={{ width: 20, height: 20, borderRadius: "50%", background: curP.color.primary }} />
          <h2 style={{ ...S.cardTitle, margin: 0, border: "none", padding: 0 }}>
            {curP.name}'s Action
          </h2>
          <span style={{ fontSize: 12, color: "#a08060" }}>({curP.yuan}¥)</span>
        </div>

        {log && (
          <div style={{ padding: 10, marginBottom: 12, borderRadius: 6, background: "rgba(212,160,23,0.1)", border: "1px solid #d4a01744" }}>
            <span style={{ fontSize: 13, color: "#d4a017" }}>Previous: {log}</span>
          </div>
        )}

        {/* Action groups */}
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 16 }}>
          {actionGroups.map((group, gIdx) => (
            <div key={gIdx} style={{
              borderRadius: 10, padding: 10,
              background: selGroup === gIdx ? "rgba(212,160,23,0.08)" : "rgba(20,10,5,0.5)",
              border: selGroup === gIdx ? "2px solid #d4a01788" : "1px solid #5a3a2066",
              opacity: canAfford(gIdx) ? 1 : 0.35,
              cursor: canAfford(gIdx) ? "pointer" : "not-allowed",
            }} onClick={() => { if (canAfford(gIdx)) { setSelGroup(gIdx); setSelAction(null); setPrivChoice(null); } }}>
              <div style={{ fontSize: 10, color: "#705030", marginBottom: 6, display: "flex", alignItems: "center", gap: 6 }}>
                <span>Group {gIdx + 1}</span>
                {dragons[gIdx].length > 0 && (
                  <span style={{ color: "#c0392b", fontSize: 10 }}>🐉×{dragons[gIdx].length} — costs 3¥</span>
                )}
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {group.map((a, aIdx) => (
                  <ActionCard key={aIdx} actionId={a.id}
                    selected={selGroup === gIdx && selAction === a.id}
                    onClick={(e) => { e?.stopPropagation?.(); if (selGroup === gIdx) { setSelAction(a.id); setPrivChoice(null); } }}
                    disabled={selGroup !== gIdx}
                    player={curP} />
                ))}
              </div>
            </div>
          ))}
        </div>

        {selAction === "privilege" && (
          <div style={{ marginBottom: 16, padding: 12, background: "rgba(0,0,0,0.2)", borderRadius: 6 }}>
            <span style={{ color: "#d4a017", fontSize: 13 }}>Choose privilege: </span>
            <button onClick={() => setPrivChoice("small")} disabled={yuanAfter < 2}
              style={{ ...bs(privChoice === "small", yuanAfter < 2), fontSize: 12, padding: "4px 12px", marginRight: 8 }}>
              Small (2¥) — 1🐉/round
            </button>
            <button onClick={() => setPrivChoice("large")} disabled={yuanAfter < 7}
              style={{ ...bs(privChoice === "large", yuanAfter < 7), fontSize: 12, padding: "4px 12px" }}>
              Large (7¥) — 2🐉/round
            </button>
          </div>
        )}

        <div style={{ display: "flex", gap: 12 }}>
          <button onClick={handleConfirm}
            disabled={selGroup === null || selAction === null || (selAction === "privilege" && !privChoice)}
            style={bs(true, selGroup === null || selAction === null || (selAction === "privilege" && !privChoice))}>
            Confirm Action
          </button>
          <button onClick={handleSkip} style={bs(false)}>Skip (top up to 3¥)</button>
        </div>
      </div>
      <PlayerAreasGrid players={uPlayers} activePlayerIdx={curPIdx} />
    </>
  );
}

// ─── PERSON PHASE ───────────────────────────────────────────────────

function PersonPhase({ gameState, onCompletePersonPhase }) {
  const { players, personTrackOrder, remainingTiles } = gameState;
  const [orderIdx, setOrderIdx] = useState(0);
  const [uPlayers, setUPlayers] = useState(players);
  const [tiles, setTiles] = useState(remainingTiles);
  const [selCard, setSelCard] = useState(null);
  const [selTile, setSelTile] = useState(null);
  const [selPalace, setSelPalace] = useState(null);
  const [replacing, setReplacing] = useState(null);
  const [releaseImmediate, setReleaseImmediate] = useState(false);
  const [done, setDone] = useState(false);

  const curPIdx = personTrackOrder[orderIdx];
  const curP = uPlayers[curPIdx];

  const avail = useMemo(() => {
    if (!selCard) return [];
    return selCard.isWild ? tiles : tiles.filter(t => t.typeId === selCard.typeId);
  }, [selCard, tiles]);

  // Placement rules
  const hasEmptySlot = curP.palaces.some(pal => pal.persons.length < pal.floors);
  const allFull = !hasEmptySlot;

  const advanceTurn = (ap, nt) => {
    setUPlayers(ap); setTiles(nt);
    setSelCard(null); setSelTile(null); setSelPalace(null);
    setReplacing(null); setReleaseImmediate(false);
    if (orderIdx + 1 < personTrackOrder.length) setOrderIdx(orderIdx + 1); else setDone(true);
  };

  const confirmP = () => {
    if (!selCard) return;
    const ap = deepClonePlayers(uPlayers); const p = ap[curPIdx];
    const ci = p.cards.findIndex(c => selCard.isWild ? c.isWild : c.typeId === selCard.typeId);
    p.cards.splice(ci, 1);
    let nt = tiles;

    if (selTile) {
      nt = tiles.filter(t => t.id !== selTile.id);
      if (releaseImmediate) {
        // Tile taken from supply but released immediately — no track advancement
      } else if (selPalace !== null) {
        if (replacing !== null) p.palaces[selPalace].persons.splice(replacing, 1);
        p.palaces[selPalace].persons.push(selTile);
        p.personTrack += selTile.value;
      }
    }
    advanceTurn(ap, nt);
  };

  if (done) return (
    <>
      <div style={S.card}>
        <h2 style={S.cardTitle}>Person Phase Complete</h2>
        <button onClick={() => onCompletePersonPhase(uPlayers, tiles)} style={bs(true)}>Continue to Event Phase →</button>
      </div>
      <PlayerAreasGrid players={uPlayers} activePlayerIdx={-1} />
    </>
  );

  // Can confirm when:
  // - Card selected and no tiles available (discard only)
  // - Tile selected and releasing immediately (all palaces full)
  // - Tile selected and placed in a palace with space
  // - Tile selected and placed in a full palace with a replacement chosen
  const canConf = selCard && (
    avail.length === 0 ||
    releaseImmediate ||
    (selTile && selPalace !== null && (
      curP.palaces[selPalace]?.persons.length < curP.palaces[selPalace]?.floors ||
      replacing !== null
    ))
  );

  return (
    <>
      <TurnOrderBar players={uPlayers} turnOrder={personTrackOrder}
        currentOrderIdx={orderIdx} phaseName="Person" />
      <div style={S.card}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
          <div style={{ width: 20, height: 20, borderRadius: "50%", background: curP.color.primary }} />
          <h2 style={{ ...S.cardTitle, margin: 0, border: "none", padding: 0 }}>{curP.name} — Play a Person Card</h2>
        </div>

        {/* Hand */}
        <div style={{ marginBottom: 16 }}>
          <span style={{ fontSize: 13, color: "#d4a017", display: "block", marginBottom: 8 }}>Your hand:</span>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            {curP.cards.map((card, i) => (
              <div key={i} onClick={() => {
                setSelCard(card); setSelTile(null); setSelPalace(null);
                setReplacing(null); setReleaseImmediate(false);
              }} style={{
                padding: "6px 12px", borderRadius: 6, fontSize: 12, cursor: "pointer",
                background: selCard === card ? "rgba(212,160,23,0.2)" : "rgba(30,15,8,0.6)",
                border: selCard === card ? "2px solid #d4a017" : "1px solid #5a3a2088",
              }}>
                {card.isWild ? "❓ Wild" : `${PERSON_TYPES[card.typeId].icon} ${PERSON_TYPES[card.typeId].name}`}
              </div>
            ))}
          </div>
        </div>

        {/* Available tiles */}
        {selCard && (
          <div style={{ marginBottom: 16 }}>
            <span style={{ fontSize: 13, color: "#d4a017", display: "block", marginBottom: 8 }}>
              Available tiles{selCard.isWild ? " (any)" : ""}:
            </span>
            {avail.length === 0 ? <p style={{ color: "#a08060", fontSize: 13 }}>None available. Card discarded.</p>
            : <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                {avail.map(t => <PersonTileDisplay key={t.id} tile={t}
                  onClick={() => { setSelTile(t); setSelPalace(null); setReplacing(null); setReleaseImmediate(false); }}
                  selected={selTile?.id === t.id} small />)}
              </div>}
          </div>
        )}

        {/* Palace placement — only show if tile selected and not releasing immediately */}
        {selTile && !releaseImmediate && (
          <div style={{ marginBottom: 16 }}>
            <span style={{ fontSize: 13, color: "#d4a017", display: "block", marginBottom: 8 }}>
              Place in palace{hasEmptySlot ? " (must use empty slot)" : ""}:
            </span>
            <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
              {curP.palaces.map((pal, i) => {
                const isFull = pal.persons.length >= pal.floors;
                // If there are empty slots anywhere, disable full palaces
                const disabled = hasEmptySlot && isFull;
                return (
                  <div key={i} onClick={() => {
                    if (disabled) return;
                    setSelPalace(i); setReplacing(null);
                  }} style={{
                    padding: 8, borderRadius: 6,
                    cursor: disabled ? "not-allowed" : "pointer",
                    opacity: disabled ? 0.4 : 1,
                    border: selPalace === i ? "2px solid #d4a017" : "1px solid #5a3a2088",
                    background: selPalace === i ? "rgba(212,160,23,0.1)" : "rgba(30,15,8,0.6)",
                  }}>
                    <PalaceDisplay palace={pal} palaceIndex={i} />
                    {isFull && !hasEmptySlot && <span style={{ fontSize: 10, color: "#c0392b" }}>Full — replace</span>}
                    {isFull && hasEmptySlot && <span style={{ fontSize: 10, color: "#5a3a20" }}>Full</span>}
                    {!isFull && <span style={{ fontSize: 10, color: "#27ae60" }}>Space available</span>}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Replacement selection — only when all palaces full and selected palace is full */}
        {selTile && !releaseImmediate && selPalace !== null && allFull && (
          <div style={{ marginBottom: 16 }}>
            <span style={{ fontSize: 13, color: "#c0392b", display: "block", marginBottom: 8 }}>Choose courtier to replace:</span>
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              {curP.palaces[selPalace].persons.map((per, i) => (
                <PersonTileDisplay key={i} tile={per} onClick={() => setReplacing(i)} selected={replacing === i} small />
              ))}
            </div>
          </div>
        )}

        {/* Release immediately option — only when all palaces full */}
        {selTile && allFull && (
          <div style={{ marginBottom: 16 }}>
            <div onClick={() => {
              setReleaseImmediate(!releaseImmediate);
              if (!releaseImmediate) { setSelPalace(null); setReplacing(null); }
            }} style={{
              display: "inline-flex", alignItems: "center", gap: 8,
              padding: "8px 16px", borderRadius: 6, cursor: "pointer",
              background: releaseImmediate ? "rgba(192,57,43,0.15)" : "rgba(0,0,0,0.15)",
              border: releaseImmediate ? "2px solid #c0392b" : "1px solid #5a3a2088",
              transition: "all 0.15s",
            }}>
              <span style={{ fontSize: 14 }}>🚫</span>
              <div>
                <div style={{ fontSize: 12, color: releaseImmediate ? "#e74c3c" : "#a08060", fontWeight: 600 }}>
                  Release immediately
                </div>
                <div style={{ fontSize: 10, color: "#806040" }}>
                  Tile discarded — no person track advancement
                </div>
              </div>
            </div>
          </div>
        )}

        <button onClick={confirmP} disabled={!canConf} style={bs(true, !canConf)}>Confirm</button>
      </div>
      <PlayerAreasGrid players={uPlayers} activePlayerIdx={curPIdx} />
    </>
  );
}

// ─── DROUGHT FEEDING UI ─────────────────────────────────────────────

function DroughtFeedingUI({ player, onConfirm }) {
  const inhabited = player.palaces.map((pal, i) => ({ palaceIdx: i, palace: pal })).filter(p => p.palace.persons.length > 0);
  const canFeedAll = player.rice >= inhabited.length;
  const maxFeed = Math.min(player.rice, inhabited.length);
  // If can feed all, pre-select everything
  const [fed, setFed] = useState(() => {
    if (canFeedAll) return new Set(inhabited.map(x => x.palaceIdx));
    return new Set();
  });

  const toggleFeed = (palaceIdx) => {
    const nf = new Set(fed);
    if (nf.has(palaceIdx)) { nf.delete(palaceIdx); }
    else if (nf.size < maxFeed) { nf.add(palaceIdx); }
    setFed(nf);
  };

  // Must use exactly as much rice as they can (feed up to maxFeed palaces)
  const ready = fed.size === maxFeed;

  return (
    <div style={{ padding: 16, background: "rgba(230,126,34,0.08)", border: "1px solid #e67e2244", borderRadius: 8, marginBottom: 16 }}>
      <h3 style={{ color: "#e67e22", fontSize: 16, margin: "0 0 8px" }}>
        ☀️ Drought — {player.name} must feed palaces
      </h3>
      <p style={{ fontSize: 13, color: "#c0a070", marginBottom: 12 }}>
        {player.rice} rice available, {inhabited.length} inhabited palace(s).
        {canFeedAll
          ? " You have enough to feed all."
          : ` Choose ${maxFeed} palace(s) to feed. Unfed palaces each lose 1 courtier.`}
      </p>
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: 16 }}>
        {inhabited.map(({ palaceIdx, palace }) => {
          const isFed = fed.has(palaceIdx);
          return (
            <div key={palaceIdx} onClick={() => toggleFeed(palaceIdx)} style={{
              background: isFed ? "rgba(39,174,96,0.1)" : "rgba(192,57,43,0.08)",
              border: isFed ? "2px solid #27ae60" : "2px solid #c0392b44",
              borderRadius: 8, padding: 10, cursor: "pointer", minWidth: 120, textAlign: "center",
              transition: "all 0.15s",
            }}>
              <PalaceDisplay palace={palace} palaceIndex={palaceIdx} />
              <div style={{
                marginTop: 6, fontSize: 11, fontWeight: 700, padding: "3px 8px",
                borderRadius: 4,
                background: isFed ? "rgba(39,174,96,0.2)" : "rgba(192,57,43,0.15)",
                color: isFed ? "#27ae60" : "#c0392b",
              }}>
                {isFed ? "🌾 Fed" : "☠️ Unfed"}
              </div>
            </div>
          );
        })}
      </div>
      <button onClick={() => onConfirm(fed)} disabled={!ready}
        style={bs(true, !ready)}>
        Confirm Feeding ({fed.size}/{maxFeed} palaces fed)
      </button>
    </div>
  );
}

// ─── EVENT PHASE ────────────────────────────────────────────────────

function EventPhase({ gameState, onCompleteEvent }) {
  const { players, events, currentRound } = gameState;
  const ev = events[currentRound];
  const [uPlayers, setUPlayers] = useState(players);
  const [resolved, setResolved] = useState(false);
  const [elog, setElog] = useState([]);

  // Generic release queue (for tribute, contagion, mongols)
  const [relQueue, setRelQueue] = useState([]);
  const [curRel, setCurRel] = useState(null);
  const [relSel, setRelSel] = useState(null);

  // Drought-specific: per-palace feeding then per-unfed-palace release
  const [droughtQueue, setDroughtQueue] = useState([]);   // [{pi, phase:"feed"|"release", unfedPalaces:[...]}]
  const [curDrought, setCurDrought] = useState(null);
  const [droughtRelSel, setDroughtRelSel] = useState(null); // person index within the specific palace

  const applyDecay = (pls, log) => {
    pls.forEach((p, i) => {
      p.palaces = p.palaces.map(pal => {
        if (pal.persons.length === 0 && pal.floors > 0) { log.push(`${p.name}: empty palace decays.`); return { ...pal, floors: pal.floors - 1 }; }
        return pal;
      }).filter(pal => pal.floors > 0);
    });
  };

  const finishEvent = (pls, log) => {
    applyDecay(pls, log);
    setUPlayers(pls); setElog(log); setResolved(true);
  };

  const resolve = () => {
    const log = []; const pls = deepClonePlayers(uPlayers); const rels = [];

    switch (ev.id) {
      case "peace":
        log.push("Peace reigns. Nothing happens.");
        finishEvent(pls, log);
        return;

      case "imperialTribute":
        pls.forEach((p, i) => {
          if (p.yuan >= 4) { p.yuan -= 4; log.push(`${p.name} pays 4¥.`); }
          else { const m = 4 - p.yuan; p.yuan = 0; log.push(`${p.name} pays ${4-m}¥, releases ${m}.`); rels.push({ pi: i, count: m, reason: "Tribute" }); }
        });
        break;

      case "drought": {
        // Build drought queue: each player with inhabited palaces needs to choose feeding
        const dq = [];
        pls.forEach((p, i) => {
          const inhabited = p.palaces.filter(pal => pal.persons.length > 0);
          if (inhabited.length === 0) { log.push(`${p.name} has no inhabited palaces.`); return; }
          if (p.rice === 0) {
            // No rice at all — skip feeding, go straight to release from all inhabited
            const unfed = p.palaces.map((pal, idx) => ({ idx, pal })).filter(x => x.pal.persons.length > 0).map(x => x.idx);
            log.push(`${p.name} has no rice — all ${unfed.length} palace(s) unfed.`);
            dq.push({ pi: i, phase: "release", unfedPalaces: unfed });
          } else {
            dq.push({ pi: i, phase: "feed" });
          }
        });
        setUPlayers(pls); setElog(log);
        if (dq.length > 0) {
          setDroughtQueue(dq); setCurDrought(dq[0]);
        } else {
          finishEvent(pls, log);
        }
        return; // don't fall through to generic release
      }

      case "contagion":
        pls.forEach((p, i) => {
          const m = countSymbols(p, "healer"); const lose = Math.max(0, 3 - m);
          const tot = p.palaces.reduce((s, pal) => s + pal.persons.length, 0);
          const act = Math.min(lose, tot);
          if (act > 0) { log.push(`${p.name} releases ${act} (3-${m} healers).`); rels.push({ pi: i, count: act, reason: "Contagion" }); }
          else log.push(`${p.name} protected.`);
        });
        break;

      case "mongolInvasion": {
        let minH = Infinity;
        const hc = pls.map((p, i) => { const h = countSymbols(p, "warrior"); p.scoringTrack += h; log.push(`${p.name} +${h} VP (warriors).`); if (h < minH) minH = h; return h; });
        hc.forEach((h, i) => { if (h === minH && pls[i].palaces.some(pal => pal.persons.length > 0)) { log.push(`${pls[i].name} fewest (${h}), releases 1.`); rels.push({ pi: i, count: 1, reason: "Mongols" }); } });
        break; }

      case "dragonFestival": {
        const fw = pls.map(p => p.fireworks); const m1 = Math.max(...fw); const m2 = Math.max(...fw.filter(f => f < m1), -1);
        pls.forEach((p, i) => {
          if (p.fireworks > 0 && p.fireworks === m1) { p.scoringTrack += 6; const r = Math.ceil(p.fireworks/2); p.fireworks -= r; log.push(`${p.name} wins! +6 VP, returns ${r}.`); }
          else if (p.fireworks > 0 && m2 > 0 && p.fireworks === m2) { p.scoringTrack += 3; const r = Math.ceil(p.fireworks/2); p.fireworks -= r; log.push(`${p.name} 2nd! +3 VP, returns ${r}.`); }
        });
        break; }
    }

    // Non-drought path: if releases needed, defer decay until after releases complete
    setUPlayers(pls); setElog(log);
    if (rels.length > 0) { setRelQueue(rels); setCurRel(rels[0]); }
    else {
      applyDecay(pls, log);
      setUPlayers(pls); setElog(log);
      setResolved(true);
    }
  };

  // ─── Drought feeding confirm ───
  const handleDroughtFeedConfirm = (fedSet) => {
    const pls = deepClonePlayers(uPlayers);
    const p = pls[curDrought.pi];
    const inhabited = p.palaces.map((pal, i) => ({ idx: i, pal })).filter(x => x.pal.persons.length > 0);
    const fedCount = fedSet.size;
    p.rice -= fedCount;

    const unfedPalaces = inhabited.filter(x => !fedSet.has(x.idx)).map(x => x.idx);
    const newLog = [...elog];
    newLog.push(`${p.name} feeds ${fedCount} palace(s) (${p.rice} rice left).`);
    if (unfedPalaces.length > 0) {
      newLog.push(`${p.name} has ${unfedPalaces.length} unfed palace(s) — must release 1 person from each.`);
    }

    setUPlayers(pls); setElog(newLog);

    if (unfedPalaces.length > 0) {
      // Move to release sub-phase for this player's unfed palaces
      setCurDrought({ pi: curDrought.pi, phase: "release", unfedPalaces });
      setDroughtRelSel(null);
    } else {
      // This player is done, advance drought queue
      advanceDroughtQueue(pls, newLog);
    }
  };

  // ─── Drought release: one person from a specific unfed palace ───
  const handleDroughtReleaseConfirm = () => {
    if (droughtRelSel === null) return;
    const pls = deepClonePlayers(uPlayers);
    const palaceIdx = curDrought.unfedPalaces[0];
    const relPerson = pls[curDrought.pi].palaces[palaceIdx].persons[droughtRelSel];
    const relName = PERSON_TYPES[relPerson.typeId]?.name || "courtier";
    pls[curDrought.pi].palaces[palaceIdx].persons.splice(droughtRelSel, 1);
    const newLog = [...elog, `${pls[curDrought.pi].name} releases ${relName} from Palace ${palaceIdx + 1}.`];
    setUPlayers(pls); setElog(newLog); setDroughtRelSel(null);

    const remainingUnfed = curDrought.unfedPalaces.slice(1);
    if (remainingUnfed.length > 0) {
      setCurDrought({ ...curDrought, unfedPalaces: remainingUnfed });
    } else {
      advanceDroughtQueue(pls, newLog);
    }
  };

  const advanceDroughtQueue = (pls, log) => {
    const nq = droughtQueue.slice(1);
    if (nq.length > 0) {
      setDroughtQueue(nq); setCurDrought(nq[0]);
    } else {
      // All drought done, apply decay and finish
      applyDecay(pls, log);
      setUPlayers(pls); setElog(log);
      setDroughtQueue([]); setCurDrought(null); setResolved(true);
    }
  };

  // ─── Generic release confirm (tribute, contagion, mongols) ───
  const confirmRel = () => {
    if (!curRel || !relSel) return;
    const pls = deepClonePlayers(uPlayers);
    pls[curRel.pi].palaces[relSel.palaceIdx].persons.splice(relSel.personIdx, 1);
    setRelSel(null);
    const nq = [...relQueue]; nq[0] = { ...nq[0], count: nq[0].count - 1 };
    if (nq[0].count <= 0) nq.shift();
    if (nq.length > 0) { setUPlayers(pls); setRelQueue(nq); setCurRel(nq[0]); }
    else {
      // All releases done — re-run decay for palaces emptied by releases
      const log = [...elog];
      applyDecay(pls, log);
      setUPlayers(pls); setElog(log);
      setRelQueue([]); setCurRel(null); setResolved(true);
    }
  };

  // ─── Determine active player for highlight ───
  const activePI = curDrought ? curDrought.pi : curRel ? curRel.pi : -1;

  return (
    <>
      <div style={S.card}>
        <h2 style={S.cardTitle}>{ev.icon} {ev.name} — Month {currentRound + 1}</h2>

        {/* Initial resolve button */}
        {!resolved && elog.length === 0 && !curRel && !curDrought && (
          <button onClick={resolve} style={bs(true)}>Resolve Event</button>
        )}

        {/* Event log */}
        {elog.length > 0 && (
          <div style={{ marginBottom: 16 }}>
            {elog.map((m, i) => <p key={i} style={{ fontSize: 13, color: "#c0a070", margin: "4px 0" }}>• {m}</p>)}
          </div>
        )}

        {/* Drought: feeding phase */}
        {curDrought && curDrought.phase === "feed" && (
          <DroughtFeedingUI player={uPlayers[curDrought.pi]} onConfirm={handleDroughtFeedConfirm} />
        )}

        {/* Drought: release from specific unfed palace */}
        {curDrought && curDrought.phase === "release" && (
          <div style={{ padding: 16, background: "rgba(192,57,43,0.1)", border: "1px solid #c0392b44", borderRadius: 6, marginBottom: 16 }}>
            <p style={{ color: "#e74c3c", fontWeight: 600, marginBottom: 4 }}>
              {uPlayers[curDrought.pi].name}: release 1 courtier from unfed Palace {curDrought.unfedPalaces[0] + 1}
            </p>
            <p style={{ color: "#a08060", fontSize: 12, marginBottom: 12 }}>
              {curDrought.unfedPalaces.length} unfed palace(s) remaining
            </p>
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: 12 }}>
              {uPlayers[curDrought.pi].palaces[curDrought.unfedPalaces[0]].persons.map((per, peI) => (
                <PersonTileDisplay key={peI} tile={per}
                  onClick={() => setDroughtRelSel(peI)}
                  selected={droughtRelSel === peI} small />
              ))}
            </div>
            <button onClick={handleDroughtReleaseConfirm} disabled={droughtRelSel === null}
              style={bs(true, droughtRelSel === null)}>
              Release Selected
            </button>
          </div>
        )}

        {/* Generic release (tribute, contagion, mongols) */}
        {curRel && (
          <div style={{ padding: 16, background: "rgba(192,57,43,0.1)", border: "1px solid #c0392b44", borderRadius: 6, marginBottom: 16 }}>
            <p style={{ color: "#e74c3c", fontWeight: 600, marginBottom: 8 }}>
              {uPlayers[curRel.pi].name}: release courtier ({curRel.reason}) — {curRel.count} left
            </p>
            <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
              {uPlayers[curRel.pi].palaces.map((pal, pi) =>
                pal.persons.map((per, peI) => (
                  <PersonTileDisplay key={`${pi}-${peI}`} tile={per}
                    onClick={() => setRelSel({ palaceIdx: pi, personIdx: peI })}
                    selected={relSel?.palaceIdx === pi && relSel?.personIdx === peI} small />
                ))
              )}
            </div>
            <button onClick={confirmRel} disabled={!relSel} style={{ ...bs(true, !relSel), marginTop: 12 }}>Release</button>
          </div>
        )}

        {resolved && <button onClick={() => onCompleteEvent(uPlayers)} style={bs(true)}>Continue to Scoring →</button>}
      </div>
      <PlayerAreasGrid players={uPlayers} activePlayerIdx={activePI} />
    </>
  );
}

// ─── SCORING PHASE ──────────────────────────────────────────────────

function ScoringPhase({ gameState, onCompleteScoring }) {
  const { players } = gameState;
  const [scored, setScored] = useState(false);
  const [uPlayers, setUPlayers] = useState(players);
  const [details, setDetails] = useState([]);

  const doScore = () => {
    const pls = deepClonePlayers(uPlayers); const d = [];
    pls.forEach((p, i) => {
      const palPts = p.palaces.length;
      let ladies = 0; p.palaces.forEach(pal => pal.persons.forEach(per => { if (per.typeId === "courtLady") ladies += per.symbols; }));
      const priv = p.privileges.small + p.privileges.large * 2;
      const total = palPts + ladies + priv;
      p.scoringTrack += total;
      d.push({ player: i + 1, palaces: palPts, ladies, privileges: priv, total });
    });
    setUPlayers(pls); setDetails(d); setScored(true);
  };

  return (
    <>
      <div style={S.card}>
        <h2 style={S.cardTitle}>⭐ Scoring Phase</h2>
        {!scored ? <button onClick={doScore} style={bs(true)}>Calculate Scores</button> : (
          <>
            <div style={{ marginBottom: 16 }}>
              {details.map(d => <p key={d.player} style={{ fontSize: 13, color: "#c0a070", margin: "4px 0" }}>
                P{d.player}: +{d.total} VP ({d.palaces} palaces, {d.ladies} ladies, {d.privileges} privileges)
              </p>)}
            </div>
            <button onClick={() => onCompleteScoring(uPlayers)} style={bs(true)}>
              {gameState.currentRound < 11 ? "Next Round →" : "Final Scoring →"}
            </button>
          </>
        )}
      </div>
      <PlayerAreasGrid players={uPlayers} activePlayerIdx={-1} />
    </>
  );
}

// ─── FINAL SCORING ──────────────────────────────────────────────────

function FinalScoring({ players }) {
  const results = players.map(p => {
    let personPts = 0, monkPts = 0;
    p.palaces.forEach(pal => pal.persons.forEach(per => {
      personPts += 2;
      if (per.typeId === "monk") monkPts += per.symbols * pal.floors;
    }));
    const sale = (p.rice + p.fireworks) * 2;
    const moneyPts = Math.floor((p.yuan + sale) / 3);
    return { ...p, personPts, monkPts, moneyPts, finalScore: p.scoringTrack + personPts + monkPts + moneyPts };
  });
  const sorted = [...results].sort((a, b) => b.finalScore !== a.finalScore ? b.finalScore - a.finalScore : b.personTrack - a.personTrack);

  return (
    <div style={S.content}>
      <div style={{ textAlign: "center", padding: "30px 0 20px", borderBottom: "2px solid #8B4513", marginBottom: 30 }}>
        <h1 style={S.title}>🐉 Game Over! 🐉</h1>
      </div>
      {sorted.map((p, rank) => (
        <div key={p.index} style={{
          ...S.card, border: rank === 0 ? "2px solid #d4a017" : S.card.border,
          boxShadow: rank === 0 ? "0 0 30px rgba(212,160,23,0.3)" : S.card.boxShadow,
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12 }}>
            <span style={{ fontSize: 28, fontWeight: 700, color: rank === 0 ? "#d4a017" : rank === 1 ? "#c0c0c0" : "#cd7f32" }}>
              #{rank + 1}
            </span>
            <div style={{ width: 20, height: 20, borderRadius: "50%", background: p.color.primary }} />
            <span style={{ fontSize: 20, color: p.color.light, fontWeight: 700 }}>{p.name}</span>
            <span style={{ fontSize: 24, fontWeight: 700, color: "#d4a017", marginLeft: "auto" }}>{p.finalScore} VP</span>
          </div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 8 }}>
            <ResourceBadge icon="⭐" label="Game Score" value={p.scoringTrack} />
            <ResourceBadge icon="👥" label="Persons" value={`+${p.personPts}`} />
            <ResourceBadge icon="☸️" label="Monks" value={`+${p.monkPts}`} />
            <ResourceBadge icon="💰" label="Money" value={`+${p.moneyPts}`} />
            <ResourceBadge icon="👤" label="Track" value={p.personTrack} />
          </div>
        </div>
      ))}
    </div>
  );
}

// ─── MAIN APP ───────────────────────────────────────────────────────

export default function App() {
  const [screen, setScreen] = useState("setup");
  const [gs, setGs] = useState(null);

  const start = (pc, names) => {
    const ev = generateEventTiles(), ti = generatePersonTiles(pc);
    const pl = Array.from({ length: pc }, (_, i) => createPlayer(i, PLAYER_COLORS[i], names[i]));
    setGs({ playerCount: pc, players: pl, events: ev, remainingTiles: ti, currentRound: 0, phase: "action" });
    setScreen("draft");
  };

  const draftDone = (pl, ti) => {
    setGs(p => ({ ...p, players: pl, remainingTiles: ti, personTrackOrder: getPersonTrackOrder(pl), actionGroups: dealActionGroups(pl.length), phase: "action" }));
    setScreen("game");
  };

  const actionDone = (pl) => setGs(p => ({ ...p, players: pl, personTrackOrder: getPersonTrackOrder(pl), phase: p.currentRound >= 11 ? "event" : "person" }));
  const personDone = (pl, ti) => setGs(p => ({ ...p, players: pl, remainingTiles: ti, personTrackOrder: getPersonTrackOrder(pl), phase: "event" }));
  const eventDone = (pl) => setGs(p => ({ ...p, players: pl, phase: "scoring" }));
  const scoreDone = (pl) => {
    const n = gs.currentRound + 1;
    if (n >= 12) { setGs(p => ({ ...p, players: pl })); setScreen("final"); }
    else setGs(p => ({ ...p, players: pl, currentRound: n, personTrackOrder: getPersonTrackOrder(pl), actionGroups: dealActionGroups(pl.length), phase: "action" }));
  };

  if (screen === "setup") return <div style={S.app}><div style={S.overlay} /><SetupScreen onStart={start} /></div>;
  if (screen === "draft") return <div style={S.app}><div style={S.overlay} /><DraftScreen players={gs.players} personTiles={gs.remainingTiles} events={gs.events} onCompleteDraft={draftDone} /></div>;
  if (screen === "final") return <div style={S.app}><div style={S.overlay} /><FinalScoring players={gs.players} /></div>;

  return (
    <div style={S.app}>
      <div style={S.overlay} />
      <div style={S.content}>
        {/* Title bar */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", borderBottom: "2px solid #8B4513", paddingBottom: 12, marginBottom: 12 }}>
          <h1 style={{ ...S.title, fontSize: 28 }}>🐉 Year of the Dragon</h1>
          <div style={{ color: "#d4a017", fontSize: 16, fontWeight: 700 }}>Round {gs.currentRound + 1}/12</div>
        </div>

        {/* Phase tracker */}
        <div style={{ marginBottom: 12 }}>
          <PhaseTracker currentPhase={gs.phase} />
        </div>

        {/* Event track */}
        <div style={{ ...S.card, padding: 12 }}>
          <div style={{ fontSize: 12, color: "#d4a017", marginBottom: 6 }}>Event Track</div>
          <EventTrack events={gs.events} currentRound={gs.currentRound} />
        </div>

        {/* Each phase renders its own PlayerAreasGrid with live state */}
        {gs.phase === "action" && <ActionPhase gameState={gs} onCompleteAction={actionDone} />}
        {gs.phase === "person" && <PersonPhase gameState={gs} onCompletePersonPhase={personDone} />}
        {gs.phase === "event" && <EventPhase gameState={gs} onCompleteEvent={eventDone} />}
        {gs.phase === "scoring" && <ScoringPhase gameState={gs} onCompleteScoring={scoreDone} />}
      </div>
    </div>
  );
}
