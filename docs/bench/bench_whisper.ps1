param([string]$Wav, [int]$Threads = 4, [string]$Model = "$env:USERPROFILE\Documents\New folder\AI-App\addon\ggml-base.en.bin", [string]$Lang = 'en')
# Runs AI-App's whisper.cpp CLI (v1.9.2 BLAS build) on the WAV with a ggml model (default base.en), polling peak working set.
$rel = "$env:USERPROFILE\Documents\New folder\AI-App\addon\whisper-blas-bin-x64\Release"
$exe = Join-Path $rel 'whisper-cli.exe'
$dir = Split-Path -LiteralPath $Wav
$so = Join-Path $dir "wcli_out_$([IO.Path]::GetFileNameWithoutExtension($Model))_t$Threads.txt"
$se = Join-Path $dir "wcli_err_$([IO.Path]::GetFileNameWithoutExtension($Model))_t$Threads.txt"
$argList = @('-m', "`"$model`"", '-f', "`"$Wav`"", '-t', "$Threads", '-nfa', '-nt', '-l', $Lang)
$sw = [Diagnostics.Stopwatch]::StartNew()
$p = Start-Process -FilePath $exe -WorkingDirectory $rel -ArgumentList $argList -PassThru -NoNewWindow -RedirectStandardOutput $so -RedirectStandardError $se
$peak = 0
while (-not $p.HasExited) {
  try { $p.Refresh(); if ($p.PeakWorkingSet64 -gt $peak) { $peak = $p.PeakWorkingSet64 } } catch {}
  Start-Sleep -Milliseconds 40
}
$sw.Stop()
"threads=$Threads wall_s=$([math]::Round($sw.Elapsed.TotalSeconds, 2)) peak_ws_mb=$([math]::Round($peak / 1MB))"
Get-Content -LiteralPath $se | Select-String -Pattern 'total time|encode time|decode time|load time|model size|system_info' | ForEach-Object { $_.Line.Trim() }
"--- transcript ---"
Get-Content -LiteralPath $so -Raw
