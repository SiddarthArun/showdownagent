"""A small, offline quality check for the calculator.

Run from the project directory:
    python tests/test_benchmark.py

The benchmark samples reproducible random Pokemon, opponents, and damaging
moves from the local data files. It does not call Gemini, Ollama, the browser,
or the live server. The calculator's best move is compared with the expected
result of choosing uniformly at random from the same three candidate moves.
"""

from random import Random
from statistics import mean

from app.calculator_v2 import MOVES, POKEDEX, estimate_damage_pct

SEED = 2026
SCENARIO_COUNT = 20
MOVES_PER_SCENARIO = 3


def _database_options() -> tuple[list[str], list[str]]:
    species = [
        data["name"]
        for data in POKEDEX.values()
        if data.get("name") and data.get("types") and data.get("baseStats")
    ]
    moves = [
        data["name"]
        for data in MOVES.values()
        if data.get("name")
        and data.get("category") in {"Physical", "Special"}
        and data.get("power")
    ]
    return species, moves


def _scenarios(rng: Random) -> list[tuple[str, str, tuple[str, ...]]]:
    species, moves = _database_options()
    if len(moves) < MOVES_PER_SCENARIO or not species:
        raise SystemExit("The local Pokemon or move database has too few usable entries.")

    scenarios = []
    for _ in range(SCENARIO_COUNT):
        attacker = rng.choice(species)
        defender = rng.choice(species)
        candidates = tuple(rng.sample(moves, MOVES_PER_SCENARIO))
        scenarios.append((attacker, defender, candidates))
    return scenarios


def run() -> None:
    scenarios = _scenarios(Random(SEED))
    results = []

    for attacker, defender, moves in scenarios:
        choices = []
        for move in moves:
            damage = estimate_damage_pct(attacker, None, move, defender)
            if damage is not None:
                choices.append((move, damage[1]))

        if choices:
            best = max(choices, key=lambda item: item[1])
            random_average = mean(damage for _, damage in choices)
            results.append((best[1], random_average, best[0], attacker, defender))

    if not results:
        raise SystemExit("No benchmark scenarios could be calculated.")

    calculator_average = mean(best for best, _, *_ in results)
    random_average = mean(random for _, random, *_ in results)
    improvement = (calculator_average / random_average - 1) * 100 if random_average else 0
    wins = sum(best > random for best, random, *_ in results)

    print("Showdown Coach calculator check")
    print("=" * 32)
    print(f"Seed:                      {SEED}")
    print(f"Scenarios:                 {len(results)}/{len(scenarios)}")
    print(f"Calculator average damage: {calculator_average:.1f}%")
    print(f"Random-choice average:      {random_average:.1f}%")
    print(f"Calculator improvement:     {improvement:+.1f}%")
    print(f"Beats random baseline:      {wins}/{len(results)} ({wins / len(results) * 100:.0f}%)")
    print("\nSampled best choices:")
    for _, _, move, attacker, defender in results[:10]:
        print(f"  {attacker} -> {defender}: {move}")
    


if __name__ == "__main__":
    run()
