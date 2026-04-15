# recept-watcher.ps1
# Bewaakt 01 Recipes/ en verwerkt nieuwe recepten automatisch via de Claude API.
# Gestart als achtergrondproces vanuit start-obsidian.bat.

$vaultPath  = "C:\Users\Renzo\Documents\Renzo\recepten"
$recipesDir = "$vaultPath\01 Recipes"
$apiKeyFile = "$vaultPath\_Setup\anthropic-api-key.txt"
$ingDir     = "$vaultPath\02 Ingredients"

function Invoke-Recept {
    param([string]$filePath)

    # Wacht tot Web Clipper klaar is met schrijven
    Start-Sleep -Seconds 3

    if (-not (Test-Path $filePath)) { return }

    $content = [System.IO.File]::ReadAllText($filePath, [System.Text.Encoding]::UTF8)

    # Sla over: al verwerkt of te kort
    if ($content -match "<!--\s*verwerkt\s*-->") { return }
    if ($content.Length -lt 200) { return }

    $apiKey = (Get-Content -Path $apiKeyFile -Raw).Trim()

    Write-Host "$(Get-Date -Format 'HH:mm:ss') Verwerken: $(Split-Path $filePath -Leaf)"

    # Bouw de prompt — gebruik @'...'@ (single-quote here-string) voor de vaste tekst
    $instructies = @'
INSTRUCTIES:

1. FRONTMATTER — vul alle velden in op basis van de tekst:
   - title: gebruik de bestaande waarde uit de frontmatter
   - source: gebruik de bestaande waarde uit de frontmatter
   - date_added: gebruik de bestaande waarde uit de frontmatter
   - cuisine: bepaal zelf (lowercase, bijv: spaans, italiaans, nederlands, grieks, aziatisch)
   - course: bepaal zelf (lowercase: voorgerecht, hoofdgerecht, bijgerecht, nagerecht, snack, tapas, ontbijt, lunch)
   - servings: alleen het getal (bijv: 4), laat leeg als onbekend
   - time_prep: voorbereidingstijd (bijv: "15 min"), laat leeg als onbekend
   - time_cook: kooktijd (bijv: "20 min"), laat leeg als onbekend
   - time_total: bereken zelf als time_prep + time_cook, laat leeg als onbekend
   - rating: altijd leeg laten
   - tried: altijd false
   - image: gebruik de bestaande waarde uit de frontmatter
   - tags: array met "recipe", "cuisine/<cuisine>", "course/<course>"

2. INGREDIENTEN — schrijf elk ingrediënt als bullet point:
   - Hoeveelheid + eenheid als platte tekst, ingredientnaam als [[wikilink]]
   - Gebruik enkelvoud en lowercase voor de wikilink-naam
   - Als de wikilink-naam verschilt van de weergavenaam: [[wikilink|weergavenaam]]
   - Voorbeelden: "500 gr [[gehakt]]", "2 [[sjalot|sjalotjes]]", "snuf [[paprikapoeder]]"
   - Water en zout/peper hoeven geen wikilink
   - Groepen met **vetgedrukte** titel als het recept secties heeft

3. BEREIDING — genummerde lijst van stappen, duidelijk Nederlands, geen reclame.

4. VERWIJDER VOLLEDIG:
   - Alle base64 data (data:image/svg+xml;base64,...)
   - Sectie "*Volledig artikel*" en alles daarna (tenzij enige bron voor ingredienten/bereiding)
   - Navigatie, reclame, stemmen, kookstand-tips, voedingswaarden, uitgebreide tips van de site
   - Dubbele content

5. Sluit af met een lege ## Notities sectie gevolgd door <!-- verwerkt -->

OUTPUT: uitsluitend schone Obsidian markdown, begin direct met ---, geen uitleg, geen codeblock.
'@

    $prompt = "Je verwerkt een ruwe, geclipte recept-pagina naar een schone Obsidian markdown note.`n`nRUWE INPUT:`n$content`n`n$instructies"

    $body = [ordered]@{
        model      = "claude-sonnet-4-6"
        max_tokens = 4096
        messages   = @(@{ role = "user"; content = $prompt })
    } | ConvertTo-Json -Depth 10 -Compress

    try {
        $wc = New-Object System.Net.WebClient
        $wc.Headers["x-api-key"]         = $apiKey
        $wc.Headers["anthropic-version"] = "2023-06-01"
        $wc.Headers["Content-Type"]      = "application/json"

        $responseBytes = $wc.UploadData("https://api.anthropic.com/v1/messages", "POST", [System.Text.Encoding]::UTF8.GetBytes($body))
        $responseText  = [System.Text.Encoding]::UTF8.GetString($responseBytes)
        $parsed        = $responseText | ConvertFrom-Json
        $cleaned       = $parsed.content[0].text.Trim()

        # Schrijf het opgeschoonde recept terug
        [System.IO.File]::WriteAllText($filePath, $cleaned, [System.Text.Encoding]::UTF8)

        # Maak stub-notes aan voor nieuwe ingredienten
        $wikilinks = [regex]::Matches($cleaned, '\[\[([^\]|#\n]+?)(?:\|[^\]\n]*)?\]\]') |
                     ForEach-Object { $_.Groups[1].Value.Trim() } |
                     Sort-Object -Unique

        $nieuw = 0
        foreach ($naam in $wikilinks) {
            $stub = "$ingDir\$naam.md"
            if (-not (Test-Path $stub)) {
                $stubContent = "---`ntitle: $naam`ntags:`n  - ingredient`ncategory: `nseason: `nsmoke_point: `norigin: `n---`n`n## Eigenschappen`n`n## Gebruik in recepten`n`n``````dataview`nLIST FROM `"01 Recipes`"`nWHERE contains(file.outlinks, this.file.link)`n``````````n`n## Notities`n"
                [System.IO.File]::WriteAllText($stub, $stubContent, [System.Text.Encoding]::UTF8)
                $nieuw++
            }
        }

        Write-Host "$(Get-Date -Format 'HH:mm:ss') Klaar: $($wikilinks.Count) ingredienten gelinkt, $nieuw nieuwe notes."

    } catch {
        Write-Host "$(Get-Date -Format 'HH:mm:ss') FOUT bij $( Split-Path $filePath -Leaf ): $_"
    }
}

# FileSystemWatcher instellen
$watcher = New-Object System.IO.FileSystemWatcher
$watcher.Path   = $recipesDir
$watcher.Filter = "*.md"
$watcher.EnableRaisingEvents = $true

Write-Host "$(Get-Date -Format 'HH:mm:ss') Recept-watcher gestart. Bewaakt: $recipesDir"

# Verwerk bestaande onverwerkte recepten bij opstart
Get-ChildItem -Path $recipesDir -Filter "*.md" | ForEach-Object {
    $c = [System.IO.File]::ReadAllText($_.FullName, [System.Text.Encoding]::UTF8)
    if ($c.Length -gt 200 -and $c -notmatch "<!--\s*verwerkt\s*-->") {
        Write-Host "$(Get-Date -Format 'HH:mm:ss') Onverwerkt gevonden: $($_.Name)"
        Invoke-Recept -filePath $_.FullName
    }
}

# Luister naar nieuwe bestanden
Register-ObjectEvent -InputObject $watcher -EventName Created -Action {
    Invoke-Recept -filePath $Event.SourceEventArgs.FullPath
} | Out-Null

# Draai totdat het venster wordt gesloten
try {
    while ($true) { Start-Sleep -Seconds 5 }
} finally {
    $watcher.EnableRaisingEvents = $false
    $watcher.Dispose()
}
