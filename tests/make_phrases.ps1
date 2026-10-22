param([Parameter(Mandatory)][string]$OutDir, [int]$Rate = 48000)
# Speaks each line of tests\phrases.txt with Windows' built-in voice into OutDir\phrase-NN.wav, mono 16-bit at
# $Rate (48 kHz, like this laptop's mic). Test audio only: it is synthetic, and *.wav is kept out of Git.
Add-Type -AssemblyName System.Speech
New-Item -ItemType Directory -Force $OutDir | Out-Null
$lines = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'phrases.txt') | Where-Object { $_.Trim() }
$fmt = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo($Rate, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$i = 0
foreach ($line in $lines) {
  $i++
  $out = Join-Path $OutDir ('phrase-{0:D2}.wav' -f $i)
  $s.SetOutputToWaveFile($out, $fmt)
  $s.Speak($line)
  $s.SetOutputToNull()
}
$s.Dispose()
"Wrote $i phrases to $OutDir at $Rate Hz"
