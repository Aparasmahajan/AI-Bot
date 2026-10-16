# TODO

This is the live status of the MWB proof of concept, last updated on 16 October 2026. The design document has the full detail: §17 is the plan and §19 the decisions.

## Now: things only you can do

- [ ] **Try MWB's dictation** (Phase 1): double-click `Start MWB.cmd`, click in any text box, double-tap Caps Lock and talk. README.md, "Using MWB", has all the keys.
  - [ ] Use it in five apps: Outlook, Teams, VS Code, Brave and one more. Tell Claude where it pasted wrongly or not at all.
  - [ ] Tell Claude about words it gets wrong; they go into `%APPDATA%\MWB\dictionary.txt`.
  - [ ] When you're happy with it, switch Wispr Flow off. That frees about 1.5 GB, which the speech engine needs.
- [ ] Answer the remaining questions:
  - [x] Call apps: Teams, and MWB must be ready for any call app (13 Oct).
  - [ ] Your work email (Microsoft 365) is only in Outlook on the web, so MWB can't read your sent mail for the journal yet. Choose one: add that account to classic Outlook, if both companies allow it; ask its admin to allow a Microsoft Graph sign-in; or leave email out of the journal.
  - [x] Hindi and Hinglish: yes, your meetings use both (13 Oct).
  - [x] Outlook: the classic app, which runs to show your meetings; MWB may start it (13 Oct).
  - [x] Work email: Outlook on the web in an Edge work profile (13 Oct).
- [ ] Run the two tests that need your hands. Paste these into PowerShell **in the MWB folder**; each prints its own steps:
  - [x] P0-2: done 14 Oct, go. Optional and passive: run `py -3.14 -I docs\bench\p0_2_keys.py` minimised through a normal working day, then press Ctrl+C and send the Results (the false-start check).
  - [ ] P0-5: `py -3.14 -I docs\bench\p0_5_mic_watch.py --watch`, left open during your next calls. Send the START and STOP lines.
  - [ ] P0-1: during a call, `.venv\Scripts\python.exe -I docs\bench\p0_1_two_lane.py`, about 10 minutes. It saves no audio, only counts it. Send the summary it prints.
  - [ ] Optional: change the Claude desktop app's quick-entry shortcut if you want Ctrl+Alt+Space for MWB; otherwise MWB uses Ctrl+Shift+Alt+Space
- [x] Approve PyAudioWPatch 0.2.12.9 and comtypes 1.4.17: installed into `MWB\.venv` on 13 Oct, pinned with PyPI's checksums in `requirements.txt`.
- [x] Groq API key saved with `Set API key.cmd` (13 Oct). To change it, open the same file again. Never paste the key into a chat or a file in this folder.
- [ ] Let the local half of P0-4 run: it needs about 3.5 GB free for about 15 minutes. You saw 0.6–2 GB free on 13 Oct.
  - Close windows you don't need, or wait until the end of your day, and tell Claude.
  - Or run it yourself: `.venv\Scripts\python.exe -I docs\bench\p0_4_sync_check.py --routes local`.
  - Then score the blind review: open `docs\bench\p0_4\review.html`, about 10 minutes, and paste the copied scores to Claude.
- [ ] Ask IT or your manager:
  - [ ] May MWB record calls with colleagues, and must they be told?
  - [x] May work text (emails, notes, code) go to Groq? You said yes: "it can go, no worries" (13 Oct).
- [ ] Optional: ask IT for a second 16 GB DDR4-3200 memory stick. Two sticks make the local models about twice as fast.
- [ ] Make the GitHub repository private, as you said you would on 13 Oct. Don't push the docs until then; see the note at the end.

## Phase 0: tests on this laptop, about 3 days (started 12 Oct)

Results so far: `docs/bench/P0-RESULTS-2026-10-12.md`.

| Test | What it checks | Status |
|---|---|---|
| P0-1 | Record both sides of a call (mic and speakers) for 10 minutes with no gaps, using PyAudioWPatch | **Technical go** (13 Oct, after your call). Mic and loopback ran together with no gaps or overflows: 60 s run, plus a 30 s self-test with an inaudible signal. The loopback sends nothing while nothing plays, so the recorder must fill silence from the clock. Still needed: the 10-minute pass test during a call (`p0_1_two_lane.py`, saves no audio) |
| P0-2 | Hold-to-talk and double taps of Caps Lock and Alt: at least 99 % caught, no false starts, and Caps Lock left unchanged. Paste into Outlook, Teams, VS Code and Brave | **Go** (14 Oct, run 3): Caps Lock 50 of 50 and Alt 50 of 50 (one possible too-slow pair, so at worst 50 of 51); Ctrl+Shift+Alt+Space held and pasted into VS Code; the paste now waits for Shift too. Passive leftovers: false starts during a normal day with the script minimised, and paste in Outlook, Teams and Brave, which Phase 1's 5-app test covers. Ctrl+Alt+Space is taken by another app, probably Claude's quick entry; the fallback Ctrl+Shift+Alt+Space works |
| P0-3 | Read today's calendar and sent-mail subjects from classic Outlook without a security pop-up | **Go** on 12 Oct (`p0_3_outlook.ps1`): no pop-up, even for meeting bodies. Dates in filters must use the Indian format. **comtypes: go** on 13 Oct (`p0_3_outlook_comtypes.py`). There was no pop-up while reading meeting bodies, sent-mail bodies and recipients. It adds about 8 MB to the core, and Outlook closes again afterwards |
| P0-4 | API speed and quality from your network, then the same tasks on Qwen3.5 2B and 4B: the first sync check | **API half: go** (13 Oct, `p0_4_sync_check.py`). gpt-oss-120b on low reasoning passed all 42 checks and 5/5 coding tasks: first word in 0.58 s, whole answer in 0.86 s (medians). Findings: dates must be worked out in code, hyphens need cleaning up, the journal prompt must be explicit. **Local half** (the sync check proper) waits for about 3.5 GB of free memory; then comes the blind review |
| P0-5 | Detect calls in every call app you use, from Windows' mic-usage list, and confirm the program names for `vc_apps.yaml` | Snapshot done (`p0_5_mic_watch.py`): Teams' name confirmed. On 13 Oct a real Teams call (10:30:46 to 10:47:01) was seen in the registry with exact start and end times. Still needs `--watch` during calls in a browser, if you ever use one |
| P0-6 | Hardware fingerprint and calibration, saved as the Lean baseline | **Done** (`p0_6_machine.py`, 12 Oct): fingerprint `530285546f`, Lean, saved in `%LOCALAPPDATA%\MWB\machine`. The API time, first words after 0.56 s, was added by P0-4 on 13 Oct |
| P0-7 | Your own voice: 20 work sentences read on your headset, with at most 10 % word errors, plus Hindi and Hinglish sentences for whisper small | To do. PyAudioWPatch is installed; this needs you to read the sentences |
| P0-8 | New on 13 Oct: can whisper small transcribe Hindi and Hinglish meetings fast enough? | **Go when plugged in** (13 Oct): 1.88× real time on 2 threads on mains power; 0.58–0.93× on battery. So: live on mains power, after the call on battery |

Phase 0 is finished when:
- the numbers are in `docs/bench/`;
- each test has a go or no-go;
- [x] the design document's estimates are replaced by measured values, in Rev G, together with the 13 Oct decisions: whisper small for meetings, live only on mains power, the API key window, any call app, gpt-oss-120b on low reasoning, dates worked out in code, and the hyphen clean-up. **Done 16 Oct** (new §6.5); the tests still waiting will add their numbers in a later revision.

## Phase 1: dictation (started 14 Oct)

Built on 14 Oct, following design §9.1, §13 and §16.2:
- **the core** (`mwb/app.py`): one instance, one Windows message loop, the hotkeys and double taps, the memory guard v0, and the SQLite history;
- **the speech worker** (`mwb/workers/asr/server.py`): AI-App's server, ported to run in AI-App's Parakeet environment, with a token, /health, /shutdown, an idle exit and better 48 kHz conversion;
- **dictation** (`mwb/skills/dictate.py`): pieces cut at 500 ms pauses and transcribed while you talk; the clean-up rules and dictionary (`cleanup.py`); paste with the clipboard put back, kept out of Win+V history, or typing when paste can't be used;
- **the tray** (pystray) and **the indicator**, Capsule skin (Pillow, layered window).

| Pass criterion (design P1) | Status, 14 Oct |
|---|---|
| Finish-to-text at most 1.0 s median, phrases up to 10 s | **976 ms median** over 20 synthetic phrases (`tests/bench_dictation.py`), on battery with the CPU busy; word errors 1.5 %. The 10 s joined-phrase run waits for free memory. Your own voice comes with P0-7 |
| Core at most 60 MB idle | **25 MB private, 43 MB working set** |
| Worker exits after 15 idle minutes | Built (the worker's own watchdog); it also exits if the core disappears. Not yet timed for the full 15 minutes |
| Works in five target apps | Paste into a test window passed; your five apps are for you to try |
| Caps Lock left unchanged after double taps | **Passed** in the end-to-end test through the real core |
| The indicator never takes focus | **Passed**: click-through, no-activate, topmost |
| Wispr Flow can be switched off | Your call, after trying it |

Found on the way:
- **Loading the speech engine takes 17–40 s when memory is tight.** It took 7.5 s on 11 Oct, with more free memory. MWB loads it at start only when 2 GB is free; otherwise the first dictation waits for it. Switching Wispr Flow off would help most.
- The memory guard refused to load at 0.3–0.97 GB free, as designed.
- In Rev G (16 Oct): Pillow and pystray are installed; push-to-talk is Ctrl+Shift+Alt+Space on this laptop; the clipboard is put back after 400 ms; the measured load times above.

## Phase 2: meetings (started 14 Oct)

Built on 14 Oct, following design §9.3:
- **the detector** (`mwb/sensors/meeting_detector.py`): which app holds the mic, read from the registry every 5 s; rules in `mwb/config/vc_apps.toml`, meeting tabs in browsers, the camera, and the subject from the Outlook calendar;
- **the "Record this call?" card**: Record, Not this one, or Never for this app. It asks every time in the first week, and always for personal apps;
- **the two-lane recorder** (`mwb/audio/recorder.py`) and **transcription with whisper small** (`mwb/skills/meeting.py`): live on mains power with a calm CPU, otherwise after the call; audio pieces are deleted once transcribed;
- **the Today page** (Ctrl+Alt+J), **transcript import** (.vtt, .docx, .txt) and **Ctrl+Alt+M** to record by hand.

Changed from the design, measured on 14 Oct:
- **whisper-cli once per piece, not whisper-server.** The server held 2.2 GB; whisper-cli peaks at 0.79 GB and gives it back after each piece. 28 s of speech took 19 s on 2 threads on battery.
- **Pieces of 22-28 s, not 10 s.** whisper always processes a 30 s window, so a 4 s piece costs as much as a 28 s one: 12 short pieces became 4.
- `vc_apps.toml`, not `.yaml` (no extra library); temporary WAV pieces, not Opus.

| Pass criterion (design P2) | Status, 14 Oct |
|---|---|
| At least 95 % of a week's calls detected | Built and unit-tested (Teams, Zoom, browser tabs, personal apps, unknown apps). Needs a week of your real calls |
| Personal apps always ask | **Passed** in the tests |
| Transcript within 2 minutes of the end | **Not yet: 355 s** in the end-to-end test (`tests/e2e_meeting.py`). Only 0.4-0.8 GB was free, so nothing could run during the call. With enough memory each 28 s piece took 28-29 s, so about a minute is expected (an estimate) |
| No audio kept unless asked | **Passed**: no files left |

Open points:
- **Memory is the limit.** whisper needs about 0.8 GB free. Switching Wispr Flow off (1.5 GB) is the biggest help; a second memory stick would be the real fix (decision 1).
- Browser meeting tabs are found from window titles, which show only the tab in front. Reading every tab through UI Automation is still to do.
- Until IT or your manager answers about recording colleagues, choose "Not this one" on work calls.

## Phase 3: understanding (started 14 Oct)

Built on 14 Oct, following design §9.2-§9.7, §10 and §12.7:
- **the router** (`mwb/llm/router.py`, `local.py`): Groq first, and Qwen3.5 on this laptop when the network, the key or Groq fails. The local model loads only if the memory guard allows it, uses its own key and port, and exits after 5 idle minutes. Batch work uses it only on mains power with a calm CPU; otherwise it waits;
- **meeting notes** in two passes (each 10 minutes, then combined), decisions, and **action items with owners**, whose dates are **worked out by code** (`skills/dates.py`);
- **Work or Timepass**: rules first (stage A), the transcript check when unsure (stage B), and your one-click correction on the Today page (stage C), which carries over to the meeting series and counts agreement;
- **Ctrl+Alt+E** explains the selected email (or the one open in classic Outlook); hold it and speak to draft a reply, which you can copy, insert, or open as an Outlook draft. **MWB never sends**;
- **Ctrl+Alt+K** explains the selected code, with Replace selection and a VS Code diff; hold it and describe code to have it written at the cursor;
- **Ctrl+Alt+R**: hold it and say how to change the selected text;
- **answer mode**: a double tap when the cursor isn't in a text box, or starting with "MWB, ...", asks instead of writing. Answers about your day come from your own data with citations; any citation that doesn't match a fact is removed;
- **the result card**: streaming text, Copy, Insert or Replace, and Esc to close. It never takes the focus;
- **the weekly sync check**, on mains power, re-runs P0-4's ten prompts through both routes.

| Pass criterion (design P3) | Status, 14 Oct |
|---|---|
| Notes within 10 minutes of a 60-minute call | Notes for a 15-minute test meeting took **3.0 s** through Groq. A 60-minute call is 6 parts plus a combining step, so well under a minute is expected (an estimate). The transcript is the slow part: see Phase 2 |
| 80 % label agreement on your first 20 meetings | Built, with the agreement count on the Today page. Needs your 20 meetings |
| 10 questions about your day answered with correct facts | **10 of 10** (`tests/e2e_answers.py`, made-up day, through Groq, 0.6-1.7 s each) |
| With the network off, every skill answers through the fallback | Built and unit-tested. **Not yet run for real**: the local model needs 1.25 GB free and only 0.2-0.8 GB was free |
| No code path that sends mail | **Passed**: a test scans every line of MWB's code |

Found on the way:
- Your terminal and VS Code don't report a "text box" to Windows, so a double tap there always writes (`always_write_in` in the settings).
- gpt-oss sometimes cites like 【M1】 or [ M1 ]; both are now read correctly.
- With only two lanes, MWB can't tell who on the other side is speaking, so their action items say "Them". Telling voices apart comes later in the design.
- The core idles at 59 MB working set (36 MB private) with the text-box check ready: just under the 60 MB target.

## After Phase 0

| Phase | What gets built | Days | Done when |
|---|---|---|---|
| 1 | Dictation: core, tray, hotkeys, double-tap Caps Lock, speech worker, clean-up, paste, indicator (Capsule skin). **Built 14 Oct; see above** | 3–11 | Text arrives within 1 s of finishing a phrase of up to 10 s; the core idles at 60 MB or less; it works in 5 apps; Wispr Flow can be switched off |
| 2 | Meetings in any call app: detector, two-lane recorder, background transcription, transcript import. **Built 14 Oct; see above** | 11–20 | At least 95 % of a week's calls are found; personal apps always ask; transcripts arrive within 2 minutes of the end |
| 3 | Understanding: API client and router with the local fallback, notes, Work or Timepass, email, code, answer mode. **Built 14 Oct; see above** | 20–30 | Notes arrive within 10 minutes of a 60-minute call; 80 % of labels match yours; everything works with the network off |
| 4 | Daily journal: collectors, facts by code, cited summary, Today page, 18:30 reminder | 30–37 | The journal is ready within 5 minutes; every commit ID is correct; every sentence cites its events |
| 5 | Profiles, effort levels and the setup screen, the other 7 indicator skins, settings, crash recovery, portable build | 37–48 | MWB runs as your daily tool for a full week |

## Decisions (design document §19)

| # | Decision | Status |
|---|---|---|
| 1 | Second memory stick | Open. Default: plan for 16 GB |
| 2 | Cloud language model | Decided: API first (Groq). Work text may go to Groq: your call, 13 Oct |
| 3 | What meeting capture records | Open. Default: both sides, asking first |
| 4 | Classic or new Outlook | Decided 13 Oct: classic Outlook, for the meeting calendar. MWB may start it when it isn't running. Work email is separate: Outlook on the web (see "Now") |
| 5 | Hindi and Hinglish | Decided 13 Oct: needed for meetings. Meetings go through whisper small, which handles Hindi and Hinglish; Parakeet stays for English dictation. P0-7 adds Hinglish sentences, and a new check, P0-8, tests whether whisper small keeps up during a call |
| 6 | Retire Wispr Flow after Phase 1 | Default: yes |
| 7 | Who gets the end-of-day report | Default: only you |
| 8 | Which call apps count as personal | Default: WhatsApp, Discord, Telegram and Phone Link always ask |
| 9 | Which features use the API | Decided: every language feature except learning your email style. From P0-4: gpt-oss-120b on low reasoning; gpt-oss-20b only for labels, clean-up and short answers |
| 10 | What a new laptop pre-selects | Default: its suggested effort level |

## Housekeeping (optional)

- [ ] Delete `%USERPROFILE%\Tools\llamacpp\backup-before-qwen3.5\`. It holds the old launchers, which point at the deleted Qwen2.5 files.
- [ ] Consider running `chat-7b.bat` with the Vulkan build: there, the 4B reads prompts about 7 times faster.
- [ ] Switch off Wispr Flow once Phase 1 passes; that frees about 1.5 GB.

## Done

- **11 Oct:**
  - laptop audit;
  - AI-App review;
  - speech benchmarks (`docs/bench`).
- **12 Oct:**
  - design document, revisions A to F (G followed on 16 Oct);
  - Q&A file;
  - interactive demo;
  - decided API first, with the local fallback kept in sync;
  - downloaded and verified Qwen3.5 2B, Qwen3.5 4B with its vision file, and whisper large-v3-turbo; reused whisper small from a verified copy already on the laptop; benchmarked them all;
  - deleted Qwen2.5;
  - moved the 5 llama.cpp launchers to Qwen3.5 and tested them;
  - added `README.md`, this file, `CLAUDE.md` and `.gitignore`;
  - Phase 0, nothing installed: P0-6 done, P0-3 go, P0-5 snapshot, P0-2 script and self-test (`docs/bench/P0-RESULTS-2026-10-12.md`).
- **13 Oct:**
  - decisions 4 and 5 settled by your answers;
  - found that your work email is only in Outlook on the web;
  - P0-8 whisper small speed measured on battery;
  - the P0-5 script now accepts `--watch:` and rejects unknown options;
  - P0-8 on mains power: go (1.88× real time on 2 threads);
  - your answers: Teams, but ready for any call app; work text may go to Groq; the repository will be made private;
  - installed PyAudioWPatch and comtypes into `.venv`, pinned with checksums in `requirements.txt`;
  - the first app code, `mwb/`: the API key window (`Set API key.cmd`), Credential Manager storage and the Groq key check, all tested;
  - wrote the P0-1 two-lane and comtypes P0-3 scripts, and ran both after your 10:30 call: P0-1 technical go, P0-3 comtypes go;
  - you saved the Groq key; P0-4 API half: go, with 45 requests and no rate limits; P0-6 completed with the API time;
  - MWB's chat client (`mwb/llm/client.py`, kept-alive streaming connection) and the ten saved sync-check prompts (`p0_4_sync_check.py`).
- **14 Oct:**
  - P0-2 keys: go (three runs, the last counted: 50 of 50 for both keys); the test now waits for Shift before pasting;
  - you approved Pillow 12.3.0, pystray 0.19.5 and six 1.17.0, installed into `.venv` and pinned with checksums;
  - Phase 1 built and tested: 22 unit tests, the paste test, the 20-phrase benchmark and an end-to-end run through the real core.
  - Phase 2 built and tested: 38 unit tests in all, and an end-to-end meeting run (correct transcript, no audio left, 355 s to ready when memory was short).
  - Phase 3 built and tested: 55 unit tests in all, notes through Groq in 3 s, and 10 of 10 day questions answered with correct facts.
- **16 Oct:**
  - design document Rev G: it now matches the code built for Phases 1 to 3 (checked against the code), with Phase 0's measured numbers in a new §6.5, the 13 Oct decisions, and six figures redrawn; republished to the same link;
  - the interactive demo brought in line: meetings through whisper-cli, the 400 ms clipboard, the 20 s API timeout, the "Record this call?" buttons and the push-to-talk fallback.

## Note on this repository

The GitHub repository `AI-Bot` is public; on 13 Oct you said you'll make it private. The documents in `docs/` mention:
- your Windows user name and Git identity;
- the laptop model;
- the company security tools on it.

Push them only after it's private (GitHub → Settings → Danger Zone → Change visibility). On 13 Oct you committed everything to the local `dev` branch; it hasn't been pushed, and `main` on GitHub still has only the first commit. The API key is never in this folder, so it can't be pushed by mistake.
