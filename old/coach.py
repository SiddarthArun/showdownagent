from fastapi import FastAPI, Request
import uvicorn, json
from dotenv import load_dotenv
from google import genai
from old.calculator import analyze_matchup
load_dotenv()

app = FastAPI()
last_turn_seen = None
current_state: dict = {}
recent_suggestions = []


client = genai.Client()  # reads GEMINI_API_KEY from env

with open("smogon_chunks.jsonl") as f:
    SMOGON_CHUNKS = [json.loads(line) for line in f]


def retrieve(species: str, k: int = 3) -> list[str]:
    if not species:
        return []
    matches = [c["text"] for c in SMOGON_CHUNKS if c["species"].lower() == species.lower()]
    return matches[:k]


def get_suggestion(state: dict) -> str:
    my_active = next((s for s, m in state["my_team"].items() if m["active"]), None)
    opp = state["opponent"]["active"]

    if opp:
        opp_species = opp["species"]
        opp_hp = f"{opp.get('hp')}/{opp.get('maxhp')}"
    else:
        opp_species = "unknown"
        opp_hp = "unknown"

    # Matchup stuff, fact building
    matchup = analyze_matchup(state)
    facts = []
    if matchup.get("best_my_move"):
        name, (lo, hi) = matchup["best_my_move"]
        facts.append(f"Your best move ({name}) deals an estimated {lo:.0f}-{hi:.0f}% to {opp_species}.")
    
    if matchup.get("opp_kills_first"):
        facts.append(
            "CRITICAL: The opponent is likely faster and can likely KO you this turn. "
            "Your own attack will NOT execute if you faint first — securing a kill on your turn is not possible here. "
            "You should switch out instead, unless you have a priority move that outpaces speed."
        )
    elif matchup.get("can_i_ko"):
        facts.append("This is likely a KO or near-KO — the opponent may switch out rather than stay in.")
    
    if matchup.get("best_opp_move"):
        name, (lo, hi) = matchup["best_opp_move"]
        facts.append(f"Opponent's {name} (revealed) could deal an estimated {lo:.0f}-{hi:.0f}% to you.")
    if matchup.get("can_opp_ko"):
        facts.append("The opponent likely threatens a KO on you this turn — consider switching rather than attacking.")
    

    if matchup.get("faster") is True:
        facts.append("You outspeed the opponent's active Pokemon (estimated) — you can afford to attack even at low HP if you'll win the exchange.")
    elif matchup.get("faster") is False:
        facts.append("The opponent is likely faster than you (estimated) — factor this into whether switching or attacking is safer.")
    if matchup.get("status_moves"):
        facts.append(f"Status/setup moves available to you: {', '.join(matchup['status_moves'])}.")

    my_hazards = ", ".join(state.get("my_side_conditions", {}).keys())
    opp_hazards = ", ".join(state.get("opp_side_conditions", {}).keys())
    if my_hazards:
        facts.append(f"Hazards already on your side: {my_hazards}. Do not suggest setting these again.")
    if opp_hazards:
        facts.append(f"Hazards already on opponent's side: {opp_hazards}. Do not suggest setting these again.")

    matchup_facts = "\n".join(facts) if facts else "No damage calc available for current moves."

    context_chunks = retrieve(my_active) + retrieve(opp_species)
    context = "\n\n".join(context_chunks) if context_chunks else "No Smogon data found."
    history = "\n".join(recent_suggestions[-2:]) if recent_suggestions else 'None yet.'

    prompt = f"""You are a Pokemon Showdown coach. Give one short, direct suggestion.

My active Pokemon: {my_active}
My available moves: {state["my_team"][my_active]["moves"] if my_active else "unknown"}
Opponent's active Pokemon: {opp_species} ({opp_hp} HP)

Your suggestions on recent turns (don't repeat advice already acted on):
{history}

If a fact marked CRITICAL is present, it overrides all other considerations — do not recommend attacking if a CRITICAL warning says you won't survive to take your turn.

Computed damage estimates are approximate (unknown opponent EVs/nature/IVs) — describe them as "likely" or "roughly X%", never "guaranteed", unless the low end of the range alone exceeds 100%.
Computed damage estimates (trust these over guesses):
{matchup_facts}

Relevant Smogon context:
{context}

Don't default to caution — if you are not at risk of fainting this turn (no CRITICAL warning present), actively look for a good setup or status-move opportunity rather than only considering switch/attack. A safe turn is a good turn to invest in boosts.

If you are likely to faint this turn regardless of your action (very low HP and no safe switch, or the opponent kills first even after switching considerations), it is often correct to attack for value with your current Pokemon rather than switch — dealing chip damage before fainting lets your replacement come in for free next turn. Weigh this against preserving the Pokemon only when survival this turn is realistic.

What should I do this turn and why? Keep it to 2-3 sentences."""

    response = client.models.generate_content(
        model="gemini-3.1-flash-lite",
        contents=prompt,
    )
    return response.text

def build_state(raw: dict) -> dict | None:
    req = raw.get("request")
    if not raw.get("title") or not req:
        return None  # page mid-load, not a real battle turn yet

    # Full move lists (move IDs) for every one of your Pokemon come from
    # request.side.pokemon — this is the same data the in-game hover
    # tooltip reads, available whether or not that mon is active.
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

    # PP/disabled status is only tracked for the currently active mon —
    # overlay that detail onto whichever team entry is marked active.
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
        "my_boosts": raw.get("my_boosts", {}),                    # <-- add
        "my_side_conditions": raw.get("my_side_conditions", {}),  # <-- add
        "opp_side_conditions": raw.get("opp_side_conditions", {}),# <-- add
        "opponent": {
            "active": raw.get("opp_active"),
            "team": {mon["species"]: mon for mon in (raw.get("opp_team") or []) if mon},
        },
    }


@app.post("/state")
async def receive_state(request: Request):
    global last_turn_seen, current_state
    raw = await request.json()

    state = build_state(raw)
    if not state or state["turn"] == last_turn_seen:
        return {"ok": True}

    last_turn_seen = state["turn"]
    current_state = state

    try:
        print(f'\nTurn {last_turn_seen}')
        print('---------------------------')
        suggestion = get_suggestion(current_state)
        print(suggestion)
        recent_suggestions.append(f"Turn {current_state['turn']}: {suggestion}")
    except Exception as e:
        print(f"[suggestion failed: {e}]")

    return {"ok": True}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning", access_log=False)