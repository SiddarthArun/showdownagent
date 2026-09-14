from fastapi import FastAPI, Request
import uvicorn
from app.state import build_state
from app.llm import get_suggestion
from app.config import setup_logging
from rich.console import Console
from rich.panel import Panel

setup_logging()
console = Console()

ACTION_STYLES = {"move": "green", "switch": "yellow"}

app = FastAPI()
last_turn_seen = None
recent_suggestions: list[str] = []


@app.post("/state")
async def receive_state(request: Request):
    global last_turn_seen
    raw = await request.json()

    state = build_state(raw)
    if not state or state["turn"] == last_turn_seen:
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

        recent_suggestions.append(f"Turn {state['turn']}: {verb} {decision['choice']} — {decision['reasoning']}")
    except Exception as e:
        console.print(f"[bold red]✗ suggestion failed:[/bold red] {e}")

    return {"ok": True}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning", access_log=False)