param([string]$Out, [string]$TextFile)
# Synthesizes the reference standup text to a 16 kHz mono 16-bit WAV (the format MWA/Parakeet consume).
Add-Type -AssemblyName System.Speech
$text = Get-Content -Raw -LiteralPath $TextFile
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
"Voices: $(($s.GetInstalledVoices() | ForEach-Object { $_.VoiceInfo.Name }) -join ', ')"
$fmt = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(16000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
$s.SetOutputToWaveFile($Out, $fmt)
$s.Rate = 0
$s.Speak($text)
$s.SetOutputToNull()
$s.Dispose()
$len = (Get-Item -LiteralPath $Out).Length
"Wrote $Out : $len bytes = $([math]::Round(($len - 44) / 32000, 1)) s"
