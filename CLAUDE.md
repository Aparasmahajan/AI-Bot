# Working on MWB (AI-Bot): notes for Claude

Read `README.md` and `TODO.md` first. The design document, `docs/MWB-POC-Design.html` (built from `docs/src`), is the specification; `TODO.md` is the live status.

## The user

- New to AI. Explain in plain language, give the reasoning, and keep answers organised.
- Works on a managed company laptop: HP EliteBook 840 G8, 16 GB in one stick, often only 0.5–3 GB free.

## Rules for this project

- **Q&A log.** Record every question the user asks about MWB in `docs/MWB-QA.md`:
  - Add it as a new numbered section before the glossary, with the question quoted exactly and your answer below it.
  - Renumber the glossary and update the contents list.
  - Don't rewrite earlier answers; add an *Update:* note instead.
- **Downloads.** Before downloading anything, search the laptop for an existing copy and check its SHA-256. Ask before any real download. Python libraries go only into `MWB\.venv`, at pinned versions.
- **Deleting files.** Don't delete the user's files outright: use the Recycle Bin unless the user asks for permanent deletion.
- **Launchers.** When models change, keep the launchers in `%USERPROFILE%\Tools\llamacpp` working, and back them up first.
- **Git.** Don't commit or push unless the user asks. The GitHub repository is public: keep API keys, recordings and new personal details out of it, and write `%USERPROFILE%` rather than the user name in paths.
- **Numbers.** The design document labels measured numbers and estimates differently; keep it that way.

## App code and its environment

- **Python environment.** `MWB\.venv` runs Python 3.14.7 and holds only approved libraries.
  - `requirements.txt` pins each library's version and PyPI's SHA-256.
  - Install with `.venv\Scripts\python.exe -m pip install --require-hashes --only-binary :all: -r requirements.txt`.
  - Add a new library there, with its hash, only after the user approves it.
- **`mwb/`** is the app, laid out as in design §16.2. So far it has:
  - `app.py`: the core (`python -m mwb`, or `Start MWB.cmd`): one instance, one message loop with a 15 ms tick, the hotkeys, the tray and the indicator. `MWB_TEST_AUDIO=<wav>` plays a file in place of the mic, for tests only;
  - `winapi.py`, `hotkeys.py`: Win32 through ctypes, with no keyboard hook. Double taps follow P0-2, and paste waits until Ctrl, Alt, Shift, Win, Caps Lock and Space are up;
  - `audio/capture.py`, `audio/vad.py`: the mic, open only while dictating; and AI-App's adaptive VAD in pure Python (`math.sumprod`), which cuts pieces at 500 ms pauses, 10 s at most;
  - `supervisor.py`, `memory_guard.py`, `workers/asr/server.py`: the speech worker in AI-App's Parakeet venv, with a token in `MWB_TOKEN`, a random port and an idle exit. The guard refuses to load below 1.0 GB free;
  - `skills/dictate.py`, `skills/cleanup.py`, `insert.py`: dictation, the clean-up rules and the paste;
  - `store/`: SQLite in `%LOCALAPPDATA%\MWB\mwb.db` (dictation history, FTS5);
  - `config/`: `default.toml`, overridden by `%APPDATA%\MWB\config.toml`, and `dictionary.txt`;
  - `credentials.py`: Credential Manager through ctypes;
  - `llm/providers.py` and `llm/client.py`:
    - the Groq entry and the key check;
    - `Connection.chat()`, a kept-alive streaming client that times the first word and never raises on API errors;
  - `ui/api_key.py`, `ui/tray.py`, `ui/indicator.py`, `ui/art.py`: the key window (opened by `Set API key.cmd` or the tray), the tray, and the Capsule indicator;
  - Phase 2, meetings:
    - `sensors/meeting_detector.py` reads which apps hold the mic from the registry every 5 s; the rules are in `config/vc_apps.toml`;
    - `sensors/system.py`: the power and CPU state;
    - `audio/recorder.py`: two lanes, mic and loopback, with loopback gaps filled with silence by the clock;
    - `skills/meeting.py`: ask, record, transcribe, finish;
    - `skills/transcripts.py`: merge the lanes, remove echo, import .vtt, .docx and .txt;
    - `collectors/outlook.py`: the meeting's subject from the calendar;
    - `ui/cards.py`: the "Record this call?" card (Tk on its own thread, never takes focus);
    - `ui/today.py`: the Today page on 127.0.0.1 with a token;
    - `MWB_TEST_MEETING="me.wav;them.wav"` replaces both devices, for tests only.
  - Phase 3, understanding:
    - `llm/router.py` sends to the API first and falls back to the local model; `allow_local=False` makes batch jobs wait;
    - `llm/local.py` runs llama-server from `Tools\llamacpp` with its own `--api-key`, and exits after 5 idle minutes;
    - `llm/prompts.py`: one prompt per skill;
    - `skills/notes.py`: notes, action items and labels (stages A to C);
    - `skills/dates.py`: dates by code;
    - `skills/assist.py`: email, code, rewrite, answer, and `decide()`, which picks write or answer;
    - `skills/answer.py`: facts with tags, and citation checking;
    - `sensors/focus.py`: is the cursor in a text box (UI Automation);
    - `collectors/selection.py`: copy the selection, restoring the clipboard;
    - results (answers, drafts, rewrites) open in the indicator's place: `ui/indicator.py` `ResultPanel`, drawn by `art.panel()`. The window takes clicks only while a panel is open and never takes the focus (`WM_MOUSEACTIVATE` → `MA_NOACTIVATE`). `Cards.result()` hands over to it.
    - Tk cards (`ui/cards.py`, "Record this call?"): never call `deiconify()`: Tk would take the focus. Show them with `ShowWindow(SW_SHOWNOACTIVATE)`.
  - `tests/e2e_answers.py` asks the 10 day questions through Groq on a scratch database.
  - Phase 4, the journal:
    - `sensors/activity.py`: the app in front every 10 s and its project, from the window title, which is never stored; away after 5 idle minutes; denylist → "Private";
    - `collectors/git.py`: commits by your git email under `repo_roots`, four repositories at a time;
    - `collectors/outlook.py` `mail_day()`, `calendar_between()`, `journal_draft()` (displayed, never sent);
    - `skills/journal.py`: the 06:00-to-06:00 day, facts rendered by code, prose from the model, `check_sentence()` (valid tag whose fact shares a word or number, known SHAs, numbers from the facts), Markdown in `Documents\MWB\journal`; your edited file is never overwritten;
    - Ctrl+Alt+N voice note, Ctrl+Alt+Shift+J writes now, 18:30 by itself; the Today page has `/journal/<day>`.
  - Phase 5:
    - `watchdog.py`: `Start MWB.cmd` runs it; exit 0 = you quit, 3 = restart now (settings saved), anything else = crash (3 restarts in 10 minutes, then it stops). `recovery.py`: `run.json` marks a run; one left over means a crash;
    - `app.py` restarts itself when `config.toml` changes and nothing is in progress (`idle()`), and guards `tick()`;
    - `config.save_user()` changes only the given keys and keeps comments; `cfg['_user']` lists the keys you set, which the governor never overrides;
    - `machine.py` (P0-6 probe and fingerprint, `%LOCALAPPDATA%\MWB\machine\<fp>.toml`), `effort.py` (governor, E1–E4 per feature, every 30 s), `ui/setup.py` (setup screen, opens when `[effort] chosen` is false), `ui/settings.py` (Settings window), `ui/style.py`;
    - `art.SKINS`: capsule, dot, bars, ring, wave, orb, mic, pixel (`[indicator] skin`);
    - `skills/forget.py`: forget a meeting or a day; the journal file goes to the Recycle Bin;
    - `tools/build_portable.py` writes `dist\MWB-portable` (gitignored), copying Python from `.venv`'s base; it downloads nothing.
    - Windows that take the focus (setup, settings) must not be opened in tests while the user is typing.
- **Meeting speech** uses whisper-cli (AI-App's build), started once per 22–28 s piece, at below-normal priority.
  - Not whisper-server, which held 2.2 GB. whisper-cli peaks at 0.79 GB and returns it when it exits.
  - Pieces are WAV files in `%LOCALAPPDATA%\MWB\audio\m<id>`, deleted once transcribed.
  - Live transcription runs only on mains power with a calm CPU; otherwise it runs after the call.
  - Every child process is placed in a Windows job (`winapi.end_with_me`), so it ends when the core ends.
- **Tests.** `.venv\Scripts\python.exe -m unittest discover -s tests -t .` runs them.
  - `tests/test_paste.py` opens a small window of its own and skips itself when it can't come to the front. Don't run it, or `tests/e2e_core.py`, while the user is typing: their keys go into the test window.
  - `tests/bench_dictation.py <folder>` (add `--joined` for about 10 s of speech) needs the clips from `tests/make_phrases.ps1` and about 1 GB free.
  - `tests/e2e_meeting.py <folder>` plays a 12-turn conversation through the meetings skill into a scratch database. It needs about 1 GB free and takes several minutes.
- **Dictated text** lives only in `mwb.db`. Logs record lengths and timings, never the words, and never window titles.
- **Window style.** Windows use Tkinter with the clam theme and the demo's light colours. Set DPI awareness before Tk starts.
- **The Groq key** is in Credential Manager as `MWB/api-key/groq`.
  - Read it only in code that sends it to Groq.
  - Never print it, log it, or put it in the chat or in a file.
  - Test with a throwaway target such as `MWB/selftest/...`, or with a deliberately fake key.
- **The sync check** is `docs/bench/p0_4_sync_check.py`: ten saved MWB prompts with automatic checks, and a blind review page.
  - It runs with `--routes groq`, `local` or `all`; `--rescore` re-runs the checks without calling any model.
  - Local routes refuse to start without enough free memory.
  - Results go to `docs/bench/p0_4/`.
  - Model text is cleaned up before use: U+2011 hyphens become `-`.
  - Dates are worked out in code, never by the model.
- **Tests that open the mic or start Outlook** (P0-1, P0-3, P0-7) don't run during a call. A call is on when the Teams key under `HKCU\...\ConsentStore\microphone` has `LastUsedTimeStop = 0`.

## Design decisions to respect

- Speech always runs on the laptop; audio is never sent anywhere.
- **Language work is API first:** Groq, `openai/gpt-oss-120b`, with the key in Windows Credential Manager.
  - The local fallback is kept in sync: Qwen3.5 2B every day, Qwen3.5 4B for code and the journal, with thinking off.
  - Learning the user's email style is local-only.
- Facts (commit IDs, times, counts) come from code. The model writes only the prose, and every sentence must cite its events. MWB never sends email.
- The core never imports numpy or onnxruntime. Heavy work runs in worker processes that exit when idle.

## Updating the design document

1. Edit `docs/src/parts/*.html`, or `docs/src/figs.mjs` for figures.
2. Run `node docs/src/build.mjs`. It writes `docs/src/out/MWB-POC.html` and prints the figure count and the modelled-day memory.
3. Copy `docs/src/out/MWB-POC.html` over `docs/MWB-POC-Design.html`, then delete `docs/src/out`.
4. Republish to the same artifact, https://claude.ai/artifact/DmETZMSZBmr5J6gME4uvTL. From a new conversation, pass it as `url`.

## Updating the demo

- The source is `docs/src/demo/MWB-Demo.html`: page content only, exactly as published. Publish it to https://claude.ai/artifact/JkKapQwt42FiU1TMUcjFCZ.
- The offline copy, `docs/MWB-Demo.html`, is the same content wrapped in `<!doctype html>`, a `<head>` with the charset and viewport tags, and `<body>`.
