# Weekmenu Voorkeuren

Dit bestand bepaalt hoe het weekmenu wordt samengesteld. Het script leest dit bestand
elke vrijdag automatisch. Pas het aan naar wens; het wordt niet overschreven door het script.

---

## Algemene voorkeuren

### Keukens

Geef per keuken aan hoe vaak je die per maand wilt eten (0 = nooit, 1 = zelden, 2 = soms, 3 = regelmatig, 5 = graag).

| Keuken          | Voorkeur (0–5) | Notities                        |
|-----------------|----------------|---------------------------------|
| indonesisch     | 5              | Favoriet, gerust 2× per week    |
| aziatisch       | 4              |                                 |
| italiaans       | 3              |                                 |
| mediterraan     | 3              |                                 |
| internationaal  | 2              |                                 |
| amerikaans      | 2              |                                 |
| spaans          | 2              |                                 |
| indiaas         | 2              |                                 |
| mexicaans       | 2              |                                 |
| overig          | 1              |                                 |

### Afwisseling

- Niet meer dan 2× dezelfde keuken per week
- Wissel af tussen vlees, vis en vegetarisch (minimaal 1× vis en 1× vegetarisch per week als mogelijk)
- Simpele diners bij voorkeur op drukke dagen (ma, di, do)
- Uitgebreide diners bij voorkeur op rustiger dagen (wo, vr)

### Dieetwensen / allergieën

<!-- Vul hier eventuele dieetwensen of allergieën in -->
Geen

---

## Week-specifieke voorkeuren

Voeg hieronder een sectie toe voor weken waarvoor je iets speciaals wilt.
Het script herkent secties op weekcode (bijv. `## 2026-W22`).
Verwijder of overschrijf de sectie na die week; het script gebruikt altijd alleen de
sectie die overeenkomt met de komende weekcode.

Voorbeeld:

```
## 2026-W22
Deze week graag minstens één Spaans gerecht. Geen vis, ik heb een uitgebreide werkweek
dus alle 5 diners mogen simpel zijn.
```

<!-- Voeg week-specifieke secties hieronder toe: -->
