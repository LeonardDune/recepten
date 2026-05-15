# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Obsidian vault voor een "Karpathy-style" Second Brain voor recepten en ingrediënten. Taal: Nederlands. Geautomatiseerde capture via n8n + AI; handmatige capture via de Obsidian Web Clipper browser-extensie.

## Vault Structuur

```
01 Recipes/       ← alle recepten als Markdown notes
02 Ingredients/   ← atomische notes per ingrediënt
04 Templates/     ← Obsidian core-template bestanden
_Setup/           ← importbestanden (Web Clipper JSON, n8n workflow JSON)
00 Dashboard.md   ← Dataview overzicht
```

`.obsidian/` bevat vault-configuratie — niet handmatig bewerken.

## Properties (Frontmatter) Schema

Elk recept in `01 Recipes/` heeft:

| Property | Type | Voorbeeld |
|---|---|---|
| `title` | text | "Spaghetti Carbonara" |
| `source` | text | URL van het originele recept |
| `date_added` | date | 2026-04-10 |
| `cuisine` | text | italiaans |
| `course` | text | hoofdgerecht |
| `servings` | number | 4 |
| `time_prep` | text | 15 min |
| `time_cook` | text | 20 min |
| `time_total` | text | 35 min |
| `rating` | number | 5 |
| `tried` | checkbox | false |
| `tags` | multitext | recipe, cuisine/italiaans, course/hoofdgerecht |

Ingrediënten worden als `[[wikilinks]]` geschreven zodat ze linken naar notes in `02 Ingredients/`.

## Dataview Queries

Het `00 Dashboard.md` vereist de [Dataview](https://github.com/blacksmithgu/obsidian-dataview) community plugin. Ingrediënt-notes gebruiken ook Dataview voor backlink-overzichten.

## Web Clipper Setup

1. Installeer de [Obsidian Web Clipper](https://obsidian.md/clipper) browser-extensie.
2. Importeer `_Setup/Web Clipper - Recept.json` als template in de extensie.
3. De template activeert automatisch op geconfigureerde receptsites (culy.nl, allerhande.nl, etc.).

## Synchronisatie-architectuur

```
n8n (cloud)
  └─→ GitHub private repo (bridge)
        └─→ Obsidian Git plugin (pull bij opstarten)
              └─→ Lokale vault op laptop
```

n8n schrijft **niet** direct naar de laptop. GitHub fungeert als tussenlaag.

## n8n Workflow Setup

Bestand: `_Setup/n8n - Recept Monitor.json` — importeer via n8n > Workflows > Import.

Na import configureer je drie dingen:

1. **RSS Feed node** — verander de URL naar de feed van de site die je wilt monitoren. Meerdere sites: dupliceer de node en verbind alle feeds naar "Filter Nieuwe Items".
2. **Extraheer Recept (AI) node** — koppel je OpenAI API credential in n8n.
3. **Sla Op in GitHub node** — maak een [GitHub Personal Access Token](https://github.com/settings/tokens) aan met `repo` scope. Voeg toe als GitHub credential in n8n. Pas `owner` en `repository` aan in de node-parameters.

## Laptop Sync: Obsidian Git

Installeer de [Obsidian Git](https://github.com/denolehov/obsidian-git) community plugin en zet in de instellingen:

- **Pull updates on startup**: aan
- **Vault backup interval**: 30 of 60 minuten
- **Push on backup**: aan

Zo haalt Obsidian bij elke start automatisch nieuwe recepten van GitHub binnen, en worden lokale wijzigingen teruggestuurd.

## Windows Startup Script

`_Setup/start-obsidian.bat` — voer eerst een `git pull` uit en start daarna Obsidian. Kopieer naar de Windows opstartmap (`Win+R` → `shell:startup`) voor volledig automatische sync bij pc-start.

## Foto-input via Claude Code (iPhone)

Als een foto van een recept wordt gedeeld (zonder andere context, of met alleen een korte instructie zoals "zet dit in de vault"), verwerk die dan automatisch naar een nieuwe note in `01 Recipes/`.

### Werkwijze

1. **Lees de foto** — extraheer titel, ingrediënten, bereidingsstappen, porties en tijden.

2. **Vertaal alles naar Nederlands**: titel, ingrediënten, bereiding én notities. Geen enkel veld in een andere taal laten staan.

3. **Zet maten om naar het metrische stelsel**:
   - cups → ml (1 cup = 240 ml)
   - fluid ounces → ml (1 fl oz = 30 ml)
   - ounces gewicht → gram (1 oz = 28 g)
   - pounds → gram of kg (1 lb = 450 g)
   - inches → cm
   - °F → °C
   - Rond af naar praktische kookmaten (bijv. 236 ml → 240 ml, 113 g → 115 g)

4. **Maak de note aan** conform `04 Templates/Recept Template.md`:
   - `title`: vertaalde Nederlandse titel
   - `source`: naam van boek of tijdschrift als zichtbaar in de foto, anders leeg
   - `date_added`: vandaag
   - `cuisine` / `course`: bepaal zelf op basis van het gerecht (lowercase)
   - `rating`: altijd leeg laten
   - `tried`: altijd false
   - `tags`: `recipe`, `cuisine/<cuisine>`, `course/<course>`
   - Ingrediënten als `[[wikilinks]]` (enkelvoud, lowercase), hoeveelheden in metrisch

5. **Bestandsnaam**: de vertaalde titel gevolgd door `.md`. Ongeldige tekens (`: / \ * ? " < > |`) vervangen door een spatie.

6. **Stub-notes**: maak voor elk nieuw ingrediënt een lege note aan in `02 Ingredients/` als die nog niet bestaat, conform `04 Templates/Ingrediënt Template.md`.

7. **Bevestig** na het schrijven: bestandsnaam van het recept + lijst van nieuw aangemaakte ingrediënt-notes.

### Voorbeeld-trigger

> *[foto bijgevoegd]* — geen verdere tekst, of: "Zet dit recept in de vault."

## Weekmenu Generator

Wekelijks weekschema (5 diners) + boodschappenlijst, gegenereerd via de Claude API.

### Bestanden

| Bestand | Doel |
|---|---|
| `_Setup/weekmenu_generator.py` | Hoofdscript — leest vault, roept Claude aan, schrijft notes |
| `_Setup/weekmenu.bat` | Wrapper voor Windows Taakplanner |
| `_Setup/weekmenu_taak_registreren.ps1` | Éénmalig registreren als geplande taak (als Administrator) |
| `_Setup/anthropic-api-key.txt` | Anthropic API key (valt terug op `ANTHROPIC_API_KEY` env-variabele) |
| `03 Weekly Plans/` | Output-map: weekschema's en boodschappenlijsten |
| `03 Weekly Plans/_Voorkeuren.md` | Algemene én week-specifieke voorkeuren |

### Gebruik

```bash
# Komende week (standaard)
python _Setup/weekmenu_generator.py

# Specifieke week
python _Setup/weekmenu_generator.py --week 2026-W22

# Met week-specifieke voorkeur (overschrijft _Voorkeuren.md)
python _Setup/weekmenu_generator.py --week-voorkeur "graag Aziatisch deze week"
```

Vereist: `pip install anthropic`

### Automatisch draaien (Windows Taakplanner)

De taak draait elke vrijdag om 08:00 en genereert het menu voor de komende week.

1. Voer `weekmenu_taak_registreren.ps1` éénmalig uit als Administrator.
2. Controleer via `taskschd.msc` → zoek op "Obsidian Weekmenu Generator".
3. Log staat in `_Setup/weekmenu_log.txt`.

### Output-structuur

Per week worden twee notes aangemaakt in `03 Weekly Plans/`:

- **`Week YYYY-Www.md`** — weekoverzicht per dag (hoofdgerecht, bijgerechten, dessert, beoordelingsvelden)
- **`Week YYYY-Www Boodschappen.md`** — gecategoriseerde boodschappenlijst met checkboxes en wikilinks naar `02 Ingredients/`

### Logica

- **3 simpele** diners (≤ 35 min, alleen hoofdgerecht) op ma/di/do
- **2 uitgebreide** diners (hoofdgerecht + bijgerecht, optioneel dessert) op wo/vr
- Recepten uit de afgelopen 8 weken worden overgeslagen
- Beoordelingen uit eerdere weekplannen wegen mee bij de selectie
- Niet meer dan 2× dezelfde keuken per week
- Week-specifieke voorkeuren staan als `## YYYY-Www`-sectie in `_Voorkeuren.md`

## Vereiste Community Plugins

| Plugin | Doel |
|---|---|
| [Dataview](https://github.com/blacksmithgu/obsidian-dataview) | Dashboard queries |
| [Obsidian Git](https://github.com/denolehov/obsidian-git) | Automatische sync met GitHub |
