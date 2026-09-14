"""Convert Showdown data files into standard JSON."""

import json
import re
import json5
import requests

def parse_ts_export(url: str) -> dict:
    text = requests.get(url, timeout=30).text
    text = re.sub(r"^export const \w+.*?=\s*", "", text, flags=re.DOTALL).rstrip().rstrip(";")
    text = re.sub(r"([{,]\s*)(\d+)(\s*:)", r'\1"\2"\3', text)
    return json5.loads(text)

BASE = "https://raw.githubusercontent.com/smogon/pokemon-showdown/master/data/"

pokedex = parse_ts_export(BASE + "pokedex.ts")
typechart = parse_ts_export(BASE + "typechart.ts")

for filename, data in [("pokedex.json", pokedex), ("typechart.json", typechart)]:
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

print(f"pokedex: {len(pokedex)} species, typechart: {len(typechart)} types")