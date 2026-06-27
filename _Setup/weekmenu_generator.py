#!/usr/bin/env python3
"""
Weekmenu Generator voor de Recepten Vault.

Genereert elke vrijdag een weekschema (5 diners) en bijbehorende boodschappenlijst
op basis van de recepten in de Obsidian vault.

Gebruik:
  python weekmenu_generator.py
  python weekmenu_generator.py --week-voorkeur "graag Aziatisch deze week"
  python weekmenu_generator.py --week 2026-W22
"""

import os
import re
import sys
import json
import time
import argparse
import calendar
from pathlib import Path
from datetime import date, timedelta

try:
    import anthropic
except ImportError:
    print("Fout: de 'anthropic' package is niet geïnstalleerd.")
    print("Voer uit: pip install anthropic")
    sys.exit(1)

# Retry-instellingen voor de Claude API (vangt tijdelijke netwerkproblemen op,
# bijv. als de laptop net uit slaapstand komt en wifi/VPN nog niet verbonden is).
# 10 pogingen met oplopende pauze (30s, 60s, 60s, ... max 90s) geeft in totaal
# ruim 10 minuten respijt - genoeg om wifi/VPN na het wakker worden te laten herstellen.
API_RETRY_ATTEMPTS = 10
API_RETRY_BASE_DELAY_SECONDS = 30
API_RETRY_MAX_DELAY_SECONDS = 90

# Foutmeldingen die wijzen op een tijdelijk netwerkprobleem (niet op een echte
# API-fout zoals een ongeldige key of een content-fout)
RETRYABLE_EXCEPTIONS = (
    anthropic.APIConnectionError,
    anthropic.APITimeoutError,
    anthropic.InternalServerError,
    anthropic.RateLimitError,
)


def call_claude_with_retry(client: "anthropic.Anthropic", **kwargs):
    """Roept client.messages.create() aan met retries bij (tijdelijke) netwerkproblemen."""
    last_error = None
    for attempt in range(1, API_RETRY_ATTEMPTS + 1):
        try:
            return client.messages.create(**kwargs)
        except RETRYABLE_EXCEPTIONS as e:
            last_error = e
            if attempt < API_RETRY_ATTEMPTS:
                delay = min(API_RETRY_BASE_DELAY_SECONDS * attempt, API_RETRY_MAX_DELAY_SECONDS)
                print(
                    f"  Netwerkfout bij Claude API (poging {attempt}/{API_RETRY_ATTEMPTS}): {e}. "
                    f"Nieuwe poging in {delay}s...",
                    file=sys.stderr,
                )
                time.sleep(delay)
    raise last_error

# ---------------------------------------------------------------------------
# Paden
# ---------------------------------------------------------------------------
VAULT_ROOT = Path(__file__).parent.parent
RECIPES_DIR = VAULT_ROOT / "01 Recipes"
INGREDIENTS_DIR = VAULT_ROOT / "02 Ingredients"
PLANS_DIR = VAULT_ROOT / "03 Weekly Plans"
PREFS_FILE = PLANS_DIR / "_Voorkeuren.md"
API_KEY_FILE = VAULT_ROOT / "_Setup" / "anthropic-api-key.txt"

# ---------------------------------------------------------------------------
# Constanten
# ---------------------------------------------------------------------------
MAIN_COURSE_TYPES = {"hoofdgerecht", "soep"}
SIDE_COURSE_TYPES = {"bijgerecht", "condiment", "saus", "voorgerecht", "tapas"}
DESSERT_TYPES = {"dessert"}
# Deze course-types zijn geen individuele recepten
EXCLUDED_COURSE_TYPES = {"artikel", "divers"}

CLAUDE_MODEL = "claude-sonnet-4-6"
SIMPLE_MAX_MINUTES = 35  # Bereidingstijd grens simpel vs. uitgebreid


# ---------------------------------------------------------------------------
# Hulpfuncties
# ---------------------------------------------------------------------------

def parse_frontmatter(content: str) -> dict:
    """Parses YAML frontmatter. Geeft een dict terug, of {} als er geen is."""
    if not content.startswith("---"):
        return {}
    end = content.find("\n---", 3)
    if end == -1:
        return {}

    fm: dict = {}
    in_list = False
    current_key = None

    for line in content[3:end].splitlines():
        # Detect list items under a key (e.g. tags)
        stripped = line.strip()
        if stripped.startswith("- ") and in_list and current_key:
            fm.setdefault(current_key, [])
            if isinstance(fm[current_key], list):
                fm[current_key].append(stripped[2:].strip())
            continue

        if ":" in line and not line.startswith(" ") and not line.startswith("\t"):
            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            current_key = key
            if val == "":
                in_list = True
                fm[key] = []
            else:
                in_list = False
                fm[key] = val
        else:
            in_list = False

    return fm


def parse_minutes(raw) -> int | None:
    """Zet time_total (int of string zoals '45 min') om naar minuten."""
    if raw is None or raw == "" or raw == []:
        return None
    s = str(raw).lower().replace("minuten", "").replace("min", "").replace("u", "").strip()
    # Handle "1u30" or "1:30" style? For now just numbers
    try:
        return int(float(s))
    except (ValueError, TypeError):
        return None


def week_str_for_next_week() -> str:
    """Geeft de ISO-weekcode voor de volgende week (bijv. '2026-W22')."""
    today = date.today()
    # Volgende maandag
    days_ahead = 7 - today.weekday()
    next_monday = today + timedelta(days=days_ahead)
    iso = next_monday.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def week_dates(week_str: str) -> tuple[date, date]:
    """Geeft (maandag, vrijdag) terug voor een weekcode."""
    year = int(week_str[:4])
    week = int(week_str[6:])
    monday = date.fromisocalendar(year, week, 1)
    friday = date.fromisocalendar(year, week, 5)
    return monday, friday


def format_date_nl(d: date) -> str:
    """Geeft dag als '19 mei 2026' terug (Nederlandstalig)."""
    maanden = [
        "", "januari", "februari", "maart", "april", "mei", "juni",
        "juli", "augustus", "september", "oktober", "november", "december"
    ]
    return f"{d.day} {maanden[d.month]} {d.year}"


# ---------------------------------------------------------------------------
# Data laden
# ---------------------------------------------------------------------------

def load_recipes() -> tuple[list[dict], dict[str, Path]]:
    """
    Leest alle recepten uit 01 Recipes/.

    Geeft terug:
      - lijst van recipe-dicts met metadata
      - dict van title -> filepath (voor later ingrediënten lezen)
    """
    recipes = []
    title_to_file: dict[str, Path] = {}

    for md_file in RECIPES_DIR.glob("*.md"):
        try:
            content = md_file.read_text(encoding="utf-8", errors="ignore")
            fm = parse_frontmatter(content)

            course = str(fm.get("course") or "").lower().strip()
            if course in EXCLUDED_COURSE_TYPES:
                continue

            title = str(fm.get("title") or md_file.stem)
            cuisine = str(fm.get("cuisine") or "onbekend").lower().strip()
            time_total = parse_minutes(fm.get("time_total"))
            tried = str(fm.get("tried") or "false").lower() == "true"

            rating_raw = fm.get("rating")
            try:
                vault_rating = float(rating_raw) if rating_raw and rating_raw != [] else None
            except (ValueError, TypeError):
                vault_rating = None

            title_to_file[title] = md_file
            recipes.append({
                "title": title,
                "cuisine": cuisine,
                "course": course,
                "time_total": time_total,
                "tried": tried,
                "vault_rating": vault_rating,
            })

        except Exception as e:
            print(f"  Waarschuwing: kon {md_file.name} niet verwerken: {e}", file=sys.stderr)

    return recipes, title_to_file


def load_history(weeks: int = 8) -> tuple[set[str], dict[str, list[float]]]:
    """
    Leest weekplanbestanden uit 03 Weekly Plans/ en geeft terug:
      - set van recept-titels gebruikt in de afgelopen N weken
      - dict van title -> lijst van beoordelingen (getal, uit het weekplan)
    """
    used: set[str] = set()
    ratings: dict[str, list[float]] = {}

    if not PLANS_DIR.exists():
        return used, ratings

    # Sorteer op naam (Week YYYY-Wxx.md), meest recent eerst
    plan_files = sorted(
        PLANS_DIR.glob("Week ????-W??.md"),
        reverse=True
    )[:weeks]

    for plan_file in plan_files:
        try:
            content = plan_file.read_text(encoding="utf-8", errors="ignore")

            # Wikilinks zijn de gebruikte recepten
            for title in re.findall(r'\[\[([^\]|]+)\]\]', content):
                used.add(title.strip())

            # Beoordelingen: "**Beoordeling Recept naam:** 4/5"
            for m in re.finditer(
                r'\*\*Beoordeling ([^:*]+):\*\*\s*(\d(?:\.\d)?)/5',
                content
            ):
                title = m.group(1).strip()
                rating = float(m.group(2))
                ratings.setdefault(title, []).append(rating)

        except Exception as e:
            print(f"  Waarschuwing: kon {plan_file.name} niet lezen: {e}", file=sys.stderr)

    return used, ratings


def load_preferences() -> str:
    """Leest het volledige voorkeuren-bestand."""
    if not PREFS_FILE.exists():
        return "Geen voorkeuren ingesteld."
    return PREFS_FILE.read_text(encoding="utf-8", errors="ignore")


def load_week_specific_prefs(week_str: str) -> str:
    """Haalt de week-specifieke sectie op uit het voorkeuren-bestand."""
    content = load_preferences()
    pattern = rf"##\s*{re.escape(week_str)}\s*\n(.*?)(?=\n##|\Z)"
    m = re.search(pattern, content, re.DOTALL)
    return m.group(1).strip() if m else ""


def load_known_ingredients() -> list[str]:
    """Geeft alle paginanamen terug uit 02 Ingredients/ (bestandsnaam zonder .md)."""
    if not INGREDIENTS_DIR.exists():
        return []
    return sorted(f.stem for f in INGREDIENTS_DIR.glob("*.md"))


# ---------------------------------------------------------------------------
# Ingrediënten lezen
# ---------------------------------------------------------------------------

def read_ingredients_section(title: str, title_to_file: dict[str, Path]) -> str:
    """Leest de ## Ingrediënten sectie uit een receptbestand."""
    file = title_to_file.get(title)
    if not file or not file.exists():
        return f"(Bestand voor '{title}' niet gevonden)"

    content = file.read_text(encoding="utf-8", errors="ignore")
    m = re.search(
        r'##\s*Ingredi[eë]nten[^\n]*\n(.*?)(?=\n##|\Z)',
        content,
        re.DOTALL | re.IGNORECASE
    )
    if m:
        return m.group(1).strip() or "(Lege ingrediëntenlijst)"
    return "(Geen ingrediënten-sectie gevonden in dit recept)"


# ---------------------------------------------------------------------------
# Claude API calls
# ---------------------------------------------------------------------------

def select_recipes(
    recipes: list[dict],
    excluded: set[str],
    history_ratings: dict[str, list[float]],
    preferences: str,
    week_str: str,
    week_specific_prefs: str,
) -> dict:
    """
    Vraagt Claude om 5 diners te kiezen (3 simpel, 2 uitgebreid).
    Geeft een dict terug met de gestructureerde selectie.
    """
    client = anthropic.Anthropic()

    monday, friday = week_dates(week_str)

    # Gemiddelde beoordelingen uit weekplannen
    avg_ratings = {
        t: round(sum(r) / len(r), 1)
        for t, r in history_ratings.items()
    }

    # Splits recepten in categorieën
    main_courses = []
    side_dishes = []
    desserts = []

    for r in recipes:
        course = r["course"]
        entry = {
            "title": r["title"],
            "cuisine": r["cuisine"],
            "time_total": r["time_total"],
            "recently_used": r["title"] in excluded,
            "avg_rating_from_plans": avg_ratings.get(r["title"]),
            "tried": r["tried"],
        }
        if course in MAIN_COURSE_TYPES:
            main_courses.append(entry)
        elif course in DESSERT_TYPES:
            desserts.append(entry)
        elif course in SIDE_COURSE_TYPES:
            side_dishes.append(entry)

    # Datums voor de 5 weekdagen
    weekday_dates = [
        (["Maandag", "Dinsdag", "Woensdag", "Donderdag", "Vrijdag"][i],
         format_date_nl(monday + timedelta(days=i)))
        for i in range(5)
    ]

    prompt = f"""Je bent een weekmenu-samensteller voor een Obsidian receptenvault.

Vandaag is het {format_date_nl(date.today())}. Stel het weekmenu samen voor:
- Maandag {format_date_nl(monday)} t/m vrijdag {format_date_nl(friday)}

## Voorkeuren (algemeen)
{preferences}

## Week-specifieke voorkeur voor {week_str}
{week_specific_prefs if week_specific_prefs else "Geen bijzondere voorkeur. Gebruik de algemene voorkeuren."}

## Opdracht
Kies precies 5 avonddiners:
- 3 SIMPEL: alleen hoofdgerecht, bereidingstijd bij voorkeur ≤{SIMPLE_MAX_MINUTES} min
- 2 UITGEBREID: hoofdgerecht + minimaal 1 bijgerecht, optioneel dessert

Regels:
1. recently_used = true → NIET kiezen (tenzij er echt niets anders is)
2. avg_rating_from_plans < 3 → liever niet kiezen
3. Niet meer dan 2× dezelfde keuken in de week
4. Koppel bijgerechten/desserts qua keuken aan het hoofdgerecht
5. Simpele diners op ma/di/do, uitgebreide op wo/vr (tenzij week-voorkeur anders zegt)

## Beschikbare hoofdgerechten
{json.dumps(main_courses, ensure_ascii=False)}

## Beschikbare bijgerechten
{json.dumps(side_dishes, ensure_ascii=False)}

## Beschikbare desserts
{json.dumps(desserts, ensure_ascii=False)}

## Gevraagd formaat
Geef ALLEEN geldig JSON terug, geen tekst eromheen:

{{
  "week": "{week_str}",
  "redenering": "Max 2 zinnen over de keukenskeuzes.",
  "diners": [
    {{
      "dag": "Maandag",
      "datum": "{weekday_dates[0][1]}",
      "type": "simpel",
      "hoofdgerecht": "<exacte titel>",
      "bijgerechten": [],
      "dessert": null
    }},
    {{
      "dag": "Dinsdag",
      "datum": "{weekday_dates[1][1]}",
      "type": "simpel",
      "hoofdgerecht": "<exacte titel>",
      "bijgerechten": [],
      "dessert": null
    }},
    {{
      "dag": "Woensdag",
      "datum": "{weekday_dates[2][1]}",
      "type": "uitgebreid",
      "hoofdgerecht": "<exacte titel>",
      "bijgerechten": ["<exacte titel>"],
      "dessert": null
    }},
    {{
      "dag": "Donderdag",
      "datum": "{weekday_dates[3][1]}",
      "type": "simpel",
      "hoofdgerecht": "<exacte titel>",
      "bijgerechten": [],
      "dessert": null
    }},
    {{
      "dag": "Vrijdag",
      "datum": "{weekday_dates[4][1]}",
      "type": "uitgebreid",
      "hoofdgerecht": "<exacte titel>",
      "bijgerechten": ["<exacte titel>"],
      "dessert": null
    }}
  ]
}}

Zorg dat elke titel EXACT overeenkomt met een titel uit de lijsten hierboven."""

    response = call_claude_with_retry(
        client,
        model=CLAUDE_MODEL,
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )

    text = response.content[0].text.strip()
    # Verwijder eventuele markdown code-fences
    text = re.sub(r'^```(?:json)?\s*\n?', '', text)
    text = re.sub(r'\n?```\s*$', '', text)

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        print(f"Fout bij parsen van Claude-respons: {e}", file=sys.stderr)
        print(f"Ontvangen tekst:\n{text}", file=sys.stderr)
        raise


def build_shopping_list(
    week_plan: dict,
    ingredients_per_recipe: dict[str, str],
    known_ingredients: list[str],
) -> str:
    """Vraagt Claude om een gecategoriseerde boodschappenlijst te genereren."""
    client = anthropic.Anthropic()

    ingredient_block = ""
    for diner in week_plan["diners"]:
        all_recipes = [diner["hoofdgerecht"]] + diner.get("bijgerechten", [])
        if diner.get("dessert"):
            all_recipes.append(diner["dessert"])
        for title in all_recipes:
            ingredient_block += f"\n### {title}\n{ingredients_per_recipe.get(title, '(niet gevonden)')}\n"

    known_list = "\n".join(f"- {name}" for name in known_ingredients)

    prompt = f"""Maak een boodschappenlijst op basis van onderstaande ingrediënten.

{ingredient_block}

REGELS — lees ze goed:

1. **Één ingredient per regel.** Combineer nooit twee verschillende ingrediënten op één regel.
   Komkommer en aubergine zijn twee aparte regels.

2. **Gebruik winkellogica voor hoeveelheden.**
   - Groenten/fruit: stuks, bossen, zakjes (bijv. "3 uien", "1 bosje koriander", "400 g spitskool")
   - Vlees/vis: gram of stuks (bijv. "500 g kipfilet", "4 zalmfilets")
   - Gember: "een stuk gember" — nooit centimeters
   - Knoflook: "1 bol knoflook" als je meer dan ~6 teentjes nodig hebt, anders "X teentjes knoflook"
   - Sauzen/droog: fles, blik, zakje, theelepels (bijv. "1 blik kokosmelk", "ketoembar")
   - Wanneer een hoeveelheid onbekend of heel klein is, schrijf dan alleen de naam

3. **Tel hoeveelheden op** als hetzelfde ingrediënt in meerdere recepten voorkomt.
   Rond af naar een praktische winkelhoeveelheid.

4. **Geen receptnamen achter de ingrediënten.** De shopper hoeft niet te weten waar iets voor is.

5. **Categorieën** (gebruik vette koppen):
   **Groenten & Fruit** | **Vlees & Vis** | **Zuivel & Eieren** | **Droog & Conserven** | **Kruiden & Specerijen** | **Overig**

6. Sorteer alfabetisch binnen elke categorie.

7. **Wikilinks:** Hieronder staat de lijst van bekende ingrediëntpagina's in de vault.
   Als de naam van een ingrediënt overeenkomt met (of zeer dicht bij) een naam in deze lijst,
   gebruik dan die exacte paginanaam als wikilink: `[[paginanaam]]`.
   Gebruik alleen een wikilink als er een goede match is; verzin geen links.

   Bekende ingrediëntpagina's:
{known_list}

8. Formaat per regel: `- [ ] [[paginanaam]] (hoeveelheid)` als er een wikilink is,
   anders: `- [ ] ingrediëntnaam (hoeveelheid)`
   Voorbeelden:
   - [ ] [[komkommer]] (1 stuk)
   - [ ] [[knoflook]] (1 bol)
   - [ ] [[gember]] (een stuk)
   - [ ] [[ketoembar]]
   - [ ] spitskool (400 g)  ← geen wikilink want geen match gevonden

9. Geef ALLEEN de Markdown-inhoud terug, geen inleiding, uitleg of samenvatting."""

    response = call_claude_with_retry(
        client,
        model=CLAUDE_MODEL,
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )

    return response.content[0].text.strip()


# ---------------------------------------------------------------------------
# Markdown genereren
# ---------------------------------------------------------------------------

def render_week_plan(week_plan: dict, week_specific_prefs: str) -> str:
    """Zet een week_plan dict om naar Markdown-inhoud voor de weekplan-note."""
    week_str = week_plan["week"]
    week_num = int(week_str[6:])
    monday, friday = week_dates(week_str)

    maanden = [
        "", "januari", "februari", "maart", "april", "mei", "juni",
        "juli", "augustus", "september", "oktober", "november", "december"
    ]
    header_date = (
        f"{monday.day}–{friday.day} {maanden[friday.month]} {friday.year}"
        if monday.month == friday.month
        else f"{monday.day} {maanden[monday.month]}–{friday.day} {maanden[friday.month]} {friday.year}"
    )

    lines = [
        "---",
        f"week: {week_str}",
        f"date_created: {date.today().isoformat()}",
        "---",
        "",
        f"# Weekmenu Week {week_num} ({header_date})",
        "",
    ]

    redenering = week_plan.get("redenering", "")
    if redenering:
        lines += [f"> {redenering}", ""]

    if week_specific_prefs:
        lines += [f"> **Week-voorkeur:** {week_specific_prefs}", ""]

    lines += [f"Boodschappenlijst: [[Week {week_str} Boodschappen]]", "", "---", ""]

    for diner in week_plan["diners"]:
        dag = diner["dag"]
        datum = diner.get("datum", "")
        type_label = diner["type"].capitalize()
        hoofdgerecht = diner["hoofdgerecht"]
        bijgerechten = diner.get("bijgerechten") or []
        dessert = diner.get("dessert")

        lines += [
            f"## {dag} {datum} — {type_label}",
            "",
            f"**Hoofdgerecht:** [[{hoofdgerecht}]]",
        ]

        for bg in bijgerechten:
            lines.append(f"**Bijgerecht:** [[{bg}]]")

        if dessert:
            lines.append(f"**Dessert:** [[{dessert}]]")

        lines.append("")

        # Beoordelingsvelden (achteraf in te vullen)
        lines.append(f"**Beoordeling {hoofdgerecht}:** _/5  ")
        for bg in bijgerechten:
            lines.append(f"**Beoordeling {bg}:** _/5  ")
        if dessert:
            lines.append(f"**Beoordeling {dessert}:** _/5  ")

        lines += ["", "---", ""]

    return "\n".join(lines)


def render_shopping_list(week_str: str, shopping_content: str, week_plan: dict) -> str:
    """Wikkelt de boodschappenlijst in een Markdown-note."""
    week_num = int(week_str[6:])
    monday, _ = week_dates(week_str)

    all_recipes = []
    for diner in week_plan["diners"]:
        all_recipes.append(diner["hoofdgerecht"])
        all_recipes.extend(diner.get("bijgerechten") or [])
        if diner.get("dessert"):
            all_recipes.append(diner["dessert"])

    recipe_links = ", ".join(f"[[{r}]]" for r in all_recipes)

    return (
        f"---\n"
        f"week: {week_str}\n"
        f"date_created: {date.today().isoformat()}\n"
        f"---\n\n"
        f"# Boodschappen Week {week_num}\n\n"
        f"*Weekplan: [[Week {week_str}]]*  \n"
        f"*Recepten: {recipe_links}*\n\n"
        f"---\n\n"
        f"{shopping_content}\n"
    )


# ---------------------------------------------------------------------------
# Hoofdprogramma
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Genereer een weekmenu en boodschappenlijst voor de Obsidian receptenvault."
    )
    parser.add_argument(
        "--week",
        default="",
        metavar="YYYY-Www",
        help="Weekcode (bijv. 2026-W22). Standaard: de komende week.",
    )
    parser.add_argument(
        "--week-voorkeur",
        default="",
        metavar="TEKST",
        help="Voorkeur voor deze specifieke week (overschrijft sectie in _Voorkeuren.md).",
    )
    args = parser.parse_args()

    week_str = args.week or week_str_for_next_week()
    print(f"\n=== Weekmenu Generator - {week_str} ===\n")

    # Laad API key uit bestand; omgevingsvariabele heeft voorrang
    if not os.environ.get("ANTHROPIC_API_KEY"):
        if not API_KEY_FILE.exists():
            print(
                f"Fout: API key niet gevonden.\n"
                f"Verwacht op: {API_KEY_FILE}",
                file=sys.stderr
            )
            sys.exit(1)
        os.environ["ANTHROPIC_API_KEY"] = API_KEY_FILE.read_text(encoding="utf-8").strip()

    PLANS_DIR.mkdir(exist_ok=True)

    plan_file = PLANS_DIR / f"Week {week_str}.md"
    if plan_file.exists():
        print(f"Weekmenu voor {week_str} bestaat al ({plan_file.name}). Overgeslagen.")
        print("Gebruik --week <andere-week> om een ander weekmenu te genereren.")
        sys.exit(0)

    print("Recepten laden...")
    recipes, title_to_file = load_recipes()
    print(f"  {len(recipes)} recepten gevonden")

    print("Weekplanhistorie lezen (laatste 8 weken)...")
    excluded, history_ratings = load_history(weeks=8)
    print(f"  {len(excluded)} recepten recent gebruikt -> worden overgeslagen")

    preferences = load_preferences()
    week_specific_prefs = args.week_voorkeur or load_week_specific_prefs(week_str)

    print("Weekschema samenstellen via Claude...")
    week_plan = select_recipes(
        recipes=recipes,
        excluded=excluded,
        history_ratings=history_ratings,
        preferences=preferences,
        week_str=week_str,
        week_specific_prefs=week_specific_prefs,
    )

    # Toon selectie
    print("\nGeselecteerde diners:")
    for diner in week_plan["diners"]:
        extra = ""
        if diner.get("bijgerechten"):
            extra = " + " + ", ".join(diner["bijgerechten"])
        if diner.get("dessert"):
            extra += f" + {diner['dessert']}"
        print(f"  {diner['dag']:10s} [{diner['type']:10s}] {diner['hoofdgerecht']}{extra}")

    print("\nIngredienten lezen voor geselecteerde recepten...")
    recipe_ingredients: dict[str, str] = {}
    for diner in week_plan["diners"]:
        all_r = [diner["hoofdgerecht"]] + (diner.get("bijgerechten") or [])
        if diner.get("dessert"):
            all_r.append(diner["dessert"])
        for title in all_r:
            if title not in recipe_ingredients:
                recipe_ingredients[title] = read_ingredients_section(title, title_to_file)

    print("Bekende ingrediënten laden...")
    known_ingredients = load_known_ingredients()
    print(f"  {len(known_ingredients)} ingredientpagina's gevonden")

    print("Boodschappenlijst genereren via Claude...")
    shopping_content = build_shopping_list(week_plan, recipe_ingredients, known_ingredients)

    # Schrijf bestanden
    shopping_file = PLANS_DIR / f"Week {week_str} Boodschappen.md"

    plan_file.write_text(render_week_plan(week_plan, week_specific_prefs), encoding="utf-8")
    print(f"\nWeekschema geschreven:      {plan_file}")

    shopping_file.write_text(
        render_shopping_list(week_str, shopping_content, week_plan),
        encoding="utf-8"
    )
    print(f"Boodschappenlijst geschreven: {shopping_file}")
    print("\nKlaar!")


if __name__ == "__main__":
    main()
