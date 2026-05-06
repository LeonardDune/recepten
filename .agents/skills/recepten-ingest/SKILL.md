---
name: recepten-ingest
description: >
  Verwerk onverwerkte recepten in de vault. Gebruik wanneer nieuwe recepten
  zijn geclipped via de Web Clipper maar nog geen verwerkt-markering hebben,
  of wanneer de dagelijkse taak onverwerkte recepten detecteert. Vult
  frontmatter aan, vertaalt ingrediënten naar Nederlands, voegt wikilinks toe.
allowed-tools: Bash Read Write Edit Glob Grep
---

# Recepten — Ingest

Verwerk ruwe, geclipte recepten naar het standaardformaat van de vault.

## Stap 1 — Detecteer onverwerkte recepten

```bash
python brain.py --stats
```

Een recept is onverwerkt als het **geen** `<!-- verwerkt -->` markering heeft in de `## Notities` sectie. Zoek alle onverwerkte recepten:

```bash
python3 -c "
from pathlib import Path
recipes = Path('01 Recipes')
for f in sorted(recipes.glob('*.md')):
    text = f.read_text(encoding='utf-8', errors='ignore')
    if '<!-- verwerkt -->' not in text and len(text) > 200:
        print(f.name)
"
```

Als er geen onverwerkte recepten zijn, stop dan en meld dit.

## Stap 2 — Verwerk elk recept

Voor elk onverwerkt recept, pas het aan naar het standaardformaat:

### 2a. Frontmatter aanvullen

Elk recept heeft deze frontmatter-velden nodig. Bepaal de waarden op basis van de recepttekst:

```yaml
---
title: "Naam van het recept"
source: "URL van het originele recept"
date_added: YYYY-MM-DD
cuisine: [lowercase: italiaans, mexicaans, amerikaans, nl, aziatisch, ...]
course: [lowercase: voorgerecht, hoofdgerecht, bijgerecht, soep, nagerecht, snack, tapas, ontbijt, lunch]
servings: [getal]
time_prep: "X min"
time_cook: "X min / X uur"
time_total: "X min / X uur X min"
rating:
tried: false
tags:
  - recipe
  - cuisine/{cuisine}
  - course/{course}
  - [overige relevante tags]
---
```

### 2b. Ingrediënten naar Nederlands met wikilinks

Schrijf elk ingrediënt als bullet point:
- Hoeveelheid + eenheid als platte tekst, ingrediëntnaam als `[[wikilink]]`
- Gebruik enkelvoud en lowercase voor de wikilink
- Als weergavenaam verschilt: `[[wikilink|weergavenaam]]`
- Groepen met **vetgedrukte** titel als het recept secties heeft

Voorbeelden:
```
- 500 gr [[gehakt]]
- 2 [[sjalot|sjalotjes]]
- 1 el [[tomatenpuree]]
- snuf [[paprikapoeder]]
```

Water en zout/peper hoeven geen wikilink.

### 2c. Bereiding in correct Nederlands

- Genummerde lijst van stappen
- Helder Nederlands, geen reclametekst
- Verwijs naar ingrediënten met `[[wikilink]]` waar logisch

### 2d. Verwijder ongewenste content

Verwijder volledig:
- Base64-data (`data:image/...;base64,...`)
- Sectie "Volledig artikel" en alles daarna (tenzij enige bron)
- Navigatie, reclame, stemmen, kookstandtips, voedingswaarden van de site

### 2e. Sluit af met Notities-sectie

```markdown
## Notities

<!-- verwerkt -->
```

## Stap 3 — Controleer ingrediëntstubs

Na het verwerken, controleer op ontbrekende ingrediëntstubs:

```bash
python brain.py --gaps
```

Als er veelgebruikte ingrediënten zijn zonder eigen pagina in `02 Ingredients/`, maak de stubs aan:

```bash
python brain.py --gaps --create
```

## Stap 4 — Meld resultaten

Meld aan de gebruiker:
- Welke recepten verwerkt zijn
- Welke ingrediëntstubs nieuw aangemaakt zijn
- Hoeveel recepten nog in de wachtrij staan

## Verwante tools

- `brain.py --query "..."` — stel een open vraag aan Claude met alle recepten als context
- `brain.py --stats` — overzicht van de vault
