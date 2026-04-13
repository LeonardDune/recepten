<%*
// ─────────────────────────────────────────────────────────────────────────────
// RECEPT VERWERKER — Templater folder template voor 01 Recipes/
// Triggered automatisch bij aanmaak van een nieuw bestand door Web Clipper.
// Leest de ruwe content, stuurt het naar de Claude API, schrijft een schone
// note terug met [[wikilinks]] voor ingrediënten.
// ─────────────────────────────────────────────────────────────────────────────

// 1. Lees API key
const keyFile = app.vault.getAbstractFileByPath("_Setup/anthropic-api-key.txt");
if (!keyFile) {
  new Notice("⚠️ Recept Verwerker: geen API key gevonden.\nMaak _Setup/anthropic-api-key.txt aan.", 8000);
  tR = tp.file.content;
  return;
}
const API_KEY = (await app.vault.read(keyFile)).trim();

// 2. Wacht tot Web Clipper klaar is met schrijven (poll max 10 sec)
// Gebruik adapter.read() — leest direct van schijf, omzeilt Obsidian cache.
// tp.file.path(true) geeft op Windows backslashes — normaliseer naar forward slashes.
const vaultRelPath = tp.file.path(true).split("\\").join("/");
let rawContent = "";
for (let i = 0; i < 20; i++) {
  await new Promise(r => setTimeout(r, 500));
  try { rawContent = await app.vault.adapter.read(vaultRelPath); } catch(e) {}
  if (rawContent.length > 200) break;
}

if (rawContent.length < 200) {
  new Notice("⚠️ Recept Verwerker: bestand lijkt leeg na 10 sec. Overgeslagen.", 8000);
  tR = rawContent;
  return;
}

// 3. Voorkom dubbele verwerking
if (rawContent.includes("<!-- verwerkt -->")) {
  tR = rawContent;
  return;
}

new Notice("🍳 Recept verwerken...", 3000);

// 4. Claude API call
const prompt = `Je verwerkt een ruwe, geclipte recept-pagina naar een schone Obsidian markdown note. Wees nauwkeurig en verlies geen informatie.

RUWE INPUT:
${rawContent}

INSTRUCTIES:

1. FRONTMATTER — vul alle velden in op basis van de tekst:
   - title: gebruik de bestaande waarde uit de frontmatter
   - source: gebruik de bestaande waarde uit de frontmatter
   - date_added: gebruik de bestaande waarde uit de frontmatter
   - cuisine: bepaal zelf (lowercase, bijv: spaans, italiaans, nederlanden, grieks, aziatisch...)
   - course: bepaal zelf (lowercase: voorgerecht, hoofdgerecht, bijgerecht, nagerecht, snack, tapas, ontbijt, lunch)
   - servings: alleen het getal (bijv: 4), laat leeg als onbekend
   - time_prep: voorbereidingstijd (bijv: "15 min"), laat leeg als onbekend
   - time_cook: kooktijd (bijv: "20 min"), laat leeg als onbekend
   - time_total: bereken zelf als time_prep + time_cook (bijv: "45 min"), laat leeg als onbekend
   - rating: altijd leeg laten
   - tried: altijd false
   - image: gebruik de bestaande waarde uit de frontmatter
   - tags: array met "recipe", "cuisine/<cuisine>", "course/<course>"

2. INGREDIËNTEN — schrijf elk ingrediënt als bullet point:
   - Hoeveelheid + eenheid als platte tekst, ingrediëntnaam als [[wikilink]]
   - Gebruik enkelvoud en lowercase voor de wikilink-naam
   - Als de wikilink-naam verschilt van de weergavenaam, gebruik dan [[wikilink|weergavenaam]]
   - Voorbeelden:
     * "500 gr [[gehakt]]"
     * "1 [[ei]]"
     * "snuf [[paprikapoeder]]"
     * "2 [[sjalot|sjalotjes]]"
     * "bosje verse [[peterselie]]"
     * "0,5 [[rode peper]]"
   - Als het recept groepen heeft (bijv "Voor de saus:"), gebruik dan **vetgedrukte** groepstitels

3. BEREIDING — genummerde lijst van stappen:
   - Duidelijk en leesbaar Nederlands
   - Geen video-verwijzingen, geen reclame, geen tips van de website

4. VERWIJDER VOLLEDIG:
   - Alle base64 data (data:image/svg+xml;base64,...)
   - De sectie "*Volledig artikel*" en alles wat daarna volgt TENZIJ dat de enige bron is voor ingrediënten of bereiding
   - Navigatie, reclame, stemformulieren, kookstand-tips van de site
   - Dubbele content (bijv: de heading die twee keer staat)
   - Voedingswaarden tabellen
   - Uitgebreide tips-secties van de website (korte bereidingstips in de bereiding zelf zijn OK)

5. SLUIT AF met een lege ## Notities sectie

OUTPUT: geef UITSLUITEND de schone Obsidian markdown terug. Begin direct met ---. Geen uitleg, geen codeblock, geen commentaar.

EXACT DIT FORMAAT:
---
title: "TITEL"
source: "URL"
date_added: YYYY-MM-DD
cuisine: cuisine
course: course
servings: N
time_prep: "N min"
time_cook: "N min"
time_total: "N min"
rating:
tried: false
image: "IMAGE_URL"
tags:
  - recipe
  - cuisine/cuisine
  - course/course
---
![](IMAGE_URL)

> Korte beschrijving van het recept.

---

## Ingrediënten

- N eenheid [[ingrediënt]]

## Bereiding

1. Eerste stap.
2. Tweede stap.

---

## Notities

<!-- verwerkt -->`;

// tp.user.claude_api() is een Templater user script (_Scripts/claude-api.js).
// User scripts draaien als Node.js module en hebben wél toegang tot https etc.
// fetch() en require('obsidian') werken niet in Templater's inline eval-context.

let cleanedContent;
try {
  const data = await tp.user.claudeApi(API_KEY, prompt);

  if (data.error) {
    new Notice("❌ Claude API fout: " + data.error.message, 10000);
    tR = rawContent;
    return;
  }

  cleanedContent = data.content[0].text.trim();

} catch (err) {
  new Notice("❌ API fout: " + err.message, 10000);
  tR = rawContent;
  return;
}

// 5. Maak stub-notes aan voor nieuwe ingrediënten
const wikilinkMatches = [...cleanedContent.matchAll(/\[\[([^\]|#\n]+?)(?:\|[^\]\n]*)?\]\]/g)];
const wikilinks = [...new Set(wikilinkMatches.map(m => m[1].trim()))];

let nieuweIngredienten = 0;
for (const naam of wikilinks) {
  const pad = `02 Ingredients/${naam}.md`;
  if (!app.vault.getAbstractFileByPath(pad)) {
    const stub = `---\ntitle: ${naam}\ntags:\n  - ingredient\ncategory: \nseason: \nsmoke_point: \norigin: \n---\n\n## Eigenschappen\n\n## Gebruik in recepten\n\n\`\`\`dataview\nLIST FROM "01 Recipes"\nWHERE contains(file.outlinks, this.file.link)\n\`\`\`\n\n## Notities\n\n`;
    await app.vault.create(pad, stub);
    nieuweIngredienten++;
  }
}

// Schrijf direct naar het bestand — app.vault.modify() vervangt de volledige content.
// tR zou alleen ingevoegd worden (niet vervangen), vandaar deze aanpak.
const targetFileObj = app.vault.getAbstractFileByPath(vaultRelPath);
if (targetFileObj) {
  await app.vault.modify(targetFileObj, cleanedContent);
}

new Notice(`✅ Klaar! ${wikilinks.length} ingrediënten gelinkt, ${nieuweIngredienten} nieuwe notes aangemaakt.`, 6000);

tR = "";
%>
