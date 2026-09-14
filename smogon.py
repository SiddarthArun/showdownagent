import json, requests
from bs4 import BeautifulSoup

ANALYSIS_URL = "https://data.pkmn.cc/analyses/gen9ou.json"

def html_to_text(html):
    if not html: return None
    return BeautifulSoup(html, 'html.parser').get_text(separator=' ', strip=True)

def chunk(analyses):
    chunks  = []

    for species, data in analyses.items():
        if data.get('outdated'):
            continue

        overview = html_to_text(data.get('overview'))
        if overview:
           chunks.append({"species": species, "set_name": None, "text": f"{species} — general strategy overview: {overview}",}) 
        
        for set_name, set_data in (data.get("sets") or {}).items():
            if set_data.get("outdated"):
                continue
            description = html_to_text(set_data.get("description"))
            if not description:
                continue
            chunks.append({
                "species": species,
                "set_name": set_name,
                "text": f"{species} ({set_name}): {description}",
            })

    return chunks

def main():
    resp = requests.get(ANALYSIS_URL, timeout=30)
    resp.raise_for_status()
    analyses = resp.json()

    chunks = chunk(analyses)
    print(f"Built {len(chunks)} chunks from {len(analyses)} Pokemon")

    with open("smogon_chunks.jsonl", "w") as f:
        for c in chunks:
            f.write(json.dumps(c) + "\n")


if __name__ == "__main__":
    main()