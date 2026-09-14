# app/cli.py
import typer
import uvicorn
from rich.console import Console
from app.config import setup_logging, BASE_DIR

app = typer.Typer(help="AI coach for Pokemon Showdown battles.")
console = Console()


@app.command()
def start(port: int = 8000, backend: str = None):
    """Start the coach server. Leave this running while you play."""
    setup_logging()
    if backend:
        import os
        os.environ["LLM_BACKEND"] = backend  # overrides .env for this run
    console.print()
    console.print("[bold cyan]◆ Showdown Coach[/bold cyan]")
    console.print(f"[dim]Listening on http://127.0.0.1:{port} — open a battle to begin.[/dim]")
    console.print()
    uvicorn.run("app.server:app", host="127.0.0.1", port=port, log_level="warning", access_log=False)


@app.command("set-key")
def set_key(key: str):
    """Save your Gemini API key to .env."""
    env_path = BASE_DIR / ".env"
    lines = [l for l in env_path.read_text().splitlines() if not l.startswith("GEMINI_API_KEY=")] if env_path.exists() else []
    lines.append(f"GEMINI_API_KEY={key}")
    env_path.write_text("\n".join(lines) + "\n")
    console.print("[green]✓ API key saved[/green]")


if __name__ == "__main__":
    app()