def build_state(raw: dict) -> dict | None:
    req = raw.get("request")
    if not raw.get("title") or not req:
        return None  # page mid-load, not a real battle turn yet

    side = req.get("side", {})
    my_team = {}
    for mon in side.get("pokemon", []):
        species = mon["details"].split(",")[0]
        my_team[species] = {
            "active": mon.get("active", False),
            "condition": mon.get("condition"),
            "item": mon.get("item") or None,
            "ability": mon.get("ability") or mon.get("baseAbility"),
            "stats": mon.get("stats"),
            "moves": mon.get("moves", []),
        }

    active_req = (req.get("active") or [{}])[0]
    active_species = next((s for s, m in my_team.items() if m["active"]), None)
    if active_species and active_req.get("moves"):
        my_team[active_species]["moves"] = [
            {
                "move": m["move"],
                "pp": m["pp"],
                "maxpp": m["maxpp"],
                "disabled": m.get("disabled", False),
            }
            for m in active_req["moves"]
        ]

    return {
        "turn": raw["turn"],
        "title": raw["title"],
        "my_team": my_team,
        "my_boosts": raw.get("my_boosts", {}),
        "my_side_conditions": raw.get("my_side_conditions", {}),
        "opp_side_conditions": raw.get("opp_side_conditions", {}),
        "opponent": {
            "active": raw.get("opp_active"),
            "team": {mon["species"]: mon for mon in (raw.get("opp_team") or []) if mon},
        },
    }