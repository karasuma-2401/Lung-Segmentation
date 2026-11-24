param(
    [string]$Python = '.venv\Scripts\python.exe',
    [string]$EvidenceDirectory = 'docs/evidence'
)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $Python)) { throw "Python not found: $Python. Follow README setup." }
$evidenceDirectory = $EvidenceDirectory
New-Item -ItemType Directory -Path $evidenceDirectory -Force | Out-Null
$environmentOutput = Join-Path $evidenceDirectory 'environment.json'
$commands = @(
    @('-m', 'lungseg.cli', 'env-check', '--output', $environmentOutput),
    @('-m', 'lungseg.cli', 'smoke-test', '--config', 'configs/smoke.yaml'),
    @('-m', 'pytest', '-q'),
    @('-m', 'pip', 'check')
)
$results = @()
for ($i = 0; $i -lt $commands.Count; $i++) {
    $arguments = $commands[$i]
    $stamp = (Get-Date).ToUniversalTime().ToString('o')
    $logPath = Join-Path $evidenceDirectory "verify_$i.txt"
    $output = & $Python @arguments 2>&1
    $code = $LASTEXITCODE
    @("timestamp_utc: $stamp", "command: $Python $($arguments -join ' ')", "exit_code: $code", $output) |
        Set-Content -LiteralPath $logPath -Encoding utf8
    $output | Write-Output
    $results += [PSCustomObject]@{ command = "$Python $($arguments -join ' ')"; exit_code = $code; log = "verify_$i.txt"; timestamp_utc = $stamp }
    if ($code -ne 0) {
        $results | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $evidenceDirectory 'verification.json') -Encoding utf8
        throw "Verification failed with exit code $code. See $logPath"
    }
}
$results | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $evidenceDirectory 'verification.json') -Encoding utf8
