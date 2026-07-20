$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

Write-Host "==> Install the pinned Windows WebRTC APM adapter"
python -m pip install "aec-audio-processing==1.0.1"
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

python -c "from aec_audio_processing import AudioProcessor; print('aec-audio-processing import passed')"
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Write-Host "Gate 6.3+6.4 audio processing dependency is ready."
exit 0
