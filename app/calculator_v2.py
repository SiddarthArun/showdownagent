import json
from app.config import DATA_DIR

with open(DATA_DIR/"pokedex.json") as f:
    POKEDEX = json.load(f)
with open(DATA_DIR/"moves.json") as f:
    MOVES = {"".join(c for c in m["name"].lower() if c.isalnum()): m for m in json.load(f)}
with open(DATA_DIR/"typechart.json") as f:
    TYPECHART = json.load(f)

TYPE_MULT = {0: 1, 1: 2, 2: 0.5, 3: 0}

def _id(name):
    return "".join(c for c in name.lower() if c.isalnum())

def get_species(name):
    return POKEDEX.get(_id(name))

def type_effectiveness(move_type, defender_types):
    mult = 1.0
    for t in defender_types:
        code = TYPECHART.get(t.lower(), {}).get("damageTaken", {}).get(move_type, 0)
        mult *= TYPE_MULT.get(code, 1)
    return mult

def boost_multiplier(stage):
    stage = max(-6, min(6, stage or 0))
    return (2 + stage) / 2 if stage >= 0 else 2 / (2 - stage)

def calc_stat(base: int, is_hp: bool = False, level: int = 100, iv: int = 31, ev: int = 0, nature: float = 1.0) -> int:
    core = int((2 * base + iv + ev // 4) * level / 100)
    return core + level + 10 if is_hp else int((core + 5) * nature)

def estimate_damage_pct(attacker_species, attacker_stats, move_name, defender_species, level=100, atk_boost=0, def_boost=0):
    move = MOVES.get(_id(move_name))
    atk_dex = get_species(attacker_species)
    def_dex = get_species(defender_species)
    if not move or not move.get("power") or not atk_dex or not def_dex:
        return None

    power = int(move["power"])
    move_type = move["type"]
    physical = move["category"] == "Physical"

    atk_stat = (attacker_stats.get("atk" if physical else "spa") if attacker_stats
                else calc_stat(atk_dex["baseStats"]["atk" if physical else "spa"]))
    def_stat = calc_stat(def_dex["baseStats"]["def" if physical else "spd"])
    atk_stat *= boost_multiplier(atk_boost)
    def_stat *= boost_multiplier(def_boost)

    stab = 1.5 if move_type in atk_dex["types"] else 1.0
    eff = type_effectiveness(move_type, def_dex["types"])
    if eff == 0:
        return (0.0, 0.0)

    base = ((2 * level / 5 + 2) * power * atk_stat / def_stat) / 50 + 2
    def_hp = def_dex["baseStats"]["hp"]
    max_hp_est = int((2 * def_hp + 31) * level / 100) + level + 10

    return (base * stab * eff * 0.85 / max_hp_est * 100, base * stab * eff / max_hp_est * 100)

def analyze_matchup(state: dict) -> dict:
    my_species = next((s for s, m in state["my_team"].items() if m["active"]), None)
    opp = state["opponent"]["active"]
    if not my_species or not opp:
        return {}

    my_stats = state["my_team"][my_species].get("stats")
    opp_species = opp["species"]
    opp_hp_pct = (opp["hp"] / opp["maxhp"] * 100) if opp.get("maxhp") and opp.get("hp") is not None else 100
    my_boosts = state.get("my_boosts", {})
    opp_boosts = opp.get("boosts", {})

    my_moves = state["my_team"][my_species]["moves"]
    my_options = []
    status_moves = []

    for m in my_moves:
        if isinstance(m, dict):
            if m.get("disabled") or m.get("pp", 1) <= 0:
                continue
            name = m.get("move")
        else:
            name = m
        if not name:
            continue
        move_data = MOVES.get(_id(name), {})
        if move_data.get("category") == "Status":
            status_moves.append(name)
        else:
            atk_boost = my_boosts.get("spa" if move_data.get("category") == "Special" else "atk", 0)
            def_boost = opp_boosts.get("spd" if move_data.get("category") == "Special" else "def", 0)
            dmg = estimate_damage_pct(my_species, my_stats, name, opp_species, atk_boost=atk_boost, def_boost=def_boost)
            if dmg:
                my_options.append((name, dmg))

    setup_moves = [m for m in status_moves if any(w in m.lower() for w in ["dance", "plot", "mind", "bulk", "shield", "shift", "charge", "defense", "agility"])]

    best_my_move = max(my_options, key=lambda x: x[1][1], default=None)
    can_i_ko = bool(best_my_move and (best_my_move[1][0] >= opp_hp_pct or (best_my_move[1][0] + best_my_move[1][1]) / 2 >= opp_hp_pct))

    opp_options = []
    for name in opp.get("revealed_moves", []):
        move_data = MOVES.get(_id(name), {})
        atk_boost = opp_boosts.get("spa" if move_data.get("category") == "Special" else "atk", 0)
        def_boost = my_boosts.get("spd" if move_data.get("category") == "Special" else "def", 0)
        dmg = estimate_damage_pct(opp_species, None, name, my_species, atk_boost=atk_boost, def_boost=def_boost)
        if dmg:
            opp_options.append((name, dmg))

    best_opp_move = max(opp_options, key=lambda x: x[1][1], default=None)

    my_hp_pct = None
    cond = state["my_team"][my_species].get("condition", "")
    if cond and "/" in cond:
        try:
            cur, mx = cond.split()[0].split("/")
            my_hp_pct = int(cur) / int(mx) * 100
        except ValueError:
            pass

    can_opp_ko = bool(best_opp_move and my_hp_pct is not None and (best_opp_move[1][0] >= my_hp_pct or (best_opp_move[1][0] + best_opp_move[1][1]) / 2 >= my_hp_pct))

    my_spe = (my_stats.get("spe") if my_stats else calc_stat(get_species(my_species)["baseStats"]["spe"])) * boost_multiplier(my_boosts.get("spe", 0))
    opp_dex = get_species(opp_species)
    opp_spe_est = calc_stat(opp_dex["baseStats"]["spe"]) * boost_multiplier(opp_boosts.get("spe", 0)) if opp_dex else None
    faster = my_spe > opp_spe_est if opp_spe_est else None
    opponent_kills_first = bool(faster is False and can_opp_ko)

    return {
        "best_my_move": best_my_move,
        "can_i_ko": can_i_ko,
        "best_opp_move": best_opp_move,
        "can_opp_ko": can_opp_ko,
        "faster": faster,
        "status_moves": status_moves,
        "setup_moves": setup_moves,
        "opp_kills_first": opponent_kills_first
    }
