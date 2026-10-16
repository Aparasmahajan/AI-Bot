# AI-Bot (MWB)

MWB is the working name of a Wispr-Flow-like work assistant for Windows. It is being built as a proof of concept on an HP EliteBook 840 G8 with 16 GB in one memory stick. You double-tap Caps Lock and talk, and it:

- types what you say, or answers your questions;
- helps with email and code;
- records and labels meetings in any call app;
- writes your end-of-day journal with real commit IDs.

**Status, 16 October 2026:**
- The design document is at Rev G: it now describes MWB as built on 14 October, with Phase 0's measured numbers. The interactive demo was brought in line too.
- **Phase 3, understanding, is built**: meeting notes with action items, Work or Timepass labels, email, code, rewrite and answers, through Groq with the local model as a fallback.
- **Phase 2, meetings, is built too**: calls in any app are found, recorded with your permission and transcribed on this laptop; see TODO.md for what still needs real calls.
- **Phase 1, dictation, is built and ready for you to try:** double-click `Start MWB.cmd`. The checks that need your voice and your apps are still to do; see [TODO.md](TODO.md).
- Phase 0, the tests on this laptop, is nearly done:
  - the keys (P0-2) passed: 50 of 50 double taps for both Caps Lock and Alt;
  - reading Outlook passed;
  - whisper small keeps up with calls when the laptop is plugged in;
  - recording both sides of a call passed its technical check;
  - Groq passed all 42 checks on MWB's ten saved tasks, with first words after 0.6 s;
  - the comparison with the local models waits for free memory, and the voice and call tests wait for real use.

See [TODO.md](TODO.md).

## Start here

| File | What it is |
|---|---|
| [TODO.md](TODO.md) | What to do next, the open decisions, and what's done |
| `Start MWB.cmd` | Double-click to start MWB. It lives in the tray, next to the clock; starting it twice does nothing |
| `Set API key.cmd` | Double-click to add your Groq key. It is checked with Groq, then kept in Windows Credential Manager, never in a file. The tray menu opens the same window |
| [mwb/](mwb/) | The app's code: the core, dictation, the speech worker, the tray and the indicator, and the API key window |
| [tests/](tests/) | Automatic tests, the 20 dictation phrases and the Phase 1 benchmark |
| [requirements.txt](requirements.txt) | The Python libraries MWB uses, with exact versions and checksums; installed only into `.venv` |
| [docs/MWB-POC-Design.html](docs/MWB-POC-Design.html) | The full design specification; open it in a browser |
| [docs/MWB-Demo.html](docs/MWB-Demo.html) | Interactive demo of the UI and the main flows |
| [docs/MWB-QA.md](docs/MWB-QA.md) | Every question asked so far, with the answers, in plain language |
| [docs/bench/](docs/bench/) | Benchmark scripts and measured results |
| [docs/src/](docs/src/) | Sources of the design document and the demo |
| [CLAUDE.md](CLAUDE.md) | Context and working rules for AI assistants on this project |

## Using MWB (Phase 1: dictation)

| Do this | And MWB |
|---|---|
| Double-tap **Caps Lock**, talk, then pause for 2 s or double-tap again | Types what you said where your cursor is. Caps Lock stays as it was |
| Hold **Ctrl+Shift+Alt+Space**, talk, let go | The same, push-to-talk. (Ctrl+Alt+Space belongs to another app on this laptop) |
| Press **Esc** while it listens | Cancels; nothing is typed |
| Double-tap **Alt** | Shows or hides the small indicator above the taskbar |
| Double-tap **Caps Lock** and ask, with the cursor outside a text box, or start with "MWB, ..." | Answers in a small card. Questions about your day ("What are my open action items?") are answered from your own meetings, notes and calendar, with citations |
| Select an email, press **Ctrl+Alt+E** | Explains it: what they want, deadlines as real dates, reply ideas. Hold the keys and speak to draft a reply; MWB never sends it |
| Select code, press **Ctrl+Alt+K** | Explains it, lists problems and suggests a better version (Replace, or a VS Code diff). Hold the keys and describe code to have it written at the cursor |
| Select text, hold **Ctrl+Alt+R** and say "shorter" or "more formal" | Rewrites it; Replace puts it back |
| **Ctrl+Alt+M** | Starts or stops recording a call by hand. Calls in Teams, Zoom, Meet and others are found by themselves, and MWB asks before recording |
| **Ctrl+Alt+J** | Opens the Today page in your browser: meetings, transcripts and search |
| **Ctrl+Alt+P** | Pauses or resumes MWB |
| **Ctrl+Alt+Shift+W** | Quits MWB |

Say "new line", "new paragraph", "bullet point", "comma", "full stop" or "question mark" for layout. "Scratch that" replaces what you just said. Fillers like "um" and "uh" are dropped. Your own spellings go in `%APPDATA%\MWB\dictionary.txt`, one per line: `preya -> Priya`.

The first dictation after MWB starts, or after 15 minutes without one, waits while the speech engine loads. That takes 10–40 s when memory is tight. After that, text arrives about a second after you finish.

**Meetings (Phase 2).** When an app has used the mic for 20 s, MWB asks "Record this call?" in a small card at the bottom right. It always asks in its first week, and always for personal apps such as WhatsApp. While it records, the tray icon and the indicator get an orange ring. Your voice and the other side are transcribed on this laptop with whisper small, which handles Hindi and Hinglish. That happens during the call on mains power, or after it on battery, and no audio is kept. The tray can also import a transcript that Teams, Zoom or Webex made (.vtt, .docx or .txt).

Where it keeps things: settings in `%APPDATA%\MWB\config.toml` (tray menu, Settings file), your dictation history in `%LOCALAPPDATA%\MWB\mwb.db`, and logs in `%LOCALAPPDATA%\MWB\logs`. Logs never contain what you said.

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
