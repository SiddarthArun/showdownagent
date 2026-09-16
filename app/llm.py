import json
import logging

import requests
from google import genai
from app.calculator_v2 import analyze_matchup
from app.retrieval import retrieve
from app.config import settings

logger = logging.getLogger(__name__)
client = genai.Client(api_key=settings.gemini_api_key) if settings.gemini_api_key else None

SYSTEM_PROMPT = """You are a Pokemon Showdown coach.

Respond ONLY with a JSON object in this exact shape, no other text:
{"action": "move" or "switch", "choice": "<exact move or Pokemon name>", "reasoning": "1-2 sentence explanation"}

If a fact marked CRITICAL is present, it overrides all other considerations — do not recommend attacking if a CRITICAL warning says you won't survive to take your turn. When switching is advised, name specific healthy bench Pokemon from the bench team list provided.

Computed damage estimates are approximate (unknown opponent EVs/nature/IVs) — describe them as "likely" or "roughly X%", never "guaranteed", unless the low end of the range alone exceeds 100%. Trust computed estimates over guesses.

Don't default to caution — if you are not at risk of fainting this turn (no CRITICAL warning present), actively look for a good setup or status-move opportunity rather than only considering switch/attack. A safe turn is a good turn to invest in boosts.

If you are likely to faint this turn regardless of your action (very low HP and no safe switch, or the opponent kills first even after switching considerations), it is often correct to attack for value with your current Pokemon rather than switch — dealing chip damage before fainting lets your replacement come in for free next turn. Weigh this against preserving the Pokemon only when survival this turn is realistic.

Keep your answer to 2-3 sentences."""

def _build_facts(state, matchup, opp_species):
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
        facts.append(f"Status moves available to you: {', '.join(matchup['status_moves'])}.")
    if matchup.get("setup_moves"):
        facts.append(f"Setup/boosting moves available to you: {', '.join(matchup['setup_moves'])}.")

    my_hazards = ", ".join(state.get("my_side_conditions", {}).keys())
    opp_hazards = ", ".join(state.get("opp_side_conditions", {}).keys())
    if my_hazards:
        facts.append(f"Hazards already on your side: {my_hazards}. Do not suggest setting these again.")
    if opp_hazards:
        facts.append(f"Hazards already on opponent's side: {opp_hazards}. Do not suggest setting these again.")

    return "\n".join(facts) if facts else "No damage calc available for current moves."

def _build_bench_summary(state):
    bench_info = []
    for species, data in state["my_team"].items():
        if data.get("active"):
            continue
        cond = data.get("condition", "unknown")
        item = data.get("item", "no item")
        moves_list = [m.get("move", m) if isinstance(m, dict) else m for m in data.get("moves", [])]
        bench_info.append(f"- {species} (HP: {cond}, Item: {item}, Moves: {', '.join(moves_list)})")
    return "\n".join(bench_info) if bench_info else "No bench Pokemon available."

def get_suggestion(state, recent_suggestions):
    my_active = next((s for s, m in state["my_team"].items() if m["active"]), None)
    opp = state["opponent"]["active"]

    if opp:
        opp_species = opp["species"]
        opp_hp = f"{opp.get('hp')}/{opp.get('maxhp')}"
    else:
        opp_species = "unknown"
        opp_hp = "unknown"

    matchup = analyze_matchup(state)
    matchup_facts = _build_facts(state, matchup, opp_species)
    bench_summary = _build_bench_summary(state)

    context_chunks = retrieve(my_active) + retrieve(opp_species)
    context = "\n\n".join(context_chunks) if context_chunks else "No Smogon data found."
    history = "\n".join(recent_suggestions[-2:]) if recent_suggestions else 'None yet.'

    user_content = f"""My active Pokemon: {my_active}
    My available moves: {state["my_team"][my_active]["moves"] if my_active else "unknown"}
    My bench team members available for switching:
    {bench_summary}

    Opponent's active Pokemon: {opp_species} ({opp_hp} HP)

    Your suggestions on recent turns (don't repeat advice already acted on):
    {history}

    Computed damage estimates:
    {matchup_facts}

    Relevant Smogon context:
    {context}
    """

    logger.info(f"Calling {settings.llm_backend} for turn {state.get('turn')}")
    response_text = _generate_response(user_content)
    try:
        decision = json.loads(response_text)
    except json.JSONDecodeError:
        logger.warning(f"Model returned non-JSON: {response_text!r}")
        decision = {"action": "move", "choice": None, "reasoning": "Failed to parse model output."}

    return validate_decision(decision, state, matchup)

def _generate_response(user_content: str) -> str:
    backend = settings.llm_backend.lower()
    if backend == "ollama":
        response = requests.post(
            f"{settings.ollama_url.rstrip('/')}/api/chat",
            json={
                "model": settings.ollama_model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
                "format": "json",
                "stream": False,
            },
            timeout=120,
        )
        response.raise_for_status()
        return response.json()["message"]["content"]

    if backend != "gemini":
        raise ValueError(f"Unsupported LLM_BACKEND: {settings.llm_backend}")
    if not client:
        raise ValueError("GEMINI_API_KEY is required when LLM_BACKEND is gemini")

    response = client.models.generate_content(
        model=settings.model_name,
        contents=user_content,
        config={"system_instruction": SYSTEM_PROMPT},
    )
    return response.text

def validate_decision(decision: dict, state: dict, matchup: dict) -> dict:
    my_active = next((s for s, m in state["my_team"].items() if m["active"]), None)
    my_moves = []
    for move in state["my_team"][my_active]["moves"]:
        if isinstance(move, dict):
            if move.get("disabled") or move.get("pp", 1) <= 0:
                continue
            name = move.get("move")
        else:
            name = move
        if name:
            my_moves.append(name)

    bench = [
        species
        for species, data in state["my_team"].items()
        if not data["active"] and data.get("condition", "0/0").split("/")[0] != "0"
    ]

    action = decision.get("action")
    choice = decision.get("choice")

    valid = (
        (action == "move" and choice in my_moves) or
        (action == "switch" and choice in bench)
    )

    if valid:
        return decision

    logger.warning(f"Invalid decision from model: {decision} — falling back")

    if matchup.get("best_my_move"):
        fallback_move = matchup["best_my_move"][0]
        return {
            "action": "move",
            "choice": fallback_move,
            "reasoning": f"(Fallback: model suggestion was invalid, defaulted to best-calculated move.)",
        }

    return {
        "action": "move",
        "choice": my_moves[0] if my_moves else None,
        "reasoning": "(Fallback: no valid decision or damage calc available.)",
    }