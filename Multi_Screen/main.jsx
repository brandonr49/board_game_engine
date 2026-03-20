import { createRoot } from "react-dom/client";
import React, { useState, lazy, Suspense } from "react";

// ─── Game Imports ──────────────────────────────────────
import BattleLineApp from "./BattleLine_MP.jsx";
import ArboretumApp from "./Arboretum_MP.jsx";
import LostCitiesApp from "./LostCities_MP.jsx";
import DragonApp from "./InTheYearOfTheDragon_MP.jsx";
import CaylusApp from "./Caylus_MP.jsx";
import TamskApp from "./Tamsk_MP.jsx";
import DvonnApp from "./Dvonn_MP.jsx";
import YinshApp from "./Yinsh_MP.jsx";
import ZertzApp from "./Zertz_MP.jsx";
import TzaarApp from "./Tzaar_MP.jsx";
import GipfApp from "./Gipf_MP.jsx";
import PunctApp from "./Punct_MP.jsx";
import LyngkApp from "./Lyngk_MP.jsx";

// ─── Game Registry ─────────────────────────────────────
const GAMES = [
  // GIPF Project Series
  { id: "gipf",   name: "GIPF",   players: "2",   component: GipfApp,   series: "gipf", desc: "Push pieces from the edge, capture rows of 4" },
  { id: "tamsk",   name: "TAMSK",  players: "2",   component: TamskApp,  series: "gipf", desc: "Race against hourglass timers on a hex board" },
  { id: "zertz",   name: "ZERTZ",  players: "2",   component: ZertzApp,  series: "gipf", desc: "Shrinking board with mandatory marble captures" },
  { id: "dvonn",   name: "DVONN",  players: "2",   component: DvonnApp,  series: "gipf", desc: "Stack pieces, stay connected to DVONN stones" },
  { id: "yinsh",   name: "YINSH",  players: "2",   component: YinshApp,  series: "gipf", desc: "Move rings, flip markers, form rows of 5" },
  { id: "punct",   name: "PUNCT",  players: "2",   component: PunctApp,  series: "gipf", desc: "Connect opposite sides with tri-hex pieces" },
  { id: "tzaar",   name: "TZAAR",  players: "2",   component: TzaarApp,  series: "gipf", desc: "Capture and stack — protect all three types" },
  { id: "lyngk",   name: "LYNGK",  players: "2",   component: LyngkApp,  series: "gipf", desc: "Claim colors, build stacks of 5 unique colors" },
  // Other Games
  { id: "battleline", name: "Battle Line",  players: "2",   component: BattleLineApp, series: "other", desc: "Poker-like card formations across 9 flags" },
  { id: "arboretum", name: "Arboretum",    players: "2–4", component: ArboretumApp,  series: "other", desc: "Plant trees in paths, score with careful hand management" },
  { id: "lostcities", name: "Lost Cities",  players: "2",   component: LostCitiesApp, series: "other", desc: "Expedition card game — invest wisely in 5 expeditions" },
  { id: "dragon",  name: "In the Year of the Dragon", players: "2–5", component: DragonApp, series: "other", desc: "Survive disasters in medieval China" },
  { id: "caylus",  name: "Caylus",         players: "2–5", component: CaylusApp,     series: "other", desc: "Build a castle for the king, manage workers" },
];

// ─── Styles ────────────────────────────────────────────
const font = `'Cinzel', Georgia, serif`;

const styles = {
  app: {
    fontFamily: font, minHeight: "100vh",
    background: "linear-gradient(160deg, #0d1117 0%, #161b22 30%, #0d1117 100%)",
    color: "#e8d5a3", position: "relative", overflow: "hidden",
  },
  overlay: {
    position: "fixed", inset: 0, pointerEvents: "none", zIndex: 0,
    backgroundImage: `repeating-linear-gradient(45deg, transparent, transparent 35px, rgba(201,168,76,0.02) 35px, rgba(201,168,76,0.02) 70px)`,
  },
  content: {
    position: "relative", zIndex: 1, maxWidth: 1000, margin: "0 auto", padding: "32px 20px",
  },
  header: {
    textAlign: "center", marginBottom: 40,
  },
  title: {
    fontFamily: font, fontSize: 42, fontWeight: 700, color: "#c9a84c",
    textShadow: "0 2px 12px rgba(0,0,0,0.6)", margin: 0, letterSpacing: 4,
  },
  subtitle: {
    color: "#888", fontSize: 14, marginTop: 8, letterSpacing: 1,
  },
  sectionTitle: {
    fontFamily: font, fontSize: 16, color: "#c9a84c", letterSpacing: 2,
    textTransform: "uppercase", marginBottom: 16, paddingBottom: 8,
    borderBottom: "1px solid rgba(201,168,76,0.2)",
  },
  grid: {
    display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280, 1fr))",
    gap: 16, marginBottom: 32,
  },
  card: {
    background: "linear-gradient(135deg, rgba(22,27,34,0.95) 0%, rgba(13,17,23,0.98) 100%)",
    border: "1px solid #30363d", borderRadius: 10, padding: "16px 20px",
    cursor: "pointer", transition: "all 0.25s ease",
    boxShadow: "0 2px 12px rgba(0,0,0,0.4)",
    display: "flex", flexDirection: "column", gap: 8,
  },
  cardHover: {
    borderColor: "#c9a84c", boxShadow: "0 4px 24px rgba(201,168,76,0.15)",
    transform: "translateY(-2px)",
  },
  cardName: {
    fontFamily: font, fontSize: 20, fontWeight: 700, color: "#e8d5a3",
    letterSpacing: 2,
  },
  cardDesc: {
    fontSize: 12, color: "#888", lineHeight: 1.4, flex: 1,
  },
  cardMeta: {
    display: "flex", justifyContent: "space-between", alignItems: "center",
    marginTop: 4,
  },
  cardPlayers: {
    fontSize: 11, color: "#555", padding: "2px 8px", borderRadius: 4,
    background: "rgba(255,255,255,0.04)", border: "1px solid #30363d",
  },
  playBtn: {
    fontFamily: font, fontSize: 11, padding: "4px 14px", borderRadius: 5,
    border: "1px solid #c9a84c", background: "transparent",
    color: "#c9a84c", cursor: "pointer", fontWeight: 600,
    transition: "all 0.2s",
  },
};

// ─── Game Card Component ───────────────────────────────
function GameCard({ game, onClick }) {
  const [hovered, setHovered] = useState(false);

  return (
    <div
      style={{ ...styles.card, ...(hovered ? styles.cardHover : {}) }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onClick={onClick}
    >
      <div style={styles.cardName}>{game.name}</div>
      <div style={styles.cardDesc}>{game.desc}</div>
      <div style={styles.cardMeta}>
        <span style={styles.cardPlayers}>{game.players} players</span>
        <span style={{
          ...styles.playBtn,
          ...(hovered ? { background: "rgba(201,168,76,0.15)" } : {}),
        }}>
          Play
        </span>
      </div>
    </div>
  );
}

// ─── Game Selector ─────────────────────────────────────
function GameSelector({ onSelect }) {
  const gipfGames = GAMES.filter(g => g.series === "gipf");
  const otherGames = GAMES.filter(g => g.series === "other");

  return (
    <div style={styles.app}>
      <div style={styles.overlay} />
      <div style={styles.content}>
        <div style={styles.header}>
          <h1 style={styles.title}>Board Game Engine</h1>
          <p style={styles.subtitle}>Choose a game to play</p>
        </div>

        <div style={styles.sectionTitle}>The GIPF Project</div>
        <div style={styles.grid}>
          {gipfGames.map(game => (
            <GameCard key={game.id} game={game} onClick={() => onSelect(game.id)} />
          ))}
        </div>

        <div style={styles.sectionTitle}>Classic Games</div>
        <div style={styles.grid}>
          {otherGames.map(game => (
            <GameCard key={game.id} game={game} onClick={() => onSelect(game.id)} />
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── Main App ──────────────────────────────────────────
function MainApp() {
  const [selectedGame, setSelectedGame] = useState(null);

  if (!selectedGame) {
    return <GameSelector onSelect={setSelectedGame} />;
  }

  const game = GAMES.find(g => g.id === selectedGame);
  if (!game) {
    setSelectedGame(null);
    return null;
  }

  const GameComponent = game.component;
  return <GameComponent />;
}

createRoot(document.getElementById("root")).render(<MainApp />);
