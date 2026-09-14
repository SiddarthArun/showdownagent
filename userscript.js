// ==UserScript==
// @name         Showdown State Reader
// @match        https://play.pokemonshowdown.com/*
// @grant        GM_xmlhttpRequest
// @connect      localhost
// ==/UserScript==

(function () {
  let lastSent = "";

  function summarizeFoe(mon) {
    if (!mon) return null;
    return {
      species: mon.speciesForme,
      item: mon.item || null,
      level: mon.level,
      hp: mon.hp,
      maxhp: mon.maxhp,
      status: mon.status,
      fainted: mon.fainted,
      boosts: mon.boosts || {},
      revealed_moves: (mon.moveTrack || []).map(m => m[0]),
    };
  }

  function readState() {
    const room = unsafeWindow.app && unsafeWindow.app.curRoom;
    if (!room || !room.battle) return null;
    const battle = room.battle;

    return {
      turn: battle.turn,
      title: room.title,
      request: room.request || null,
      my_team: battle.myPokemon || null,
      opp_active: summarizeFoe(battle.farSide.active && battle.farSide.active[0]),
      opp_team: (battle.farSide.pokemon || []).map(summarizeFoe),
      my_boosts: (battle.mySide.active[0] && battle.mySide.active[0].boosts) || {},
      my_side_conditions: battle.mySide.sideConditions || {},
      opp_side_conditions: battle.farSide.sideConditions || {},
    };
  }

  setInterval(() => {
    const state = readState();
    if (!state) return;

    const serialized = JSON.stringify(state);
    if (serialized === lastSent) return;
    lastSent = serialized;

    GM_xmlhttpRequest({
      method: "POST",
      url: "http://localhost:8000/state",
      data: serialized,
      headers: { "Content-Type": "application/json" },
    });
  }, 1000);
})();