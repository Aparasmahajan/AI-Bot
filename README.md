# AI-Bot (MWB)

MWB is the working name of a Wispr-Flow-like work assistant for Windows. It is being built as a proof of concept on an HP EliteBook 840 G8 with 16 GB in one memory stick. You double-tap Caps Lock and talk, and it:

- types what you say, or answers your questions;
- helps with email and code;
- records and labels meetings in any call app;
- writes your end-of-day journal with real commit IDs.

**Status, 13 October 2026:**
- The design is complete (Rev F) and an interactive demo exists.
- The first app code is in: the API key window.
- Phase 0, about three days of tests on the laptop, started on 12 October:
  - the laptop's fingerprint is recorded;
  - reading Outlook passed;
  - whisper small keeps up with calls when the laptop is plugged in;
  - the two Python libraries are installed;
  - recording both sides of a call and reading Outlook through comtypes passed their technical checks;
  - Groq passed all 42 checks on MWB's ten saved tasks, with first words after 0.6 s;
  - the comparison with the local models waits for free memory, and the key and call tests wait for real use.

See [TODO.md](TODO.md).

## Start here

| File | What it is |
|---|---|
| [TODO.md](TODO.md) | What to do next, the open decisions, and what's done |
| `Set API key.cmd` | Double-click to add your Groq key. It is checked with Groq, then kept in Windows Credential Manager, never in a file |
| [mwb/](mwb/) | The app's code. So far: the API key window, Credential Manager storage and the Groq key check |
| [requirements.txt](requirements.txt) | The Python libraries MWB uses, with exact versions and checksums; installed only into `.venv` |
| [docs/MWB-POC-Design.html](docs/MWB-POC-Design.html) | The full design specification; open it in a browser |
| [docs/MWB-Demo.html](docs/MWB-Demo.html) | Interactive demo of the UI and the main flows |
| [docs/MWB-QA.md](docs/MWB-QA.md) | Every question asked so far, with the answers, in plain language |
| [docs/bench/](docs/bench/) | Benchmark scripts and measured results |
| [docs/src/](docs/src/) | Sources of the design document and the demo |
| [CLAUDE.md](CLAUDE.md) | Context and working rules for AI assistants on this project |

## How it works, in short

- **A small core** of about 40 MB runs in the tray and loads no AI model. Models run in separate worker processes that start when needed and exit when idle.
- **Speech to text runs on the laptop:** NVIDIA Parakeet TDT 0.6B v2 (int8) for English, and whisper.cpp for Hindi and Hinglish. Audio never leaves the laptop.
- **Writing and answers go to an API first:** Groq, `openai/gpt-oss-120b`. When the API can't be reached, a local model kept in sync takes over: Qwen3.5 2B every day, and Qwen3.5 4B for code and the journal.
- **Facts come from code.** Commit IDs, times and counts come from code, and the language model only writes the words around them. MWB never sends email.
- **Meetings are found in any call app** by watching which app is using the microphone. Each one gets a Work or Timepass label with its reasons.
- **Each laptop gets its own effort level,** E1 to E4, chosen on a setup screen.

## Measured on this laptop (11–12 October 2026)

| What | Result |
|---|---|
| Parakeet, a 5-second phrase, 4 threads | 0.91 s |
| Parakeet memory while warm | 0.99 GB |
| whisper small (multilingual), 62-second clip | 23.9 s, 4.2 % word errors, 1.06 GB |
| whisper large-v3-turbo q5_0, same clip | 137 s, slower than real time; 7.8 %; 1.27 GB |
| Qwen3.5 2B on the CPU | reads 42 tokens/s, writes 10.3 tokens/s, 1.25 GB |
| Qwen3.5 4B on the CPU | reads 13.4 tokens/s, writes 3.6 tokens/s, 2.42 GB |
| Qwen3.5 on the Iris Xe GPU (Vulkan) | reads prompts 5–7× faster; writes at about the same speed or slower |
| Coding check, 5 small Python tasks | Qwen2.5-Coder 3B 2/5, Qwen3.5 2B 3/5, Qwen3.5 4B 4/5 |

## Where things are on this laptop

| Item | Location |
|---|---|
| AI-App, whose speech engine MWB reuses | `%USERPROFILE%\Documents\New folder\AI-App` |
| llama.cpp build 11015 (CPU and Vulkan) and your launchers | `%USERPROFILE%\Tools\llamacpp` |
| Qwen3.5 2B, 4B and the 4B's vision file | `%USERPROFILE%\Tools\llamacpp\models`, also listed in LM Studio |
| whisper small and large-v3-turbo | `%LOCALAPPDATA%\MWB\models` |
| Parakeet | the Hugging Face cache, `%USERPROFILE%\.cache\huggingface\hub` |

## Published pages (private until shared)

- Design document: https://claude.ai/artifact/DmETZMSZBmr5J6gME4uvTL
- Demo: https://claude.ai/artifact/JkKapQwt42FiU1TMUcjFCZ
