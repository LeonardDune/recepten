# weekmenu_taak_registreren.ps1
# Registreert de weekmenu-taak in Windows Taakplanner (elke vrijdag om 08:00).
# Voer éénmalig uit als Administrator:
#   Rechtermuisknop op dit bestand → "Uitvoeren met PowerShell"
#   Of: powershell -ExecutionPolicy Bypass -File weekmenu_taak_registreren.ps1

$TaskName = "Obsidian Weekmenu Generator"
$BatFile  = Join-Path $PSScriptRoot "weekmenu.bat"

# Verwijder bestaande taak met dezelfde naam (voor herinstallatie)
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Bestaande taak '$TaskName' verwijderd."
}

# Actie: voer het .bat-bestand uit
$Action = New-ScheduledTaskAction `
    -Execute "cmd.exe" `
    -Argument "/c `"$BatFile`""

# Trigger: elke vrijdag om 08:00
$Trigger = New-ScheduledTaskTrigger `
    -Weekly `
    -DaysOfWeek Friday `
    -At "08:00"

# Instellingen
$Settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 15) `
    -MultipleInstances IgnoreNew `
    -StartWhenAvailable   # Start alsnog als de pc om 08:00 uit stond

# Registreer als huidige gebruiker
Register-ScheduledTask `
    -TaskName $TaskName `
    -Action   $Action `
    -Trigger  $Trigger `
    -Settings $Settings `
    -RunLevel Highest `
    -Force | Out-Null

Write-Host ""
Write-Host "Taak '$TaskName' succesvol geregistreerd."
Write-Host "De taak draait elke vrijdag om 08:00."
Write-Host ""
Write-Host "Controleren: open Taakplanner (taskschd.msc) en zoek op '$TaskName'."
Write-Host "Handmatig starten: Start-ScheduledTask -TaskName '$TaskName'"
