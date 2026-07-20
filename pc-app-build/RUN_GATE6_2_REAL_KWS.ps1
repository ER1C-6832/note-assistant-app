param(
    [string]$ModelDir = "",
    [double]$Duration = 30.0,
    [int]$InputDeviceIndex = -1
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

if ([string]::IsNullOrWhiteSpace($ModelDir)) {
    $ModelDir = Join-Path $env:LOCALAPPDATA "NoteAssistant\models\kws\sherpa-onnx-kws-zipformer-zh-en-3M-2025-12-20"
}

$Tokens = Join-Path $ModelDir "tokens.txt"
$Encoder = Join-Path $ModelDir "encoder-epoch-13-avg-2-chunk-16-left-64.onnx"
$Decoder = Join-Path $ModelDir "decoder-epoch-13-avg-2-chunk-16-left-64.onnx"
$Joiner = Join-Path $ModelDir "joiner-epoch-13-avg-2-chunk-16-left-64.onnx"
$Keywords = Join-Path $ModelDir "keywords_xiaozhi.txt"

Write-Host "==> Gate 6.2 model package smoke"
python tools/verify_gate6_2_model_package.py --models-root (Split-Path -Parent $ModelDir)
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

$Arguments = @(
    "tools/probe_gate6_kws.py",
    "--tokens", $Tokens,
    "--encoder", $Encoder,
    "--decoder", $Decoder,
    "--joiner", $Joiner,
    "--keywords-file", $Keywords,
    "--duration", "$Duration",
    "--required-hits", "1"
)
if ($InputDeviceIndex -ge 0) {
    $Arguments += "--input-device-index"
    $Arguments += "$InputDeviceIndex"
}

Write-Host "==> Gate 6.2 real offline KWS acceptance (say the wake phrase once)"
python @Arguments
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Write-Host "Gate 6.2 real offline KWS acceptance passed."
exit 0
