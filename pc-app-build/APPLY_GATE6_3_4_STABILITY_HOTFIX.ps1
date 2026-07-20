$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = $PSScriptRoot
$Pattern = "Users*AppDataLocalTempnote-assistant-*-pytest-*"

Write-Host "==> Remove accidentally committed pytest temporary trees"
$TemporaryTrees = @(
    Get-ChildItem -LiteralPath $RepoRoot -Directory -Filter $Pattern -ErrorAction SilentlyContinue
)
foreach ($Tree in $TemporaryTrees) {
    $ResolvedRoot = [System.IO.Path]::GetFullPath($RepoRoot)
    $ResolvedTree = [System.IO.Path]::GetFullPath($Tree.FullName)
    if (-not $ResolvedTree.StartsWith($ResolvedRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove a path outside the repository root: $ResolvedTree"
    }
    Write-Host "    removing: $($Tree.Name)"
    Remove-Item -LiteralPath $ResolvedTree -Recurse -Force
}

if ($TemporaryTrees.Count -eq 0) {
    Write-Host "    no matching temporary tree found"
}

Write-Host "==> Gate 6.3/6.4 stability hotfix is ready"
Write-Host "Native acoustic barge-in is fail-closed; offline KWS remains available."
Write-Host "Run .\VERIFY_GATE6_3_4_STABILITY_HOTFIX.ps1 next."
