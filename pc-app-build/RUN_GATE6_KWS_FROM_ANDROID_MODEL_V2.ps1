[CmdletBinding()]
param(
    [string]$AndroidModelDir = "C:\yuyinzhushou\note-assistant-android\assistant-wakeword\src\main\assets\sherpa-onnx-kws-zipformer-zh-en-3M-2025-12-20",
    [string]$ModelDir = (Join-Path $env:LOCALAPPDATA "NoteAssistant\models\kws\sherpa-onnx-kws-zipformer-zh-en-3M-2025-12-20"),
    [ValidateRange(5, 120)]
    [int]$Duration = 15,
    [switch]$SkipCopy
)

$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProbePath = Join-Path $ScriptRoot "tools\probe_gate6_kws.py"
$Files = @(
    "tokens.txt",
    "encoder-epoch-13-avg-2-chunk-16-left-64.onnx",
    "decoder-epoch-13-avg-2-chunk-16-left-64.onnx",
    "joiner-epoch-13-avg-2-chunk-16-left-64.onnx",
    "keywords_xiaozhi.txt"
)

if (-not (Test-Path -LiteralPath $ProbePath -PathType Leaf)) {
    throw "Probe not found: $ProbePath. Place this script in the pc-app-build root directory."
}

if (-not $SkipCopy) {
    if (-not (Test-Path -LiteralPath $AndroidModelDir -PathType Container)) {
        throw "Android model directory not found: $AndroidModelDir"
    }

    foreach ($Name in $Files) {
        $SourcePath = Join-Path $AndroidModelDir $Name
        if (-not (Test-Path -LiteralPath $SourcePath -PathType Leaf)) {
            throw "Required source file not found: $SourcePath"
        }
    }

    New-Item -ItemType Directory -Path $ModelDir -Force | Out-Null
    Write-Host "==> Copy KWS model assets"
    foreach ($Name in $Files) {
        $SourcePath = Join-Path $AndroidModelDir $Name
        $TargetPath = Join-Path $ModelDir $Name
        Copy-Item -LiteralPath $SourcePath -Destination $TargetPath -Force

        $SourceHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $SourcePath).Hash
        $TargetHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $TargetPath).Hash
        if ($SourceHash -ne $TargetHash) {
            throw "SHA-256 copy verification failed: $Name"
        }
        Write-Host "    verified: $Name"
    }
}

foreach ($Name in $Files) {
    $TargetPath = Join-Path $ModelDir $Name
    if (-not (Test-Path -LiteralPath $TargetPath -PathType Leaf)) {
        throw "Required model file not found: $TargetPath"
    }
}

$VenvPython = Join-Path $ScriptRoot "venv\Scripts\python.exe"
if (Test-Path -LiteralPath $VenvPython -PathType Leaf) {
    $Python = $VenvPython
} else {
    $Python = (Get-Command python -ErrorAction Stop).Source
}

Write-Host "==> Gate 6 real KWS probe"
Write-Host "Model directory: $ModelDir"
Write-Host "After the microphone prompt, say the wake phrase twice, about 2 seconds apart."

& $Python $ProbePath `
    --tokens (Join-Path $ModelDir "tokens.txt") `
    --encoder (Join-Path $ModelDir "encoder-epoch-13-avg-2-chunk-16-left-64.onnx") `
    --decoder (Join-Path $ModelDir "decoder-epoch-13-avg-2-chunk-16-left-64.onnx") `
    --joiner (Join-Path $ModelDir "joiner-epoch-13-avg-2-chunk-16-left-64.onnx") `
    --keywords-file (Join-Path $ModelDir "keywords_xiaozhi.txt") `
    --duration $Duration

if ($LASTEXITCODE -ne 0) {
    throw "Gate 6 real KWS probe failed with exit code $LASTEXITCODE."
}

Write-Host "Gate 6 real KWS probe completed."
