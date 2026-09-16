
import typer
import uvicorn
from rich.console import Console

from app.config import BASE_DIR, settings, setup_logging

HOST = "127.0.0.1"
DEFAULT_PORT = 8000
BACKENDS = {"gemini", "ollama"}
ENV_PATH = BASE_DIR / ".env"

app = typer.Typer(help="AI coach for Pokemon Showdown battles.", no_args_is_help=True)
console = Console()


def _backend(value: str | None) -> str:
    value = (value or settings.llm_backend).lower()
    if value not in BACKENDS:
        raise typer.BadParameter(f"Choose one of: {', '.join(sorted(BACKENDS))}")
    settings.llm_backend = value
    return value


def _save_env(**updates: str) -> None:
    old = ENV_PATH.read_text().splitlines() if ENV_PATH.exists() else []
    keys = set(updates)
    lines = [line for line in old if line.split("=", 1)[0] not in keys]
    ENV_PATH.write_text("\n".join([*lines, *(f"{key}={value}" for key, value in updates.items())]) + "\n")


def _info() -> None:
    console.print("""[bold]Showdown Coach - complete setup[/bold]

[bold cyan]1. Install the program[/bold cyan]
Download the latest Source code (zip) from the GitHub Releases page, or clone
the repository. Open a terminal in the extracted project folder, then create
a virtual environment:
  [bold]python -m venv .venv[/bold]

Activate it:
  Windows: [bold].venv\\Scripts\\activate[/bold]
  macOS/Linux: [bold]source .venv/bin/activate[/bold]

Install the source checkout:
  Windows: [bold]py -m pip install -e .[/bold]
  macOS/Linux: [bold]python -m pip install -e .[/bold]

Keep the project folder: the userscript, battle data, and build_chroma.py are
repository files used during setup. If the command is unavailable later, use
[bold]python -m app.cli info[/bold] from this folder.

[bold cyan]2. Configure an AI backend[/bold cyan]
The easiest option is:
  [bold]showdown-coach setup[/bold]

Choose one:
  [bold]Gemini[/bold] - get an API key from https://aistudio.google.com/
  and paste it when prompted. The key is saved in the local .env file.

  [bold]Ollama[/bold] - install Ollama from https://ollama.com/, start it,
  then download a model, for example:
    [bold]ollama pull llama3.1[/bold]
  Choose Ollama and enter [bold]llama3.1[/bold] in the setup prompt.

You can also create .env manually in the project folder:
  LLM_BACKEND=gemini
  GEMINI_API_KEY=your_key_here

For Ollama instead use:
  LLM_BACKEND=ollama
  OLLAMA_MODEL=llama3.1
  OLLAMA_URL=http://127.0.0.1:11434

[bold cyan]3. Install the browser userscript[/bold cyan]
1. Install Tampermonkey: https://www.tampermonkey.net/
2. Open the project's [bold]userscript.js[/bold] file.
3. In Tampermonkey choose [bold]Create a new script[/bold].
4. Remove the template and paste in the entire userscript.js file.
5. Save the script and make sure it is enabled.
6. Keep the browser open; the script sends state to http://127.0.0.1:8000.

[bold cyan]4. Build the local strategy index[/bold cyan]
Run this once from the project folder:
  Windows: [bold]py build_chroma.py[/bold]
  macOS/Linux: [bold]python build_chroma.py[/bold]
Repeat only if the Smogon data changes.

[bold cyan]5. Start the coach[/bold cyan]
Run [bold]showdown-coach start[/bold], then open https://play.pokemonshowdown.com/
in the same browser and enter a battle. Suggestions appear from turn 1 onward.

[bold cyan]Useful commands[/bold cyan]
  [bold]showdown-coach setup[/bold]          Create or update .env
  [bold]showdown-coach info[/bold]           Show this guide
  [bold]showdown-coach start[/bold]          Run the coach
  [bold]showdown-coach start --backend ollama[/bold]
  [bold]showdown-coach start --port 8001[/bold]

[bold cyan]Simple calculator check[/bold cyan]
  Run this from the project folder:
    [bold]python tests/test_benchmark.py[/bold]
  It compares the calculator's highest-damage move with the expected damage
  from choosing randomly among the same moves. It reports average damage,
  improvement percentage, and how often it beats random. This is an offline
  calculator sanity check, not a real battle win rate or LLM evaluation.

  Compile-check the project with:
    [bold]python -m compileall -q app tests[/bold]
  Success produces no output and exits with code 0.

[bold cyan]Troubleshooting[/bold cyan]
- No suggestions: check the server, Tampermonkey, the complete userscript,
  and that the battle is on play.pokemonshowdown.com.
- Gemini errors: verify GEMINI_API_KEY in .env and restart the coach.
- Ollama errors: verify Ollama is running, the model was pulled, and OLLAMA_URL.
- Chroma errors: run [bold]python build_chroma.py[/bold] from the project folder.
  Without the index, the coach can still start but will run without Smogon
  context until the index is built.

- Stop the coach with Ctrl+C.

The browser reader and live coach use localhost. The calculator check is
optional and never runs as part of the live tool.

This GitHub download is a source release, not a standalone PyPI package. Keep
the project folder after installation.""")


@app.command()
def start(
    port: int = typer.Option(DEFAULT_PORT, min=1, max=65535, help="Local server port."),
    backend: str | None = typer.Option(None, help="LLM backend: gemini or ollama."),
) -> None:
    """Start the coach server while you play."""
    selected = _backend(backend)
    setup_logging()
    console.print(
        f"\n[bold cyan]Showdown Coach[/bold cyan]\n"
        f"[dim]Backend: {selected} | http://{HOST}:{port}[/dim]\n"
    )
    uvicorn.run("app.server:app", host=HOST, port=port, log_level="warning", access_log=False)


@app.command()
def setup() -> None:
    """Create the local .env file through a short guided setup."""
    console.print("[bold]Let's get Showdown Coach ready.[/bold]")
    backend = _backend(typer.prompt("Backend [gemini/ollama]", default="gemini"))
    if backend == "gemini":
        key = typer.prompt("Gemini API key", hide_input=True)
        if not key:
            raise typer.BadParameter("A Gemini API key is required.")
        _save_env(LLM_BACKEND=backend, GEMINI_API_KEY=key)
    else:
        model = typer.prompt("Ollama model", default="llama3.1")
        _save_env(LLM_BACKEND=backend, OLLAMA_MODEL=model)
    console.print(
        f"[green]Saved configuration to {ENV_PATH.name}[/green]\n"
        "Run [bold]showdown-coach info[/bold] for the remaining setup steps."
    )


@app.command()
def info() -> None:
    """Show setup, usage, testing, and troubleshooting information."""
    _info()


if __name__ == "__main__":
    app()