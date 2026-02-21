import { useState, useCallback, useRef, useEffect } from "react";

// ============================================================
// CONSTANTS & BUILDING DEFINITIONS
// ============================================================

const PLAYER_COLORS = {
  blue: { bg: "#2563eb", light: "#93c5fd", text: "#1e3a5f", name: "Blue" },
  red: { bg: "#dc2626", light: "#fca5a5", text: "#7f1d1d", name: "Red" },
  green: { bg: "#16a34a", light: "#86efac", text: "#14532d", name: "Green" },
  orange: { bg: "#ea580c", light: "#fdba74", text: "#7c2d12", name: "Orange" },
  black: { bg: "#374151", light: "#9ca3af", text: "#111827", name: "Black" },
};

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

const SPECIAL_BUILDINGS = [
  { id: "gate", name: "Gate", description: "Move worker to any unoccupied space for free" },
  { id: "trading_post", name: "Trading Post", description: "Take 3 deniers from stock" },
  { id: "merchants_guild", name: "Merchants' Guild", description: "Move provost 1-3 spaces" },
  { id: "joust_field", name: "Joust Field", description: "Pay 1 denier + 1 cloth → 1 royal favor" },
  { id: "stables", name: "Stables", description: "Change turn order (up to 3 workers)", slots: 3 },
  { id: "inn", name: "Inn", description: "Pay only 1 denier per worker next turn", slots: 2 },
];

const NEUTRAL_BUILDINGS = [
  { id: "n_farm", name: "Farm", type: "neutral", category: "production", description: "Gain 2 food OR 1 cloth", effect: { type: "choice", options: [{ food: 2 }, { cloth: 1 }] } },
  { id: "n_sawmill", name: "Sawmill", type: "neutral", category: "production", description: "Gain 1 wood", effect: { type: "gain", resources: { wood: 1 } } },
  { id: "n_quarry", name: "Quarry", type: "neutral", category: "production", description: "Gain 1 stone", effect: { type: "gain", resources: { stone: 1 } } },
  { id: "n_carpenter", name: "Carpenter", type: "neutral", category: "construction", description: "Build a wood (brown) building", effect: { type: "build", buildType: "wood" } },
  { id: "n_market", name: "Marketplace", type: "neutral", category: "marketplace", description: "Sell 1 cube for 4 deniers", effect: { type: "sell", price: 4 } },
  { id: "n_peddler", name: "Peddler", type: "neutral", category: "peddler", description: "Buy 1 cube (no gold) for 1 denier", effect: { type: "buy", max: 1, costPer: 1 } },
];

const BASIC_BUILDINGS = [
  { id: "b_peddler", name: "Peddler", type: "basic", category: "peddler", description: "Buy 1 cube (no gold) for 1 denier", effect: { type: "buy", max: 1, costPer: 1 } },
  { id: "b_market", name: "Marketplace", type: "basic", category: "marketplace", description: "Sell 1 cube for 4 deniers", effect: { type: "sell", price: 4 } },
  { id: "b_goldmine", name: "Gold Mine", type: "basic", category: "production", description: "Gain 1 gold", effect: { type: "gain", resources: { gold: 1 } } },
];

const WOOD_BUILDINGS = [
  { id: "w_farm", name: "Wood Farm", type: "wood", category: "production", cost: { food: 1, wood: 1 }, vp: 2, description: "Gain 2 food OR 1 cloth", effect: { type: "choice", options: [{ food: 2 }, { cloth: 1 }] } },
  { id: "w_sawmill", name: "Sawmill", type: "wood", category: "production", cost: { food: 1, wood: 1 }, vp: 2, description: "Gain 2 wood", effect: { type: "gain", resources: { wood: 2 } } },
  { id: "w_quarry", name: "Quarry", type: "wood", category: "production", cost: { food: 1, wood: 1 }, vp: 2, description: "Gain 2 stone", effect: { type: "gain", resources: { stone: 2 } } },
  { id: "w_market", name: "Market", type: "wood", category: "marketplace", cost: { wood: 2 }, vp: 2, description: "Sell 1 cube for 6 deniers", effect: { type: "sell", price: 6 } },
  { id: "w_peddler", name: "Peddler", type: "wood", category: "peddler", cost: { food: 1, wood: 1 }, vp: 2, description: "Buy 1-2 cubes (no gold) for 2 deniers each", effect: { type: "buy", max: 2, costPer: 2 } },
  { id: "w_tailor", name: "Tailor", type: "wood", category: "converter", cost: { wood: 1, cloth: 1 }, vp: 3, description: "Pay 1 cloth → 2 VP, or 3 cloth → 6 VP", effect: { type: "tailor" } },
  { id: "w_church", name: "Church", type: "wood", category: "converter", cost: { stone: 2, wood: 1 }, vp: 4, favorOnBuild: 1, description: "Pay 2$ → 3 VP, or 4$ → 5 VP", effect: { type: "church" } },
  { id: "w_lawyer", name: "Lawyer", type: "wood", category: "special", cost: { stone: 1, cloth: 1 }, vp: 3, description: "Pay 1 cloth + 1$ → transform building to residential", effect: { type: "lawyer" }, cannotBeTransformed: true },
];

const STONE_BUILDINGS = [
  { id: "s_farm", name: "Stone Farm", type: "stone", category: "production", cost: { food: 1, stone: 2 }, vp: 3, description: "Gain 2 food AND 1 cloth", effect: { type: "gain", resources: { food: 2, cloth: 1 } }, ownerBonus: ["food", "cloth"] },
  { id: "s_sawmill", name: "Stone Sawmill", type: "stone", category: "production", cost: { food: 1, stone: 2 }, vp: 3, description: "Gain 2 wood AND 1 food", effect: { type: "gain", resources: { wood: 2, food: 1 } }, ownerBonus: ["wood", "food"] },
  { id: "s_quarry", name: "Stone Quarry", type: "stone", category: "production", cost: { food: 1, stone: 2 }, vp: 3, description: "Gain 2 stone AND 1 food", effect: { type: "gain", resources: { stone: 2, food: 1 } }, ownerBonus: ["stone", "food"] },
  { id: "s_market", name: "Stone Market", type: "stone", category: "marketplace", cost: { stone: 2, wood: 1 }, vp: 3, description: "Sell 1 cube for 8 deniers", effect: { type: "sell", price: 8 } },
  { id: "s_mason", name: "Mason", type: "stone", category: "construction", cost: { wood: 1, stone: 2 }, vp: 3, description: "Build a stone (gray) building", effect: { type: "build", buildType: "stone" } },
  { id: "s_architect", name: "Architect", type: "stone", category: "construction", cost: { stone: 3 }, vp: 4, description: "Build a prestige (blue) building", effect: { type: "build", buildType: "prestige" } },
  { id: "s_bank", name: "Bank", type: "stone", category: "converter", cost: { stone: 2, wood: 1 }, vp: 3, description: "Pay 2$ → 1 gold, or 5$ → 2 gold", effect: { type: "bank" } },
  { id: "s_alchemist", name: "Alchemist", type: "stone", category: "converter", cost: { stone: 2, cloth: 1 }, vp: 3, description: "Pay 2 cubes → 1 gold, or 4 cubes → 2 gold", effect: { type: "alchemist" } },
  { id: "s_goldmine", name: "Gold Mine", type: "stone", category: "production", cost: { wood: 1, stone: 3 }, vp: 4, description: "Gain 1 gold", effect: { type: "gain", resources: { gold: 1 } } },
];

const PRESTIGE_BUILDINGS = [
  { id: "p_statue", name: "Statue", type: "prestige", cost: { gold: 1, stone: 2 }, vp: 7, favorOnBuild: 1 },
  { id: "p_theater", name: "Theater", type: "prestige", cost: { gold: 1, wood: 1, stone: 1 }, vp: 8, favorOnBuild: 1 },
  { id: "p_university", name: "University", type: "prestige", cost: { gold: 1, stone: 2, wood: 1 }, vp: 8, favorOnBuild: 1 },
  { id: "p_monument", name: "Monument", type: "prestige", cost: { gold: 2, stone: 3 }, vp: 10, favorOnBuild: 2 },
  { id: "p_granary", name: "Granary", type: "prestige", cost: { gold: 1, stone: 1, wood: 1 }, vp: 6 },
  { id: "p_weaver", name: "Weaver", type: "prestige", cost: { gold: 1, cloth: 1, stone: 1 }, vp: 6 },
  { id: "p_cathedral", name: "Cathedral", type: "prestige", cost: { gold: 2, stone: 3, wood: 1 }, vp: 12 },
  { id: "p_library", name: "Library", type: "prestige", cost: { gold: 1, stone: 1 }, vp: 5 },
  { id: "p_hotel", name: "Hotel", type: "prestige", cost: { gold: 1, stone: 1, wood: 1 }, vp: 5 },
];

const FAVOR_TRACKS = {
  prestige: {
    name: "Prestige", icon: "⭐",
    levels: [
      { label: "1VP", desc: "+1 VP", auto: true },
      { label: "2VP", desc: "+2 VP", auto: true },
      { label: "3VP", desc: "+3 VP", auto: true },
      { label: "4VP", desc: "+4 VP", auto: true },
      { label: "5VP", desc: "+5 VP", auto: true },
    ],
  },
  deniers: {
    name: "Deniers", icon: "💰",
    levels: [
      { label: "3$", desc: "+3 deniers", auto: true },
      { label: "4$", desc: "+4 deniers", auto: true },
      { label: "5$", desc: "+5 deniers", auto: true },
      { label: "6$", desc: "+6 deniers", auto: true },
      { label: "7$", desc: "+7 deniers", auto: true },
    ],
  },
  resources: {
    name: "Resources", icon: "📦",
    levels: [
      { label: "1🌾", desc: "+1 food", auto: true },
      { label: "🪵/🪨", desc: "+1 wood or stone", auto: false },
      { label: "1🧵", desc: "+1 cloth", auto: true },
      { label: "swap", desc: "Trade 1 cube → 2 cubes (no gold)", auto: false },
      { label: "1✦", desc: "+1 gold", auto: true },
    ],
  },
  buildings: {
    name: "Buildings", icon: "🏗️",
    levels: [
      { label: "—", desc: "No effect", auto: true },
      { label: "Carp-1", desc: "Build wood building (-1 resource)", auto: false },
      { label: "Mason-1", desc: "Build stone building (-1 resource)", auto: false },
      { label: "Lawyer", desc: "Free lawyer: transform a building", auto: false },
      { label: "Archi-1", desc: "Build prestige building (-1 resource)", auto: false },
    ],
  },
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

// ============================================================
// HELPERS
// ============================================================

function shuffle(arr) {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

function deepClone(obj) { return JSON.parse(JSON.stringify(obj)); }
function pName(color) { return PLAYER_COLORS[color]?.name || color; }

// ============================================================
// GAME LOGIC
// ============================================================

function getWorkerCost(game) {
  for (let i = 0; i < game.passingScale.length; i++) {
    if (game.passingScale[i] === null) return i + 1;
  }
  return game.passingScale.length;
}

function getNextActivePlayer(game, afterIndex) {
  const n = game.players.length;
  for (let i = 1; i <= n; i++) {
    const idx = (afterIndex + i) % n;
    if (!game.players[idx].passed) return idx;
  }
  return -1;
}

function allPlayersPassed(game) { return game.players.every(p => p.passed); }

function countResidentialBuildings(game, color) {
  return game.road.filter(s => s.building?.type === "residential" && s.house === color).length;
}

function hasBuilding(game, color, id) {
  return game.road.some(s => s.building?.id === id && s.house === color);
}

function addLog(g, msg) { g.log = [msg, ...g.log.slice(0, 149)]; }

function returnWorker(g, color) {
  const p = g.players.find(pl => pl.color === color);
  if (p) p.workers.placed = Math.max(0, p.workers.placed - 1);
}

// ============================================================
// FAVOR SYSTEM
// ============================================================

function grantFavors(g, favorList, returnAction) {
  // favorList: [{ color, count }] — e.g. [{ color:"blue", count:2 }]
  // Build queue entries with separate tracking per player
  const queue = favorList.filter(f => f.count > 0).map(f => ({
    color: f.color, remaining: f.count, tracksUsed: [],
  }));
  if (queue.length === 0) return dispatchFavorReturn(g, returnAction);
  g.pendingFavors = { queue, queueIndex: 0, subChoice: null, returnAction };
  return g; // UI will render favor picker
}

function dispatchFavorReturn(g, action) {
  g.pendingFavors = null;
  if (action === "continueSpecial") return continueSpecialAfterJoust(g);
  if (action === "advanceActivation") return advanceActivation(g);
  if (action === "afterCastle") return afterCastleFavors(g);
  if (action === "afterCount") return afterCountFavors(g);
  return g;
}

function getAvailableFavorTracks(game, playerColor, tracksUsed) {
  const p = game.players.find(x => x.color === playerColor);
  if (!p) return [];
  const maxCol = game.favorColumnsAvailable;
  const tracks = [];
  for (const [key, track] of Object.entries(FAVOR_TRACKS)) {
    const currentLevel = p.favors[key] || 0;
    if (tracksUsed.includes(key)) continue; // already used this round
    const maxed = currentLevel >= 5;
    const nextLevel = maxed ? 5 : currentLevel + 1;
    if (!maxed && nextLevel > maxCol) continue; // column not unlocked yet
    tracks.push({
      key,
      name: track.name,
      icon: track.icon,
      nextLevel,
      reward: track.levels[nextLevel - 1],
      currentLevel,
      maxed,
    });
  }
  return tracks;
}

function resolveFavorChoice(game, trackKey) {
  const g = deepClone(game);
  const pf = g.pendingFavors;
  if (!pf) return g;
  const entry = pf.queue[pf.queueIndex];
  const p = g.players.find(x => x.color === entry.color);
  if (!p) return advanceFavorQueue(g);

  const currentLevel = p.favors[trackKey] || 0;
  const maxed = currentLevel >= 5;
  const nextLevel = maxed ? 5 : currentLevel + 1;
  if (!maxed) p.favors[trackKey] = nextLevel;
  entry.tracksUsed.push(trackKey);

  const track = FAVOR_TRACKS[trackKey];

  if (maxed) {
    addLog(g, `${pName(entry.color)} uses ${track.name} favor (maxed at col 5)`);
  } else {
    addLog(g, `${pName(entry.color)} takes ${track.name} favor → col ${nextLevel}`);
  }

  // For prestige and deniers, player can choose which level effect to use (1 through current)
  if (trackKey === "prestige") {
    if (nextLevel === 1) {
      p.score += 1;
      addLog(g, `  +1 VP`);
    } else {
      // Let player choose level 1 through nextLevel
      const options = [];
      for (let lvl = 1; lvl <= nextLevel; lvl++) {
        options.push({ id: `prestlvl_${lvl}`, label: `+${lvl} VP`, desc: `Level ${lvl}` });
      }
      pf.subChoice = { type: "prestige_level_pick", options };
      return g;
    }
  } else if (trackKey === "deniers") {
    if (nextLevel === 1) {
      p.deniers += 3;
      addLog(g, `  +3$`);
    } else {
      const options = [];
      for (let lvl = 1; lvl <= nextLevel; lvl++) {
        options.push({ id: `denlvl_${lvl}`, label: `+${lvl + 2}$`, desc: `Level ${lvl}` });
      }
      pf.subChoice = { type: "deniers_level_pick", options };
      return g;
    }
  } else if (trackKey === "resources") {
    // Player can choose any level from 1 to nextLevel
    if (nextLevel === 1) {
      p.resources.food += 1;
      addLog(g, `  +1 food`);
    } else {
      const resOptions = [];
      resOptions.push({ id: "reslvl_1", label: `+1 ${RESOURCE_ICONS.food.symbol}`, desc: "Level 1: +1 food" });
      if (nextLevel >= 2) resOptions.push({ id: "reslvl_2", label: `${RESOURCE_ICONS.wood.symbol}/${RESOURCE_ICONS.stone.symbol}`, desc: "Level 2: +1 wood or stone" });
      if (nextLevel >= 3) resOptions.push({ id: "reslvl_3", label: `+1 ${RESOURCE_ICONS.cloth.symbol}`, desc: "Level 3: +1 cloth" });
      if (nextLevel >= 4) resOptions.push({ id: "reslvl_4", label: "Swap 1→2", desc: "Level 4: Trade 1 cube for 2" });
      if (nextLevel >= 5) resOptions.push({ id: "reslvl_5", label: `+1 ${RESOURCE_ICONS.gold.symbol}`, desc: "Level 5: +1 gold" });
      pf.subChoice = { type: "res_level_pick", options: resOptions };
      return g;
    }
  } else if (trackKey === "buildings") {
    if (nextLevel === 1) {
      // No effect
    } else {
      const bldOptions = [];
      if (nextLevel >= 2) {
        const wStock = g.buildingStock.wood || [];
        const hasEmptySlot = g.road.some(x => x.building === null);
        bldOptions.push({ id: "bldlvl_2", label: "Carpenter -1", desc: `Build wood building (${wStock.length} avail)`,
          disabled: wStock.length === 0 || !hasEmptySlot });
      }
      if (nextLevel >= 3) {
        const sStock = g.buildingStock.stone || [];
        const hasEmptySlot = g.road.some(x => x.building === null);
        bldOptions.push({ id: "bldlvl_3", label: "Mason -1", desc: `Build stone building (${sStock.length} avail)`,
          disabled: sStock.length === 0 || !hasEmptySlot });
      }
      if (nextLevel >= 4) {
        const hasTarget = g.road.some((rs) => {
          if (!rs.building || rs.building.cannotBeTransformed) return false;
          const bt = rs.building.type;
          if (bt === "prestige" || bt === "residential" || bt === "basic") return false;
          return bt === "neutral" || (rs.house === entry.color && (bt === "wood" || bt === "stone"));
        });
        bldOptions.push({ id: "bldlvl_4", label: "Lawyer", desc: "Transform building (1 cloth)", disabled: !hasTarget || p.resources.cloth < 1 });
      }
      if (nextLevel >= 5) {
        const pStock = g.buildingStock.prestige || [];
        const hasResidential = g.road.some(x => x.building?.type === "residential" && x.house === entry.color);
        bldOptions.push({ id: "bldlvl_5", label: "Architect -1", desc: `Build prestige building (${pStock.length} avail)`,
          disabled: pStock.length === 0 || !hasResidential });
      }
      bldOptions.push({ id: "bldlvl_skip", label: "Skip", desc: "Don't use building effect" });

      if (bldOptions.length > 1) {
        pf.subChoice = { type: "bld_level_pick", options: bldOptions };
        return g;
      }
      addLog(g, `  No building effects available`);
    }
  }

  entry.remaining--;
  return advanceFavorQueue(g);
}

function resolveFavorSubChoice(game, choiceId) {
  const g = deepClone(game);
  const pf = g.pendingFavors;
  if (!pf || !pf.subChoice) return g;
  const entry = pf.queue[pf.queueIndex];
  const p = g.players.find(x => x.color === entry.color);

  if (pf.subChoice.type === "prestige_level_pick") {
    const lvl = parseInt(choiceId.replace("prestlvl_", ""));
    p.score += lvl;
    addLog(g, `  ${pName(entry.color)} takes +${lvl} VP`);
    pf.subChoice = null;
    entry.remaining--;
    return advanceFavorQueue(g);
  }

  if (pf.subChoice.type === "deniers_level_pick") {
    const lvl = parseInt(choiceId.replace("denlvl_", ""));
    const amount = lvl + 2;
    p.deniers += amount;
    addLog(g, `  ${pName(entry.color)} takes +${amount}$`);
    pf.subChoice = null;
    entry.remaining--;
    return advanceFavorQueue(g);
  }

  if (pf.subChoice.type === "res_level_pick") {
    const lvl = parseInt(choiceId.replace("reslvl_", ""));
    if (lvl === 1) { p.resources.food += 1; addLog(g, `  ${pName(entry.color)} takes +1 food (lvl 1)`); }
    else if (lvl === 2) {
      pf.subChoice = { type: "res2", options: [
        { id: "wood", label: `+1 ${RESOURCE_ICONS.wood.symbol}`, desc: "1 wood" },
        { id: "stone", label: `+1 ${RESOURCE_ICONS.stone.symbol}`, desc: "1 stone" },
      ]};
      return g;
    }
    else if (lvl === 3) { p.resources.cloth += 1; addLog(g, `  ${pName(entry.color)} takes +1 cloth (lvl 3)`); }
    else if (lvl === 4) {
      const giveOptions = ["food","wood","stone","cloth","gold"].filter(r => p.resources[r] > 0).map(r => ({
        id: r, label: `-1 ${RESOURCE_ICONS[r]?.symbol}`, desc: `Give 1 ${r}`,
      }));
      if (giveOptions.length > 0) {
        pf.subChoice = { type: "res4_give", options: giveOptions };
        return g;
      }
      addLog(g, `  ${pName(entry.color)} has no cubes to trade`);
    }
    else if (lvl === 5) { p.resources.gold += 1; addLog(g, `  ${pName(entry.color)} takes +1 gold (lvl 5)`); }
    pf.subChoice = null;
    entry.remaining--;
    return advanceFavorQueue(g);
  }

  if (pf.subChoice.type === "res2") {
    p.resources[choiceId] += 1;
    addLog(g, `  ${pName(entry.color)} picks +1 ${choiceId}`);
    pf.subChoice = null;
    entry.remaining--;
    return advanceFavorQueue(g);
  }

  if (pf.subChoice.type === "res4_give") {
    p.resources[choiceId] -= 1;
    addLog(g, `  ${pName(entry.color)} gives 1 ${choiceId}`);
    // Now pick 2 cubes to receive (no gold)
    pf.subChoice = { type: "res4_take", picks: 0, maxPicks: 2, options: [
      { id: "food", label: `${RESOURCE_ICONS.food.symbol}`, desc: "food" },
      { id: "wood", label: `${RESOURCE_ICONS.wood.symbol}`, desc: "wood" },
      { id: "stone", label: `${RESOURCE_ICONS.stone.symbol}`, desc: "stone" },
      { id: "cloth", label: `${RESOURCE_ICONS.cloth.symbol}`, desc: "cloth" },
    ]};
    return g;
  }

  if (pf.subChoice.type === "res4_take") {
    p.resources[choiceId] += 1;
    pf.subChoice.picks++;
    addLog(g, `  ${pName(entry.color)} takes +1 ${choiceId} (${pf.subChoice.picks}/2)`);
    if (pf.subChoice.picks >= pf.subChoice.maxPicks) {
      pf.subChoice = null;
      entry.remaining--;
      return advanceFavorQueue(g);
    }
    return g; // need another pick
  }

  if (pf.subChoice.type === "bld_level_pick") {
    if (choiceId === "bldlvl_skip") {
      addLog(g, `  ${pName(entry.color)} skips building effect`);
      pf.subChoice = null;
      entry.remaining--;
      return advanceFavorQueue(g);
    }
    const lvl = parseInt(choiceId.replace("bldlvl_", ""));
    if (lvl === 2 || lvl === 3 || lvl === 5) {
      const buildType = lvl === 2 ? "wood" : lvl === 3 ? "stone" : "prestige";
      const stock = g.buildingStock[buildType] || [];
      const isPrestige = lvl === 5;
      const validTarget = isPrestige
        ? g.road.some(x => x.building?.type === "residential" && x.house === entry.color)
        : g.road.some(x => x.building === null);
      if (stock.length > 0 && validTarget) {
        const options = stock.map(b => {
          const costEntries = Object.entries(b.cost || {});
          const canAffordWithDiscount = costEntries.length > 0 && costEntries.some(([r, a]) => {
            const needed = { ...b.cost, [r]: a - 1 };
            return Object.entries(needed).every(([rr, aa]) => aa <= 0 || p.resources[rr] >= aa);
          });
          return {
            id: `fbuild_${b.id}`, label: b.name,
            desc: `${Object.entries(b.cost||{}).map(([r,a])=>`${a}${RESOURCE_ICONS[r]?.symbol||r}`).join("+")} (-1) → +${b.vp}VP`,
            disabled: !canAffordWithDiscount, buildingId: b.id,
          };
        });
        pf.subChoice = { type: "build_favor", buildType, options, discount: 1, isPrestige };
        return g;
      }
      addLog(g, `  No ${buildType} buildings available or no valid target`);
    } else if (lvl === 4) {
      // Lawyer: pay 1 cloth, transform a building
      const options = [];
      g.road.forEach((rs, ri) => {
        if (!rs.building || rs.building.cannotBeTransformed) return;
        const bt = rs.building.type;
        if (bt === "prestige" || bt === "residential" || bt === "basic") return;
        if (bt === "neutral" || (rs.house === entry.color && (bt === "wood" || bt === "stone"))) {
          options.push({
            id: `flawyer_${ri}`, label: `${rs.building.name} (pos ${ri+1})`,
            desc: bt === "neutral" ? "Transform neutral" : "Transform your building",
            targetIndex: ri,
          });
        }
      });
      if (options.length > 0) {
        pf.subChoice = { type: "lawyer_favor", options };
        return g;
      }
      addLog(g, `  No buildings to transform`);
    }
    pf.subChoice = null;
    entry.remaining--;
    return advanceFavorQueue(g);
  }

  if (pf.subChoice.type === "build_favor") {
    if (choiceId === "skip") {
      addLog(g, `  ${pName(entry.color)} skips building favor`);
    } else if (pf.subChoice.isPrestige && !pf.subChoice.chosenBuildingId) {
      // Prestige: first pick building, then pick residential target
      const bId = choiceId.replace("fbuild_", "");
      pf.subChoice = { ...pf.subChoice, chosenBuildingId: bId };
      // Show residential targets
      const targets = [];
      g.road.forEach((rs, ri) => {
        if (rs.building?.type === "residential" && rs.house === entry.color) {
          targets.push({ id: `fptarget_${ri}`, label: `Residential (pos ${ri+1})`, targetIndex: ri });
        }
      });
      pf.subChoice = { type: "build_favor_prestige_target", buildType: pf.subChoice.buildType, chosenBuildingId: bId, options: targets, discount: 1 };
      return g;
    } else {
      const bId = choiceId.replace("fbuild_", "");
      const stock = g.buildingStock[pf.subChoice.buildType];
      const bIdx = stock.findIndex(b => b.id === bId);
      if (bIdx >= 0) {
        const b = stock[bIdx];
        // Find cheapest discount: remove 1 of the resource with highest count in cost
        const costCopy = { ...b.cost };
        for (const [r, a] of Object.entries(costCopy).sort(([,a1],[,a2]) => a2 - a1)) {
          if (a > 0) { costCopy[r] = a - 1; break; }
        }
        const canAfford = Object.entries(costCopy).every(([r, a]) => a <= 0 || p.resources[r] >= a);
        if (canAfford) {
          Object.entries(costCopy).forEach(([r, a]) => { if (a > 0) p.resources[r] -= a; });
          const emptySlot = g.road.find(x => x.building === null);
          if (emptySlot) {
            emptySlot.building = { ...stock.splice(bIdx, 1)[0] };
            emptySlot.house = p.color;
            p.score += (b.vp || 0);
            p.houses.placed++;
            addLog(g, `  ${pName(entry.color)} builds ${b.name} (favor discount) → +${b.vp}VP`);
            if (b.favorOnBuild) {
              // Queue additional favors — they'll be processed after current favor queue
              addLog(g, `  ${b.name} grants ${b.favorOnBuild} favor${b.favorOnBuild>1?"s":""}`);
              entry.remaining += b.favorOnBuild;
            }
          }
        }
      }
    }
    pf.subChoice = null;
    entry.remaining--;
    return advanceFavorQueue(g);
  }

  if (pf.subChoice.type === "build_favor_prestige_target") {
    if (choiceId === "skip") {
      addLog(g, `  ${pName(entry.color)} skips prestige building placement`);
    } else {
      const opt = pf.subChoice.options.find(o => o.id === choiceId);
      if (opt) {
        const stock = g.buildingStock.prestige;
        const bIdx = stock.findIndex(b => b.id === pf.subChoice.chosenBuildingId);
        if (bIdx >= 0) {
          const b = stock[bIdx];
          const costCopy = { ...b.cost };
          for (const [r, a] of Object.entries(costCopy).sort(([,a1],[,a2]) => a2 - a1)) {
            if (a > 0) { costCopy[r] = a - 1; break; }
          }
          const canAfford = Object.entries(costCopy).every(([r, a]) => a <= 0 || p.resources[r] >= a);
          if (canAfford) {
            Object.entries(costCopy).forEach(([r, a]) => { if (a > 0) p.resources[r] -= a; });
            const target = g.road[opt.targetIndex];
            target.building = { ...stock.splice(bIdx, 1)[0] };
            p.score += (b.vp || 0);
            addLog(g, `  ${pName(entry.color)} builds ${b.name} (favor discount) → +${b.vp}VP`);
            if (b.favorOnBuild) {
              addLog(g, `  ${b.name} grants ${b.favorOnBuild} favor${b.favorOnBuild>1?"s":""}`);
              entry.remaining += b.favorOnBuild;
            }
          }
        }
      }
    }
    pf.subChoice = null;
    entry.remaining--;
    return advanceFavorQueue(g);
  }

  if (pf.subChoice.type === "lawyer_favor") {
    if (choiceId === "skip") {
      addLog(g, `  ${pName(entry.color)} skips lawyer favor`);
    } else {
      const opt = pf.subChoice.options.find(o => o.id === choiceId);
      if (opt && p.resources.cloth >= 1) {
        p.resources.cloth -= 1; // Favor lawyer costs 1 cloth (no denier)
        const target = g.road[opt.targetIndex];
        const oldBuilding = target.building;
        const oldName = oldBuilding.name;
        const wasNeutral = oldBuilding.type === "neutral";
        // Return craft buildings to stock
        if (!wasNeutral && (oldBuilding.type === "wood" || oldBuilding.type === "stone")) {
          const stockType = oldBuilding.type;
          if (g.buildingStock[stockType]) {
            g.buildingStock[stockType].push({ ...oldBuilding });
          }
        }
        target.building = { id: `res_${opt.targetIndex}`, name: "Residential", type: "residential", category: "residential", description: "+1 denier income" };
        if (wasNeutral) target.house = p.color;
        p.score += 2;
        addLog(g, `  ${pName(entry.color)} transforms ${oldName} → Residential (+2VP, -1 cloth) (favor lawyer)`);
      }
    }
    pf.subChoice = null;
    entry.remaining--;
    return advanceFavorQueue(g);
  }

  return g;
}

function advanceFavorQueue(g) {
  const pf = g.pendingFavors;
  if (!pf) return g;
  const entry = pf.queue[pf.queueIndex];
  if (entry.remaining > 0) {
    // Still have favors for this player — check if tracks available
    const avail = getAvailableFavorTracks(g, entry.color, entry.tracksUsed);
    if (avail.length === 0) {
      addLog(g, `${pName(entry.color)} has no more available favor tracks`);
      entry.remaining = 0;
    } else {
      return g; // UI will show picker
    }
  }
  // Move to next in queue
  pf.queueIndex++;
  if (pf.queueIndex < pf.queue.length) {
    return g; // next player's favors
  }
  // All done
  return dispatchFavorReturn(g, pf.returnAction);
}

// --- Phase 1: Income ---
function processIncome(game) {
  const g = deepClone(game);
  g.players.forEach(p => {
    let income = 2;
    income += countResidentialBuildings(g, p.color);
    if (hasBuilding(g, p.color, "p_library")) income += 1;
    if (hasBuilding(g, p.color, "p_hotel")) income += 2;
    p.deniers += income;
    addLog(g, `${pName(p.color)} collects ${income}$`);
  });
  g.currentPhase = 1;
  g.currentPlayerIndex = 0;
  addLog(g, "— Phase 2: Place Workers —");
  return g;
}

// --- Phase 2: Worker Placement ---
function canPlaceOnRoadSlot(game, idx, color) {
  const s = game.road[idx];
  if (!s.building) return false;
  if (s.building.type === "prestige" || s.building.type === "residential") return false;
  if (s.worker !== null) return false;
  return true;
}

function canPlaceOnSpecial(game, id, color) {
  const ss = game.specialState;
  if (id === "stables") return !ss.stables.some(s => s === color) && ss.stables.some(s => s === null);
  if (id === "inn") return ss.inn.left === null;
  return ss[id]?.worker === null;
}

function canPlaceInCastle(game, color) { return !game.castle.workers.includes(color); }

function processPass(game) {
  const g = deepClone(game);
  const p = g.players[g.currentPlayerIndex];
  const slot = g.passingScale.findIndex(s => s === null);
  g.passingScale[slot] = p.color;
  p.passed = true;
  p.passOrder = slot;
  if (slot === 0) { p.deniers += 1; addLog(g, `${pName(p.color)} passes (first — gains 1$)`); }
  else addLog(g, `${pName(p.color)} passes`);
  if (allPlayersPassed(g)) return advanceToPhase3(g);
  g.currentPlayerIndex = getNextActivePlayer(g, g.currentPlayerIndex);
  return g;
}

function placeWorkerOnRoad(game, slotIndex) {
  const g = deepClone(game);
  const p = g.players[g.currentPlayerIndex];
  const s = g.road[slotIndex];
  const isOwn = s.house === p.color;
  const cost = isOwn ? 1 : (p.innOccupant ? 1 : getWorkerCost(g));
  if (p.deniers < cost || p.workers.total - p.workers.placed <= 0) return null;
  p.deniers -= cost;
  p.workers.placed += 1;
  s.worker = p.color;
  if (s.house && s.house !== p.color) {
    const owner = g.players.find(x => x.color === s.house);
    if (owner) { owner.score += 1; addLog(g, `${pName(p.color)} → ${s.building.name} (${pName(s.house)}'s, +1VP) for ${cost}$`); }
  } else if (isOwn) { addLog(g, `${pName(p.color)} → own ${s.building.name} for ${cost}$`); }
  else { addLog(g, `${pName(p.color)} → ${s.building.name} for ${cost}$`); }
  if (allPlayersPassed(g)) return advanceToPhase3(g);
  g.currentPlayerIndex = getNextActivePlayer(g, g.currentPlayerIndex);
  return g;
}

function placeWorkerOnSpecial(game, specialId) {
  const g = deepClone(game);
  const p = g.players[g.currentPlayerIndex];
  const cost = p.innOccupant ? 1 : getWorkerCost(g);
  if (p.deniers < cost || p.workers.total - p.workers.placed <= 0) return null;
  p.deniers -= cost;
  p.workers.placed += 1;
  if (specialId === "stables") { const i = g.specialState.stables.findIndex(s => s === null); g.specialState.stables[i] = p.color; }
  else if (specialId === "inn") { g.specialState.inn.left = p.color; }
  else { g.specialState[specialId].worker = p.color; }
  addLog(g, `${pName(p.color)} → ${SPECIAL_BUILDINGS.find(b=>b.id===specialId).name} for ${cost}$`);
  if (allPlayersPassed(g)) return advanceToPhase3(g);
  g.currentPlayerIndex = getNextActivePlayer(g, g.currentPlayerIndex);
  return g;
}

function placeWorkerInCastle(game) {
  const g = deepClone(game);
  const p = g.players[g.currentPlayerIndex];
  const cost = p.innOccupant ? 1 : getWorkerCost(g);
  if (p.deniers < cost || p.workers.total - p.workers.placed <= 0) return null;
  p.deniers -= cost;
  p.workers.placed += 1;
  g.castle.workers.push(p.color);
  addLog(g, `${pName(p.color)} → Castle for ${cost}$`);
  if (allPlayersPassed(g)) return advanceToPhase3(g);
  g.currentPlayerIndex = getNextActivePlayer(g, g.currentPlayerIndex);
  return g;
}

// --- Phase 3: Special Buildings ---
function advanceToPhase3(g) {
  g.currentPhase = 2;
  addLog(g, "— Phase 3: Special Buildings —");
  return processSpecialBuildings(g);
}

function processSpecialBuildings(game) {
  const g = game; // already cloned
  const ss = g.specialState;

  if (ss.gate.worker) {
    const gateColor = ss.gate.worker;
    // Find valid targets: road buildings, special buildings, castle, inn, stables
    const roadTargets = g.road
      .map((s, i) => ({ slot: s, index: i }))
      .filter(({ slot }) => slot.building && !slot.worker && slot.building.type !== "residential" && slot.building.type !== "prestige");
    // Special building targets
    const specialTargets = [];
    if (ss.trading_post.worker === null) specialTargets.push("trading_post");
    if (ss.merchants_guild.worker === null) specialTargets.push("merchants_guild");
    if (ss.joust_field.worker === null) specialTargets.push("joust_field");
    if (ss.stables.some(s => s === null) && !ss.stables.some(s => s === gateColor)) specialTargets.push("stables");
    if (ss.inn.left === null) specialTargets.push("inn");
    const canCastle = !g.castle.workers.includes(gateColor);

    if (roadTargets.length > 0 || specialTargets.length > 0 || canCastle) {
      addLog(g, `${pName(gateColor)} may redirect Gate worker to any unoccupied building`);
      ss.gate.worker = null;
      g.pendingGate = { playerColor: gateColor, specialTargets, canCastle };
      return g; // pause for UI
    } else {
      addLog(g, `${pName(gateColor)}'s Gate — no unoccupied buildings available`);
      returnWorker(g, gateColor); ss.gate.worker = null;
    }
  }
  return continueAfterGate(g);
}

function resolveGate(game, target) {
  const g = deepClone(game);
  const pg = g.pendingGate;
  if (!pg) return g;

  if (target === "skip") {
    addLog(g, `${pName(pg.playerColor)} skips Gate — worker returns`);
    returnWorker(g, pg.playerColor);
  } else if (target === "castle") {
    g.castle.workers.push(pg.playerColor);
    addLog(g, `${pName(pg.playerColor)} Gate → Castle (free)`);
  } else if (typeof target === "string" && target.startsWith("special_")) {
    const specId = target.replace("special_", "");
    if (specId === "stables") {
      const i = g.specialState.stables.findIndex(s => s === null);
      g.specialState.stables[i] = pg.playerColor;
    } else if (specId === "inn") {
      g.specialState.inn.left = pg.playerColor;
    } else {
      g.specialState[specId].worker = pg.playerColor;
    }
    addLog(g, `${pName(pg.playerColor)} Gate → ${SPECIAL_BUILDINGS.find(b=>b.id===specId)?.name || specId} (free)`);
  } else {
    // Road index
    const roadIndex = target;
    const slot = g.road[roadIndex];
    // If placing on another player's building, they get +1 VP
    if (slot.house && slot.house !== pg.playerColor) {
      const owner = g.players.find(x => x.color === slot.house);
      if (owner) { owner.score += 1; addLog(g, `${pName(pg.playerColor)} Gate → ${slot.building.name} (${pName(slot.house)}'s, +1VP) (free)`); }
    } else {
      addLog(g, `${pName(pg.playerColor)} Gate → ${slot.building.name} (pos ${roadIndex + 1}) (free)`);
    }
    slot.worker = pg.playerColor;
  }

  g.pendingGate = null;
  return continueAfterGate(g);
}

function continueAfterGate(g) {
  const ss = g.specialState;

  if (ss.trading_post.worker) {
    const p = g.players.find(x => x.color === ss.trading_post.worker);
    p.deniers += 3;
    addLog(g, `${pName(ss.trading_post.worker)} gains 3$ (Trading Post)`);
    returnWorker(g, ss.trading_post.worker); ss.trading_post.worker = null;
  }
  // Merchants' Guild — interactive provost move
  if (ss.merchants_guild.worker) {
    const guildColor = ss.merchants_guild.worker;
    addLog(g, `${pName(guildColor)} may move provost via Merchants' Guild`);
    returnWorker(g, guildColor); ss.merchants_guild.worker = null;
    // Calculate provost bounds: can't go before bridge (index 0), can't go past last road space
    const minPos = 0;
    const maxPos = g.road.length - 1;
    g.pendingProvost = {
      playerColor: guildColor, type: "guild",
      minPos, maxPos, maxDelta: 3,
    };
    return g; // pause — UI will show provost controls, then call continueAfterGuild
  }
  return continueSpecialBuildings(g);
}

function continueAfterGuild(game) {
  const g = deepClone(game);
  g.pendingProvost = null;
  return continueSpecialBuildings(g);
}

function continueSpecialBuildings(g) {
  const ss = g.specialState;

  if (ss.joust_field.worker) {
    const jp = g.players.find(x => x.color === ss.joust_field.worker);
    if (jp.deniers >= 1 && jp.resources.cloth >= 1) {
      jp.deniers -= 1; jp.resources.cloth -= 1;
      addLog(g, `${pName(ss.joust_field.worker)} pays 1$+1cloth at Joust Field → 1 favor`);
      returnWorker(g, ss.joust_field.worker);
      const jColor = ss.joust_field.worker;
      ss.joust_field.worker = null;
      return grantFavors(g, [{ color: jColor, count: 1 }], "continueSpecial");
    } else { addLog(g, `${pName(ss.joust_field.worker)} can't pay for Joust Field`); }
    returnWorker(g, ss.joust_field.worker); ss.joust_field.worker = null;
  }
  return continueSpecialAfterJoust(g);
}

function continueSpecialAfterJoust(g) {
  const ss = g.specialState;
  if (ss.stables.some(s => s !== null)) {
    let rank = 0;
    const orderMap = {};
    ss.stables.forEach(color => { if (color) { orderMap[color] = rank++; returnWorker(g, color); } });
    g.players.filter(p => !(p.color in orderMap)).sort((a,b)=>a.turnOrder-b.turnOrder).forEach(p => { orderMap[p.color] = rank++; });
    g.players.forEach(p => { p.turnOrder = orderMap[p.color]; });
    g.players.sort((a,b)=>a.turnOrder-b.turnOrder);
    addLog(g, `Stables: new turn order — ${g.players.map(p=>pName(p.color)).join(", ")}`);
    ss.stables = [null, null, null];
  }
  if (ss.inn.left !== null) {
    if (ss.inn.right !== null) {
      const old = g.players.find(p => p.color === ss.inn.right);
      if (old) old.innOccupant = false;
      returnWorker(g, ss.inn.right);
      addLog(g, `${pName(ss.inn.right)} driven out of Inn`);
    }
    ss.inn.right = ss.inn.left; ss.inn.left = null;
    const np = g.players.find(p => p.color === ss.inn.right);
    if (np) np.innOccupant = true;
    addLog(g, `${pName(ss.inn.right)} enters Inn (1$ workers)`);
  } else if (ss.inn.right !== null) {
    // Nobody played inn this turn — right occupant may choose to stay or leave
    g.pendingInn = { playerColor: ss.inn.right };
    return g; // pause for UI
  }

  // Transition to Phase 4: Provost Movement
  return startProvostPhase(g);
}

function resolveInn(game, stay) {
  const g = deepClone(game);
  const pi = g.pendingInn;
  if (!pi) return g;
  if (stay) {
    addLog(g, `${pName(pi.playerColor)} stays in Inn (1$ workers)`);
  } else {
    const p = g.players.find(x => x.color === pi.playerColor);
    if (p) p.innOccupant = false;
    returnWorker(g, pi.playerColor);
    g.specialState.inn.right = null;
    addLog(g, `${pName(pi.playerColor)} leaves Inn`);
  }
  g.pendingInn = null;
  return startProvostPhase(g);
}

// --- Phase 4: Provost Movement ---

function startProvostPhase(g) {
  g.currentPhase = 3;
  addLog(g, "— Phase 4: Move Provost —");

  // Build order from passing scale (first who passed speaks first)
  const order = g.passingScale.filter(c => c !== null);
  // Add anyone who didn't pass (shouldn't happen, but safety)
  g.players.forEach(p => { if (!order.includes(p.color)) order.push(p.color); });

  g.provostPhase = { order, index: 0 };
  return advanceProvostPhase(g);
}

function advanceProvostPhase(g) {
  const pp = g.provostPhase;
  if (!pp || pp.index >= pp.order.length) {
    // All players have spoken — proceed to Phase 5
    return finishProvostPhase(g);
  }

  const color = pp.order[pp.index];
  const player = g.players.find(p => p.color === color);
  // Calculate how far they can move (1-3 spaces, 1 denier each)
  const maxAfford = player ? player.deniers : 0;
  const maxDelta = Math.min(3, maxAfford);

  if (maxDelta === 0) {
    // Player can't afford to move provost, auto-pass
    addLog(g, `${pName(color)} has no deniers — passes on provost`);
    pp.index++;
    return advanceProvostPhase(g);
  }

  // Show UI for this player
  g.pendingProvost = {
    playerColor: color, type: "phase4",
    maxDelta,
    minPos: 0,
    maxPos: g.road.length - 1,
  };
  return g;
}

function resolveProvostMove(game, delta) {
  const g = deepClone(game);
  const pp = g.pendingProvost;
  if (!pp) return g;

  const player = g.players.find(p => p.color === pp.playerColor);
  const absDelta = Math.abs(delta);

  if (delta === 0) {
    addLog(g, `${pName(pp.playerColor)} passes on provost`);
  } else {
    // Validate position
    const newPos = g.provostPosition + delta;
    const clampedPos = Math.max(pp.minPos, Math.min(pp.maxPos, newPos));
    const actualDelta = clampedPos - g.provostPosition;
    const isFree = pp.type === "guild"; // guild move is free
    const cost = isFree ? 0 : Math.abs(actualDelta);

    if (Math.abs(actualDelta) > 0 && player && (isFree || player.deniers >= cost)) {
      if (cost > 0) player.deniers -= cost;
      g.provostPosition = clampedPos;
      const dir = actualDelta > 0 ? "forward" : "backward";
      const costStr = isFree ? "(free, Guild)" : `(-${cost}$)`;
      addLog(g, `${pName(pp.playerColor)} moves provost ${Math.abs(actualDelta)} ${dir} to pos ${clampedPos + 1} ${costStr}`);
    } else {
      addLog(g, `${pName(pp.playerColor)} passes on provost`);
    }
  }

  g.pendingProvost = null;

  if (pp.type === "guild") {
    return continueAfterGuild(g);
  }

  // Phase 4 — advance to next player
  if (g.provostPhase) {
    g.provostPhase.index++;
    return advanceProvostPhase(g);
  }
  return finishProvostPhase(g);
}

function finishProvostPhase(g) {
  g.provostPhase = null;
  g.pendingProvost = null;
  g.currentPhase = 4;
  addLog(g, "— Phase 5: Activate Buildings —");

  // Now remove workers beyond provost
  for (let i = g.provostPosition + 1; i < g.road.length; i++) {
    if (g.road[i].worker) {
      addLog(g, `${pName(g.road[i].worker)}'s worker beyond provost (pos ${i+1}) — returns unused`);
      returnWorker(g, g.road[i].worker);
      g.road[i].worker = null;
      applyDelayedTransformations(g, i);
    }
  }
  g.activationIndex = -1;
  g.pendingActivation = null;
  return advanceActivation(g);
}

// --- Phase 5: Step-by-step Building Activation ---

function resolveOwnerBonus(game, resource) {
  const g = deepClone(game);
  const ob = g.pendingOwnerBonus;
  if (!ob) return g;
  const own = g.players.find(x => x.color === ob.ownerColor);
  if (own) {
    own.resources[resource]++;
    addLog(g, `${pName(ob.ownerColor)} takes +1 ${resource} (owner bonus for ${ob.buildingName})`);
  }
  g.pendingOwnerBonus = null;
  return advanceActivation(g);
}

function applyDelayedTransformations(g, roadIndex) {
  if (!g.delayedTransformations || g.delayedTransformations.length === 0) return;
  const pending = g.delayedTransformations.filter(dt => dt.targetIndex === roadIndex);
  if (pending.length === 0) return;
  g.delayedTransformations = g.delayedTransformations.filter(dt => dt.targetIndex !== roadIndex);
  pending.forEach(dt => {
    const target = g.road[dt.targetIndex];
    const oldName = dt.oldBuilding.name;
    // Return craft buildings to stock
    if (!dt.wasNeutral && (dt.oldBuildingType === "wood" || dt.oldBuildingType === "stone")) {
      if (g.buildingStock[dt.oldBuildingType]) {
        g.buildingStock[dt.oldBuildingType].push({ ...dt.oldBuilding });
        addLog(g, `  ${oldName} returned to ${dt.oldBuildingType} building stock`);
      }
    }
    target.building = { id: `res_${dt.targetIndex}`, name: "Residential", type: "residential", category: "residential", description: "+1 denier income" };
    if (dt.wasNeutral) {
      const lp = g.players.find(x => x.color === dt.lawyerColor);
      if (lp) target.house = dt.lawyerColor;
    }
    addLog(g, `  Delayed: ${oldName} → Residential (lawyer by ${pName(dt.lawyerColor)})`);
  });
}

function advanceActivation(game) {
  const g = game;
  // Walk from current activationIndex+1 to provostPosition, find next worker
  for (let i = g.activationIndex + 1; i <= g.provostPosition && i < g.road.length; i++) {
    const s = g.road[i];
    if (!s.worker || !s.building) continue;
    g.activationIndex = i;

    const wc = s.worker;
    const p = g.players.find(x => x.color === wc);
    if (!p) { returnWorker(g, wc); s.worker = null; continue; }

    const eff = s.building.effect;
    if (!eff) { returnWorker(g, wc); s.worker = null; continue; }

    // Simple auto-resolve: "gain" with no choice
    if (eff.type === "gain") {
      Object.entries(eff.resources).forEach(([r, a]) => { p.resources[r] = (p.resources[r]||0) + a; });
      const gains = Object.entries(eff.resources).map(([r,a])=>`${a} ${r}`).join(", ");
      addLog(g, `${pName(wc)} activates ${s.building.name}: +${gains}`);
      if (s.building.type === "stone" && s.house && s.house !== wc && s.building.ownerBonus) {
        const own = g.players.find(x => x.color === s.house);
        if (own) {
          if (s.building.ownerBonus.length === 1) {
            const br = s.building.ownerBonus[0];
            own.resources[br]++;
            addLog(g, `  ${pName(s.house)} +1 ${br} (owner bonus)`);
          } else {
            // Owner must choose which resource to take
            returnWorker(g, wc); s.worker = null;
            g.pendingOwnerBonus = {
              ownerColor: s.house,
              options: s.building.ownerBonus,
              buildingName: s.building.name,
            };
            return g; // pause for owner choice
          }
        }
      }
      returnWorker(g, wc); s.worker = null;
      applyDelayedTransformations(g, i);
      continue;
    }

    // Everything else needs player choice — build a pending activation
    const pending = buildPendingActivation(g, i, s, p, eff);
    if (pending) {
      g.pendingActivation = pending;
      return g; // pause — UI will show choices
    }
    // If no valid pending (e.g. no options), skip
    addLog(g, `${pName(wc)} activates ${s.building.name} — no valid options, skipped`);
    returnWorker(g, wc); s.worker = null;
  }

  // No more workers to activate — proceed to castle phase
  g.activationIndex = -1;
  g.pendingActivation = null;
  g.currentPhase = 5;
  addLog(g, "— Phase 6: Castle —");
  return processCastle(g);
}

function buildPendingActivation(g, roadIndex, slot, player, eff) {
  const wc = slot.worker;
  const bName = slot.building.name;
  const isProduction = slot.building.category === "production";

  if (eff.type === "choice") {
    // Production choice: e.g. "2 food OR 1 cloth"
    const choices = eff.options.map((opt, i) => ({
      id: `opt_${i}`,
      label: Object.entries(opt).map(([r,a]) => `${a} ${RESOURCE_ICONS[r]?.symbol||r}`).join(" + "),
      desc: Object.entries(opt).map(([r,a]) => `${a} ${r}`).join(", "),
    }));
    return { roadIndex, workerColor: wc, buildingName: bName, effectType: "choice", choices, canSkip: !isProduction };
  }

  if (eff.type === "sell") {
    const sellable = ["food","wood","stone","cloth","gold"].filter(r => player.resources[r] > 0);
    const choices = sellable.map(r => ({
      id: `sell_${r}`, label: `Sell 1 ${RESOURCE_ICONS[r]?.symbol||r} for ${eff.price}$`,
      desc: `Sell ${r}`,
    }));
    if (choices.length === 0) return { roadIndex, workerColor: wc, buildingName: bName, effectType: "sell", choices: [], canSkip: true };
    return { roadIndex, workerColor: wc, buildingName: bName, effectType: "sell", choices, canSkip: true };
  }

  if (eff.type === "buy") {
    const buyable = ["food","wood","stone","cloth"].filter(() => player.deniers >= eff.costPer);
    const choices = buyable.length > 0
      ? ["food","wood","stone","cloth"].map(r => ({
          id: `buy_${r}`, label: `Buy 1 ${RESOURCE_ICONS[r]?.symbol||r} (${eff.costPer}$)`, desc: `Buy ${r}`,
        }))
      : [];
    return { roadIndex, workerColor: wc, buildingName: bName, effectType: "buy", choices, canSkip: true, buyMax: eff.max, buyRemaining: eff.max, buyCostPer: eff.costPer };
  }

  if (eff.type === "build") {
    const stock = g.buildingStock[eff.buildType] || [];
    const isPrestige = eff.buildType === "prestige";
    // Prestige buildings replace owned residential; others go to first empty slot
    const validTarget = isPrestige
      ? g.road.some(x => x.building?.type === "residential" && x.house === player.color)
      : g.road.some(x => x.building === null);
    const choices = stock.map(b => {
      const canAfford = b.cost && Object.entries(b.cost).every(([r,a]) => player.resources[r] >= a);
      return {
        id: `build_${b.id}`, label: b.name,
        desc: `Cost: ${Object.entries(b.cost||{}).map(([r,a])=>`${a}${RESOURCE_ICONS[r]?.symbol||r}`).join("+")} → +${b.vp}VP`,
        cost: b.cost, vp: b.vp, buildingId: b.id,
        disabled: !canAfford || !validTarget,
      };
    });
    if (isPrestige) {
      // Player also needs to choose which residential to replace
      return { roadIndex, workerColor: wc, buildingName: bName, effectType: "build", choices, canSkip: true, buildType: eff.buildType, needsTarget: true };
    }
    return { roadIndex, workerColor: wc, buildingName: bName, effectType: "build", choices, canSkip: true, buildType: eff.buildType };
  }

  if (eff.type === "church") {
    const choices = [];
    if (player.deniers >= 2) choices.push({ id: "church_2", label: "Pay 2$ → +3VP", desc: "2 deniers for 3 VP" });
    if (player.deniers >= 4) choices.push({ id: "church_4", label: "Pay 4$ → +5VP", desc: "4 deniers for 5 VP" });
    return { roadIndex, workerColor: wc, buildingName: bName, effectType: "church", choices, canSkip: true };
  }

  if (eff.type === "tailor") {
    const choices = [];
    if (player.resources.cloth >= 1) choices.push({ id: "tailor_1", label: `Pay 1${RESOURCE_ICONS.cloth.symbol} → +2VP`, desc: "1 cloth for 2 VP" });
    if (player.resources.cloth >= 3) choices.push({ id: "tailor_3", label: `Pay 3${RESOURCE_ICONS.cloth.symbol} → +6VP`, desc: "3 cloth for 6 VP" });
    return { roadIndex, workerColor: wc, buildingName: bName, effectType: "tailor", choices, canSkip: true };
  }

  if (eff.type === "bank") {
    const choices = [];
    if (player.deniers >= 2) choices.push({ id: "bank_2", label: "Pay 2$ → 1✦", desc: "2 deniers for 1 gold" });
    if (player.deniers >= 5) choices.push({ id: "bank_5", label: "Pay 5$ → 2✦", desc: "5 deniers for 2 gold" });
    return { roadIndex, workerColor: wc, buildingName: bName, effectType: "bank", choices, canSkip: true };
  }

  if (eff.type === "alchemist") {
    const nonGold = Object.entries(player.resources).filter(([k])=>k!=="gold").reduce((s,[,v])=>s+v,0);
    const choices = [];
    if (nonGold >= 2) choices.push({ id: "alch_2", label: "Pay 2 cubes → 1✦", desc: "2 any cubes for 1 gold" });
    if (nonGold >= 4) choices.push({ id: "alch_4", label: "Pay 4 cubes → 2✦", desc: "4 any cubes for 2 gold" });
    return { roadIndex, workerColor: wc, buildingName: bName, effectType: "alchemist", choices, canSkip: true, alchPicking: false, alchTarget: 0, alchPicked: 0 };
  }

  if (eff.type === "lawyer") {
    // Find buildings that can be transformed: neutral or own craft buildings (not lawyer, not prestige, not residential, not basic)
    const choices = [];
    g.road.forEach((rs, ri) => {
      if (!rs.building) return;
      if (rs.building.cannotBeTransformed) return;
      const bt = rs.building.type;
      if (bt === "prestige" || bt === "residential" || bt === "basic") return;
      // Neutral buildings can be transformed by anyone; own craft buildings only by owner
      if (bt === "neutral" || (rs.house === wc && (bt === "wood" || bt === "stone"))) {
        choices.push({
          id: `lawyer_${ri}`, label: `${rs.building.name} (pos ${ri+1})`,
          desc: bt === "neutral" ? "Transform neutral building" : "Transform your building",
          targetIndex: ri,
        });
      }
    });
    const canPay = player.deniers >= 1 && player.resources.cloth >= 1;
    return { roadIndex, workerColor: wc, buildingName: bName, effectType: "lawyer",
      choices: canPay ? choices : [], canSkip: true };
  }

  return null;
}

function resolveActivation(game, choiceId) {
  const g = deepClone(game);
  const pa = g.pendingActivation;
  if (!pa) return g;

  const slot = g.road[pa.roadIndex];
  const p = g.players.find(x => x.color === pa.workerColor);
  const eff = slot.building.effect;

  if (choiceId === "skip") {
    addLog(g, `${pName(pa.workerColor)} skips ${pa.buildingName}`);
    returnWorker(g, pa.workerColor);
    slot.worker = null;
    g.pendingActivation = null;
    return advanceActivation(g);
  }

  if (pa.effectType === "choice") {
    const optIdx = parseInt(choiceId.split("_")[1]);
    const chosen = eff.options[optIdx];
    Object.entries(chosen).forEach(([r, a]) => { p.resources[r] = (p.resources[r]||0) + a; });
    addLog(g, `${pName(pa.workerColor)} activates ${pa.buildingName}: +${Object.entries(chosen).map(([r,a])=>`${a} ${r}`).join(", ")}`);
    if (slot.building.type === "stone" && slot.house && slot.house !== pa.workerColor && slot.building.ownerBonus) {
      const own = g.players.find(x => x.color === slot.house);
      if (own) {
        if (slot.building.ownerBonus.length === 1) {
          const br = slot.building.ownerBonus[0];
          own.resources[br]++;
          addLog(g, `  ${pName(slot.house)} +1 ${br} (owner bonus)`);
        } else {
          // Owner must choose
          returnWorker(g, pa.workerColor);
          slot.worker = null;
          g.pendingActivation = null;
          g.pendingOwnerBonus = {
            ownerColor: slot.house,
            options: slot.building.ownerBonus,
            buildingName: slot.building.name,
          };
          return g;
        }
      }
    }
  }

  else if (pa.effectType === "sell") {
    const res = choiceId.split("_")[1];
    p.resources[res]--;
    p.deniers += eff.price;
    addLog(g, `${pName(pa.workerColor)} sells 1 ${res} for ${eff.price}$ at ${pa.buildingName}`);
  }

  else if (pa.effectType === "buy") {
    const res = choiceId.split("_")[1];
    p.deniers -= pa.buyCostPer;
    p.resources[res]++;
    addLog(g, `${pName(pa.workerColor)} buys 1 ${res} for ${pa.buyCostPer}$ at ${pa.buildingName}`);
    // Check if can buy more
    const remaining = (pa.buyRemaining || pa.buyMax) - 1;
    if (remaining > 0 && p.deniers >= pa.buyCostPer) {
      // Show buy choices again with done option
      g.pendingActivation = { ...pa, buyRemaining: remaining, canSkip: true, choices:
        ["food","wood","stone","cloth"].map(r => ({ id:`buy_${r}`, label:`Buy 1 ${RESOURCE_ICONS[r]?.symbol||r} (${pa.buyCostPer}$)`, desc:`Buy ${r}` }))
      };
      return g; // pause for next buy choice
    }
  }

  else if (pa.effectType === "church") {
    if (choiceId === "church_4") { p.deniers -= 4; p.score += 5; addLog(g, `${pName(pa.workerColor)} Church: -4$ → +5VP`); }
    else { p.deniers -= 2; p.score += 3; addLog(g, `${pName(pa.workerColor)} Church: -2$ → +3VP`); }
  }

  else if (pa.effectType === "tailor") {
    if (choiceId === "tailor_3") { p.resources.cloth -= 3; p.score += 6; addLog(g, `${pName(pa.workerColor)} Tailor: -3 cloth → +6VP`); }
    else { p.resources.cloth -= 1; p.score += 2; addLog(g, `${pName(pa.workerColor)} Tailor: -1 cloth → +2VP`); }
  }

  else if (pa.effectType === "bank") {
    if (choiceId === "bank_5") { p.deniers -= 5; p.resources.gold += 2; addLog(g, `${pName(pa.workerColor)} Bank: -5$ → +2 gold`); }
    else { p.deniers -= 2; p.resources.gold += 1; addLog(g, `${pName(pa.workerColor)} Bank: -2$ → +1 gold`); }
  }

  else if (pa.effectType === "alchemist") {
    if (!pa.alchPicking) {
      // Player just chose 2 or 4 cubes tier — now pick cubes one at a time
      const count = choiceId === "alch_4" ? 4 : 2;
      const gold = count === 4 ? 2 : 1;
      const available = ["food","wood","stone","cloth"].filter(r => p.resources[r] > 0).map(r => ({
        id: `alchcube_${r}`, label: `${RESOURCE_ICONS[r].symbol} ${r}`, desc: `Give 1 ${r}`,
      }));
      g.pendingActivation = { ...pa, alchPicking: true, alchTarget: count, alchPicked: 0, alchGold: gold,
        choices: available, canSkip: false, effectType: "alchemist" };
      return g;
    }
    // Picking a specific cube
    const res = choiceId.replace("alchcube_", "");
    p.resources[res] -= 1;
    const newPicked = pa.alchPicked + 1;
    addLog(g, `${pName(pa.workerColor)} gives 1 ${res} to Alchemist (${newPicked}/${pa.alchTarget})`);
    if (newPicked >= pa.alchTarget) {
      // Done picking — grant gold
      p.resources.gold += pa.alchGold;
      addLog(g, `${pName(pa.workerColor)} Alchemist: → +${pa.alchGold} gold`);
    } else {
      // More cubes to pick
      const available = ["food","wood","stone","cloth"].filter(r => p.resources[r] > 0).map(r => ({
        id: `alchcube_${r}`, label: `${RESOURCE_ICONS[r].symbol} ${r}`, desc: `Give 1 ${r}`,
      }));
      if (available.length > 0) {
        g.pendingActivation = { ...pa, alchPicked: newPicked, choices: available };
        return g;
      }
      // Ran out of cubes — give gold anyway
      p.resources.gold += pa.alchGold;
      addLog(g, `${pName(pa.workerColor)} Alchemist: ran out of cubes → +${pa.alchGold} gold`);
    }
  }

  else if (pa.effectType === "build") {
    // If prestige building and we haven't chosen a target residential yet
    if (pa.needsTarget && !pa.chosenBuildingId) {
      // Player just picked which prestige building to construct — now pick residential target
      const bId = choiceId.replace("build_", "");
      const stock = g.buildingStock[pa.buildType];
      const b = stock.find(x => x.id === bId);
      if (!b) { returnWorker(g, pa.workerColor); slot.worker = null; g.pendingActivation = null; return advanceActivation(g); }
      // Show residential targets
      const targets = [];
      g.road.forEach((rs, ri) => {
        if (rs.building?.type === "residential" && rs.house === pa.workerColor) {
          targets.push({ id: `ptarget_${ri}`, label: `Residential (pos ${ri+1})`, desc: `Replace with ${b.name}`, targetIndex: ri });
        }
      });
      g.pendingActivation = { ...pa, effectType: "prestige_target", chosenBuildingId: bId, choices: targets, canSkip: true };
      return g;
    }
    const bId = choiceId.replace("build_", "");
    const stock = g.buildingStock[pa.buildType];
    const bIdx = stock.findIndex(b => b.id === bId);
    if (bIdx >= 0) {
      const b = stock[bIdx];
      Object.entries(b.cost).forEach(([r,a]) => { p.resources[r] -= a; });
      const emptySlot = g.road.find(x => x.building === null);
      if (emptySlot) {
        emptySlot.building = { ...stock.splice(bIdx, 1)[0] };
        emptySlot.house = p.color;
        p.score += (b.vp || 0);
        p.houses.placed++;
        addLog(g, `${pName(pa.workerColor)} builds ${b.name} → +${b.vp}VP`);
        if (b.favorOnBuild) {
          addLog(g, `  ${b.name} grants ${b.favorOnBuild} favor${b.favorOnBuild>1?"s":""}`);
          returnWorker(g, pa.workerColor);
          slot.worker = null;
          g.pendingActivation = null;
          return grantFavors(g, [{ color: pa.workerColor, count: b.favorOnBuild }], "advanceActivation");
        }
      }
    }
  }

  else if (pa.effectType === "prestige_target") {
    const targetIdx = pa.choices.find(c => c.id === choiceId)?.targetIndex;
    if (targetIdx !== undefined) {
      const stock = g.buildingStock.prestige;
      const bIdx = stock.findIndex(b => b.id === pa.chosenBuildingId);
      if (bIdx >= 0) {
        const b = stock[bIdx];
        Object.entries(b.cost).forEach(([r,a]) => { p.resources[r] -= a; });
        const target = g.road[targetIdx];
        // Replace residential with prestige building
        target.building = { ...stock.splice(bIdx, 1)[0] };
        // House stays as the player's
        p.score += (b.vp || 0);
        addLog(g, `${pName(pa.workerColor)} builds ${b.name} (replacing Residential at pos ${targetIdx+1}) → +${b.vp}VP`);
        if (b.favorOnBuild) {
          addLog(g, `  ${b.name} grants ${b.favorOnBuild} favor${b.favorOnBuild>1?"s":""}`);
          returnWorker(g, pa.workerColor);
          slot.worker = null;
          g.pendingActivation = null;
          return grantFavors(g, [{ color: pa.workerColor, count: b.favorOnBuild }], "advanceActivation");
        }
      }
    }
  }

  else if (pa.effectType === "lawyer") {
    const targetIdx = pa.choices.find(c => c.id === choiceId)?.targetIndex;
    if (targetIdx !== undefined) {
      p.deniers -= 1;
      p.resources.cloth -= 1;
      const target = g.road[targetIdx];
      const oldBuilding = target.building;
      const oldName = oldBuilding.name;
      const wasNeutral = oldBuilding.type === "neutral";

      if (target.worker !== null) {
        // Target has a worker — pay now but delay transformation until after that building activates
        if (!g.delayedTransformations) g.delayedTransformations = [];
        g.delayedTransformations.push({
          targetIndex: targetIdx,
          lawyerColor: pa.workerColor,
          wasNeutral,
          oldBuildingType: oldBuilding.type,
          oldBuilding: { ...oldBuilding },
        });
        addLog(g, `${pName(pa.workerColor)} pays for ${oldName} transformation (delayed — worker present)`);
        p.score += 2;
      } else {
        // No worker — transform immediately
        if (!wasNeutral && (oldBuilding.type === "wood" || oldBuilding.type === "stone")) {
          const stockType = oldBuilding.type;
          if (g.buildingStock[stockType]) {
            g.buildingStock[stockType].push({ ...oldBuilding });
            addLog(g, `  ${oldName} returned to ${stockType} building stock`);
          }
        }
        target.building = { id: `res_${targetIdx}`, name: "Residential", type: "residential", category: "residential", description: "+1 denier income" };
        if (!wasNeutral && target.house) {
          // Own craft building — stays owned
        } else {
          target.house = p.color; // neutral → player claims it
        }
        p.score += 2;
        addLog(g, `${pName(pa.workerColor)} transforms ${oldName} → Residential (+2VP)`);
      }
    }
  }

  // Done — return worker and advance
  returnWorker(g, pa.workerColor);
  slot.worker = null;
  applyDelayedTransformations(g, pa.roadIndex);
  g.pendingActivation = null;
  return advanceActivation(g);
}

// --- Phase 6: Castle ---
function processCastle(game) {
  const g = game;
  if (g.castle.workers.length === 0) {
    g.currentPhase = 6;
    addLog(g, "— Phase 7: End of Turn —");
    return processEndTurn(g);
  }
  // Process castle workers one at a time in castle scale order
  g.castlePhase = { workerIndex: 0, housesThisTurn: {} };
  return advanceCastleWorker(g);
}

function advanceCastleWorker(g) {
  const cp = g.castlePhase;
  if (!cp || cp.workerIndex >= g.castle.workers.length) {
    return finishCastlePhase(g);
  }
  const wc = g.castle.workers[cp.workerIndex];
  const p = g.players.find(x => x.color === wc);
  if (!p) { cp.workerIndex++; return advanceCastleWorker(g); }

  // Check if player can give a batch: food + 2 different non-food resource types
  const batchOptions = getCastleBatchOptions(p, g);
  if (batchOptions.length > 0) {
    g.pendingCastle = { playerColor: wc, canGive: true };
    return g; // UI will show batch choices
  }
  // Can't give a batch
  const sec = g.castle.currentSection;
  const parts = g.castle[sec];
  const secFull = parts.every(x => x !== null);
  const nextSec = sec === "dungeon" ? "walls" : sec === "walls" ? "towers" : null;
  const nextFull = nextSec ? g.castle[nextSec].every(x => x !== null) : true;
  if (sec === "towers" && secFull && nextFull) {
    // No room in towers — no penalty
    addLog(g, `${pName(wc)} — no room left in Towers (no penalty)`);
  } else {
    p.score = Math.max(0, p.score - 2);
    addLog(g, `${pName(wc)} can't contribute to castle → -2VP`);
  }
  returnWorker(g, wc);
  cp.workerIndex++;
  return advanceCastleWorker(g);
}

function getCastleBatchOptions(player, game) {
  // A batch = 1 food + 2 cubes of different types (from wood, stone, cloth, gold)
  // Check if player has food and at least 2 other different resource types
  if (player.resources.food < 1) return [];
  const others = ["wood","stone","cloth","gold"].filter(r => player.resources[r] >= 1);
  if (others.length < 2) return [];

  // Find current available section
  const sec = game.castle.currentSection;
  const parts = game.castle[sec];
  const hasRoom = parts.some(x => x === null);
  const nextSec = sec === "dungeon" ? "walls" : sec === "walls" ? "towers" : null;
  const nextHasRoom = nextSec ? game.castle[nextSec].some(x => x === null) : false;
  if (!hasRoom && !nextHasRoom) return [];

  // Generate all valid 2-resource combos from available types
  const combos = [];
  for (let i = 0; i < others.length; i++) {
    for (let j = i + 1; j < others.length; j++) {
      combos.push([others[i], others[j]]);
    }
  }
  return combos;
}

function resolveCastleBatch(game, res1, res2) {
  const g = deepClone(game);
  const cp = g.castlePhase;
  const wc = g.castle.workers[cp.workerIndex];
  const p = g.players.find(x => x.color === wc);

  // Pay resources
  p.resources.food -= 1;
  p.resources[res1] -= 1;
  p.resources[res2] -= 1;

  // Place house in current section, overflow to next if full
  let sec = g.castle.currentSection;
  let parts = g.castle[sec];
  let empty = parts.findIndex(x => x === null);
  let placedSection = sec;
  if (empty === -1) {
    // Overflow to next section
    const nextSec = sec === "dungeon" ? "walls" : sec === "walls" ? "towers" : null;
    if (nextSec) {
      parts = g.castle[nextSec];
      empty = parts.findIndex(x => x === null);
      placedSection = nextSec;
    }
  }
  if (empty !== -1) {
    parts[empty] = p.color;
    const vpPerBatch = CASTLE_SECTIONS[placedSection].vpPerBatch;
    p.score += vpPerBatch;
    p.houses.placed++;
    cp.housesThisTurn[wc] = (cp.housesThisTurn[wc] || 0) + 1;
    addLog(g, `${pName(wc)} builds ${CASTLE_SECTIONS[placedSection].name} (food+${res1}+${res2}) → +${vpPerBatch}VP`);
  }

  // Check if can give another batch
  const moreOptions = getCastleBatchOptions(p, g);
  if (moreOptions.length > 0) {
    g.pendingCastle = { playerColor: wc, canGive: true };
    return g; // stay on same worker for more batches
  }

  // Done with this worker
  g.pendingCastle = null;
  returnWorker(g, wc);
  cp.workerIndex++;
  return advanceCastleWorker(g);
}

function skipCastleBatch(game) {
  const g = deepClone(game);
  const cp = g.castlePhase;
  const wc = g.castle.workers[cp.workerIndex];

  // If player hasn't given ANY batch this turn, they get the -2VP penalty
  if (!cp.housesThisTurn[wc]) {
    const p = g.players.find(x => x.color === wc);
    const sec = g.castle.currentSection;
    const parts = g.castle[sec];
    const secFull = parts.every(x => x !== null);
    const nextSec = sec === "dungeon" ? "walls" : sec === "walls" ? "towers" : null;
    const nextFull = nextSec ? g.castle[nextSec].every(x => x !== null) : true;
    if (sec === "towers" && secFull && (!nextSec || nextFull)) {
      addLog(g, `${pName(wc)} — no room left (no penalty)`);
    } else if (p) {
      p.score = Math.max(0, p.score - 2);
      addLog(g, `${pName(wc)} declines to build castle → -2VP`);
    }
  } else {
    addLog(g, `${pName(wc)} stops building castle (${cp.housesThisTurn[wc]} batch${cp.housesThisTurn[wc]>1?"es":""})`);
  }

  g.pendingCastle = null;
  returnWorker(g, wc);
  cp.workerIndex++;
  return advanceCastleWorker(g);
}

function finishCastlePhase(g) {
  const cp = g.castlePhase;
  // Determine best builder this turn
  let best = null, bestC = 0;
  for (const [color, count] of Object.entries(cp.housesThisTurn)) {
    if (count > bestC) { bestC = count; best = color; }
    else if (count === bestC && best) {
      // Tie: first to place a worker in castle wins
      const bestIdx = g.castle.workers.indexOf(best);
      const colorIdx = g.castle.workers.indexOf(color);
      if (colorIdx < bestIdx) best = color;
    }
  }

  // Return remaining workers
  g.castle.workers.forEach(wc => returnWorker(g, wc));
  g.castle.workers = [];
  g.castlePhase = null;
  g.pendingCastle = null;
  g.currentPhase = 6;

  if (best && bestC > 0) {
    addLog(g, `${pName(best)} is best castle builder (${bestC} batch${bestC>1?"es":""}) → 1 favor`);
    return grantFavors(g, [{ color: best, count: 1 }], "afterCastle");
  }

  addLog(g, "— Phase 7: End of Turn —");
  return processEndTurn(g);
}

function afterCastleFavors(g) {
  addLog(g, "— Phase 7: End of Turn —");
  return processEndTurn(g);
}

// --- Phase 7: End Turn ---
function processEndTurn(game) {
  const g = game;
  const ahead = g.provostPosition > g.bailiffPosition;
  const mv = ahead ? 2 : 1;
  g.bailiffPosition = Math.min(g.bailiffPosition + mv, g.road.length - 1);
  g.provostPosition = g.bailiffPosition;
  addLog(g, `Bailiff moves ${mv} → pos ${g.bailiffPosition+1}, Provost resets`);

  const sec = g.castle.currentSection;
  const parts = g.castle[sec];
  const full = parts.every(p => p !== null);
  const TRIGGERS = { dungeon: 10, walls: 16, towers: 22 };
  let doCount = full;
  if (!doCount && !g.castle[sec+"Counted"] && g.bailiffPosition >= TRIGGERS[sec]) doCount = true;

  if (doCount) {
    return processCastleCount(g); // may pause for favors
  }

  return finishEndTurn(g);
}

function processCastleCount(g) {
  const sec = g.castle.currentSection;
  const parts = g.castle[sec];
  addLog(g, `🏰 Counting ${CASTLE_SECTIONS[sec].name}!`);

  const favorQueue = [];

  g.players.forEach(p => {
    const h = parts.filter(x => x === p.color).length;
    let favors = 0;
    if (sec === "dungeon") {
      if (h === 0) { p.score = Math.max(0, p.score-2); addLog(g, `${pName(p.color)}: 0 houses → -2VP`); }
      else if (h >= 2) { favors = 1; addLog(g, `${pName(p.color)}: ${h} houses → 1 favor`); }
      else addLog(g, `${pName(p.color)}: ${h} house`);
    } else if (sec === "walls") {
      if (h === 0) { p.score = Math.max(0, p.score-3); addLog(g, `${pName(p.color)}: 0 houses → -3VP`); }
      else if (h >= 5) { favors = 3; addLog(g, `${pName(p.color)}: ${h} houses → 3 favors`); }
      else if (h >= 3) { favors = 2; addLog(g, `${pName(p.color)}: ${h} houses → 2 favors`); }
      else if (h >= 2) { favors = 1; addLog(g, `${pName(p.color)}: ${h} houses → 1 favor`); }
      else addLog(g, `${pName(p.color)}: ${h} house`);
    } else {
      if (h === 0) { p.score = Math.max(0, p.score-4); addLog(g, `${pName(p.color)}: 0 houses → -4VP`); }
      else if (h >= 6) { favors = 3; addLog(g, `${pName(p.color)}: ${h} houses → 3 favors`); }
      else if (h >= 4) { favors = 2; addLog(g, `${pName(p.color)}: ${h} houses → 2 favors`); }
      else if (h >= 2) { favors = 1; addLog(g, `${pName(p.color)}: ${h} houses → 1 favor`); }
      else addLog(g, `${pName(p.color)}: ${h} house`);
    }
    if (favors > 0) favorQueue.push({ color: p.color, count: favors });
  });

  // Advance section
  if (sec === "dungeon") { g.castle.dungeonCounted = true; g.castle.currentSection = "walls"; g.favorColumnsAvailable = 4; addLog(g, "→ Walls phase. Favor cols 3-4 open."); }
  else if (sec === "walls") { g.castle.wallsCounted = true; g.castle.currentSection = "towers"; g.favorColumnsAvailable = 5; addLog(g, "→ Towers phase. All favor cols open."); }
  else { g.castle.towersCounted = true; g.gameOver = true; addLog(g, "🏁 Game Over!"); }

  if (favorQueue.length > 0) {
    return grantFavors(g, favorQueue, "afterCount");
  }
  return finishEndTurn(g);
}

function afterCountFavors(g) {
  return finishEndTurn(g);
}

function finishEndTurn(g) {
  g.turn++;
  g.currentPhase = 0;
  g.currentPlayerIndex = 0;
  g.passingScale = Array(g.players.length).fill(null);
  g.players.forEach(p => { p.passed = false; p.passOrder = -1; });
  g.pendingActivation = null;
  g.activationIndex = -1;
  g.provostPhase = null;
  g.pendingProvost = null;
  g.pendingFavors = null;
  g.pendingGate = null;
  g.pendingCastle = null;
  g.castlePhase = null;
  g.pendingInn = null;
  g.pendingOwnerBonus = null;
  g.delayedTransformations = [];

  if (g.gameOver) processEndGame(g);
  else addLog(g, `━━━ Turn ${g.turn} ━━━`);
  return g;
}

function processEndGame(g) {
  addLog(g, "━━━ FINAL SCORING ━━━");
  g.players.forEach(p => {
    const gb = p.resources.gold * 3;
    const cb = Math.floor(Object.entries(p.resources).filter(([k])=>k!=="gold").reduce((s,[,v])=>s+v,0) / 3);
    const db = Math.floor(p.deniers / 4);
    p.score += gb + cb + db;
    addLog(g, `${pName(p.color)}: +${gb}(gold) +${cb}(cubes) +${db}($) = ${p.score}VP total`);
  });
  const w = g.players.reduce((b,p)=>p.score>b.score?p:b, g.players[0]);
  addLog(g, `🏆 ${pName(w.color)} wins with ${w.score}VP!`);
}

// ============================================================
// GAME INIT
// ============================================================

function initializeGame(numPlayers) {
  const colors = shuffle(Object.keys(PLAYER_COLORS).slice(0, numPlayers));
  const players = colors.map((c, i) => ({
    color: c, turnOrder: i,
    deniers: i === 0 ? 5 : i <= 2 ? 6 : 7,
    resources: { food: 2, wood: 1, stone: 0, cloth: 0, gold: 0 },
    workers: { total: 6, placed: 0 }, houses: { total: 20, placed: 0 },
    score: 0, passed: false, passOrder: -1,
    favors: { prestige: 0, deniers: 0, resources: 0, buildings: 0 },
    innOccupant: false,
  }));
  const neutrals = shuffle(NEUTRAL_BUILDINGS);
  const road = [];
  neutrals.forEach((b, i) => road.push({ index: i, building: {...b}, owner: null, worker: null, house: null }));
  BASIC_BUILDINGS.forEach((b, i) => road.push({ index: 6+i, building: {...b}, owner: null, worker: null, house: null }));
  for (let i = 6 + BASIC_BUILDINGS.length; i < 30; i++) road.push({ index: i, building: null, owner: null, worker: null, house: null });

  return {
    players, road,
    specialState: { gate:{worker:null}, trading_post:{worker:null}, merchants_guild:{worker:null}, joust_field:{worker:null}, stables:[null,null,null], inn:{left:null,right:null} },
    castle: { currentSection:"dungeon", dungeon:Array(6).fill(null), walls:Array(10).fill(null), towers:Array(14).fill(null), workers:[], dungeonCounted:false, wallsCounted:false, towersCounted:false },
    buildingStock: { wood:[...WOOD_BUILDINGS], stone:[...STONE_BUILDINGS], prestige:[...PRESTIGE_BUILDINGS] },
    bailiffPosition: 5, provostPosition: 5,
    currentPhase: 0, currentPlayerIndex: 0, turn: 1,
    passingScale: Array(numPlayers).fill(null),
    gameOver: false, favorColumnsAvailable: 2,
    pendingActivation: null, activationIndex: -1,
    provostPhase: null,
    pendingProvost: null,
    pendingFavors: null,
    pendingGate: null, // { playerColor }
    pendingCastle: null, // { playerColor, canGive }
    castlePhase: null, // { workerIndex, housesThisTurn }
    pendingInn: null, // { playerColor }
    pendingOwnerBonus: null, // { ownerColor, options, buildingName }
    delayedTransformations: [], // for lawyer targeting occupied buildings
    log: ["━━━ Turn 1 ━━━"],
  };
}

// ============================================================
// UI COMPONENTS
// ============================================================

const TC = { neutral:{bg:"#f5d0c5",border:"#d4a089"}, basic:{bg:"#f5d0c5",border:"#d4a089"}, wood:{bg:"#d4a574",border:"#92400e"}, stone:{bg:"#b8b8b8",border:"#6b7280"}, prestige:{bg:"#93c5fd",border:"#2563eb"}, residential:{bg:"#86efac",border:"#16a34a"}, empty:{bg:"#e8dcc8",border:"#c4b59a"} };

function ResourceBadge({ type, count, small }) {
  const r = RESOURCE_ICONS[type]; if (!r) return null;
  return <span style={{ display:"inline-flex", alignItems:"center", gap:2, background:r.color+"22", border:`1px solid ${r.color}55`, borderRadius:4, padding:small?"0 3px":"1px 5px", fontSize:small?11:13, color:r.color, fontWeight:600 }}><span>{r.symbol}</span>{count>0&&<span>{count}</span>}</span>;
}

function PlayerToken({ color, size = 16 }) {
  const c = PLAYER_COLORS[color]; if (!c) return null;
  return <span style={{ display:"inline-block", width:size, height:size, borderRadius:"50%", background:c.bg, border:`2px solid ${c.light}`, boxShadow:`0 1px 3px ${c.bg}66`, flexShrink:0 }} />;
}

function WorkerCylinder({ color, size = 14 }) {
  const c = PLAYER_COLORS[color]; if (!c) return null;
  return <span style={{ display:"inline-block", width:size, height:size*1.3, borderRadius:`${size/2}px ${size/2}px 2px 2px`, background:`linear-gradient(135deg, ${c.light}, ${c.bg})`, border:`1.5px solid ${c.bg}`, flexShrink:0 }} />;
}

function HousePiece({ color, size = 12 }) {
  const c = PLAYER_COLORS[color]; if (!c) return null;
  return <span style={{ display:"inline-block", width:0, height:0, borderLeft:`${size/2}px solid transparent`, borderRight:`${size/2}px solid transparent`, borderBottom:`${size*0.7}px solid ${c.bg}` }} />;
}

function Btn({ children, onClick, disabled, variant="primary", small, style: xs }) {
  const V = { primary:{bg:"linear-gradient(135deg,#92400e,#78350f)",color:"#fef3c7",border:"1px solid #78350f"}, secondary:{bg:"#fef3c7",color:"#78350f",border:"1px solid #d4a574"}, danger:{bg:"#fee2e2",color:"#dc2626",border:"1px solid #fca5a5"}, success:{bg:"#dcfce7",color:"#16a34a",border:"1px solid #86efac"} };
  const s = V[variant];
  return <button onClick={onClick} disabled={disabled} style={{ background:disabled?"#e8dcc8":s.bg, color:disabled?"#a08060":s.color, border:disabled?"1px solid #c4b59a":s.border, borderRadius:6, padding:small?"3px 8px":"6px 14px", fontSize:small?11:13, fontWeight:700, cursor:disabled?"not-allowed":"pointer", opacity:disabled?0.6:1, fontFamily:"inherit", ...xs }}>{children}</button>;
}

// ============================================================
// ACTION PANEL
// ============================================================

function ActionPanel({ game, setGame }) {
  const phase = PHASES[game.currentPhase];
  const p = game.players[game.currentPlayerIndex];
  const c = PLAYER_COLORS[p.color];
  const wCost = getWorkerCost(game);
  const avail = p.workers.total - p.workers.placed;

  if (game.gameOver) {
    const sorted = [...game.players].sort((a,b)=>b.score-a.score);
    return (
      <div style={{ background:"#fef3c7", border:"2px solid #d97706", borderRadius:10, padding:16, textAlign:"center" }}>
        <div style={{ fontSize:24, fontWeight:800, color:"#78350f" }}>🏆 Game Over!</div>
        {sorted.map((pl,i) => (
          <div key={pl.color} style={{ display:"flex", alignItems:"center", gap:8, justifyContent:"center", padding:3, fontWeight:i===0?800:400, fontSize:i===0?18:14, color:PLAYER_COLORS[pl.color].bg }}>
            <PlayerToken color={pl.color} size={i===0?22:16} /> {pName(pl.color)}: {pl.score}VP {i===0&&"👑"}
          </div>
        ))}
        <Btn onClick={()=>setGame(null)} style={{marginTop:12}}>New Game</Btn>
      </div>
    );
  }

  if (game.currentPhase === 0) {
    return (
      <div style={{ background:`${c.bg}10`, border:`2px solid ${c.bg}44`, borderRadius:10, padding:12 }}>
        <div style={{ fontWeight:700, color:"#78350f", marginBottom:8 }}>Phase 1: Collect Income</div>
        <Btn onClick={() => setGame(processIncome(game))}>Collect Income for All Players</Btn>
      </div>
    );
  }

  if (game.currentPhase === 1) {
    return (
      <div style={{ background:`${c.bg}10`, border:`2px solid ${c.bg}`, borderRadius:10, padding:12 }}>
        <div style={{ display:"flex", alignItems:"center", gap:8, marginBottom:6 }}>
          <PlayerToken color={p.color} size={22} />
          <span style={{ fontWeight:800, fontSize:16, color:c.bg }}>{c.name}'s Turn</span>
          <span style={{ fontSize:12, color:"#78350f" }}>{avail} workers • {p.deniers}$ • Cost: {p.innOccupant?1:wCost}$</span>
        </div>
        <div style={{ fontSize:12, color:"#5c3a1e", marginBottom:8 }}>
          Click a building, special building, or castle to place a worker. Or pass.
        </div>
        <div style={{ display:"flex", gap:6 }}>
          <Btn onClick={() => setGame(processPass(game))} variant="danger">Pass</Btn>
          {avail <= 0 && <span style={{fontSize:12,color:"#dc2626",alignSelf:"center"}}>No workers — must pass</span>}
        </div>
      </div>
    );
  }

  // Gate picker — click a building on the road
  if (game.pendingGate) {
    const gc = PLAYER_COLORS[game.pendingGate.playerColor];
    const roadTargets = game.road.filter(s => s.building && !s.worker && s.building.type !== "residential" && s.building.type !== "prestige").length;
    const specials = game.pendingGate.specialTargets || [];
    const canCastle = game.pendingGate.canCastle;
    return (
      <div style={{ background:`${gc.bg}10`, border:`2px solid #0ea5e9`, borderRadius:10, padding:12 }}>
        <div style={{ display:"flex", alignItems:"center", gap:8, marginBottom:6 }}>
          <PlayerToken color={game.pendingGate.playerColor} size={22} />
          <span style={{ fontWeight:800, fontSize:15, color:gc.bg }}>{gc.name}</span>
          <span style={{ fontSize:13, color:"#78350f" }}>⛩ Gate — choose a destination</span>
        </div>
        <div style={{ fontSize:12, color:"#5c3a1e", marginBottom:8 }}>
          Click any unoccupied building on the road (highlighted in blue), or choose a special target below.
        </div>
        <div style={{ display:"flex", gap:5, flexWrap:"wrap", marginBottom:6 }}>
          {specials.map(sid => (
            <Btn key={sid} onClick={() => setGame(resolveGate(game, `special_${sid}`))} small variant="success">
              {SPECIAL_BUILDINGS.find(b=>b.id===sid)?.name || sid}
            </Btn>
          ))}
          {canCastle && (
            <Btn onClick={() => setGame(resolveGate(game, "castle"))} small variant="success">
              🏰 Castle
            </Btn>
          )}
        </div>
        <Btn onClick={() => setGame(resolveGate(game, "skip"))} variant="secondary" small>
          Skip (return worker instead)
        </Btn>
      </div>
    );
  }

  // Owner bonus picker
  if (game.pendingOwnerBonus) {
    const ob = game.pendingOwnerBonus;
    const oc = PLAYER_COLORS[ob.ownerColor];
    return (
      <div style={{ background:`${oc.bg}10`, border:`2px solid ${oc.bg}`, borderRadius:10, padding:12 }}>
        <div style={{ display:"flex", alignItems:"center", gap:8, marginBottom:6 }}>
          <PlayerToken color={ob.ownerColor} size={22} />
          <span style={{ fontWeight:800, fontSize:15, color:oc.bg }}>{oc.name}</span>
          <span style={{ fontSize:13, color:"#78350f" }}>Owner bonus — {ob.buildingName}</span>
        </div>
        <div style={{ fontSize:12, color:"#5c3a1e", marginBottom:8 }}>
          Choose 1 resource to take as building owner:
        </div>
        <div style={{ display:"flex", gap:5 }}>
          {ob.options.map(r => (
            <Btn key={r} onClick={() => setGame(resolveOwnerBonus(game, r))} small variant="success">
              +1 {RESOURCE_ICONS[r]?.symbol} {r}
            </Btn>
          ))}
        </div>
      </div>
    );
  }

  // Inn stay/leave choice
  if (game.pendingInn) {
    const ic = PLAYER_COLORS[game.pendingInn.playerColor];
    return (
      <div style={{ background:`${ic.bg}10`, border:`2px solid ${ic.bg}`, borderRadius:10, padding:12 }}>
        <div style={{ display:"flex", alignItems:"center", gap:8, marginBottom:6 }}>
          <PlayerToken color={game.pendingInn.playerColor} size={22} />
          <span style={{ fontWeight:800, fontSize:15, color:ic.bg }}>{ic.name}</span>
          <span style={{ fontSize:13, color:"#78350f" }}>🏨 Inn — stay or leave?</span>
        </div>
        <div style={{ fontSize:12, color:"#5c3a1e", marginBottom:8 }}>
          Nobody played the Inn this turn. You may stay (continue paying 1$ per worker) or leave.
        </div>
        <div style={{ display:"flex", gap:6 }}>
          <Btn onClick={() => setGame(resolveInn(game, true))} variant="success" small>Stay in Inn</Btn>
          <Btn onClick={() => setGame(resolveInn(game, false))} variant="secondary" small>Leave Inn</Btn>
        </div>
      </div>
    );
  }

  // Favor picker
  if (game.pendingFavors) {
    const pf = game.pendingFavors;
    const entry = pf.queue[pf.queueIndex];
    if (entry) {
      const fc = PLAYER_COLORS[entry.color];
      const fp = game.players.find(x => x.color === entry.color);

      // Sub-choice mode
      if (pf.subChoice) {
        return (
          <div style={{ background:`${fc.bg}10`, border:`2px solid ${fc.bg}`, borderRadius:10, padding:12 }}>
            <div style={{ display:"flex", alignItems:"center", gap:8, marginBottom:6 }}>
              <PlayerToken color={entry.color} size={22} />
              <span style={{ fontWeight:800, fontSize:15, color:fc.bg }}>{fc.name}</span>
              <span style={{ fontSize:13, color:"#78350f" }}>
                {pf.subChoice.type === "res4" ? `Pick a resource (${pf.subChoice.picks+1}/2)` : "Choose:"}
              </span>
            </div>
            <div style={{ display:"flex", gap:5, flexWrap:"wrap", marginBottom:6 }}>
              {pf.subChoice.options.map(opt => (
                <button key={opt.id} onClick={() => !opt.disabled && setGame(resolveFavorSubChoice(game, opt.id))}
                  disabled={opt.disabled}
                  style={{
                    background: opt.disabled ? "#e8dcc8" : "#fef3c7",
                    border: opt.disabled ? "1px solid #c4b59a" : "2px solid #d97706",
                    borderRadius: 8, padding: "6px 12px", fontSize: 13, fontWeight: 700,
                    cursor: opt.disabled ? "not-allowed" : "pointer", fontFamily: "inherit",
                    color: opt.disabled ? "#a08060" : "#78350f",
                    opacity: opt.disabled ? 0.5 : 1,
                  }}>
                  <div>{opt.label}</div>
                  {opt.desc && <div style={{ fontSize:10, fontWeight:400, color:"#92400e88" }}>{opt.desc}</div>}
                </button>
              ))}
              {(pf.subChoice.type === "build_favor" || pf.subChoice.type === "lawyer_favor" || pf.subChoice.type === "build_favor_prestige_target") && (
                <Btn onClick={() => setGame(resolveFavorSubChoice(game, "skip"))} variant="secondary" small>Skip</Btn>
              )}
            </div>
          </div>
        );
      }

      // Track selection mode
      const availTracks = getAvailableFavorTracks(game, entry.color, entry.tracksUsed);
      return (
        <div style={{ background:`${fc.bg}10`, border:`2px solid ${fc.bg}`, borderRadius:10, padding:12 }}>
          <div style={{ display:"flex", alignItems:"center", gap:8, marginBottom:6 }}>
            <PlayerToken color={entry.color} size={22} />
            <span style={{ fontWeight:800, fontSize:15, color:fc.bg }}>{fc.name}</span>
            <span style={{ fontSize:13, color:"#78350f" }}>
              👑 Choose a royal favor ({entry.remaining} remaining)
            </span>
          </div>
          {fp && (
            <div style={{ fontSize:11, color:"#5c3a1e", marginBottom:6, display:"flex", gap:6, flexWrap:"wrap", alignItems:"center" }}>
              <span>💰{fp.deniers}</span>
              {Object.entries(fp.resources).map(([r,ct]) => ct > 0 && <ResourceBadge key={r} type={r} count={ct} small />)}
            </div>
          )}
          <div style={{ display:"flex", gap:6, flexWrap:"wrap" }}>
            {availTracks.map(track => (
              <button key={track.key} onClick={() => setGame(resolveFavorChoice(game, track.key))}
                style={{
                  background: "#fef3c7", border: "2px solid #d97706", borderRadius: 10,
                  padding: "8px 14px", fontSize: 12, fontWeight: 700, cursor: "pointer",
                  fontFamily: "inherit", color: "#78350f", textAlign: "center",
                  minWidth: 110, boxShadow: "0 2px 6px #d9770622",
                }}>
                <div style={{ fontSize: 18, marginBottom: 2 }}>{track.icon}</div>
                <div style={{ fontWeight: 800 }}>{track.name}</div>
                <div style={{ fontSize: 10, color: "#92400e", marginTop: 2 }}>
                  {track.maxed ? "MAX (use any effect)" : `col ${track.currentLevel} → ${track.nextLevel}`}
                </div>
                <div style={{
                  marginTop: 3, fontSize: 11, fontWeight: 600,
                  background: "#fff8ee", borderRadius: 4, padding: "2px 6px",
                  color: "#78350f",
                }}>
                  {track.reward.desc}
                </div>
              </button>
            ))}
          </div>
          {availTracks.length === 0 && (
            <div style={{ fontSize: 12, color: "#dc2626" }}>No favor tracks available!</div>
          )}
        </div>
      );
    }
  }

  if (game.pendingProvost) {
    const pp = game.pendingProvost;
    const pc = PLAYER_COLORS[pp.playerColor];
    const ppPlayer = game.players.find(x => x.color === pp.playerColor);
    const currentPos = game.provostPosition;
    const isGuild = pp.type === "guild";
    const maxDelta = pp.maxDelta;
    // Build move options: -maxDelta to +maxDelta (clamped to board and affordability)
    const moveOptions = [];
    for (let d = -maxDelta; d <= maxDelta; d++) {
      const newPos = currentPos + d;
      if (newPos < 0 || newPos >= game.road.length) continue;
      const cost = isGuild ? 0 : Math.abs(d);
      if (!isGuild && d !== 0 && ppPlayer && ppPlayer.deniers < cost) continue;
      moveOptions.push({ delta: d, newPos, cost });
    }

    return (
      <div style={{ background:`${pc.bg}10`, border:`2px solid ${pc.bg}`, borderRadius:10, padding:12 }}>
        <div style={{ display:"flex", alignItems:"center", gap:8, marginBottom:6 }}>
          <PlayerToken color={pp.playerColor} size={22} />
          <span style={{ fontWeight:800, fontSize:15, color:pc.bg }}>{pc.name}</span>
          <span style={{ fontSize:13, color:"#78350f" }}>
            {isGuild ? "moves provost (Merchants' Guild)" : "may move provost"}
          </span>
        </div>
        <div style={{ fontSize:11, color:"#5c3a1e", marginBottom:6 }}>
          Provost is at position {currentPos + 1}.
          {isGuild
            ? ` Move up to ${maxDelta} spaces in either direction (free).`
            : ` Pay 1$ per space (max ${maxDelta}).`}
          {ppPlayer && !isGuild && <span> You have 💰{ppPlayer.deniers}.</span>}
        </div>

        {/* Visual provost position strip */}
        <div style={{ display:"flex", gap:2, overflowX:"auto", paddingBottom:4, marginBottom:8 }}>
          {game.road.slice(0, Math.max(currentPos + maxDelta + 2, 12)).map((slot, i) => {
            const isCurrentProvost = i === currentPos;
            const isBailiff = i === game.bailiffPosition;
            const isReachable = moveOptions.some(mo => mo.newPos === i);
            const moveDelta = i - currentPos;
            const moveCost = Math.abs(moveDelta);
            const hasWorker = slot.worker !== null;
            return (
              <div key={i}
                onClick={() => isReachable && setGame(resolveProvostMove(game, moveDelta))}
                style={{
                  width: 40, minHeight: 38, flexShrink: 0,
                  background: isCurrentProvost ? "#fef3c7" : isReachable ? "#fff8ee" : "#f0e6d2",
                  border: isCurrentProvost ? "2px solid #eab308"
                    : isReachable ? "2px solid #d97706"
                    : "1px solid #d4a57444",
                  borderRadius: 5, display: "flex", flexDirection: "column",
                  alignItems: "center", justifyContent: "center", gap: 1,
                  cursor: isReachable ? "pointer" : "default",
                  boxShadow: isReachable ? "0 0 6px #d9770633" : "none",
                  opacity: (!slot.building && !isReachable && !isCurrentProvost) ? 0.3 : 1,
                  fontSize: 9, position: "relative",
                }}>
                {isCurrentProvost && (
                  <span style={{ fontSize: 11, fontWeight: 800, color: "#92400e" }}>P</span>
                )}
                {!isCurrentProvost && isReachable && (
                  <span style={{ fontSize: 10, fontWeight: 700, color: moveDelta < 0 ? "#dc2626" : "#16a34a" }}>
                    {moveDelta > 0 ? `+${moveDelta}` : moveDelta}
                  </span>
                )}
                <span style={{ color: "#78350f", fontWeight: 600 }}>{i + 1}</span>
                {isReachable && moveDelta !== 0 && (
                  <span style={{ fontSize: 8, color: "#92400e88" }}>{isGuild ? "free" : `${moveCost}$`}</span>
                )}
                {hasWorker && (
                  <div style={{ position: "absolute", top: 1, right: 1 }}>
                    <WorkerCylinder color={slot.worker} size={6} />
                  </div>
                )}
                {isBailiff && (
                  <span style={{ position: "absolute", bottom: 0, fontSize: 7, background: "#475569", color: "#fff", borderRadius: 2, padding: "0 2px", fontWeight: 800 }}>B</span>
                )}
              </div>
            );
          })}
        </div>

        <div style={{ display:"flex", gap:6, flexWrap:"wrap" }}>
          <Btn onClick={() => setGame(resolveProvostMove(game, 0))} variant="secondary" small>
            Don't move provost
          </Btn>
          {moveOptions.filter(mo => mo.delta !== 0).map(mo => (
            <Btn key={mo.delta} onClick={() => setGame(resolveProvostMove(game, mo.delta))} small
              variant={mo.delta < 0 ? "danger" : "success"}>
              {mo.delta > 0 ? `+${mo.delta} forward` : `${mo.delta} backward`}{isGuild ? "" : ` (${mo.cost}$)`}
            </Btn>
          ))}
        </div>
      </div>
    );
  }

  if (game.currentPhase === 4 && game.pendingActivation) {
    const pa = game.pendingActivation;
    const ac = PLAYER_COLORS[pa.workerColor];
    const actPlayer = game.players.find(x => x.color === pa.workerColor);
    return (
      <div style={{ background:`${ac.bg}10`, border:`2px solid ${ac.bg}`, borderRadius:10, padding:12 }}>
        <div style={{ display:"flex", alignItems:"center", gap:8, marginBottom:6 }}>
          <PlayerToken color={pa.workerColor} size={22} />
          <span style={{ fontWeight:800, fontSize:15, color:ac.bg }}>{ac.name}</span>
          <span style={{ fontSize:13, color:"#78350f" }}>activates <strong>{pa.buildingName}</strong></span>
        </div>
        {actPlayer && (
          <div style={{ fontSize:11, color:"#5c3a1e", marginBottom:6, display:"flex", gap:6, flexWrap:"wrap", alignItems:"center" }}>
            <span>💰{actPlayer.deniers}</span>
            {Object.entries(actPlayer.resources).map(([r,ct]) => ct > 0 && <ResourceBadge key={r} type={r} count={ct} small />)}
          </div>
        )}
        {pa.buyRemaining != null && pa.buyRemaining < pa.buyMax && (
          <div style={{ fontSize:12, color:"#16a34a", fontWeight:600, marginBottom:4 }}>
            Buy another? ({pa.buyRemaining} remaining)
          </div>
        )}
        <div style={{ display:"flex", gap:5, flexWrap:"wrap", marginBottom:6 }}>
          {pa.choices.map(ch => (
            <button key={ch.id} onClick={() => !ch.disabled && setGame(resolveActivation(game, ch.id))}
              disabled={ch.disabled}
              title={ch.desc || ch.label}
              style={{
                background: ch.disabled ? "#e8dcc8" : pa.effectType === "build" ? (TC[pa.buildType]?.bg || "#fef3c7") : "#fef3c7",
                border: ch.disabled ? "1px solid #c4b59a" : "2px solid #d97706",
                borderRadius: 8, padding: "6px 12px", fontSize: 12, fontWeight: 700,
                cursor: ch.disabled ? "not-allowed" : "pointer", fontFamily: "inherit",
                color: ch.disabled ? "#a08060" : "#78350f",
                opacity: ch.disabled ? 0.5 : 1,
                minWidth: pa.effectType === "build" ? 140 : "auto",
                textAlign: "left",
              }}>
              <div>{ch.label}</div>
              {ch.desc && <div style={{ fontSize:10, fontWeight:400, color:"#92400e88", marginTop:1 }}>{ch.desc}</div>}
            </button>
          ))}
        </div>
        {(pa.canSkip || pa.choices.length === 0) && (
          <Btn onClick={() => setGame(resolveActivation(game, "skip"))} variant="secondary" small>
            {pa.choices.length === 0 ? "No options — Skip" : "Skip (don't use)"}
          </Btn>
        )}
      </div>
    );
  }

  // Castle batch picker
  if (game.pendingCastle) {
    const cc = PLAYER_COLORS[game.pendingCastle.playerColor];
    const castlePlayer = game.players.find(x => x.color === game.pendingCastle.playerColor);
    const batchOptions = castlePlayer ? getCastleBatchOptions(castlePlayer, game) : [];
    const hasGivenSome = game.castlePhase?.housesThisTurn[game.pendingCastle.playerColor] > 0;
    const sec = game.castle.currentSection;
    return (
      <div style={{ background:`${cc.bg}10`, border:`2px solid ${cc.bg}`, borderRadius:10, padding:12 }}>
        <div style={{ display:"flex", alignItems:"center", gap:8, marginBottom:6 }}>
          <PlayerToken color={game.pendingCastle.playerColor} size={22} />
          <span style={{ fontWeight:800, fontSize:15, color:cc.bg }}>{cc.name}</span>
          <span style={{ fontSize:13, color:"#78350f" }}>
            🏰 Castle — contribute a batch to {CASTLE_SECTIONS[sec].name}
            {hasGivenSome && ` (${game.castlePhase.housesThisTurn[game.pendingCastle.playerColor]} so far)`}
          </span>
        </div>
        {castlePlayer && (
          <div style={{ fontSize:11, color:"#5c3a1e", marginBottom:6, display:"flex", gap:6, flexWrap:"wrap", alignItems:"center" }}>
            <span>💰{castlePlayer.deniers}</span>
            {Object.entries(castlePlayer.resources).map(([r,ct]) => ct > 0 && <ResourceBadge key={r} type={r} count={ct} small />)}
          </div>
        )}
        <div style={{ fontSize:11, color:"#5c3a1e", marginBottom:6 }}>
          A batch = 1 food + 2 different cubes. Pick which cubes to contribute:
        </div>
        <div style={{ display:"flex", gap:5, flexWrap:"wrap", marginBottom:6 }}>
          {batchOptions.map(([r1, r2]) => (
            <button key={`${r1}_${r2}`}
              onClick={() => setGame(resolveCastleBatch(game, r1, r2))}
              style={{
                background: "#fef3c7", border: "2px solid #d97706", borderRadius: 8,
                padding: "6px 12px", fontSize: 12, fontWeight: 700, cursor: "pointer",
                fontFamily: "inherit", color: "#78350f",
              }}>
              {RESOURCE_ICONS.food.symbol} + {RESOURCE_ICONS[r1].symbol} + {RESOURCE_ICONS[r2].symbol}
              <div style={{ fontSize:9, color:"#92400e88" }}>food + {r1} + {r2}</div>
            </button>
          ))}
        </div>
        <Btn onClick={() => setGame(skipCastleBatch(game))} variant={hasGivenSome ? "secondary" : "danger"} small>
          {hasGivenSome ? "Done (stop contributing)" : "Can't/Won't contribute (-2VP)"}
        </Btn>
      </div>
    );
  }

  return null;
}

// ============================================================
// BOARD PANELS
// ============================================================

function PhaseTracker({ currentPhase }) {
  return (
    <div style={{ display:"flex", gap:3, flexWrap:"wrap" }}>
      {PHASES.map((ph,i) => (
        <div key={ph.id} style={{ padding:"3px 8px", borderRadius:6, fontSize:11, fontWeight:700, background:i===currentPhase?"#92400e":"transparent", color:i===currentPhase?"#fef3c7":"#92400e66", border:i===currentPhase?"1px solid #78350f":"1px solid transparent" }}>{ph.name}</div>
      ))}
    </div>
  );
}

function SpecialBuildingsPanel({ game, setGame }) {
  const active = game.currentPhase === 1;
  const p = game.players[game.currentPlayerIndex];
  const handle = (id) => {
    if (!active || p.passed || !canPlaceOnSpecial(game, id, p.color)) return;
    const r = placeWorkerOnSpecial(game, id);
    if (r) setGame(r);
  };
  return (
    <div style={{ background:"rgba(120,80,40,0.06)", borderRadius:10, padding:10, border:"1px solid #d4a57444" }}>
      <div style={{ fontSize:12, fontWeight:700, color:"#78350f", marginBottom:6, letterSpacing:1 }}>⚜ SPECIAL BUILDINGS</div>
      <div style={{ display:"flex", gap:5, flexWrap:"wrap" }}>
        {SPECIAL_BUILDINGS.map(sb => {
          const can = active && !p.passed && canPlaceOnSpecial(game, sb.id, p.color);
          return (
            <div key={sb.id} onClick={()=>handle(sb.id)} title={sb.description} style={{
              background:can?"#fff8ee":"#f5ead6", border:can?"2px solid #d97706":"1.5px solid #c4995a88",
              borderRadius:6, padding:"5px 8px", minWidth:74, textAlign:"center",
              cursor:can?"pointer":"default", boxShadow:can?"0 0 8px #d9770644":"none", fontSize:11,
            }}>
              <div style={{ fontWeight:700, color:"#78350f", marginBottom:3 }}>{sb.name}</div>
              {sb.id==="stables" && (
                <div style={{display:"flex",gap:2,justifyContent:"center"}}>
                  {game.specialState.stables.map((s,i)=>(
                    <div key={i} style={{ width:16,height:16,borderRadius:"50%", border:s?"none":"1.5px dashed #92400e44", background:s?PLAYER_COLORS[s]?.bg:"transparent", display:"flex",alignItems:"center",justifyContent:"center" }}>
                      {!s&&<span style={{fontSize:8,color:"#92400e66"}}>{i+1}</span>}
                    </div>
                  ))}
                </div>
              )}
              {sb.id==="inn" && (
                <div style={{display:"flex",gap:2,justifyContent:"center",alignItems:"center"}}>
                  <div style={{ width:16,height:16,borderRadius:"50%", border:game.specialState.inn.left?"none":"1.5px dashed #92400e44", background:game.specialState.inn.left?PLAYER_COLORS[game.specialState.inn.left]?.bg:"transparent" }} />
                  <span style={{fontSize:8,color:"#92400e66"}}>→</span>
                  <div style={{ width:16,height:16,borderRadius:"50%", border:game.specialState.inn.right?"none":"1.5px dashed #92400e44", background:game.specialState.inn.right?PLAYER_COLORS[game.specialState.inn.right]?.bg:"transparent" }} />
                </div>
              )}
              {sb.id!=="stables"&&sb.id!=="inn"&&(
                <div style={{ width:16,height:16,borderRadius:"50%",margin:"0 auto", border:game.specialState[sb.id]?.worker?"none":"1.5px dashed #92400e44", background:game.specialState[sb.id]?.worker?PLAYER_COLORS[game.specialState[sb.id].worker]?.bg:"transparent" }} />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function RoadPanel({ game, setGame }) {
  const active = game.currentPhase === 1;
  const p = game.players[game.currentPlayerIndex];
  const gateMode = !!game.pendingGate;
  const lastBuilt = game.road.reduce((m,s,i) => s.building ? i : m, 7);
  const visible = game.road.slice(0, Math.min(lastBuilt + 4, game.road.length));
  const handle = (i) => {
    if (gateMode) {
      const slot = game.road[i];
      if (slot.building && !slot.worker && slot.building.type !== "residential" && slot.building.type !== "prestige") {
        setGame(resolveGate(game, i));
      }
      return;
    }
    if (!active || p.passed || !canPlaceOnRoadSlot(game, i, p.color)) return;
    const r = placeWorkerOnRoad(game, i);
    if (r) setGame(r);
  };
  return (
    <div style={{ background:"rgba(120,80,40,0.06)", borderRadius:10, padding:10, border:"1px solid #d4a57444" }}>
      <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:6 }}>
        <span style={{ fontSize:12, fontWeight:700, color:"#78350f", letterSpacing:1 }}>🛤️ THE ROAD</span>
        <span style={{ fontSize:10, color:"#92400e88" }}>B:{game.bailiffPosition+1} P:{game.provostPosition+1}</span>
      </div>
      <div style={{ display:"flex", gap:4, overflowX:"auto", paddingBottom:6 }}>
        {visible.map((slot,i) => {
          const b = slot.building;
          const ti = b ? TC[b.type]||TC.empty : TC.empty;
          const can = active && !p.passed && canPlaceOnRoadSlot(game, i, p.color);
          const isGateTarget = gateMode && b && !slot.worker && b.type !== "residential" && b.type !== "prestige";
          const beyond = i > game.provostPosition;
          const isActivating = game.pendingActivation && game.pendingActivation.roadIndex === i;
          const highlight = can || isGateTarget;
          return (
            <div key={i} style={{flexShrink:0}} onClick={()=>handle(i)}>
              <div style={{
                width:76, minHeight:68,
                background: isActivating ? "#fefce8" : isGateTarget ? "#e0f2fe" : can ? "#fff8ee" : ti.bg,
                border: isActivating ? "2px solid #eab308"
                  : isGateTarget ? "2px solid #0ea5e9"
                  : can ? "2px solid #d97706"
                  : slot.worker ? `2px solid ${PLAYER_COLORS[slot.worker]?.bg}` : `1.5px solid ${ti.border}`,
                borderRadius:6, padding:3, position:"relative", display:"flex", flexDirection:"column",
                alignItems:"center", justifyContent:"center", gap:1,
                opacity:!b?0.35:beyond?0.5:1, cursor: highlight ? "pointer" : "default",
                boxShadow: isActivating ? "0 0 12px #eab30866"
                  : isGateTarget ? "0 0 10px #0ea5e944"
                  : can ? "0 0 8px #d9770644" : "0 1px 3px rgba(0,0,0,0.08)",
                fontSize:10,
              }}>
                {b ? (<>
                  <div style={{fontWeight:700,textAlign:"center",lineHeight:1.1,color:"#3d2a14"}}>{b.name}</div>
                  {b.cost && <div style={{display:"flex",gap:1,flexWrap:"wrap",justifyContent:"center"}}>{Object.entries(b.cost).map(([r,c])=><ResourceBadge key={r} type={r} count={c} small/>)}</div>}
                  {b.vp && <div style={{position:"absolute",top:1,right:2,background:"#fbbf24",color:"#78350f",borderRadius:3,padding:"0 2px",fontSize:9,fontWeight:800}}>+{b.vp}</div>}
                  {slot.worker && <div style={{position:"absolute",bottom:1,left:3}}><WorkerCylinder color={slot.worker} size={9}/></div>}
                  {slot.house && <div style={{position:"absolute",top:1,left:3}}><HousePiece color={slot.house} size={7}/></div>}
                  {isGateTarget && <div style={{position:"absolute",bottom:1,right:2,fontSize:8,fontWeight:800,color:"#0ea5e9"}}>⛩</div>}
                </>) : <span style={{color:"#a08060",fontSize:16}}>+</span>}
              </div>
              <div style={{display:"flex",gap:1,justifyContent:"center",marginTop:1,height:13}}>
                {i===game.bailiffPosition&&<span style={{fontSize:8,background:"#fff",border:"1px solid #475569",borderRadius:2,padding:"0 2px",fontWeight:800,color:"#475569"}}>B</span>}
                {i===game.provostPosition&&<span style={{fontSize:8,background:"#fef3c7",border:"1px solid #92400e",borderRadius:2,padding:"0 2px",fontWeight:800,color:"#92400e"}}>P</span>}
              </div>
              <div style={{fontSize:8,textAlign:"center",color:"#a08060"}}>{i+1}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function CastlePanel({ game, setGame }) {
  const active = game.currentPhase === 1;
  const p = game.players[game.currentPlayerIndex];
  const can = active && !p.passed && canPlaceInCastle(game, p.color);
  const handle = () => { if (!can) return; const r = placeWorkerInCastle(game); if (r) setGame(r); };
  const secs = [
    { key:"dungeon", ...CASTLE_SECTIONS.dungeon, parts:game.castle.dungeon, counted:game.castle.dungeonCounted },
    { key:"walls", ...CASTLE_SECTIONS.walls, parts:game.castle.walls, counted:game.castle.wallsCounted },
    { key:"towers", ...CASTLE_SECTIONS.towers, parts:game.castle.towers, counted:game.castle.towersCounted },
  ];
  return (
    <div style={{ background:"rgba(120,80,40,0.06)", borderRadius:10, padding:10, border:"1px solid #d4a57444" }}>
      <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:6 }}>
        <span style={{ fontSize:12, fontWeight:700, color:"#78350f", letterSpacing:1 }}>🏰 CASTLE</span>
        {can && <Btn onClick={handle} small variant="success">Place Worker ({p.innOccupant?1:getWorkerCost(game)}$)</Btn>}
      </div>
      <div style={{ display:"flex", gap:8, flexWrap:"wrap" }}>
        {secs.map(s=>(
          <div key={s.key} style={{ background:s.key===game.castle.currentSection?"#fef3c7":"#f5ead6", border:s.key===game.castle.currentSection?"2px solid #d97706":"1px solid #d4a57444", borderRadius:8, padding:6, minWidth:100 }}>
            <div style={{fontWeight:700,fontSize:11,color:"#78350f",marginBottom:3,textAlign:"center"}}>
              {s.name} ({s.parts.filter(x=>x!==null).length}/{s.capacity}){s.counted&&<span style={{color:"#16a34a",marginLeft:3}}>✓</span>}
            </div>
            <div style={{display:"flex",flexWrap:"wrap",gap:2,justifyContent:"center"}}>
              {s.parts.map((pt,i)=>(
                <div key={i} style={{ width:14,height:14,borderRadius:3, border:pt?"none":"1px dashed #c4995a55", background:pt?PLAYER_COLORS[pt]?.bg:"transparent" }} />
              ))}
            </div>
            <div style={{fontSize:9,color:"#92400e88",textAlign:"center",marginTop:2}}>+{s.vpPerBatch}VP/batch</div>
          </div>
        ))}
      </div>
      {game.castle.workers.length>0&&(
        <div style={{marginTop:4,fontSize:10,color:"#78350f",display:"flex",gap:3,alignItems:"center"}}>
          Workers: {game.castle.workers.map((w,i)=><WorkerCylinder key={i} color={w} size={9}/>)}
        </div>
      )}
    </div>
  );
}

function PlayerPanel({ player, isActive }) {
  const c = PLAYER_COLORS[player.color];
  const avail = player.workers.total - player.workers.placed;
  return (
    <div style={{
      background:isActive?`${c.bg}12`:"#faf5eb", border:isActive?`2px solid ${c.bg}`:"1px solid #d4a57444",
      borderRadius:8, padding:8, minWidth:160, flex:"1 1 160px",
      boxShadow:isActive?`0 0 10px ${c.bg}33`:"none",
    }}>
      <div style={{display:"flex",alignItems:"center",gap:5,marginBottom:4}}>
        <PlayerToken color={player.color} size={18}/>
        <span style={{fontWeight:800,color:c.bg,fontSize:13}}>{c.name}</span>
        <span style={{fontSize:10,color:"#92400e88"}}>#{player.turnOrder+1}</span>
        {player.passed&&<span style={{fontSize:9,background:"#fee2e2",color:"#dc2626",borderRadius:3,padding:"0 3px",fontWeight:700}}>PASS</span>}
        {player.innOccupant&&<span style={{fontSize:9,background:"#dbeafe",color:"#2563eb",borderRadius:3,padding:"0 3px",fontWeight:700}}>INN</span>}
      </div>
      <div style={{display:"flex",alignItems:"center",gap:4,marginBottom:3}}>
        <span style={{fontWeight:800,fontSize:16,color:"#78350f",background:"#fef3c7",borderRadius:4,padding:"1px 6px"}}>{player.score}VP</span>
        <span style={{fontWeight:700,fontSize:13,color:"#92400e",background:"#fef3c7",borderRadius:4,padding:"1px 5px",border:"1px solid #f59e0b55"}}>💰{player.deniers}</span>
      </div>
      <div style={{display:"flex",gap:2,flexWrap:"wrap",marginBottom:3}}>
        {Object.entries(player.resources).map(([r,ct])=><ResourceBadge key={r} type={r} count={ct} small/>)}
      </div>
      <div style={{fontSize:10,color:"#78350f",display:"flex",gap:2,alignItems:"center"}}>
        Workers: {Array.from({length:avail}).map((_,i)=><WorkerCylinder key={i} color={player.color} size={7}/>)}
        {avail===0&&<span style={{color:"#92400e88"}}>none</span>}
      </div>
    </div>
  );
}

function FavorTablePanel({ game }) {
  const fca = game.favorColumnsAvailable;
  return (
    <div style={{ background:"rgba(120,80,40,0.06)", borderRadius:10, padding:10, border:"1px solid #d4a57444" }}>
      <div style={{ fontSize:12, fontWeight:700, color:"#78350f", marginBottom:4 }}>👑 ROYAL FAVORS</div>
      <table style={{ borderCollapse:"collapse", fontSize:10, width:"100%" }}>
        <thead><tr>
          <th style={{textAlign:"left",padding:"2px 4px",color:"#78350f"}}>Track</th>
          {[1,2,3,4,5].map(n=><th key={n} style={{padding:"2px 4px",color:"#78350f",textAlign:"center",opacity:n<=fca?1:0.25,background:n<=fca?"#fef3c7":"transparent",borderRadius:3}}>{n}</th>)}
        </tr></thead>
        <tbody>
          {Object.entries(FAVOR_TRACKS).map(([k,t])=>(
            <tr key={k}>
              <td style={{padding:"2px 4px",fontWeight:600,color:"#78350f"}}>{t.icon} {t.name}</td>
              {t.levels.map((l,i)=>(
                <td key={i} style={{padding:"2px 4px",textAlign:"center",opacity:i<fca?1:0.25,color:"#5c3a1e",position:"relative"}}>
                  <div>{l.label}</div>
                  <div style={{display:"flex",gap:1,justifyContent:"center",marginTop:1}}>
                    {game.players.filter(p => p.favors[k] === i+1).map(p => (
                      <div key={p.color} style={{width:8,height:8,borderRadius:"50%",background:PLAYER_COLORS[p.color]?.bg,border:`1px solid ${PLAYER_COLORS[p.color]?.light}`}} />
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

function BuildingStockPanel({ buildingStock }) {
  return (
    <div style={{ background:"rgba(120,80,40,0.06)", borderRadius:10, padding:10, border:"1px solid #d4a57444" }}>
      <div style={{ fontSize:12, fontWeight:700, color:"#78350f", marginBottom:4 }}>📋 BUILDING STOCK</div>
      <div style={{ display:"flex", gap:10, flexWrap:"wrap" }}>
        {Object.entries(buildingStock).map(([type, buildings]) => (
          <div key={type}>
            <div style={{fontSize:10,fontWeight:700,color:TC[type].border,marginBottom:2,textTransform:"capitalize"}}>{type} ({buildings.length})</div>
            <div style={{display:"flex",gap:2,flexWrap:"wrap",maxWidth:260}}>
              {buildings.map(b=><div key={b.id} title={b.description||b.name} style={{background:TC[type].bg,border:`1px solid ${TC[type].border}`,borderRadius:3,padding:"1px 4px",fontSize:9,fontWeight:600,color:"#3d2a14"}}>{b.name}</div>)}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function GameLog({ log }) {
  return (
    <div style={{ background:"rgba(120,80,40,0.06)", borderRadius:10, padding:10, border:"1px solid #d4a57444" }}>
      <div style={{ fontSize:12, fontWeight:700, color:"#78350f", marginBottom:4 }}>📜 LOG</div>
      <div style={{ maxHeight:200, overflowY:"auto", fontSize:11, color:"#5c3a1e", lineHeight:1.4 }}>
        {log.map((e,i)=><div key={i} style={{ borderBottom:"1px solid #d4a57411", padding:"1px 0", fontWeight:e.startsWith("━")||e.startsWith("🏰")||e.startsWith("🏁")||e.startsWith("🏆")?700:400, color:e.startsWith("━")?"#78350f":e.startsWith("—")?"#92400e":"#5c3a1e" }}>{e}</div>)}
      </div>
    </div>
  );
}

// ============================================================
// SETUP + GAME BOARD + APP
// ============================================================

function SetupScreen({ onStart }) {
  const [n, setN] = useState(3);
  return (
    <div style={{maxWidth:480,margin:"0 auto",textAlign:"center",padding:40}}>
      <div style={{fontSize:48,marginBottom:8}}>🏰</div>
      <h1 style={{fontFamily:"'Cinzel','Palatino Linotype','Book Antiqua',serif",fontSize:40,color:"#78350f",margin:"0 0 4px",textShadow:"0 2px 4px rgba(120,80,40,0.15)"}}>CAYLUS</h1>
      <p style={{fontFamily:"'Crimson Text','Georgia',serif",fontSize:15,color:"#92400e",fontStyle:"italic",margin:"0 0 28px"}}>Build the King's castle and earn his favor</p>
      <div style={{background:"#faf5eb",border:"2px solid #d4a574",borderRadius:12,padding:20,textAlign:"left"}}>
        <label style={{display:"block",fontWeight:700,fontSize:13,color:"#78350f",marginBottom:6}}>Number of Players</label>
        <div style={{display:"flex",gap:6,marginBottom:16}}>
          {[2,3,4,5].map(x=><button key={x} onClick={()=>setN(x)} style={{width:44,height:44,borderRadius:8,fontSize:18,fontWeight:800,border:x===n?"2px solid #92400e":"2px solid #d4a57466",background:x===n?"#92400e":"#fef3c7",color:x===n?"#fef3c7":"#92400e",cursor:"pointer",fontFamily:"inherit"}}>{x}</button>)}
        </div>
        <div style={{marginBottom:16}}>
          <div style={{fontSize:11,fontWeight:600,color:"#92400e88",marginBottom:4}}>PLAYERS</div>
          <div style={{display:"flex",gap:6,flexWrap:"wrap"}}>
            {Object.keys(PLAYER_COLORS).slice(0,n).map(color=>{const c=PLAYER_COLORS[color]; return <div key={color} style={{display:"flex",alignItems:"center",gap:4,background:`${c.bg}15`,border:`1.5px solid ${c.bg}`,borderRadius:6,padding:"3px 8px"}}><PlayerToken color={color}/><span style={{fontSize:12,fontWeight:600,color:c.bg}}>{c.name}</span></div>;})}
          </div>
        </div>
        <button onClick={()=>onStart(n)} style={{width:"100%",padding:"10px 20px",borderRadius:8,background:"linear-gradient(135deg,#92400e,#78350f)",color:"#fef3c7",fontSize:15,fontWeight:800,border:"none",cursor:"pointer",fontFamily:"inherit",boxShadow:"0 4px 12px rgba(120,53,15,0.3)",letterSpacing:1}}>BEGIN CONSTRUCTION ⚒</button>
      </div>
    </div>
  );
}

function GameBoard({ game, setGame }) {
  const cp = game.players[game.currentPlayerIndex];
  return (
    <div style={{display:"flex",flexDirection:"column",gap:8}}>
      <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",flexWrap:"wrap",gap:6}}>
        <div>
          <h1 style={{fontFamily:"'Cinzel','Palatino Linotype','Book Antiqua',serif",fontSize:22,color:"#78350f",margin:0}}>🏰 CAYLUS</h1>
          <span style={{fontSize:11,color:"#92400e88"}}>Turn {game.turn}</span>
        </div>
        <PhaseTracker currentPhase={game.currentPhase} />
      </div>
      <ActionPanel game={game} setGame={setGame} />
      <div style={{display:"flex",gap:3,alignItems:"center",padding:"2px 8px",fontSize:11,color:"#78350f"}}>
        <span style={{fontWeight:700,marginRight:3}}>Pass:</span>
        {game.passingScale.map((ps,i)=>(
          <div key={i} style={{width:24,height:24,borderRadius:5,border:ps?`2px solid ${PLAYER_COLORS[ps].bg}`:"1.5px dashed #c4995a44",background:ps?`${PLAYER_COLORS[ps].bg}22`:"transparent",display:"flex",alignItems:"center",justifyContent:"center",fontSize:10,fontWeight:700,color:"#92400e"}}>
            {ps?<PlayerToken color={ps} size={12}/>:i+1}
          </div>
        ))}
        <span style={{fontSize:9,color:"#92400e66",marginLeft:3}}>Cost={getWorkerCost(game)}$</span>
      </div>
      <div style={{display:"flex",gap:6,flexWrap:"wrap"}}>
        {game.players.map((pl,i)=><PlayerPanel key={pl.color} player={pl} isActive={i===game.currentPlayerIndex&&!game.gameOver}/>)}
      </div>
      <SpecialBuildingsPanel game={game} setGame={setGame} />
      <RoadPanel game={game} setGame={setGame} />
      <CastlePanel game={game} setGame={setGame} />
      <div style={{display:"flex",gap:8,flexWrap:"wrap"}}>
        <div style={{flex:"1 1 300px"}}><FavorTablePanel game={game}/></div>
        <div style={{flex:"1 1 300px"}}><BuildingStockPanel buildingStock={game.buildingStock}/></div>
      </div>
      <GameLog log={game.log} />
    </div>
  );
}

export default function CaylusApp() {
  const [game, setGame] = useState(null);
  return (
    <div style={{minHeight:"100vh",background:"linear-gradient(160deg,#faf5eb 0%,#f0e6d2 50%,#e8dcc8 100%)",fontFamily:"'Crimson Text','Georgia',serif",color:"#3d2a14"}}>
      <style>{`@import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@400;600;800&family=Crimson+Text:ital,wght@0,400;0,600;0,700;1,400&display=swap');*{box-sizing:border-box;}::-webkit-scrollbar{height:5px;width:5px;}::-webkit-scrollbar-track{background:transparent;}::-webkit-scrollbar-thumb{background:#c4995a55;border-radius:3px;}`}</style>
      <div style={{maxWidth:1100,margin:"0 auto",padding:"12px 10px"}}>
        {!game ? <SetupScreen onStart={(n)=>setGame(initializeGame(n))}/> : <GameBoard game={game} setGame={setGame}/>}
      </div>
    </div>
  );
}
