def build_state(raw: dict) -> dict | None:
    """Convert a userscript payload into the state shape used by the coach."""
    if not isinstance(raw, dict):
        return None

    req = raw.get("request")
    turn = raw.get("turn")
    title = raw.get("title")
    if not title or not isinstance(req, dict) or not isinstance(turn, int):
        return None  # page mid-load, not a real battle turn yet

    my_team = {}
    side = req.get("side") or {}
    for mon in side.get("pokemon") or []:
        details = mon.get("details") if isinstance(mon, dict) else None
        if not details:
            continue
        species = details.split(",", 1)[0].strip()
        if not species:
            continue
        my_team[species] = {
            "active": mon.get("active", False),
            "condition": mon.get("condition") or "",
            "item": mon.get("item") or None,
            "ability": mon.get("ability") or mon.get("baseAbility"),
            "stats": mon.get("stats"),
            "moves": mon.get("moves", []),
        }

    active_req = (req.get("active") or [{}])[0]
    active_species = next((s for s, m in my_team.items() if m["active"]), None)
    if active_species and isinstance(active_req, dict) and active_req.get("moves"):
        my_team[active_species]["moves"] = [
            {
                "move": move.get("move"),
                "pp": move.get("pp", 0),
                "maxpp": move.get("maxpp", 0),
                "disabled": move.get("disabled", False),
            }
            for move in active_req["moves"]
            if isinstance(move, dict) and move.get("move")
        ]

    if not my_team or not active_species:
        return None

    opponent_team = {}
    for mon in raw.get("opp_team") or []:
        if isinstance(mon, dict) and mon.get("species"):
            opponent_team[mon["species"]] = mon

    return {
        "turn": turn,
        "title": title,
        "my_team": my_team,
        "my_boosts": raw.get("my_boosts", {}),
        "my_side_conditions": raw.get("my_side_conditions", {}),
        "opp_side_conditions": raw.get("opp_side_conditions", {}),
        "opponent": {
            "active": raw.get("opp_active"),
            "team": opponent_team,
        },
    }