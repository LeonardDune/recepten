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

## Vereiste Community Plugins

| Plugin | Doel |
|---|---|
| [Dataview](https://github.com/blacksmithgu/obsidian-dataview) | Dashboard queries |
| [Obsidian Git](https://github.com/denolehov/obsidian-git) | Automatische sync met GitHub |
