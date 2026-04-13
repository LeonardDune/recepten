---
tags:
  - dashboard
---

# Recept Dashboard

> Vereist de [Dataview](https://github.com/blacksmithgu/obsidian-dataview) community plugin.

---

## Alle Recepten

```dataview
TABLE WITHOUT ID
  file.link AS "Recept",
  cuisine AS "Keuken",
  course AS "Gang",
  time_total AS "Tijd",
  rating AS "⭐"
FROM "01 Recipes"
WHERE contains(tags, "recipe")
SORT rating DESC
```

---

## Recent Toegevoegd

```dataview
TABLE WITHOUT ID
  file.link AS "Recept",
  date_added AS "Toegevoegd",
  cuisine AS "Keuken"
FROM "01 Recipes"
SORT date_added DESC
LIMIT 10
```

---

## Nog Niet Geprobeerd

```dataview
TABLE WITHOUT ID
  file.link AS "Recept",
  cuisine AS "Keuken",
  time_total AS "Tijd"
FROM "01 Recipes"
WHERE tried = false
SORT date_added DESC
```

---

## Per Keuken

```dataview
TABLE WITHOUT ID
  cuisine AS "Keuken",
  length(rows) AS "Aantal"
FROM "01 Recipes"
WHERE contains(tags, "recipe")
GROUP BY cuisine
SORT length(rows) DESC
```

---

## Favorieten (⭐⭐⭐⭐⭐)

```dataview
TABLE WITHOUT ID
  file.link AS "Recept",
  cuisine AS "Keuken",
  time_total AS "Tijd"
FROM "01 Recipes"
WHERE rating = 5
SORT cuisine ASC
```
