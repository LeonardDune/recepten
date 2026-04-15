#!/usr/bin/env python3
"""
brain.py — Lokale vault-intelligentie voor de Obsidian recepten-vault.

Gebruik:
  python brain.py --gaps               # ingrediënten zonder eigen note (gesorteerd op frequentie)
  python brain.py --gaps --create      # zelfde + maak de ontbrekende stubs meteen aan
  python brain.py --stats              # overzicht van de vault
  python brain.py --query "..."        # open vraag aan Claude met je recepten als context
"""

import argparse
import json
import re
import sys
import urllib.request
import urllib.error
from collections import Counter
from pathlib import Path

# Forceer UTF-8 output op Windows (anders cp1252 in cmd/PowerShell)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# ── Paden ────────────────────────────────────────────────────────────────────
VAULT         = Path(__file__).parent
RECIPES_DIR   = VAULT / "01 Recipes"
ING_DIR       = VAULT / "02 Ingredients"
API_KEY_FILE  = VAULT / "_Setup" / "anthropic-api-key.txt"

WIKILINK_RE   = re.compile(r'\[\[([^\]|#\n]+?)(?:\|[^\]\n]*)?\]\]')
FRONTMATTER_RE = re.compile(r'^---\n(.*?)\n---', re.DOTALL)

# ── Helpers ───────────────────────────────────────────────────────────────────

def load_recipes() -> dict[str, str]:
    """Geeft {bestandsnaam: volledige tekst} voor alle recepten."""
    return {
        f.name: f.read_text(encoding="utf-8")
        for f in sorted(RECIPES_DIR.glob("*.md"))
    }


def extract_wikilinks(text: str) -> list[str]:
    return WIKILINK_RE.findall(text)


def existing_ingredient_names() -> set[str]:
    return {f.stem.lower() for f in ING_DIR.glob("*.md")}


def ingredient_stub(naam: str) -> str:
    return (
        f"---\ntitle: {naam}\ntags:\n  - ingredient\n"
        "category: \nseason: \nsmoke_point: \norigin: \n---\n\n"
        "## Eigenschappen\n\n"
        "## Gebruik in recepten\n\n"
        "```dataview\n"
        'LIST FROM "01 Recipes"\n'
        "WHERE contains(file.outlinks, this.file.link)\n"
        "```\n\n"
        "## Notities\n\n"
    )


def call_claude(prompt: str) -> str:
    if not API_KEY_FILE.exists():
        sys.exit(f"Geen API key gevonden op {API_KEY_FILE}")
    api_key = API_KEY_FILE.read_text(encoding="utf-8").strip()

    payload = json.dumps({
        "model": "claude-sonnet-4-6",
        "max_tokens": 4096,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
            return data["content"][0]["text"]
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        sys.exit(f"Claude API fout {e.code}: {body}")


# ── Commando's ────────────────────────────────────────────────────────────────

def cmd_gaps(create: bool) -> None:
    """Ingrediënten die in recepten worden gebruikt maar geen eigen note hebben."""
    recipes   = load_recipes()
    existing  = existing_ingredient_names()

    # Tel hoe vaak elk ingredient voorkomt (over alle recepten)
    counts: Counter = Counter()
    sources: dict[str, list[str]] = {}   # ingredient → lijst van recepten
    for name, text in recipes.items():
        for link in extract_wikilinks(text):
            link_lower = link.strip().lower()
            counts[link_lower] += 1
            sources.setdefault(link_lower, [])
            if name not in sources[link_lower]:
                sources[link_lower].append(name)

    gaps = {ing: cnt for ing, cnt in counts.items() if ing not in existing}

    if not gaps:
        print("Geen hiaten gevonden — alle wikilinks hebben een ingrediënt-note.")
        return

    print(f"{'INGREDIËNT':<30} {'VERMELDINGEN':>12}  RECEPTEN")
    print("─" * 72)
    for ing, cnt in sorted(gaps.items(), key=lambda x: -x[1]):
        recepten = ", ".join(
            r.replace(".md", "") for r in sources[ing][:3]
        )
        meer = f" (+{len(sources[ing])-3})" if len(sources[ing]) > 3 else ""
        print(f"{ing:<30} {cnt:>12}  {recepten}{meer}")

    if create:
        print(f"\n→ Stubs aanmaken voor {len(gaps)} ingrediënten...")
        for ing in gaps:
            path = ING_DIR / f"{ing}.md"
            path.write_text(ingredient_stub(ing), encoding="utf-8")
            print(f"  ✓ {path.name}")
        print("Klaar.")


def cmd_stats() -> None:
    """Overzicht van de vault."""
    recipes   = load_recipes()
    existing  = existing_ingredient_names()

    all_links: list[str] = []
    tried_count = 0
    rated_count = 0
    cuisines: Counter = Counter()
    courses:  Counter = Counter()

    for name, text in recipes.items():
        all_links.extend(extract_wikilinks(text))
        fm_match = FRONTMATTER_RE.match(text)
        if fm_match:
            fm = fm_match.group(1)
            if re.search(r'^tried:\s*true', fm, re.MULTILINE | re.IGNORECASE):
                tried_count += 1
            if re.search(r'^rating:\s*\d', fm, re.MULTILINE):
                rated_count += 1
            m = re.search(r'^cuisine:\s*(.+)', fm, re.MULTILINE)
            if m:
                cuisines[m.group(1).strip()] += 1
            m = re.search(r'^course:\s*(.+)', fm, re.MULTILINE)
            if m:
                courses[m.group(1).strip()] += 1

    link_counts = Counter(l.lower() for l in all_links)
    top5 = link_counts.most_common(5)
    gaps = sum(1 for ing in link_counts if ing not in existing)

    print("-" * 40)
    print(f"  Recepten            {len(recipes):>6}")
    print(f"  Ingrediënt-notes    {len(existing):>6}")
    print(f"  Unieke wikilinks    {len(link_counts):>6}")
    print(f"  Ontbrekende notes   {gaps:>6}")
    print(f"  Al geprobeerd       {tried_count:>6} / {len(recipes)}")
    print(f"  Beoordeeld          {rated_count:>6} / {len(recipes)}")
    print("-" * 40)

    if cuisines:
        print("\n  Keukens:")
        for c, n in cuisines.most_common():
            print(f"    {c:<20} {n}")

    if courses:
        print("\n  Gangen:")
        for c, n in courses.most_common():
            print(f"    {c:<20} {n}")

    if top5:
        print("\n  Meest gebruikte ingrediënten:")
        for ing, cnt in top5:
            print(f"    {ing:<24} {cnt}×")
    print()


def cmd_query(question: str) -> None:
    """Stuur een open vraag naar Claude met de volledige vault als context."""
    recipes = load_recipes()

    vault_context = "\n\n---\n\n".join(
        f"## {name}\n\n{text}" for name, text in recipes.items()
    )

    ing_names = sorted(existing_ingredient_names())

    prompt = f"""Je bent een assistent die helpt bij het analyseren van een persoonlijke receptenvault in Obsidian.

BESCHIKBARE INGREDIËNT-NOTES (bestandsnamen zonder .md):
{', '.join(ing_names)}

RECEPTEN IN DE VAULT:
{vault_context}

VRAAG VAN DE GEBRUIKER:
{question}

Geef een concreet, beknopt antwoord in het Nederlands. Verwijs naar recepten bij naam. Als je nieuwe Obsidian-notes suggereert, gebruik dan [[wikilink]]-notatie."""

    print("Vraag aan Claude...\n")
    antwoord = call_claude(prompt)
    print(antwoord)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="brain.py — vault-intelligentie voor je Obsidian receptenvault",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Voorbeelden:\n"
            "  python brain.py --gaps\n"
            "  python brain.py --gaps --create\n"
            "  python brain.py --stats\n"
            '  python brain.py --query "Welke recepten zijn geschikt voor een doordeweekse avond?"\n'
        ),
    )
    parser.add_argument("--gaps",   action="store_true", help="toon ingrediënten zonder note")
    parser.add_argument("--create", action="store_true", help="maak ontbrekende stubs aan (gebruik samen met --gaps)")
    parser.add_argument("--stats",  action="store_true", help="vault-statistieken")
    parser.add_argument("--query",  metavar="VRAAG",    help="open vraag aan Claude")

    args = parser.parse_args()

    if args.gaps:
        cmd_gaps(create=args.create)
    elif args.stats:
        cmd_stats()
    elif args.query:
        cmd_query(args.query)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
