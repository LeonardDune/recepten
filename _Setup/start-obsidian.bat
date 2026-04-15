@echo off
:: Start-script voor Obsidian Recepten Vault
:: Zet dit bestand in je Windows Opstartmap:
::   Win+R → shell:startup → kopieer dit bestand daarnaar

:: Synchroniseer vault met GitHub voordat Obsidian opent
cd /d "C:\Users\Renzo\Documents\Renzo\recepten"

:: Commit lokale wijzigingen (bijv. via Web Clipper) vóór de pull
:: Zo gaat er nooit iets verloren en loopt de pull niet vast
git add -A
git diff --cached --quiet || git commit -m "vault backup: lokale wijzigingen voor sync"

:: Haal remote wijzigingen op (n8n recepten)
git pull origin main

:: Start de recept-watcher als verborgen achtergrondproces
:: PowerShell -WindowStyle Hidden zodat er geen extra venster openblijft
start "" /B powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "%~dp0recept-watcher.ps1"

:: Start Obsidian
start "" "C:\Users\Renzo\AppData\Local\Programs\Obsidian\Obsidian.exe"
