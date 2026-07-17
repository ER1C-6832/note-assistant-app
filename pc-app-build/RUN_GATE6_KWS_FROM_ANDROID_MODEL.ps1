[CmdletBinding()]
param(
    [string]$AndroidModelDir = "C:\yuyinzhushou\note-assistant-android\assistant-wakeword\src\main\assets\sherpa-onnx-kws-zipformer-zh-en-3M-2025-12-20",
    [string]$ModelDir = (Join-Path $env:LOCALAPPDATA "NoteAssistant\models\kws\sherpa-onnx-kws-zipformer-zh-en-3M-2025-12-20"),
    [ValidateRange(5, 120)]
    [int]$Duration = 15,
    [switch]$SkipCopy
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
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
    throw "找不到 $ProbePath。请把本脚本放在 pc-app-build 根目录后再运行。"
}

if (-not $SkipCopy) {
    if (-not (Test-Path -LiteralPath $AndroidModelDir -PathType Container)) {
        throw "找不到 Android 模型目录：$AndroidModelDir"
    }

    $MissingSourceFiles = @(
        foreach ($Name in $Files) {
            $Path = Join-Path $AndroidModelDir $Name
            if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
                $Path
            }
        }
    )
    if ($MissingSourceFiles.Count -gt 0) {
        throw "Android 模型目录缺少文件：`n$($MissingSourceFiles -join "`n")"
    }

    New-Item -ItemType Directory -Path $ModelDir -Force | Out-Null
    Write-Host "==> Copy KWS model assets"
    foreach ($Name in $Files) {
        Copy-Item -LiteralPath (Join-Path $AndroidModelDir $Name) -Destination (Join-Path $ModelDir $Name) -Force
    }

    Write-Host "==> Verify copied files with SHA-256"
    foreach ($Name in $Files) {
        $SourceHash = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $AndroidModelDir $Name)).Hash
        $TargetHash = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $ModelDir $Name)).Hash
        if ($SourceHash -ne $TargetHash) {
            throw "复制校验失败：$Name"
        }
        Write-Host "    verified: $Name"
    }
}

$MissingTargetFiles = @(
    foreach ($Name in $Files) {
        $Path = Join-Path $ModelDir $Name
        if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
            $Path
        }
    }
)
if ($MissingTargetFiles.Count -gt 0) {
    throw "KWS 模型目录缺少文件：`n$($MissingTargetFiles -join "`n")"
}

$VenvPython = Join-Path $ScriptRoot "venv\Scripts\python.exe"
if (Test-Path -LiteralPath $VenvPython -PathType Leaf) {
    $Python = $VenvPython
} else {
    $PythonCommand = Get-Command python -ErrorAction Stop
    $Python = $PythonCommand.Source
}

Write-Host "==> Gate 6 real KWS probe"
Write-Host "模型目录：$ModelDir"
Write-Host "出现提示后，请说两次唤醒词；建议说“小智小智”，两次间隔约 2 秒。"

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
