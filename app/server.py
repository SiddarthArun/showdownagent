import uvicorn
from fastapi import FastAPI, Request
from rich.console import Console
from rich.panel import Panel

from app.config import setup_logging
from app.llm import get_suggestion
from app.state import build_state

setup_logging()
console = Console()

ACTION_STYLES = {"move": "green", "switch": "yellow"}
MIN_BATTLE_TURN = 1

app = FastAPI()
last_turn_seen = None
current_battle_title: str | None = None
recent_suggestions: list[str] = []


def should_process_turn(turn: int, last_seen: int | None) -> bool:
    """Return whether a battle turn should produce a suggestion."""
    return turn >= MIN_BATTLE_TURN and turn != last_seen


@app.post("/state")
async def receive_state(request: Request):
    global last_turn_seen, current_battle_title, recent_suggestions
    raw = await request.json()
    state = build_state(raw)
    if not state:
        return {"ok": True}

    if state["title"] != current_battle_title:
        current_battle_title = state["title"]
        last_turn_seen = None
        recent_suggestions = []

    if not should_process_turn(state["turn"], last_turn_seen):
        return {"ok": True}

    last_turn_seen = state["turn"]

    try:
        with console.status("[dim]thinking...[/dim]", spinner="dots"):
            decision = get_suggestion(state, recent_suggestions)

        style = ACTION_STYLES.get(decision["action"], "white")
        verb = "USE" if decision["action"] == "move" else "SWITCH TO"

        console.print(Panel(
            f"[bold {style}]{verb} {decision['choice']}[/bold {style}]\n\n[dim]{decision['reasoning']}[/dim]",
            title=f"Turn {state['turn']}",
            border_style=style,
            padding=(1, 2),
        ))

        recent_suggestions.append(
            f"Turn {state['turn']}: {verb} {decision['choice']} — {decision['reasoning']}"
        )
        del recent_suggestions[:-2]
    except Exception as error:
        console.print(f"[bold red]✗ suggestion failed:[/bold red] {error}")

    return {"ok": True}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning", access_log=False)