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
  - `credentials.py`: Credential Manager through ctypes;
  - `llm/providers.py` and `llm/client.py`:
    - the Groq entry and the key check;
    - `Connection.chat()`, a kept-alive streaming client that times the first word and never raises on API errors;
  - `ui/api_key.py`: the key window, opened by `Set API key.cmd`.
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
