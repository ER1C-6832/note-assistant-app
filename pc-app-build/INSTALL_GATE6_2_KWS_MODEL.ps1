param(
    [string]$AndroidModelDir = "C:\yuyinzhushou\note-assistant-android\assistant-wakeword\src\main\assets\sherpa-onnx-kws-zipformer-zh-en-3M-2025-12-20"
)

$ErrorActionPreference = "Stop"
$Destination = Join-Path $env:LOCALAPPDATA "NoteAssistant\models\kws\sherpa-onnx-kws-zipformer-zh-en-3M-2025-12-20"
$Required = @(
    "tokens.txt",
    "encoder-epoch-13-avg-2-chunk-16-left-64.onnx",
    "decoder-epoch-13-avg-2-chunk-16-left-64.onnx",
    "joiner-epoch-13-avg-2-chunk-16-left-64.onnx",
    "keywords_xiaozhi.txt"
)

if (-not (Test-Path -LiteralPath $AndroidModelDir -PathType Container)) {
    throw "Android KWS model directory was not found: $AndroidModelDir"
}
New-Item -ItemType Directory -Force -Path $Destination | Out-Null
foreach ($Name in $Required) {
    $Source = Join-Path $AndroidModelDir $Name
    if (-not (Test-Path -LiteralPath $Source -PathType Leaf)) {
        throw "Required KWS model file was not found: $Name"
    }
    Copy-Item -LiteralPath $Source -Destination (Join-Path $Destination $Name) -Force
    Write-Host "installed: $Name"
}
Write-Host "Gate 6.2 KWS model installed at: $Destination"
