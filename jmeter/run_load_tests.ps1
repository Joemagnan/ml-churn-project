# Campagnes de charge JMeter : 100, 500 puis 1000 utilisateurs (PARTIE 18) - Windows
# Usage : .\jmeter\run_load_tests.ps1 [-JMeter "C:\outils\apache-jmeter-5.6.3\bin\jmeter.bat"] [-Port 8000] [-Label campagne]
# Résultats : jmeter\results\<Label>\<n>_users\ (results.jtl, report\index.html) + results\summary.md
param(
    [string]$JMeter = "jmeter.bat",
    [string]$TargetHost = "localhost",
    [int]$Port = 8000,
    [int]$RampUp = 10,
    [int]$Loops = 10,
    [int[]]$Users = @(100, 500, 1000),
    [string]$Label = "campagne"
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$plan = Join-Path $PSScriptRoot "churn_test_plan.jmx"

Invoke-RestMethod "http://${TargetHost}:${Port}/health" | Out-Null  # l'API doit répondre

foreach ($n in $Users) {
    $out = Join-Path $PSScriptRoot (Join-Path "results" (Join-Path $Label "${n}_users"))
    if (Test-Path $out) { Remove-Item -Recurse -Force $out }
    New-Item -ItemType Directory -Force $out | Out-Null
    Write-Host "=== $n utilisateurs (ramp-up $RampUp s, $Loops boucles) ==="
    & $JMeter -n -t $plan "-Jthreads=$n" "-Jrampup=$RampUp" "-Jloops=$Loops" "-Jhost=$TargetHost" "-Jport=$Port" `
        -l (Join-Path $out "results.jtl") -e -o (Join-Path $out "report") -j (Join-Path $out "jmeter.log")
    # statistics.json (versionné) ; le rapport HTML et le .jtl restent en local
    Copy-Item (Join-Path $out "report\statistics.json") (Join-Path $out "statistics.json")
    Start-Sleep -Seconds 15  # laisser l'API revenir au repos entre deux campagnes
}

python (Join-Path $PSScriptRoot "summarize_results.py")
