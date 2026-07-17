param(
    [string]$StreamDelayMs = "auto",
    [ValidateSet("aec_only", "aec_ns", "ns_only")]
    [string]$ProcessingMode = "aec_only",
    [double]$SpeechStartDelay = 1.5
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

if ($StreamDelayMs -ne "auto") {
    $ParsedDelay = 0
    if (-not [int]::TryParse($StreamDelayMs, [ref]$ParsedDelay) -or $ParsedDelay -lt 0 -or $ParsedDelay -gt 500) {
        throw "StreamDelayMs must be 'auto' or an integer from 0 to 500."
    }
}

function Invoke-Gate60RealCheck {
    param([string]$Name, [string[]]$Arguments)
    Write-Host "[Gate 6.0 corrected] $Name"
    & python @Arguments
    if ($LASTEXITCODE -ne 0) {
        Write-Error "$Name failed or was inconclusive with exit code $LASTEXITCODE."
        exit $LASTEXITCODE
    }
}

Invoke-Gate60RealCheck "device inventory" @("tools/probe_gate6_audio_devices.py")
Invoke-Gate60RealCheck "real duplex" @("tools/probe_gate6_duplex.py", "--duration", "3")
Invoke-Gate60RealCheck "AEC capability" @("tools/probe_gate6_aec.py", "--scenario", "capability")
Invoke-Gate60RealCheck "AEC far-end-only semantic acceptance" @(
    "tools/probe_gate6_aec.py",
    "--scenario", "far_end_only",
    "--duration", "5",
    "--stream-delay-ms", $StreamDelayMs,
    "--processing-mode", $ProcessingMode
)
Invoke-Gate60RealCheck "AEC double-talk near-end preservation" @(
    "tools/probe_gate6_aec.py",
    "--scenario", "double_talk",
    "--duration", "6",
    "--stream-delay-ms", $StreamDelayMs,
    "--processing-mode", $ProcessingMode,
    "--speech-start-delay", "$SpeechStartDelay"
)

Write-Host "Gate 6.0 corrected Windows AEC evidence passed. KWS live and macOS remain separate evidence."
exit 0
