"""A small, offline quality check for the calculator.

Run from the project directory:
    python tests/test_benchmark.py

This does not call Gemini, Ollama, the browser, or the live server. It compares
one simple prediction: the calculator's highest-damage move versus choosing
uniformly at random from the same legal move list.
"""

from statistics import mean

from app.calculator_v2 import estimate_damage_pct


SCENARIOS = (
    ("Charizard", "Bulbasaur", ("Flamethrower", "Air Slash", "Dragon Claw")),
    ("Pikachu", "Squirtle", ("Thunderbolt", "Quick Attack", "Iron Tail")),
    ("Garchomp", "Charizard", ("Earthquake", "Stone Edge", "Dragon Claw")),
    ("Venusaur", "Blastoise", ("Giga Drain", "Sludge Bomb", "Energy Ball")),
    ("Lucario", "Tyranitar", ("Aura Sphere", "Flash Cannon", "Close Combat")),
    ("Starmie", "Charizard", ("Surf", "Psychic", "Ice Beam")),
)


def run() -> None:
    results = []
    for attacker, defender, moves in SCENARIOS:
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
    print(f"Scenarios:                 {len(results)}/{len(SCENARIOS)}")
    print(f"Calculator average damage: {calculator_average:.1f}%")
    print(f"Random-choice average:      {random_average:.1f}%")
    print(f"Calculator improvement:     {improvement:+.1f}%")
    print(f"Beats random baseline:      {wins}/{len(results)} ({wins / len(results) * 100:.0f}%)")
    print("\nBest calculated choices:")
    for _, _, move, attacker, defender in results:
        print(f"  {attacker} -> {defender}: {move}")


if __name__ == "__main__":
    run()
