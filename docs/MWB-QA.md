# MWB · Questions and answers

Your questions from our conversation, quoted exactly as you wrote them, each followed by my answer. You asked: *"write my question along with your answer on a md file"*. This is that file.

Prepared 12 October 2026.

- **Design document (Rev F):** https://claude.ai/artifact/DmETZMSZBmr5J6gME4uvTL (private until you share it from the page's Share menu)
- **Offline copy of the design document:** `docs/MWB-POC-Design.html`
- **Interactive demo of the UI:** https://claude.ai/artifact/JkKapQwt42FiU1TMUcjFCZ, offline copy `docs/MWB-Demo.html`
- **Benchmark scripts and raw numbers:** `docs/bench/`
- **Source of the design document:** `docs/src/`. Rebuild it with `node docs\src\build.mjs`; the page is written to `docs/src/out/`.

## Contents

1. [The original request](#1-the-original-request)
2. [Effort when the configuration is better](#2-effort-when-the-configuration-is-better)
3. [Every video-call app, not only Teams](#3-every-video-call-app-not-only-teams)
4. [Using MWB on another laptop](#4-using-mwb-on-another-laptop)
5. [Did you download a model, or will we use API keys?](#5-did-you-download-a-model-or-will-we-use-api-keys)
6. [Choosing the effort when setting up a new device](#6-choosing-the-effort-when-setting-up-a-new-device)
7. [AI models, explained properly](#7-ai-models-explained-properly)
8. [The running loop, double Caps and the on-screen icon](#8-the-running-loop-double-caps-and-the-on-screen-icon)
9. [Is the document complete?](#9-is-the-document-complete)
10. [What happens in Phase 0](#10-what-happens-in-phase-0)
11. [Your Qwen models, API first, and whisper](#11-your-qwen-models-api-first-and-whisper)
12. [What will you download?](#12-what-will-you-download)
13. [Qwen3.5 instead of Qwen2.5, and whisper turbo](#13-qwen35-instead-of-qwen25-and-whisper-turbo)
14. [Remove Qwen2.5 completely](#14-remove-qwen25-completely)
15. [How MWB will work, and a demo of the UI](#15-how-mwb-will-work-and-a-demo-of-the-ui)
16. [What now?](#16-what-now)
17. [Is everything written down in this folder?](#17-is-everything-written-down-in-this-folder)
18. [Continuing Phase 0](#18-continuing-phase-0)
19. [Your answers: Hinglish, Outlook and work email](#19-your-answers-hinglish-outlook-and-work-email)
20. [Where are we?](#20-where-are-we)
21. [The libraries, a window for the Groq key, and your answers](#21-the-libraries-a-window-for-the-groq-key-and-your-answers)
22. [How to use Set API key.cmd](#22-how-to-use-set-api-keycmd)
23. [Groq tested: results, and what you do next](#23-groq-tested-results-and-what-you-do-next)
24. [Is Phase 1 complete?](#24-is-phase-1-complete)
25. [The key test: the shortcut opened Claude](#25-the-key-test-the-shortcut-opened-claude)
26. [Alt again? Where to work normally, and reading a hold line](#26-alt-again-where-to-work-normally-and-reading-a-hold-line)
27. [The key test passed: what now?](#27-the-key-test-passed-what-now)
28. [Phase 1: dictation is built](#28-phase-1-dictation-is-built)
29. [Phase 2: meetings are built](#29-phase-2-meetings-are-built)
30. [Phase 3: understanding is built](#30-phase-3-understanding-is-built)
31. [The code and flow changed: update the docs](#31-the-code-and-flow-changed-update-the-docs)
32. [Results in the indicator's place, like Wispr Flow](#32-results-in-the-indicators-place-like-wispr-flow)
33. [Glossary](#33-glossary)

---

## 1. The original request

**Your question**

> see and understand my current laptop configuration i want you to create an ai bot that takes summary of my day to day task helps me in email writting and understanding and transcribing my task uses least ram and memory
> has best transcribing model like i used in "C:\Users\parmahaj\Documents\New folder\AI-App" also helps me in writing and understanding optimised code
>
> see i am new to this ai stuff as of now i just want a poc having all the required data and ways to achieve a best bot like whisper flow see it must have understanding of my meeting tracks it
> separates timepass meating from work related ones
>
> at the end of the day even writes the summary of what i did even if i commit any code its commit id basicallically every damn thing
>
> also it can run and stop with simple shortcuts like i used for the AI app i created just read the code of ai app if required
>
> write all artchitecture and requirements and plan to proceed with this kind of app i asked write poc details in well organised manner not vibe coded or anything use cool graphics not like ai generated ones also make it scalable lets say in near future i have a good quality laptop i need to use its best configuration so keep in mind that too
>
> also write detailed doc

**My answer**

Before designing anything I did four things:

1. Read your laptop's configuration.
2. Read the AI-App code.
3. Benchmarked AI-App's speech engines on this laptop.
4. Checked the current (October 2026) state of speech and language models.

Then I wrote the design document, which now has 21 sections and 21 diagrams. The summary is below.

### What your laptop is

| Part | What you have | What it means |
|---|---|---|
| Laptop | HP EliteBook 840 G8, managed by company IT | Install in user mode, no admin rights |
| CPU | Intel Core i7-1185G7, 4 cores / 8 threads | Fast enough for speech models. Supports AVX-512 VNNI, which speeds up AI maths |
| Graphics | Intel Iris Xe, built into the CPU | No NVIDIA graphics card, so AI runs on the CPU |
| NPU ("AI chip") | None | Plan for the CPU |
| RAM | 16 GB, **one stick in one of two slots** | Memory runs at half speed (single channel) |
| Free RAM | 0.5 to 3 GB during the audit | MWB must be tiny when idle |
| Disk | 500 GB NVMe, 114 GB free | Plenty of room for models |
| Already running | Wispr Flow, using about 1.5 GB | MWB's dictation is designed to replace it |

**Cheapest upgrade:** a second matching 16 GB stick (Crucial CT16G4SFRA32A). You'd get 32 GB and double the memory speed, which roughly doubles how fast a local AI model writes. On a company laptop, ask IT first.

### What I reused from AI-App

- **The speech engine:** NVIDIA **Parakeet TDT 0.6B v2** (int8). **whisper.cpp** stays as the fallback for Hindi and Hinglish.
- **Two-lane listening:** your mic is one lane, and the other side of the call (system audio) is the other. That tells you who spoke without any extra model.
- **Tuned audio handling:** voice detection, volume levelling and echo removal.
- **The hotkey pattern:** global shortcuts, a fallback when a key is taken, and a pause-all key.

**Left out:**

- **The Electron shell.** It's heavy on RAM.
- **The screen-share-hiding overlay.** MWB is a visible assistant, and a meeting recorder should show that it's recording.

### What I measured on your laptop

| Engine | 5-second phrase | 62 seconds of speech | Misheard words (of 167) | RAM |
|---|---|---|---|---|
| Parakeet, 4 threads | **0.91 s** | 12.7 s | **0** | about 1.0 GB |
| Parakeet, 2 threads (AI-App's setting) | 1.98 s | 14.1 s | 0 | about 1.0 GB |
| whisper.cpp base.en | not measured | 21.8 s | 2 | about 0.5 GB |

Two findings shaped the design:

- **Cut audio into pieces.** Sending audio in 10-second pieces is faster than one long piece and uses about 530 MB less memory.
- **Load early.** Loading the model takes 7.5 to 12 seconds, so MWB starts loading the moment you press the dictation key. Most of that time hides behind your speech.

### What MWB is

- **The core:** a small always-on program (target about 40 MB) that owns hotkeys, the tray icon, meeting detection, data collection and the database.
- **Workers:** separate programs for the AI models, started only when needed and closed when idle. Closing a program is the only reliable way to give RAM back to Windows.

| You asked for | MWB feature |
|---|---|
| Summary of my day-to-day tasks | **End-of-day journal** at 18:30: commits with their IDs, meetings, emails, notes and time per project |
| Email writing and understanding | **Ctrl+Alt+E**: explain the selected email, or speak a reply and get a draft in your style. It never sends anything. |
| Transcribing | **Hold Ctrl+Alt+Space**, speak, release. Cleaned text appears where you're typing, like Wispr Flow. |
| Best transcribing model | Parakeet from AI-App (measured above) |
| Least RAM | Models load on demand and close when idle. In a modelled workday MWB averages **0.45 GB**, against Wispr Flow's constant 1.5 GB. |
| Writing and understanding optimised code | **Ctrl+Alt+K**: explain or optimise selected code in any app |
| Understand and track meetings, separate timepass from work | Automatic meeting capture, plus a **Work or Timepass** label with a reason and a time split. It learns from your corrections. |
| Commit IDs and "every damn thing" | Git collector across your 27 repos, plus meetings, email, dictation, voice notes and time per app |
| Run and stop with simple shortcuts | **Ctrl+Alt+W** starts MWB, **Ctrl+Alt+P** pauses everything, **Ctrl+Alt+Shift+W** quits |
| Scalable to a better laptop | Four hardware profiles, four effort levels, and automatic re-tuning on new hardware |
| Architecture, requirements, plan, graphics | The design document: requirements with a test for each, architecture, a 6-phase plan of 48 days, 21 diagrams |

Where to read more in the design document: §4 your laptop, §5 AI-App, §6 measurements, §7 requirements, §8 architecture, §9 pipelines, §17 plan.

---

## 2. Effort when the configuration is better

**Your question**

> keep in mind updating effort if configuration is more

**My answer**

MWB has **effort levels** from **E1 (low)** to **E4 (max)**. The stronger the machine, the higher the level it can run, and the more MWB does:

| What changes | E1 low | E2 normal | E3 high | E4 max |
|---|---|---|---|---|
| Threads for speech | 2 | 4 | 4–6 | all fast cores |
| Writing model size | smallest that fits | 2B–4B | 4B–9B | largest that fits |
| Extra checking passes | none | none | draft + self-check | draft, check, polish |
| Speaker separation | off | off | on | on, with names from the calendar |
| Models kept loaded | none | speech while you're active | speech + writing in work hours | all day |
| Live features | none | none | rolling meeting notes | live captions |
| Night re-processing (plugged in, idle) | off | off | re-write notes and journal | re-transcribe with a bigger model |

A part of the core called the **effort governor** can also adjust the level automatically, within limits you set (see question 6):

- **Down a level:** on battery, or when the laptop is busy or short of memory.
- **Back up:** when you're plugged in and idle.

I also re-estimated the plan for the extra work. Supporting every video-call app added 2 days, the effort system and re-tuning on new hardware added 2 days, and the setup screen added 1 day. The double-tap and indicator features from question 8 added 3 more. The plan is now **48 days** instead of 40.

Design document: §12.5 and Figure 12.2.

---

## 3. Every video-call app, not only Teams

**Your question**

> also dont keep just limited to team go for each and every vc app

**My answer**

Meeting detection no longer depends on any one vendor:

- **How it works:** every 5 seconds MWB asks Windows which apps are using the microphone right now. Windows keeps that record for every app, so any app that holds the mic for 20 seconds or more can be a meeting.
- **Desktop apps** (Teams, Zoom, Webex, Slack, WhatsApp, Discord and others) are recognised by their program name.
- **Browser meetings** (Google Meet, or Teams or Zoom in Brave or Edge) are recognised from the browser's tab titles and from the meeting link in your Outlook calendar.
- **A list you can extend:** `config/vc_apps.yaml` names the known apps. Adding a new one needs no code change.
- **A recording policy per app: record, ask or never.**
  - Personal apps (WhatsApp, Discord, Telegram, Phone Link) **always ask**.
  - An unknown app is asked about once, and your answer is remembered.
- **Works the same everywhere:** the other side of the call is recorded from system audio, which works for every app.
- **Import instead of recording:** if the meeting platform already made a transcript (Teams, Zoom, Google Meet, Webex), MWB can import it. Then nothing is recorded at all.

Design document: §9.3.

---

## 4. Using MWB on another laptop

**Your question**

> see if i load this app ino another laptop i want to use updated configuration and effort based on that laptop

**My answer**

Yes. Settings are split in two:

- **Yours (they travel with the app):** hotkeys, dictionary, recording policies, privacy choices, and your history if you copy it.
- **The machine's (never copied):** profile, effort level, thread counts, chosen models and speed-test results. MWB works these out on each machine.

MWB recognises a machine by a **hardware fingerprint** built from the CPU model, RAM size, number of memory sticks, GPU and its memory, and any NPU. It checks the fingerprint on every start. If it changed (a new laptop, or this laptop after a RAM upgrade), MWB:

1. tests the machine for about a minute,
2. suggests a profile and an effort level,
3. lets you choose on the setup screen (question 6),
4. lists the models your choice needs, with their sizes, and downloads them after you confirm. Models already on that machine are reused.

**To move MWB:** install it on the new laptop (or copy the portable folder), then copy `%APPDATA%\MWB` for your settings. If you want your history too, copy `%LOCALAPPDATA%\MWB\mwb.db` and `Documents\MWB\journal`.

Design document: §12.6 and Figure 12.4.

---

## 5. Did you download a model, or will we use API keys?

**Your question**

> also have you downloaded any ai model or will we use via api keys

**My answer**

- **I downloaded nothing and used no API key.**
  - My tests ran on two models that AI-App had already put on your laptop: Parakeet (631 MB, downloaded by AI-App on 1 October) and whisper base.en (148 MB).
  - My test script switched on "offline mode", so nothing could be downloaded by accident.
- **MWB is local-first.**
  - Speech-to-text always runs on your laptop; audio never leaves it.
  - The writing model (notes, email, code, journal) also runs locally by default. It isn't on your laptop yet; it's a 1–3 GB download in Phase 0, after you approve it.
- **API keys are optional, per feature.** If your company allows it, you can give MWB a key (Groq like AI-App, OpenAI, or a company endpoint) for faster and smarter answers on the features you choose. Then **text, never audio**, goes to that service.

Question 7 explains all of this properly.

*Update (Rev E, 12 Oct):* you chose the API route for language work for now, with a local model kept in sync as the fallback. Speech stays local. Still nothing was downloaded: llama.cpp and the Qwen2.5 models were already on your laptop, and whisper small was copied from a verified file that was already there. See question 11.

---

## 6. Choosing the effort when setting up a new device

**Your question**

> see as of effort i want user can make it configurable when setting up on new device

**My answer**

Done. The design is updated to Rev C. On the first start on any new device, MWB opens a **setup screen**:

```text
┌────────────────────────────────────────────────────────────────────────┐
│ MWB setup · new device detected                               [mockup] │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│ Found     Intel Core i7-1185G7 · 16 GB, one stick · Iris Xe · no NPU   │
│ Tested    speech 5.5× real time · writing model ~12 tokens/s           │
│ Suggests  Lean profile · Balanced effort (E2)                          │
│                                                                        │
│ How hard should MWB work on this laptop?                               │
│   ( )  E1  Battery saver   smallest models, 2 threads                  │
│   (•)  E2  Balanced        suggested for this laptop                   │
│   ( )  E3  High            bigger models; needs ~4 GB free; slower     │
│    -   E4  Max             not available here: needs a GPU or 32 GB    │
│                                                                        │
│ [x] Adjust automatically between E1 and my choice                      │
│     (lower on battery, back up when plugged in)                        │
│                                                                        │
│ Per feature   Journal: High          Meetings: Balanced                │
│               Dictation: Balanced    Email and code: Balanced          │
│                                                                        │
│ Needs Qwen3.5 2B (1.5 GB). Parakeet is already here.                   │
│                                     [ Later ]   [ Download 1.5 GB ]    │
└────────────────────────────────────────────────────────────────────────┘
```

What you can set there:

1. **The level:** E1 Battery saver, E2 Balanced, E3 High or E4 Max. The suggested level is pre-selected, and you can pick another.
   - If the hardware can run a level but slowly, you get a warning.
   - If it can't run a level at all, that level is greyed out with the reason. On your laptop, E4 needs a GPU or 32 GB in two sticks.
2. **Fixed or automatic.**
   - Fixed: always that level.
   - Automatic: MWB moves within a range you set, for example between E1 and E2.
3. **Battery behaviour:** lower the level on battery, or keep it.
4. **Per feature:** for example, the journal at High (it runs in the evening when you're plugged in) and dictation at Balanced.
5. **Models:** see which models your choice needs and how big they are, then download now or later.

Your choice is saved **for that machine only**, in `%LOCALAPPDATA%\MWB\machine\<fingerprint>.toml`. Your other laptop keeps its own choice. You can reopen the same screen at any time from **Settings → Performance**.

**One preference that travels:** if you always want the same kind of choice, set it once in your own settings. For example, `effort_preference = "max-available"`. Every new device then pre-selects that, and you still confirm.

The saved file on this laptop would look like this:

```toml
[hardware]                 # detected at setup
cpu = "Intel Core i7-1185G7"
ram_gb = 16
memory_channels = 1
gpu = "Intel Iris Xe (shared memory)"
npu = false

[effort]                   # your choice on the setup screen
mode = "auto"              # auto: adjust within the range; fixed: always "highest"
lowest = "E1"
highest = "E2"
on_battery = "lower"       # lower | keep

[effort.by_feature]
journal = "E3"             # runs in the evening on AC power, so it can afford more
```

This added one day to Phase 5 of the plan.

Design document: §12.5 with Figure 12.3 (the setup screen), §12.6, and requirement CTL-5.

---

## 7. AI models, explained properly

**Your question**

> for ai model i still need explaination please explain thoroughly man

**My answer**

This section assumes no AI background. It goes step by step from "what is a model" to exactly which models MWB uses, where they run, what they cost, and when an API key makes sense.

### 7.1 What an AI model is

An AI model is **a file full of numbers**. The numbers were learned by training on huge amounts of data. On its own the file does nothing. A program called a **runtime** loads the file and uses those numbers to turn an input into an output.

| Piece | What it is | Example in MWB |
|---|---|---|
| Model file | The trained "brain", stored on disk | Parakeet, a 631 MB file |
| Runtime | The engine that runs the brain | onnxruntime, whisper.cpp, llama.cpp |
| Your app | Decides what to give the model and what to do with the answer | MWB |

The numbers are called **parameters**. "0.6B" means 0.6 billion (600 million) parameters. More parameters usually mean a smarter model, but also a bigger file, more RAM and slower answers.

### 7.2 The kinds of models MWB needs

1. **Speech-to-text** (ASR, automatic speech recognition). Audio in, text out. Used for dictation and meetings. Example: **Parakeet**.
2. **Language model** (LLM, large language model). Text in, text out. It writes meeting notes, labels meetings Work or Timepass, explains and drafts emails, explains code, and writes the journal. Examples: **Qwen**, **Gemma**, **Phi**, or GPT-style models in the cloud.
3. **Small helpers.**
   - Voice activity detection decides when someone is speaking. In MWB this is plain code from AI-App, not a model.
   - Later, a diarization model can tell which voice is which.

### 7.3 What happens when a model runs on your laptop

These are the steps, with numbers I measured for Parakeet on your laptop:

1. **Load.** The runtime reads the model file from disk into RAM. This took **7.5 seconds** with 4 threads and **12.2 seconds** with 2 threads. Memory rose to about **0.95–0.99 GB**: the file is 631 MB, and the runtime needs extra working space on top.
2. **Run** (called *inference*). Audio goes in and text comes out. A 5-second phrase took **0.91 seconds** with 4 threads.
3. **Stay loaded, or close.** A loaded model answers instantly next time but keeps holding RAM. Closing its program frees all of it. MWB keeps the speech model loaded while you're actively dictating and closes it after 15 idle minutes.

One surprise from the tests: feeding 62 seconds of audio in one go left memory about 530 MB higher afterwards, because the runtime keeps its scratch memory. Feeding the same audio in 10-second pieces avoided that, and it was faster too. So MWB always uses pieces of 10 seconds or less.

### 7.4 Why RAM, and RAM speed, matter so much

**The whole model must fit in memory while it runs.** That means RAM, or the memory on a graphics card (VRAM). If it doesn't fit, Windows starts swapping to disk and everything crawls. With 0.5–3 GB free on your laptop, this is the main limit.

**A language model writes one token at a time.** A token is a piece of a word, about three quarters of a word on average. For every token, the model reads all of its numbers from RAM once. So its writing speed is capped by **memory bandwidth**, which is how fast RAM can feed the CPU:

- Your RAM (one stick) gives about 25.6 GB/s in theory, roughly 19 GB/s in practice.
- A 2B model at 4-bit is about 1.5 GB, so it writes at most about **12 tokens per second** (19 ÷ 1.5).
- With a second stick (dual channel), that roughly doubles to about **22 tokens per second**.
- For comparison, people read at about 5–7 tokens per second.

**Speech models work differently.** They process a whole chunk of audio in one big calculation, so CPU power matters more than RAM speed. That's why Parakeet is already fast on your laptop.

### 7.5 Making models smaller: quantization

Each parameter is a number stored with a certain number of bits. Storing it with fewer bits is called **quantization**. It shrinks the file, cuts RAM use and speeds things up, at a small cost in quality.

**Rough size = parameters × bits ÷ 8**

| Model | Parameters | 16-bit | 8-bit (int8) | 4-bit |
|---|---|---|---|---|
| Parakeet (speech) | 0.6 B | ~1.2 GB | **~0.6 GB, and yours is 631 MB** | not used |
| Qwen3.5 2B (writing) | 2 B | ~4 GB | ~2 GB | **~1.3–1.9 GB** |
| Qwen3.5 4B | 4 B | ~8 GB | ~4 GB | ~2.7–3.4 GB |
| Qwen3.5 9B | 9 B | ~18 GB | ~9 GB | ~5.8–6.6 GB |
| gpt-oss-120b (cloud, used by AI-App through Groq) | 120 B | — | — | ~60+ GB: impossible on a laptop |

Real 4-bit files come out a little above the formula, because some parts are kept at higher precision. "Q4_K_M" in a file name is one popular 4-bit recipe.

### 7.6 File formats and the programs that run them

| Format | Example models | Runtime (engine) | What MWB uses it for |
|---|---|---|---|
| ONNX | Parakeet | onnxruntime + onnx-asr (Python) | English speech |
| GGML (.bin) | Whisper | whisper.cpp (`whisper-server.exe`) | Hindi and Hinglish speech |
| GGUF | Qwen, Gemma, Phi | llama.cpp (`llama-server.exe`), or Ollama, a friendlier wrapper around the same kind of engine | Writing |
| none (remote) | Cloud models | The provider's servers, over the internet | Optional, with an API key |

### 7.7 What is on your laptop right now

| Item | Where | Size | How it got there |
|---|---|---|---|
| Parakeet TDT 0.6B v2, int8 | `C:\Users\parmahaj\.cache\huggingface\hub\models--istupakov--parakeet-tdt-0.6b-v2-onnx` | 631 MB | Downloaded by AI-App on 1 Oct 2026 |
| Whisper base.en | `C:\Users\parmahaj\Documents\New folder\AI-App\addon\ggml-base.en.bin` | 148 MB | AI-App's setup script |
| Speech runtimes | AI-App's Python environment (onnxruntime 1.30, onnx-asr 0.12) and whisper.cpp v1.9.2 in `AI-App\addon` | — | AI-App's setup script |
| A language model | ~~None. No Ollama, no llama.cpp, no GGUF files.~~ **Wrong, see the correction below.** | — | — |
| OLMoE folder | In the same Hugging Face cache | 1 KB, empty | Created on 18 Sep; no model files inside |

Check it yourself in PowerShell:

```powershell
Get-ChildItem "$env:USERPROFILE\.cache\huggingface\hub"                        # Parakeet's folder is here
Get-ChildItem "C:\Users\parmahaj\Documents\New folder\AI-App\addon\*.bin"       # whisper base.en
Get-Command ollama, llama-server -ErrorAction SilentlyContinue                   # prints nothing: no LLM runtime installed
```

*Correction (12 Oct):* this table was wrong. llama.cpp (build 11015) is installed in `C:\Users\parmahaj\Tools\llamacpp`, and LM Studio 0.4.25 is installed too. Three Qwen2.5 models (Coder 3B, Coder 7B and VL 3B, 8.75 GB in total) are in `Tools\llamacpp\models`. The `Get-Command` check printed nothing only because llama.cpp isn't on the PATH. Whisper small is now in `%LOCALAPPDATA%\MWB\models`. See question 11. Since then, Qwen3.5 has replaced the Qwen2.5 models (question 13).

### 7.8 The models MWB will use

| Job | Model | On disk | RAM while running | Speed here | Status |
|---|---|---|---|---|---|
| English speech to text | NVIDIA Parakeet TDT 0.6B v2, int8 | 631 MB | ~1.0 GB | 5 s phrase in 0.91 s (measured) | **Already on your laptop** |
| Hindi and Hinglish speech | OpenAI Whisper small (or large-v3-turbo), via whisper.cpp | ~0.5 GB (small) | ~0.6–1.6 GB | slower, so it runs in the background | Phase 0 download, only if you need Hindi |
| Writing, default | Qwen3.5 2B, 4-bit | ~1.3–1.9 GB | ~1.8 GB | ~12 tokens/s (estimate) | Phase 0 download |
| Writing, better quality | Qwen3.5 4B, 4-bit | ~2.7–3.4 GB | ~3.2 GB | ~6 tokens/s (estimate) | Optional |
| Writing, low memory | Qwen3.5 0.8B, 4-bit | under 1 GB | ~0.9 GB | ~25 tokens/s (estimate) | Optional |
| Who spoke when | Sortformer | — | — | — | Later, on a machine with more RAM |
| Optional cloud | For example gpt-oss-120b on Groq | nothing on disk | none on your laptop | fast | Only with your key, and only for features you allow |

*Update (Rev E, 12 Oct):* writing now goes to the API first (Groq, `openai/gpt-oss-120b`). The local fallback is Qwen2.5-Coder 3B, which is already on your laptop, so the Qwen3.5 rows are a later upgrade, not a Phase 0 download. Whisper small is already on your laptop too. *Update (Rev F):* Qwen3.5 2B and 4B are now downloaded and are the local fallback, replacing Qwen2.5 (question 13).

**Why these models:**

- **Parakeet for English.**
  - Two bigger models score slightly better on the public Open ASR Leaderboard: IBM Granite Speech 4.1 2B (5.33 % word error rate) and Cohere Transcribe 2B (5.42 %), against Parakeet's 6.05 %.
  - Those models are about three times larger and too slow for your CPU. Parakeet gives the best accuracy for its speed on this laptop, and it made zero recognition errors in my test.
  - It adds punctuation and capitals itself, but it understands **English only**.
- **Whisper for Hindi.** It handles 99 languages, including Hindi, which is why it stays as the fallback for Hindi and Hinglish.
- **Qwen3.5 for writing.**
  - Released in March 2026, with small sizes (0.8B, 2B, 4B, 9B), long context and a free licence (Apache 2.0).
  - It's an "open-weight" model: you can download it and run it yourself at no cost.
  - The final choice comes from a short Phase 0 comparison against Gemma 4 E2B/E4B, Phi-4-mini and Qwen3-4B. Each is scored on measured speed and on three real MWB tasks: meeting notes, an email draft and a Work or Timepass label.

### 7.9 Local model vs API key: the real difference

Think of it as **cooking at home versus ordering from a restaurant**.

- **At home (local):** you cook in your own small kitchen. It's private, costs nothing per meal and works without internet, but there's only so much you can make.
- **The restaurant (API):** a giant kitchen that serves faster and fancier food. But you hand over your order, pay per dish, and depend on it being open.

| | Local model | API model (cloud, with a key) |
|---|---|---|
| Where it runs | Your CPU and RAM | The provider's GPU servers |
| What leaves your laptop | Nothing | The text of each request |
| Internet | Not needed | Needed |
| Cost | Free per use (you pay in disk, RAM and battery) | Per token, or a free tier with limits |
| Writing speed here | ~12 tokens/s with a 2B model (estimate) | Often 100+ tokens/s |
| Quality | Good for notes, labels and short drafts | Better for hard reasoning and big code changes |
| Biggest model you can use | About 4B on this laptop | 100B and more (gpt-oss-120b is 60 times bigger than a 2B model) |
| Setup | Download a 1–3 GB file once | Make an account, copy a key |
| Risks | Slower, RAM pressure | Company policy, outages, models being retired (AI-App already has code for retired Groq models) |

### 7.10 What an API key is, and how MWB would use one

An **API key** is a long secret string, like a password, that identifies your account with a provider such as Groq, OpenAI, Google, or your company's Azure OpenAI. Every request carries the key, and the provider bills or rate-limits that account.

How MWB would use one:

1. You add the key in Settings. It's stored encrypted in Windows Credential Manager, the same protection (DPAPI) AI-App uses for its keys.
2. You choose which features may use it. For example: "code help: cloud allowed", "meetings: local only".
3. The first time a feature uses the cloud, MWB shows you exactly what text it will send, and you approve it.
4. Only that text is sent, over an encrypted connection. **Audio is never sent.**
5. If there's no internet or no key, the feature quietly uses the local model instead.

**Important:** whether work content may go to a cloud service is your company's decision. Providers' API terms often say they don't train on API data, but your employer's policy is what counts. Check before switching it on.

### 7.11 What it costs

- **Local models:** free per use. You pay with disk space, RAM, and battery while a model runs, which is why MWB's bigger jobs wait for the charger.
- **API models:** you pay per token, counting both what you send and what comes back. A busy MWB day is roughly:

| Activity | Tokens per day (approx.) |
|---|---|
| Notes for 2 hours of meetings | ~26,000 |
| End-of-day journal | ~7,000 |
| 10 email explanations or drafts | ~13,000 |
| 5 code explanations | ~12,000 |
| 10 voice rewrites | ~6,000 |
| **Total** | **~60,000 (call it 50,000–100,000)** |

Multiply that by the provider's price per million tokens. Prices change often, so check the provider's pricing page. Groq has a free tier with rate limits, which is why AI-App uses it by default.

### 7.12 How MWB decides where to run a request

```text
You press Ctrl+Alt+K on some selected code
 ├─ Is "code help" allowed to use the cloud?          no  → local model → answer in ~5–15 s
 ├─ yes: is there an API key and an internet link?    no  → local model (same as above)
 ├─ yes: first time? Show the exact text to be sent → you approve
 └─ send the selected code (text only) → answer in ~1–2 s
```

Speech never goes through this decision. It is always local.

### 7.13 Downloading models: when, from where, how big

- **When:** in Phase 0, after you approve the list. The setup screen shows each file and its size before anything downloads.
- **From where:**
  - Model files come from **Hugging Face**, the main public website for AI models (think of it as GitHub for models).
  - The llama.cpp program comes from its GitHub releases page. It's a download of a few tens of MB.
- **Where they go:** `%LOCALAPPDATA%\MWB\models`. Parakeet stays where it already is.
- **How much space on your laptop:** about 2–3 GB in total.
  - Parakeet: already here.
  - A 2B writing model: about 1.5 GB.
  - Whisper small: about 0.5 GB, only if you need Hindi.
  - You have 114 GB free.
- **On a company network:** if Hugging Face is blocked, download the files somewhere else and copy them into the models folder. Model files are ordinary files.
- **Removing models:** delete the file, or use Settings → Models.

*Update (Rev E, 12 Oct):* no model downloads are planned now, and llama.cpp is already installed. Question 12 has the full download list.

### 7.14 What changes on a better laptop

Say your next laptop has 32 GB of RAM and a graphics card with 8–16 GB of memory. Its setup screen would suggest the **Performance** profile:

- Parakeet runs on the graphics card, so transcription is close to instant.
- A **9B** writing model runs on the graphics card at roughly 40–80 tokens per second, instead of ~12.
- Meetings can use a top-accuracy speech model, such as Granite Speech or Cohere Transcribe.
- Speaker separation and live captions switch on.

You choose the effort level, confirm a download of about 8 GB, and that's it. Nothing in the code changes.

### 7.15 Common questions

- **Does the model learn from my data?** No. A model's numbers don't change when you use it. MWB improves by saving your corrections (for example, when you flip a meeting from Timepass to Work) and showing them to the model as examples next time. Later it may train a tiny classifier on your laptop. Nothing leaves the machine.
- **Does it work offline?** Yes, everything local does. Cloud features fall back to the local model.
- **Is my audio ever sent anywhere?** No, not even when you use API keys.
- **Why not use ChatGPT or Claude for everything?** You can add cloud models as API options if your company allows it. The default is local because of privacy, cost, offline use and company policy.
- **Can I switch models later?** Yes. `config/models.yaml` lists the models for each job. Swapping one is a configuration change, not a code change.
- **What does "open-weight" mean?** The model file is published, so you can download it and run it yourself under its licence. Qwen3.5 is Apache 2.0, Parakeet is CC-BY-4.0 and Whisper is MIT.
- **Will a model slow my laptop down?** Only while it's running. MWB caps how many CPU threads models use, runs background work at low priority, and closes models when they're idle.

---

## 8. The running loop, double Caps and the on-screen icon

**Your question**

> tell me how will the bot and running app loop i want more like Wispr Flow like it runs to write or answer my question by pressing double caps also provide option to let it show or unshow [Image #2] this icon from wispr flow by pressing double alt configurable in setting also can show or unshow there change with multiple cool icons

*(Image #2 was a screenshot of Wispr Flow's small pill-shaped indicator at the bottom of the screen.)*

**My answer**

All of this is now in the design document (Rev D):

- §8.6, with Figures 8.2 and 8.3: the running loop and one round of use.
- §9.1: double-tap Caps Lock.
- §9.7: answer mode.
- §13.3, with Figure 13.3: the indicator and its eight skins, drawn in every state.

### 8.1 How the app runs: one loop that mostly sleeps

MWB doesn't spin around checking things all the time. Its core sits inside **one Windows event loop** and is asleep almost always. It wakes up only when something happens:

- **You tap keys:** a double tap of Caps Lock or Alt. The core checks only these two keys, every 15 ms.
- **You press a shortcut:** Ctrl+Alt+something. Windows itself tells MWB.
- **Windows tells it something:** the charger was unplugged, a headset was connected, or the screen was locked.
- **You click the tray icon.**
- **A timer fires** (see the table below).

Each wake-up takes microseconds, and then the core goes back to sleep. Heavy work, such as speech recognition or writing a summary, never happens inside the loop. The loop hands it to a background thread or a worker program and keeps sleeping. That's why MWB uses about 0 % CPU while you're just working.

| Part | When it runs | Cost |
|---|---|---|
| Event loop | Always, asleep until something happens | ~0 % CPU |
| Double-tap watch | Every 15 ms, reading only Caps Lock and Alt | ~0 % CPU |
| Meeting detector | Every 5 s: "is any app using the mic?" | microseconds |
| Activity sampler | Every 10 s: which window is active, are you idle | microseconds |
| Effort governor | Every 30 s, and when power changes | microseconds |
| Indicator | Animates only while listening or working; otherwise one still picture | up to ~2 % CPU while animating (estimate) |
| Speech worker (Parakeet) | From the moment you start talking until 15 idle minutes later | ~1.0 GB while loaded |
| Language worker (Qwen 2B) | Per job; closes 5 minutes after the last one | 0.9–3.4 GB while loaded |
| Journal | 18:30, or when you ask | a few minutes of CPU |

### 8.2 One round: from double Caps to text or an answer

**Idle → (2× Caps) → Listening → (2× Caps or a 2 s pause) → Finish → Write at the cursor, or Answer in a card → Idle.** Esc cancels at any point.

1. **Idle.** Nothing is loaded except the small core. The indicator shows its idle look, or nothing if you've hidden it.
2. **You double-tap Caps Lock.** Within milliseconds:
   - the mic starts recording into memory, so your first word isn't lost;
   - the indicator switches to **listening** (blue, moving with your voice);
   - if the speech model isn't loaded, MWB starts loading it now. That takes 7.5 seconds on your laptop, but it happens while you talk.
3. **You talk.** Every time you pause for half a second, the piece you just said goes to Parakeet and becomes text in the background. With "live words" on, the indicator shows your last few words.
4. **You finish.** Double-tap Caps Lock again, or just stop talking for 2 seconds; Esc cancels everything. Only the last bit is left to transcribe, which takes about **0.7 seconds** on your laptop. The indicator switches to **working** (amber).
5. **MWB decides: write or answer** (see 8.3).
6. **Write:**
   - filler words are removed and your dictionary is applied ("preya" becomes "Priya");
   - the text is pasted where your cursor is;
   - the indicator flashes **done** (green), then returns to idle.
7. **Answer:**
   - a small card opens above the indicator, and the answer appears word by word;
   - Esc closes it, Copy copies it, and Insert types it at the cursor;
   - another double tap within 30 seconds asks a follow-up.
8. **Back to idle.** After 15 minutes without talking, the speech model closes and its ~1 GB goes back to Windows.

### 8.3 Write or answer: how MWB decides

MWB **answers** when either of these is true:

- the cursor is **not** in a text box, for example when you're looking at a web page or the desktop;
- you **start with the wake word**, as in "MWB, what's my next meeting?" The default wake word is "MWB" and you can change it.

MWB **rewrites** when text is selected and you say a command such as "make this shorter". In every other case MWB **writes** what you said.

| You're in | You say | MWB does |
|---|---|---|
| An Outlook reply | "Thanks, I'll share the build by Wednesday" | Types it |
| An Outlook reply | "MWB, when is my next meeting?" | Answers in the card; nothing is typed |
| The desktop or a web page | "What did I commit today?" | Answers with your commit list and the real commit IDs |
| Any app, with text selected | "Make this more formal" | Rewrites the selection |
| VS Code, with a function selected | "Explain this" | Answers with an explanation |

If you'd rather not have it decide, Settings can make the double tap **always write** or **always answer**.

**What it can answer:**

- **About your day:** "What did I commit today?", "What did Priya say about Kafka?", "What are my action items?", "When is my next meeting?" MWB looks these up in its own database and your calendar, so the names, times and commit IDs are real.
- **General questions,** such as "What's the difference between HashMap and ConcurrentHashMap?" These go to the language model:
  - local by default, with the first words in about 1–2 seconds;
  - or an API model, if you allow API use for answers. The whole answer then takes about 1–2 seconds.

### 8.4 How the double tap works, and why it's safe

- **Only two keys are watched.** Caps Lock and Alt can't be normal shortcuts without breaking their usual jobs, so MWB checks the up/down state of just these two keys every 15 ms. It **cannot see any other key**, which keeps it far from anything that looks like a keylogger. That matters on your laptop, because it runs Microsoft Defender for Endpoint.
- **Two quick taps** within 350 ms count as a double tap.
- **Caps Lock comes back unchanged.** Two taps turn it on and off again. If anything still leaves it changed, for example a third tap, MWB sets it back to how it was before you started.
- **Alt side effect:** a single Alt tap still reaches your app as usual. In Office it flashes the key tips for a moment, and the second tap hides them.
- **Fallback:** if checking every 15 ms ever misses taps in testing (Phase 0 task P0-2), the fallback is a keyboard hook limited to these two keys, after asking IT.
- **Push-to-talk still exists** if you prefer holding a key: Ctrl+Alt+Space.

### 8.5 The on-screen icon, like Wispr Flow's

MWB shows a small floating **indicator** at the bottom centre of your screen, like Wispr Flow's pill:

- **Where:** 48 px above the taskbar, on the screen you're working on.
- **Never in the way:** clicks pass straight through it, and it never takes the keyboard focus, so your text always lands in your app.
- **Show or hide it with a double tap of Alt.** MWB keeps working while it's hidden, and the tray icon still shows the state.
- **Colours match the tray icon:**
  - **blue** = listening;
  - **amber** = working;
  - **green** = done;
  - **orange ring** = a meeting is being recorded (this always shows, so recording is never hidden);
  - **grey** = paused.

**Eight built-in skins.** You pick one in Settings; Figure 13.3 in the design document draws all of them.

| Skin | Idle | Listening | Working | Done |
|---|---|---|---|---|
| **Capsule** (default, like Wispr) | small outline pill | wider pill with moving voice bars | pill with three pulsing dots | pill with a check mark |
| **Dot** | tiny dot | dot with ripples | dot with a spinning arc | circle with a check |
| **Bars** | five flat bars | equalizer bars dancing | soft wave of bars | bars and a check |
| **Ring** | thin ring | ring with a level arc | spinner arc | ring with a check |
| **Wave** | flat line | moving sine wave | dotted wave | line ending in a check |
| **Orb** | small soft orb | glowing orb that grows with your voice | orb with an orbiting dot | filled orb with a check |
| **Mic** | microphone outline | filled mic with level bars | mic with dots | mic and a check |
| **Pixel** | three blocks | 8-bit equalizer | chasing blocks | pixel check mark |

**Your own icons:**

1. Make a folder: `%APPDATA%\MWB\skins\<any name>\`.
2. Put one PNG per state in it: `idle.png`, `listening.png`, `working.png`, `done.png`, `recording.png`, `paused.png`.

It appears in the Skin list and switches without a restart.

**Settings (Settings → Indicator):**

| Setting | Choices | Default |
|---|---|---|
| Show indicator | on, off | on |
| Show or hide with | double-tap Alt, double-tap Right Ctrl, double-tap Shift, Ctrl+Alt+I, none | double-tap Alt |
| Skin | the eight above, or your own | Capsule |
| When visible | always, or only while listening and working | always |
| Size | small, medium, large | small |
| Position | bottom centre, top centre, any corner, near the text cursor | bottom centre |
| Opacity | 40 % to 100 % | 85 % |
| Live words | show the last few words while you talk | on |
| Full-screen apps | hide while a full-screen app is in front | on |
| Sounds | a soft tick at start and finish | off |

In the settings file it looks like this:

```toml
[triggers]
talk = "double-tap caps lock"     # push-to-talk on ctrl+alt+space also works
finish = "double-tap or 2 s pause"
talk_mode = "decide"              # decide | always-write | always-answer
wake_word = "MWB"

[indicator]
show = true
toggle = "double-tap alt"         # double-tap right ctrl | double-tap shift | ctrl+alt+i | none
skin = "capsule"                  # dot | bars | ring | wave | orb | mic | pixel | your own folder
visible = "always"                # or "while-active"
size = "small"
position = "bottom-centre"
opacity = 0.85
live_words = true
hide_in_fullscreen = true
```

**What it costs:** the indicator is a tiny transparent Windows window drawn with Pillow, with no browser engine. It adds roughly 10–15 MB to MWB. It redraws only while something is happening, so it uses no CPU at rest (estimate).

### 8.6 What changed in the plan

These features added three days:

- **Phase 1:** the double-tap trigger and the first skin.
- **Phase 3:** answer mode.
- **Phase 5:** the other seven skins and the indicator settings.

The plan is now **48 days**, about seven weeks.

---

## 9. Is the document complete?

**Your question**

> as per you entire doc is written or any doubts pending?

**My answer**

Yes, the design document is complete as a POC specification. Before answering, I checked all four revisions against each other and fixed what had gone stale:

- 4 lines in the document, written before double-tap Caps Lock became the main trigger;
- 3 counts in this file.

Then I republished the document at the same link.

Nothing is missing that I know of. What's still open falls into three groups.

**1. Decisions only you can make.** Each has a default, so work can start without them. They're listed in §19 of the document.

| # | Decision | Default |
|---|---|---|
| 1 | Ask IT for a second 16 GB RAM stick? | Plan for the current 16 GB |
| 2 | Is a cloud AI (API key) allowed at work, and which one? | Everything local |
| 3 | Meeting recording: both sides, only your mic, or only the meeting app's own transcript? | Both sides, asking first each time |
| 4 | Classic Outlook, or the new Outlook / Outlook on the web? | Classic |
| 5 | How much Hindi or Hinglish is in your meetings? | English first |
| 6 | Turn off Wispr Flow once dictation works? | Yes |
| 7 | Who gets the end-of-day report? | Only you |
| 8 | Which call apps count as personal? | WhatsApp, Discord, Telegram and Phone Link always ask before recording |
| 9 | Which features may use an API key? | None |
| 10 | What should a new laptop's setup screen pre-select? | Its suggested level |

*Update (Rev E, 12 Oct):* decisions 2 and 9 are made. Every language skill uses the API, except learning your email style, which runs locally. Speech never uses it. Still open: whether your company allows work text to go to the API.

**2. Not yet checked on your laptop.** Phase 0 tests these first (question 10):

- **Writing speed and quality:** no local writing model is installed yet, so every writing speed in the document is an estimate.
- **Call audio:** whether recording the other side of a call works from Python 3.14.
- **Double taps:** whether checking Caps Lock and Alt every 15 ms catches them reliably.
- **Outlook:** whether classic Outlook lets MWB read it without security pop-ups.
- **Call apps:** the exact program names for Zoom, Webex and browser meetings.
- **Your voice:** my test used a computer voice, so its result was a best case.

*Update:* the voice test is now Phase 0 task P0-7. Accuracy on real meetings with colleagues is checked in Phase 2, once your company agrees to recording.

**3. Company checks.**

- Recording colleagues needs your company's policy, and possibly their consent.
- Whether cloud AI is allowed for work content.
- Whether you may install tools like uv and llama.cpp, and download models from Hugging Face, on this managed laptop.

**Optional extras** that a POC spec doesn't need: a test plan section, drawings of the Today page and the Settings window, and how MWB gets installed and updated.

---

## 10. What happens in Phase 0

**Your question**

> what will you do in phase 0

**My answer**

Phase 0 means **measure before building**. Before writing the real app, I write seven small throwaway test programs; developers call them *spikes*. Each one answers one question about this laptop. It takes about **3 days**, and nothing is set up for good:

- nothing starts with Windows;
- nothing needs admin rights;
- AI-App and Wispr Flow stay unchanged. The voice test borrows AI-App's speech engine as it is.

It's §17 of the design document, tasks P0-1 to P0-7. P0-7, the test on your own voice, was added while answering this question.

### 10.1 The seven tests

| Task | Question it answers | What I do | What you do | Passes when |
|---|---|---|---|---|
| P0-1 | Can MWB hear both sides of a call? | Record your mic and your laptop's sound together for 10 minutes with two audio libraries, PyAudioWPatch and soundcard, and keep the better one | Play a video or podcast and talk now and then, wearing the headset you use for calls | 10 minutes with no gaps on either side |
| P0-2 | Do the shortcuts and double taps work everywhere? | Hold Ctrl+Alt+Space and let go: a test sentence is pasted into Outlook, Teams, VS Code and Brave. A watcher logs only *when* Caps Lock and Alt are pressed | Work normally for a day with the watcher on, and do 50 deliberate double taps of each key | At least 99 % of double taps caught, none fired by accident, the Caps Lock light never left changed |
| P0-3 | Can MWB read Outlook without pop-ups? | Read today's meetings and today's sent-mail subjects from classic Outlook, show them on screen, save nothing | Keep Outlook open and tell me if a warning appears | No security warning. This also answers decision 4 |
| P0-4 | Which writing model is fast and good enough? | Download llama.cpp and Qwen3.5 0.8B, 2B and 4B. Measure speed, memory and load time on the CPU and on the Iris Xe graphics. Give each the same MWB jobs: meeting notes, an email draft, a Work or Timepass label, a code explanation and a few general questions | Rate the answers side by side, with the model names hidden (about 20 minutes) | The 2B writes at least as fast as you read, about 7 tokens a second, and you rate its answers usable |
| P0-5 | Does MWB notice every call, in any app? | Every 5 s, read Windows' own record of which app is using the mic, the same record behind the mic icon in the taskbar. For Meet in Brave, also read the tab title. No audio is recorded | Make a short test call in each app you use | Every call caught at start and end, and the exact program names saved in `vc_apps.yaml`. This also answers decision 8 |
| P0-6 | What does this laptop measure as? | Read CPU, RAM, graphics and NPU to make the laptop's fingerprint. Run a 5-minute speed calibration and save it as the Lean baseline, as the setup screen will later do on any laptop | Keep the charger plugged in | Results saved |
| P0-7 | Does MWB understand your voice? | Write 20 sentences using your work's names and terms. Run your recordings through Parakeet and whisper, and count the mistakes | Read the sentences on your headset (about 10 minutes), plus Hinglish ones if you use Hinglish in meetings | At most 10 % of words wrong, the limit in §7.2 |

### 10.2 Day by day

- **Day 1:** set up a test folder for MWB, separate from AI-App. Run tests 1, 2, 3 and 6. The double-tap watcher then keeps running while you work.
- **Day 2:** test 4 runs for an hour or two and keeps the laptop busy, so it's best over lunch. Then your test calls (test 5) and your voice recording (test 7).
- **Day 3:** the results, a go or no-go for each test, and the design document updated with the measured numbers.

Your time in total: about 2 hours, spread over the three days.

### 10.3 What gets downloaded

I ask before each download and show its size.

| What | Size | Why |
|---|---|---|
| uv and a few Python packages | tens of MB | The test programs, in MWB's own folder |
| llama.cpp, CPU and Vulkan builds | tens of MB | The program that runs writing models |
| Qwen3.5 0.8B, 2B and 4B, 4-bit | about 5–6 GB together | The writing-model comparison. The models that lose are deleted |
| whisper small | about 0.5 GB | Only if you use Hinglish |

- Your C: drive has about 115 GB free.
- Models go in `%LOCALAPPDATA%\MWB\models\`.
- Before each model download, I check that llama.cpp can run it.
- Gemma 4 and Phi-4-mini are tested only if Qwen3.5 disappoints.

*Update (Rev E, 12 Oct):* Phase 0 downloads no model and no program: llama.cpp and the Qwen2.5 models were already on your laptop, and whisper small was copied from a verified file that was already there. The only downloads are two Python libraries, 0.4 MB in total (question 12). Test 4 now checks the API and the Qwen2.5-Coder 3B fallback, instead of comparing Qwen3.5 sizes. See question 11.

### 10.4 What I won't do

- **Record a colleague.** Call audio in Phase 0 comes from test calls and videos.
- **Read keys other than Caps Lock and Alt**, or save your mail or calendar.
- **Send your data anywhere.** The only internet use is the downloads.
- **Work around Defender or company policy.** If something is blocked, I stop, and you ask IT.

### 10.5 What you get at the end

- `docs/bench/` with the numbers, and a **go** or **no-go** for each test.
- The design document with its estimates replaced by measured values.
- For each no-go, the fallback the design document already names:

| If this fails | The fallback |
|---|---|
| Call audio from Python | The other library, a Python 3.13 environment, or recording only your mic |
| Double taps | Other shortcuts, or a keyboard hook limited to those two keys, after asking IT |
| Outlook without pop-ups | Select an email's text and press a shortcut; Microsoft Graph later |
| Writing speed | The smaller model for short text, an API key for features you pick (if allowed), or the second RAM stick, which nearly doubles the speed |
| Your voice | The dictionary for names and terms, or another speech model from §12.4 |

Then Phase 1 builds the dictation app (double-tap Caps Lock, talk, text appears) on whatever passed.

---

## 11. Your Qwen models, API first, and whisper

**Your question**

> i have qwen3.5 and qwen 7 man
>
> also i think focus on api key as of now as model will use much ram and all keep that model in sync too
>
> download whisper only
>
> llama.cpp ig i have check that if not present then only download

**My answer**

### 11.1 What is on your laptop

This time I searched every file in your user folder for model files and llama.cpp programs, not only the PATH.

| Item | Where | Size |
|---|---|---|
| llama.cpp, build 11015 (September 2026), CPU and Vulkan versions | `C:\Users\parmahaj\Tools\llamacpp\cpu` and `...\vulkan` | — |
| LM Studio 0.4.25, with its own copies of llama.cpp | `C:\Users\parmahaj\.lmstudio` | — |
| Qwen2.5-Coder-7B-Instruct, 4-bit | `C:\Users\parmahaj\Tools\llamacpp\models` | 4.36 GB |
| Qwen2.5-Coder-3B-Instruct, 4-bit | same folder | 1.80 GB |
| Qwen2.5-VL-3B-Instruct, 4-bit, plus its image part | same folder | 1.80 + 0.79 GB |
| whisper small, multilingual | `Documents\New folder\dmp\incomp\AI App\addon\ggml-small.bin` | 487 MB |

- **Your "qwen 7" is Qwen2.5-Coder 7B.** Your other Qwen models are Qwen2.5 too. I found **no Qwen3.5 file** in your user folder or the main folders on C:. If you downloaded Qwen3.5 somewhere else, tell me where and I'll add it.
- **Your models aren't stored twice.** LM Studio's folder and `Tools\llamacpp\models` point to the same files (hard links), so the four files take 8.75 GB once.
- **My first audit was wrong** about this. It said there was no llama.cpp and no language model, because it only looked at the PATH and the Hugging Face cache. Question 7.7 and the design document's §4.4 are now corrected.

### 11.2 llama.cpp: already there

It is installed and recent: build 11015, from September 2026. So **nothing was downloaded**. MWB will use `Tools\llamacpp\cpu\llama-server.exe`.

### 11.3 Whisper: copied, not downloaded

The `ggml-small.bin` already on your laptop is exactly the official file. Its SHA-256 (`1be3a9b2…987b`) and its size (487,601,967 bytes) match what Hugging Face publishes. So instead of downloading 487 MB again, I copied it to `%LOCALAPPDATA%\MWB\models\ggml-small.bin` and tested it on the same 62-second clip as before:

| Engine | Time for 62 s of audio | Word errors | Memory |
|---|---|---|---|
| Parakeet, English | 12.7 s | 0.6 % | 1.13 GB |
| whisper base.en | 21.8 s | 1.8 % | 0.52 GB |
| **whisper small, multilingual** | **23.9 s** | **4.2 %** | **1.06 GB** |

Whisper small is slower and less accurate on English, as expected. It's there for **Hindi and Hinglish**, which Parakeet can't do. English dictation stays on Parakeet.

### 11.4 API first, with the local model kept in sync

This is now the design, in Rev E of the document (§12.7):

- **The API route is the default.** Notes, email, code, answers and the journal go to Groq with `openai/gpt-oss-120b`. That's the same provider and model AI-App already uses, so the same key works in both apps. A paragraph takes 1 to 2 seconds, and MWB stays near 1 GB of memory.
- **The local fallback** is Qwen2.5-Coder 3B on your llama.cpp. It takes over by itself when the API can't be reached: no network, no answer within 10 seconds, a rate limit or a bad key. The 7B needs about 5 GB free, which this laptop rarely has, so it waits for more RAM.
- **How "in sync" works:**
  - Both routes use the same prompts and the same output checks.
  - A **sync check** sends 10 saved test prompts through both routes. It runs in Phase 0, after any change to a prompt or a model, and once a week. If the local answers stop matching, the Today page tells you.
  - Switching any skill between API and local is one setting, so on a bigger laptop MWB can go fully local.
- **Speech never uses the API.** Audio stays on the laptop.
- **One thing to check: company policy.** On the API route, the text of your notes, emails and code goes to Groq. Make sure your company allows that for work content. Until it's confirmed, any skill can be set to **local-only**. Learning your email style starts local-only, because it reads 30 sent emails at once.
- **Groq has no Qwen models any more.** AI-App's own notes record that Groq retired all of them in 2026. So API answers come from gpt-oss and the fallback from Qwen, and the sync check keeps their output consistent. If you ever want Qwen on both routes, OpenRouter offers Qwen models.

### 11.5 What it does to memory

Over the same modelled workday (Figure 11.2):

| Route | Average | Peak | Time above Wispr Flow's 1.54 GB |
|---|---|---|---|
| API, the default | 0.40 GB | 1.17 GB | never |
| Local fallback all day, if the API is down | 0.46 GB | 3.37 GB | 17 of 600 min |

### 11.6 What changed in the plan

- **Phase 0 downloads no models and no programs**, only two Python libraries of 0.4 MB (question 12). Test 4 now checks the API, measuring its speed from your network and the quality of its answers. It then runs the same tasks on the Qwen2.5-Coder 3B fallback with your llama.cpp. That's the first sync check.
- **Phase 3** builds the API client and the router, with the fallback.
- The plan is still **48 days**. The design document is now **Rev E**, at the same link.
- `docs/bench/bench_whisper.ps1` can now test any whisper model (`-Model`, `-Lang`). The whisper small numbers are in `docs/bench/RESULTS-2026-10-11.md`.

*Update (Rev F, 12 Oct):* the local fallback is now Qwen3.5 2B and 4B, and Qwen2.5 is deleted for good. See questions 13 and 14.

---

## 12. What will you download?

**Your question**

> what will you downlaod please tell me

**My answer**

**First, a correction.** In question 11 I said Phase 0 downloads nothing. That's true for models and programs, but four of the tests need two small Python libraries, 0.4 MB in total. The full list is below. It's also in the design document, §16.5.

**Models: nothing.** Everything MWB needs is already on your laptop:

- Parakeet, for English speech;
- whisper small, for Hindi and Hinglish;
- Qwen2.5-Coder 3B, the local fallback.

**Programs: nothing.** Python 3.14, llama.cpp, whisper.cpp (inside AI-App) and git are already installed. I also dropped **uv** (15.8 MB), because Python's built-in `venv` does the same job.

**Python libraries: a few small ones, from PyPI** (pypi.org, the official site for Python libraries):

| Library | When | Size | What it's for |
|---|---|---|---|
| PyAudioWPatch 0.2.12.9 | Phase 0 | 0.10 MB | Records your mic and the call audio (tests 1 and 7) |
| comtypes 1.4.17 | Phase 0 | 0.30 MB | Talks to Outlook (test 3) and reads browser tab titles (test 5) |
| Pillow 12.3.0 | Phase 1 | 7.24 MB | Draws the floating indicator icons |
| pystray 0.19.5 + six | Phase 1 | 0.06 MB | The tray icon |
| soundfile 0.14 | Phase 2, optional | ~1 MB | Compresses meeting audio; without it, the temporary audio just stays as WAV |

**Total: 0.4 MB in Phase 0, and about 7.7 MB for the whole POC.**

- I checked first. None of these libraries is on your laptop yet, in any Python environment, and both Phase 0 libraries have versions built for your Python 3.14.
- For Outlook I picked **comtypes (0.3 MB) instead of pywin32 (7 MB)**. It does the same job here.

**Only if something fails:**

- **soundcard + numpy + cffi (12.9 MB):** only if PyAudioWPatch can't record the call audio in test 1.
- **truststore (under 0.1 MB):** only if your company network blocks the API's secure connection in test 4.

**Later, and only if you choose:**

- a Qwen3.5 2B or 4B model (1.3–3.4 GB), for a better local model on a bigger laptop;
- whisper large-v3-turbo (about 0.6 GB), once there's more RAM.

**Not a download, but it uses the network:** the Groq API calls, once you add your key. They send text only, never audio.

**How the downloads happen:**

- Before each install I show you its name and size, and I install it only after you say yes.
- Every version is fixed, so nothing updates by itself.
- Everything goes into `MWB\.venv` only. Nothing is installed system-wide, and AI-App isn't touched.
- Deleting that folder removes it all.

*Update (12 Oct):* at your request I then downloaded Qwen3.5 2B and 4B, the 4B's vision file and whisper large-v3-turbo (5.2 GB, every file checked against Hugging Face), and deleted Qwen2.5 for good. The Python libraries above are unchanged. See questions 13 and 14.

---

## 13. Qwen3.5 instead of Qwen2.5, and whisper turbo

**Your question**

> see is qwen 3.5 is better than 2.5 in terms of coding and productivity then remove 2.5 and download 3.5
>
> also download that whisper 0.6 gb too

**My answer**

### 13.1 Is Qwen3.5 better? Yes, clearly

These are published scores, from Qwen's own model cards and the Qwen2.5-Coder technical report:

| Score | Qwen2.5-Coder 3B | Qwen2.5-Coder 7B | Qwen3.5 2B | Qwen3.5 4B |
|---|---|---|---|---|
| LiveCodeBench (coding) | 10.8 | 18.2 | not published | **55.8** |
| MMLU-Pro (knowledge) | 35.2 | 45.6 | 55.3 | **79.1** |
| IFEval (following instructions) | 44.2 | 58.6 | 61.2 | **89.8** |
| Context | 32K tokens | 32K | 262K | 262K |
| Reads images | no | no | yes | yes |
| File size (4-bit) | 1.8 GB | 4.4 GB | 1.27 GB | 2.71 GB |

- **Coding:** the 4B beats even the old 7B coding model, and it is smaller. The two LiveCodeBench versions use different problems, but the gap is far too large to change the answer.
- **Productivity** (emails, notes, following instructions): both Qwen3.5 sizes beat both old models.
- **One catch:** Qwen3.5 scores best with "thinking" on, where it reasons step by step first, and that is slow on your CPU. Your launchers and MWB run it with thinking off, which gives back part of the lead. It is still well ahead.

**On your own laptop**, I also gave each model 5 small Python tasks, checked automatically by tests, with thinking off:

| Model | Tasks passed | Writing speed |
|---|---|---|
| Qwen2.5-Coder 3B (old) | 2 of 5 | 7.3 tokens/s |
| Qwen3.5 2B | 3 of 5 | 8.8 tokens/s |
| Qwen3.5 4B | 4 of 5 | 3.6 tokens/s |

Same answer: Qwen3.5 is better. The 2B beats the old 3B at about the same speed. The 4B is the best coder, but on this laptop it writes slower than you read.

### 13.2 What I downloaded

All from Hugging Face, and each file was checked against the SHA-256 that Hugging Face publishes:

| File | Size | Where | Why |
|---|---|---|---|
| Qwen3.5-4B-Q4_K_M.gguf | 2.71 GB | `Tools\llamacpp\models` | The best coder: replaces Coder 7B |
| mmproj-Qwen3.5-4B-BF16.gguf | 0.68 GB | same folder | The 4B's vision part. It keeps image chat in your `gui.bat` working, in place of Qwen2.5-VL |
| Qwen3.5-2B-Q4_K_M.gguf | 1.27 GB | same folder | Small and quick: replaces Coder 3B, and is MWB's everyday fallback |
| ggml-large-v3-turbo-q5_0.bin | 0.57 GB | `%LOCALAPPDATA%\MWB\models` | The whisper you asked for |

Total: 5.2 GB. LM Studio sees the Qwen3.5 files too, through hard links: the same files, with no extra space.

### 13.3 How they run on your laptop

| Model | Reading your prompt | Writing | Memory while loaded |
|---|---|---|---|
| Qwen3.5 2B | 42 tokens/s (211 on the Iris Xe GPU) | 10.3 tokens/s | 1.3 GB |
| Qwen3.5 4B | 13 tokens/s (90 on the GPU) | 3.6 tokens/s | 2.4 GB (3.4 GB with its vision part) |

- **Thinking off works:** no reasoning text. The first words appear after about 1 second on the 2B and 3 seconds on the 4B.
- **The same request to both:** *"Rewrite more politely: send me the build by Wednesday, I still need Kafka access."*
  - 2B: "Could you please send me the build by Wednesday so that I can still obtain the required Kafka access?"
  - 4B: "Could you please share the build by Wednesday so I can proceed with obtaining Kafka access?"
  - Both are polite, but both joined the two requests as if one depended on the other. Read drafts before you send them.
- **Image chat (4B with its vision file):** I gave it a picture with the words "Build 4217 OK" and it read them back exactly, in 10 seconds.

**Whisper large-v3-turbo** is downloaded and works, but it's **slower than real time on this CPU**:

- 137 s for the 62-second test clip, where whisper small takes 24 s;
- 1.27 GB of memory;
- 7.8 % word errors, 4 points of which are formatting. It was the only engine to spell "Priya" right.

So on this laptop MWB keeps whisper small for everyday Hindi and Hinglish, and uses turbo only for overnight re-runs, or on a stronger laptop.

### 13.4 What I removed, and your launchers

- **Qwen2.5 is in the Recycle Bin:** Coder 3B, Coder 7B, VL 3B and its vision file, 8.75 GB in all. You can restore them from there, and emptying the bin frees the space. LM Studio's entries for them were removed too. *Update:* at your request they were then deleted for good (question 14).
- **Your 5 launchers in `Tools\llamacpp` now use Qwen3.5**, so none of them broke:

| Launcher | Before | Now | Checked |
|---|---|---|---|
| `chat-3b.bat` | Coder 3B | 2B, thinking off (fast) | ran it: answered correctly |
| `chat-7b.bat` | Coder 7B | 4B, thinking off (best answers, slower) | ran it: answered correctly |
| `gui-coder.bat` | Coder 3B | 2B, thinking off | same settings as `serve.bat`; not run, because it opens a browser tab |
| `gui.bat` | VL 3B and its vision file | 4B and its vision file, thinking off | read a test picture correctly |
| `serve.bat` (AI-App's custom provider) | Coder 3B | 2B, thinking off | ran it on a spare port: answered correctly |

- For a hard problem in `chat-7b.bat`, you can turn thinking on; the line to add is written in the file. Each answer then takes minutes on this laptop.
- The 4B reads long pastes about 7× faster with the GPU build (the `vulkan` folder). I left your launchers on the CPU build, as you had them.

- The file names didn't change, so your shortcuts still work. The originals are in `Tools\llamacpp\backup-before-qwen3.5\`.
- The launchers also use Qwen's recommended settings: temperature, top-p and so on.

### 13.5 What changed in MWB's design (now Rev F)

- **The local fallback is now Qwen3.5.** The 2B is used every day, because it fits next to the speech model within 3.5 GB. The 4B handles code and the journal when there's room.
- **The API stays the default.** The sync check now compares the API with Qwen3.5.
- **New finding:** on the Iris Xe GPU (Vulkan), prompts are read 5 to 7 times faster, while writing is slower or about the same. So long inputs like meeting notes and the journal go to Vulkan, and short chats stay on the CPU.

---

## 14. Remove Qwen2.5 completely

**Your question**

> take qwn 3.5 to download and remove 2.5 completely from my pc now

**My answer**

**Qwen3.5 was already downloaded**, so there was nothing new to fetch. I re-checked all three files against the checksums Hugging Face publishes, and they're intact:

| File | Size | Check |
|---|---|---|
| Qwen3.5-2B-Q4_K_M.gguf | 1.27 GB | OK |
| Qwen3.5-4B-Q4_K_M.gguf | 2.71 GB | OK |
| mmproj-Qwen3.5-4B-BF16.gguf | 0.68 GB | OK |

They're in `C:\Users\parmahaj\Tools\llamacpp\models`, and LM Studio lists them too.

**Qwen2.5 is deleted for good:**

- I deleted the 4 Qwen2.5 files from the Recycle Bin permanently: Coder 3B, Coder 7B, VL 3B and its vision file, 8.75 GB in total.
- A search of your whole user folder now finds **no Qwen2.5 model file**.
- Free space on C: went from 110.5 GB to 119.2 GB.
- I didn't empty the Recycle Bin. Its 1,980 other items are untouched.

**What still mentions Qwen2.5, and why I left it.** None of these is a model; they're small text files:

- **LM Studio's own cache and index files** (`.lmstudio\.internal\*.json`). They're shared with other models, so editing them by hand could break LM Studio, and LM Studio refreshes them itself.
- **One LM Studio chat** (`.lmstudio\conversations\1791227597220.conversation.json`) that you had with a Qwen2.5 model. That's your chat history, so I left it.
- **Your old launcher backups** in `Tools\llamacpp\backup-before-qwen3.5\`. They only point at the deleted files, so they won't run any more. Delete that folder whenever you like.
- **A folder called `qwen25-14b`** inside a Codex plugin (`.codex\.tmp\plugins\...`). It's a configuration template that belongs to that plugin, not a model.

---

## 15. How MWB will work, and a demo of the UI

**Your question**

> now tell how will it functiona add one demo html to show ui and all for this

**My answer**

The demo is here: https://claude.ai/artifact/JkKapQwt42FiU1TMUcjFCZ. There's an offline copy at `docs/MWB-Demo.html`; double-click it to open it in your browser.

### 15.1 How MWB works through your day

1. **It starts with Windows.** A small core, about 40 MB, sits in the tray. It holds no AI model, and it sleeps until something happens: a double tap of Caps Lock or Alt, one of your shortcuts, an app starting to use the microphone (checked every 5 s), or the window you're working in (checked every 10 s).
2. **You talk: double-tap Caps Lock.**
   - The indicator turns blue and the microphone starts recording.
   - The speech worker (Parakeet, about 1 GB) loads if needed and turns each piece of speech into text while you keep talking.
   - You finish with another double tap, or by pausing for 2 seconds.
   - Clean-up rules remove fillers and fix punctuation and names.
   - MWB pastes the text at your cursor and restores your clipboard.
3. **Write or answer.** If no text box is selected, or you start with "MWB", it answers in a small card instead of typing.
4. **Help with text:**
   - <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>R</kbd> rewrites a selection.
   - <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>E</kbd> explains the open email and drafts a reply in your style.
   - <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>K</kbd> explains code and suggests a faster version.

   The text goes to the API (Groq) and comes back in 1 to 2 seconds. If the API is down, Qwen3.5 2B on your laptop answers instead, more slowly. Facts such as commit IDs, times and counts always come from code, never from the model. MWB never sends email.
5. **Meetings, in any call app:**
   - When an app starts using the microphone, MWB treats it as a meeting.
   - It asks before recording during the first week. Personal apps like WhatsApp always ask.
   - It records you and the other side separately and transcribes in the background at low priority.
   - After the call it gives you the transcript in about a minute, then notes, action items and a Work or Timepass label with its reasons.
6. **End of day, 18:30.** The Today page lists:
   - your meetings and their labels;
   - your commits with their IDs;
   - the emails you sent;
   - where your time went;
   - a journal written from those facts.

   You can copy it as Markdown or save it as an Outlook draft.
7. **Memory.** Workers start only when needed and exit when idle: speech after 15 minutes, the local language model after 5. On the API route MWB averages about 0.4 GB, against Wispr Flow's constant 1.54 GB.
8. **You stay in control:**
   - <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>P</kbd> pauses everything.
   - Double-tap <kbd>Alt</kbd> to show or hide the indicator.
   - <kbd>Esc</kbd> cancels.
   - The tray menu has the rest.

### 15.2 What the demo shows

- **A simulated laptop screen** with Outlook, Teams, VS Code, a browser and a Teams call, plus MWB's floating indicator, result cards, notifications and tray menu.
- **10 scenarios, in tour order:**
  1. dictate;
  2. fix a mistake while talking;
  3. ask about your day;
  4. rewrite a selection;
  5. explain an email;
  6. explain code;
  7. a meeting starts;
  8. the API is down;
  9. end of the day;
  10. pause everything.

  Click one, or press **Play all**. Each step is explained under the screen as it happens.
- **An "Under the hood" panel:** which workers are running, how much memory MWB uses against Wispr Flow's line, and a live event log. **Skip 15 idle minutes** shows the workers exiting and the memory dropping.
- **The Today page**, where you can click a Work or Timepass label to change it, and click a citation in the journal to find its commit, meeting or email.
- **Settings**, where every change applies to the demo straight away:
  - the indicator's 8 skins;
  - show or hide, and live words;
  - API or local;
  - a "pretend the API is down" switch;
  - the effort level;
  - per-app recording rules;
  - the shortcuts.
- **Your own keys:** click the screen, then double-tap <kbd>Caps Lock</kbd>. It dictates in Outlook, cleans up a sentence in Teams, and answers in the browser.
- **Direct links:** add `#meeting`, `#ask`, `#today` or `#settings` to the end of the link to open that scenario or view directly.

The demo uses sample data, and it can't hear your microphone, so the spoken words are scripted. Its speeds and memory figures are the ones measured on your laptop.

---

## 16. What now?

**Your question**

> what now?

**My answer**

**Next is Phase 0:** about 3 days of quick tests on your laptop, before any of the real app is built. Two parts are already done: the Qwen3.5 speeds and whisper turbo were measured on 12 October. These are still to do:

1. Record both sides of a call (PyAudioWPatch).
2. Double taps and pasting into Outlook, Teams, VS Code and Brave.
3. Read Outlook without security pop-ups.
4. API speed and quality from your network, plus the first sync check against Qwen3.5.
5. Detect calls in the call apps you use.
6. The laptop's fingerprint and calibration.
7. Accuracy on your own voice.

**To start, I need three things from you:**

1. **A yes** to install 2 small Python libraries, PyAudioWPatch and comtypes (0.4 MB in total), into MWB's own folder.
2. **Your Groq API key**, when we reach test 4. I'll give you a one-line command to run in your own PowerShell window. It stores the key in Windows Credential Manager, so the key never appears in our chat. It can be the same key AI-App uses.
3. **Three quick answers:**
   - Which call apps do you use? (Teams, Zoom, Google Meet, Webex, Slack, WhatsApp, others?)
   - Do your meetings have Hindi or Hinglish?
   - Do you use classic Outlook or the new Outlook every day?

**Only you can do these, in parallel:**

- **Ask IT or your manager** whether it's OK to record calls with colleagues (and whether they must be told), and whether work text such as emails, notes and code may go to Groq. Until they say yes, MWB keeps those features on your laptop.
- **Optionally, ask IT for a second 16 GB memory stick.** It roughly doubles the local model's speed.

**After Phase 0:**

| Phase | What gets built | Days |
|---|---|---|
| 1 | Dictation: double-tap Caps Lock, text in any app, the indicator. At the end you can switch off Wispr Flow and free 1.5 GB | about 8 |
| 2 | Meetings in any call app | about 9 |
| 3 | Email, code and answers | about 10 |
| 4 | The end-of-day journal | about 7 |
| 5 | Effort levels, the other indicator skins, polish | about 11 |

That's about 48 days in all.

---

## 17. Is everything written down in this folder?

**Your question**

> have you written every thing to do and context anywhere in this folder?

**My answer**

Before this question, everything was written down, but spread over the long design document and this file. There was no single to-do list, and my notes for future sessions lived outside the folder. Now the folder has:

| File | What it holds |
|---|---|
| `README.md` | What MWB is, how it works in short, the measured numbers, where every file and model is, and the links |
| `TODO.md` | Everything still to do, with checkboxes: your tasks, the Phase 0 tests and their status, Phases 1 to 5, the open decisions, housekeeping, and what's done |
| `CLAUDE.md` | Context and rules for future AI sessions. It travels with the folder, so it works on another laptop too |
| `.gitignore` | Keeps the Python environment, build output and voice recordings out of Git |
| `docs/src/demo/MWB-Demo.html` | The demo's source, for future changes |

**One thing to check: your GitHub repository `AI-Bot` is public.** The documents you staged mention:

- your Windows user name;
- your Git identity;
- the laptop model;
- the company security tools on it.

Before you push them, either make the repository private (GitHub → Settings → Danger Zone → Change visibility), or ask me to remove those details. I haven't committed or pushed anything.

---

## 18. Continuing Phase 0

**Your question**

> continue ig i did changes for phase 0

**My answer**

First I checked what had changed on the laptop. The steps that need you hadn't happened yet:
- there's no `MWB\.venv`, so the two small libraries aren't installed;
- there's no Groq key in Credential Manager;
- the three questions in `TODO.md` were still open.

The only changes were the files from my last answer: `README.md`, `TODO.md`, `CLAUDE.md`, `.gitignore` and the demo source. That's fine. Four of the seven tests can at least start without installing anything, so I did that. Everything below used only Python's built-in library and Windows PowerShell. Full numbers are in `docs/bench/P0-RESULTS-2026-10-12.md`.

| Test | What happened |
|---|---|
| **P0-6** Fingerprint | **Done.** MWB's "ID card" for this laptop is `530285546f`, and the suggested level is **Lean**. It's saved in `%LOCALAPPDATA%\MWB\machine\530285546f.toml`, outside Git. Only the API speed is missing; test 4 adds it once your Groq key is stored |
| **P0-3** Outlook | **Passed.** MWB read today's calendar, including the meeting links inside invitations, and sent-mail subjects, with no security pop-up. Windows Defender being on is why Outlook allows it |
| **P0-5** Call detection | **Half done.** Windows' list of apps that used your mic shows Teams, under the exact name the design expected. The other half needs real calls (below) |
| **P0-2** Keys | **Script ready.** I tested it with simulated key presses: all 13 double taps were caught, and 2 slow pairs were correctly ignored. Real fingers are less regular, so the real test is yours |

**Things I learned that change the design a little:**

1. **Outlook reads dates the Indian way** (day-month-year). Written the American way, a date search silently found nothing. The fix is simple, and it's now in the notes.
2. **Ctrl+Alt+Space is already taken**, most likely by the Claude desktop app's quick-entry shortcut. You can change that app's shortcut, or MWB can use **Ctrl+Shift+Alt+Space** for push-to-talk, which is free.
3. **AI-App's portable build is called `OneDrive.exe`.** MWB must not confuse it with the real OneDrive, so programs with common names will be recognised by their full folder path.
4. **Your classic Outlook hasn't sent anything in about four weeks.** For the end-of-day journal, I need to know where you really send email from.

**What I need from you now:**

- **Four answers:**
  1. Which call apps do you use? So far only Teams has used your mic. Telegram and Phone Link are installed, and web meetings in Brave or Edge are possible.
  2. Do your meetings have Hindi or Hinglish?
  3. Classic Outlook? New Outlook has never been opened on this laptop, so I believe it's classic. Please confirm.
  4. Where do you send work email from: Outlook on the web, your phone, or something else?
- **Two short tests**, run in PowerShell from `docs\bench`. Each one prints its steps:
  - `py -3.14 -I p0_2_keys.py`: double-tap Caps Lock 50 times, then Alt 50 times, then work normally for 5 minutes, then try push-to-talk in Outlook, Teams, VS Code and Brave. About 10 minutes. Press Ctrl+C at the end and send me the summary.
  - `py -3.14 -I p0_5_mic_watch.py --watch`: leave it running while you take your next calls, then send me what it printed. Meeting names stay on your laptop and aren't saved in this folder.
- **Still waiting:** a yes to installing PyAudioWPatch and comtypes (tests 1, 3 and 7), and your Groq key (test 4).

One side effect: the Outlook test started Outlook without a window, and Outlook ignored the request to close again. It's harmless, just like Outlook running minimised. It goes away when you open Outlook and close it, or when you sign out.

---

## 19. Your answers: Hinglish, Outlook and work email

**Your question**

> make it
>
> see i meet in hinglish and hindi
> i use outlook app needs to run to see my meeting and transcribe it
>
> work emails are form edge [work domain] profile

(The repository is public, so the email domain is left out. You also pasted the start of the P0-2 test and the output of `p0_5_mic_watch.py --watch:`.)

**My answer**

**Thank you: that settles decisions 4 and 5.**

| You said | What it changes |
|---|---|
| Meetings are in Hindi and Hinglish | Parakeet only understands English, so meetings go through **whisper small**, which understands Hindi and Hinglish. Dictation stays on Parakeet, which is faster |
| You use the Outlook app, and it has to run to see your meetings | Classic Outlook it is. MWB reads your meetings from it, and may start it when it isn't running |
| Work email is in Edge, in your work profile | That account is on Microsoft 365 and lives only in Outlook on the web. Classic Outlook holds a different account, so MWB can't see your work email yet |

**For the work email, choose one:**

1. **Add your work account to classic Outlook**, if both companies allow it. Then MWB reads it exactly like your meetings. This is the simplest option.
2. **Ask that account's admin to allow a Microsoft Graph sign-in** for MWB, which lets MWB read your sent mail with your permission.
3. **Leave email out of the journal.** "Explain this email" still works on any text you select in Edge.

**I measured whisper small on this laptop just now (new test P0-8).** It decides whether meeting notes can be ready quickly:

- On **battery**, it can't keep up with a call: 62 seconds of audio took 67 seconds on 4 threads, and 106 seconds on the 2 threads MWB allows during a call.
- On **mains power** the same clip took 24 seconds on 12 October, so it should keep up there. One run while plugged in will confirm it.
- **Until then, MWB records Hindi and Hinglish meetings and transcribes them after the call.** A one-hour meeting would take about 25 minutes when plugged in. The design's "notes within 10 minutes" target only holds for English meetings for now.

**About the two tests you ran:**

- **P0-2** started correctly. It then waits for you: do the four steps it prints, then press **Ctrl+C**. Ctrl+C is what makes it print the results, so please send me that summary.
- **P0-5:** the colon in `--watch:` made the script show a one-time list instead of watching. I've fixed it so `--watch:` works too, and the script now says when it has only shown a list. Run it from the MWB folder like this, and leave it open during your next call:
  `py -3.14 -I docs\bench\p0_5_mic_watch.py --watch`
- **The "can't open file" error** came from running the script in the MWB folder without its folder name. The commands in `TODO.md` now include `docs\bench\`, so they work from the MWB folder.

"Make it" can mean a few different things here, so I asked you which one you meant before doing anything bigger.

---

## 20. Where are we?

**Your question**

> where are we

**My answer**

I checked on the morning of 13 October. Nothing had changed overnight:
- no libraries are installed;
- no Groq key is stored;
- the key test's log has no taps in it yet.

| Stage | Status |
|---|---|
| Design document (Rev F) and the interactive demo | Done |
| Models: Qwen3.5 2B and 4B, whisper small and turbo downloaded and checked; Qwen2.5 removed; launchers updated | Done |
| Phase 0, tests on this laptop | About half done (below) |
| Phases 1 to 5, building the app | Not started. There is no MWB app code yet |

**Phase 0, test by test:**

| Test | Status | Waiting for |
|---|---|---|
| P0-6 Laptop fingerprint | Done | Nothing |
| P0-3 Reading classic Outlook | Passed | Nothing |
| P0-4 API compared with the local models | Local half measured | Your Groq key |
| P0-5 Finding calls | Teams confirmed | `--watch` running during your next call |
| P0-2 Double taps and pasting | Script ready; your run started but no taps were recorded | Your 10-minute run |
| P0-8 whisper small for Hindi and Hinglish | Too slow on battery (0.93× real time) | One run on mains power |
| P0-1 Recording both sides of a call | Not started | A yes to the two libraries |
| P0-7 Your own voice | Not started | A yes to the two libraries |

**Decided yesterday:**
- Meetings go through whisper small, because they're in Hindi and Hinglish.
- Meetings come from classic Outlook.

**Still open:** how MWB should see your work email. The three options are in answer 19.

**What moves things forward, in order:**

1. **A yes** to installing PyAudioWPatch and comtypes (0.4 MB) into `MWB\.venv`. It unblocks three tests.
2. **Your Groq key,** stored with a one-line command that I'll give you. Never paste it into the chat.
3. **The two hands-on tests:** P0-2 now, and P0-5 during your next call.
4. **Two answers:**
   - Do you use any call apps besides Teams?
   - Which work-email option do you prefer?
5. **Questions for IT:**
   - May MWB record calls with colleagues?
   - May work text go to Groq?
6. **The repository:** it's still public, and nothing has been committed or pushed yet.

The laptop was plugged in when I checked, so P0-8 can be finished in about two minutes whenever you say so.

---

## 21. The libraries, a window for the Groq key, and your answers

**Your question**

> install two py lib
>
> provide me option in app to add groq key
>
> you can run
>
> see i use teams but be ready for any vc
>
> it can go no worries
>
> sure will make private

**My answer**

| You said | What I did |
|---|---|
| Install the two libraries | Done. PyAudioWPatch 0.2.12.9 and comtypes 1.4.17 are in `MWB\.venv`. The download was 0.4 MB, 2.5 MB once installed. `requirements.txt` records their exact versions and PyPI's checksums, so pip refuses any other file. I also checked that the PyAudioWPatch file was published by the project's own GitHub workflow |
| A way in the app to add the Groq key | Done. MWB has no tray icon until Phase 1, so I built the key window now, as MWB's first real code. Double-click **`Set API key.cmd`** in the MWB folder. From Phase 1, the tray menu opens the same window |
| You can run | Done: whisper small on mains power (P0-8). When plugged in, it keeps up with a Hindi or Hinglish call: 62 s of audio in 33 s on 2 threads. On battery it can't, so meetings are transcribed live when plugged in and after the call on battery |
| Teams, but ready for any call app | That's how MWB finds calls: it watches which app is using the microphone, so any call app is noticed. Teams is recognised by name; MWB asks once about an app it doesn't know |
| "It can go, no worries" | I took this to mean that work text may go to Groq, and noted it |
| You'll make the repository private | Noted. Push the docs only after that |

**How the key window works:**

1. Paste the key with Ctrl+V. The box hides it; tick Show to see it.
2. Press Save. MWB first asks Groq whether the key works, by asking for its list of models; none of your text is sent. Only a key Groq accepts is stored.
3. The key goes into Windows Credential Manager as `MWB/api-key/groq`, encrypted with your Windows sign-in.
   - It is never written to a file.
   - The window only ever shows its last 4 characters.
4. Check key tests the stored key again. Remove deletes it.

**Tested:**
- Saving, reading and deleting in Credential Manager, on a throwaway entry.
- A deliberately fake key got Groq's "401 Invalid API Key" back in 0.4 s. Your network reaches Groq without trouble.
- The window's look, at your 150 % display scaling.

**Two tests are waiting for your Teams call to end.** Teams took the mic at 10:30, and these two would open the mic or start Outlook, so they run once the call is over:
- **P0-1:** recording both sides of a call. It saves no audio.
- **P0-3:** reading Outlook through comtypes.

**Next for you:**
1. Save the key with `Set API key.cmd`. Then I'll run the API half of P0-4.
2. Two open questions:
   - Which work-email option do you prefer?
   - May MWB record calls with colleagues?
3. The hands-on tests in `TODO.md`: the key test, and the call watch and the 10-minute recording check during a call.
4. Make the repository private.

*Update, 10:55:* your call ended at 10:47, so I ran the two tests.

- **P0-1, recording both sides: technical go.**
  - The mic and the speakers' loopback recorded together with no gaps and no overflows.
  - The loopback lane only receives sound while something plays. So I added a self-test that plays an inaudible signal, about −90 dBFS. The loopback lane then ran without a break as well.
  - The full pass test is still 10 minutes during a real call. It saves no audio.
- **P0-3, Outlook through comtypes: go.**
  - No security pop-up, even when reading meeting bodies, sent-mail bodies and recipients.
  - It adds about 8 MB to MWB's core.
  - Outlook closed again by itself afterwards.
- **Your 10:30 call:** Windows recorded it exactly, 10:30:46 to 10:47:01, which is how MWB will notice calls. It wasn't in the classic Outlook calendar, so it was either an unscheduled call or a meeting in your work account's web calendar.

---

## 22. How to use Set API key.cmd

**Your question**

> Set API key.cmd
>
> how to set

**My answer**

I opened the window for you. It's called **MWB · Groq API key**.

**1. Open the window** (next time):
- In File Explorer, go to `Documents\New folder\MWB` and double-click `Set API key.cmd`. A black window flashes, then the key window opens.
- Or, in PowerShell: `& "$env:USERPROFILE\Documents\New folder\MWB\Set API key.cmd"`. Typing only `Set API key.cmd` does nothing, because PowerShell reads "Set" as one of its own commands.

**2. Get a key.** AI-App's key box hides the key and won't let you copy it, so the easiest way is a new key just for MWB. It's free, and separate keys let you switch one off without breaking the other app.
1. Click the `console.groq.com/keys` link in the window, and sign in to Groq.
2. Click **Create API Key**, name it `MWB`, and click **Copy**. Groq shows the key only once.

**3. Save it:**
1. Click in the **Key** box and press **Ctrl+V**. The key shows as dots; tick **Show** to check it.
2. Click **Save**.
   - MWB first asks Groq whether the key works, which takes about half a second.
   - Then the status turns green: "Stored, ends in …" plus the key's last 4 characters.
   - The line under the buttons says "✓ Saved. Groq accepted the key…".
3. Close the window.

**If something goes wrong:**

| The window says | What to do |
|---|---|
| ✗ Groq rejected this key (HTTP 401) | Part of the key was missed, or the key was deleted. Copy it again, or create a new one. Nothing was saved |
| Couldn't reach api.groq.com | Check the internet connection or VPN, then press Save again |
| Paste your key in the box first | The box was empty when you pressed Save |
| No window appears | In PowerShell, run `cd "$env:USERPROFILE\Documents\New folder\MWB"; .venv\Scripts\python.exe -m mwb.ui.api_key` and send me what it prints |

Once it's saved, tell me. I'll then run the API half of P0-4: Groq's speed and quality against the local Qwen3.5 models.

---

## 23. Groq tested: results, and what you do next

**Your question**

> done with api key now tell what to do
>
> or youwill run your tests

**My answer**

I ran the tests: the API half of P0-4. Ten everyday MWB tasks went to Groq, all made up for the test:
- meeting notes for an English call and for a Hindi-and-English call;
- two Work or Timepass labels;
- explaining an email;
- drafting a reply;
- explaining code;
- cleaning up dictation;
- the end-of-day journal;
- a quick answer.

The 5 coding tasks from 12 October were added. Each answer was checked automatically.

| Groq model | Checks passed | First word | Whole answer | Coding |
|---|---|---|---|---|
| **gpt-oss-120b, reasoning low** | **42 of 42** | 0.6 s | 0.9 s | 5 of 5 |
| gpt-oss-20b, reasoning low | 39 of 42 | 0.4 s | 0.6 s | 5 of 5 |
| gpt-oss-120b, reasoning medium | 40 of 42 | 0.9 s | 1.1 s | not run |

For comparison, the local models on 12 October solved 3 (2B) and 4 (4B) of the 5 coding tasks, and wrote about 10 and 4 tokens (pieces of words) per second.

**What this changes in MWB:**
- **MWB uses gpt-oss-120b with low reasoning.** Medium reasoning was slower and no better on these tasks. The smaller 20b gets only the quick jobs it always got right: labels, clean-up and short answers.
- **MWB works out dates itself.** The 20b turned "by Friday" into the wrong date, and the 120b once wrote "Thursday, 14 Oct" when Thursday is the 15th. The model will say "by Friday", and MWB's code turns that into the date.
- **MWB cleans up hyphens.** Groq's models wrote ticket IDs like `PAY-412` with a look-alike hyphen character, which breaks search and links. MWB swaps it for a normal hyphen.
- **The journal prompt now spells out what it wants.** At first the models left out the commit IDs and added things that hadn't happened. The stricter prompt fixed this for the 120b. MWB's code will also check that every commit ID is there and exact.
- Your Hindi-and-English meeting was summarised correctly in English.

**The local half didn't run.** Only 0.6–2 GB of memory was free, and comparing with the local models needs about 3.5 GB for 15 minutes. The script checked first and skipped it, rather than slowing your laptop.

**What you do next:**
1. **When you can free about 3.5 GB,** close windows you don't need or wait until the end of the day, and tell me. I'll run the local half. Then you score the answers on a review page that hides which model wrote which; it takes about 10 minutes.
2. **The key test (P0-2),** about 10 minutes, whenever you like: `py -3.14 -I docs\bench\p0_2_keys.py` in the MWB folder.
3. **In your next call,** start the call watcher (P0-5) and the 10-minute recording check (P0-1). The commands are in `TODO.md`.
4. **Three answers:**
   - Was the 10:30 call a scheduled meeting?
   - How should MWB see your work email?
   - May MWB record calls with colleagues?
5. **Make the GitHub repository private.**

---

## 24. Is Phase 1 complete?

**Your question**

> where are we ig phase 1 is complete?

**My answer**

No. Phase 1 hasn't started yet. We are still in **Phase 0**, the tests on your laptop. Phase 0 checks that each part of MWB can work on this laptop before we build it. Phase 1 builds the dictation app itself.

**What exists in `mwb/` so far** is groundwork for Phase 3, not Phase 1:
- the window for the Groq key;
- saving the key in Credential Manager;
- the Groq chat client.

We built these early because the P0-4 test needed them.

**Phase 0, test by test:**

| Test | What it checks | Status |
|---|---|---|
| P0-1 | Recording both sides of a call | Technical go. The 10-minute test during a call is still to do |
| P0-2 | Hotkeys and double Caps Lock | Script ready. Needs your 10-minute run |
| P0-3 | Reading Outlook | Go |
| P0-4 | Groq, and the local models kept in sync | Groq half: go. The local half needs about 3.5 GB free, then your blind review |
| P0-5 | Spotting calls | Teams confirmed. The `--watch` run during calls is still to do |
| P0-6 | Laptop fingerprint | Done |
| P0-7 | Your own voice, in English, Hindi and Hinglish | To do. You read 20 sentences |
| P0-8 | whisper small speed for Hindi and Hinglish | Go when plugged in |

So 4 of the 8 tests are finished and 4 are waiting. Each of those 4 needs you: your hands, a call, or more free memory.

**After the tests,** I update the design document to Rev G. That swaps its estimates for the measured numbers and adds the 13 October decisions. Then Phase 0 is finished.

**Phase 1, dictation, comes next.** It takes about 8 working days and builds:
- the core and the tray icon;
- the hotkeys and double Caps Lock;
- the speech worker;
- clean-up and paste;
- the on-screen indicator.

It is done when text arrives within 1 second of finishing a phrase, the core idles at 60 MB or less, it works in 5 apps, and you can switch Wispr Flow off.

**Can Phase 1 start before Phase 0 ends?** Partly. Only P0-2 (the keys) and P0-7 (your voice) decide how dictation is built. The other open tests are about meetings (Phase 2) and the local models (Phase 3). So the quickest path is:
1. Run P0-2 now. It needs no call and takes about 10 minutes: `py -3.14 -I docs\bench\p0_2_keys.py` in the MWB folder.
2. Read the P0-7 sentences; I'll prepare that script.
3. Then I start Phase 1. The call tests and the local half of P0-4 can finish alongside it.

**A note on Git.** On 13 October at 23:57 you committed everything to the `dev` branch on this laptop. That's fine: `dev` hasn't been pushed to GitHub. Keep it that way until the repository is private.

---

## 25. The key test: the shortcut opened Claude

**Your question**

> done that but tell me control shift space opened claude
>
> also haven tested this  work normally for 5 minutes (typing, Alt+Tab, capitals): anything detected then is a false start;

**My answer**

**Why Claude opened.** The hold-to-talk test needs four keys held together: **Ctrl + Shift + Alt + Space**. The Claude app owns Ctrl+Alt+Space, the same keys without Shift, so a press without Shift opens Claude. I sent both Ctrl+Shift+Alt+Space and Ctrl+Shift+Space from software. Both reached the test, and Claude didn't react to either. Your log has no hold at all, so a key was probably missing when you pressed it.

**What the first run measured (14 Oct, 00:03–00:04):**

| Key | Double taps caught | Unpaired taps |
|---|---|---|
| Caps Lock | 42 | 2 |
| Alt | 54 | 3 |

- Caps Lock always ended where it started.
- None of the double taps had Ctrl, Shift, Win or Tab down.
- An unpaired tap is a tap with no second tap within 0.35 s. Each one is either a stray tap or a double tap that was too slow.

The pass mark is 99 % of the double taps you actually did. So I need your own counts, or the Results lines the first window printed when you pressed Ctrl+C.

**Run 2 is open** for what's left: counting in sets of 10, 5 minutes of normal work, and the paste test.

*Update (14 Oct, 00:11):* you pasted run 2's results. It lasted 1.1 minutes.
- **The shortcut works.** Ctrl+Shift+Alt+Space reached the test and pasted. That confirms a key was missing in the first run. The paste went into the test window itself, so it still has to be tried in Outlook, Teams, VS Code and Brave.
- **Caps Lock: 19 double taps from 38 taps.** Every tap was part of a double tap, with none left over, so nothing was missed. One tap was shorter than 15 ms and was still caught. Caps Lock stayed off throughout.
- **Still to do:** Alt in sets of 10, the 5 minutes of normal work, and the paste test in the four apps.

---

## 26. Alt again? Where to work normally, and reading a hold line

**Your question**

> did alt already use that
>
> where to do noemal work
>
>  held 0.17 s, all keys up 942 ms later, pasted into "MWB P0-2 key test (run 2)" in 413 ms. Check that the line appeared. tek it for example

**My answer**

**Alt: yes, you did it in the first run.** That run caught 54 Alt double taps from 111 presses. 3 presses didn't pair up, and each of those is either a stray press or a double tap that was too slow. So between 0 and 2 double taps may have been missed, and that sits right on the 99 % line. Two counted sets of 10 settle it in about 30 seconds.

**Normal work: anywhere.** The test watches the keyboard across the whole laptop, so the window can sit in the background or be minimised.
- Use your laptop as usual: reply in Teams, write an email, code in VS Code, search in Brave.
- Use Alt+Tab and capital letters (Shift, or a single Caps Lock press) the way you normally do.
- The test only records key timings, never what you type.
- If a "double tap" line appears while you weren't doing one on purpose, that's a false start.

**Reading the hold line:**

| Part | Meaning |
|---|---|
| `held 0.17 s` | How long Ctrl, Alt and Space stayed down together, measured until the first of them came up. In MWB, that's how long you're talking. Hold for 1–2 s in the test |
| `all keys up 942 ms later` | From letting go of the first key to the last one coming up. The paste waits for all of them, or a held Ctrl, Alt or Shift would change Ctrl+V into a different shortcut. 0.9 s is a slow release; letting go of all four together takes about 0.1 s. In MWB, speech recognition will start while you let go, so this wait overlaps with it |
| `pasted into "MWB P0-2 key test (run 2)"` | The window in front at the time. Here it was the test window itself, so click into an app's text box first |
| `in 413 ms` | The time before your clipboard was put back. 400 ms of that is a deliberate pause so the app has time to read the clipboard. The line itself appears almost at once |

**A fix in the test.** The release wait checked Ctrl, Alt and Space, but not Shift. The shortcut includes Shift, so a late Shift would have turned the paste into Ctrl+Shift+V, which opens a Markdown preview in VS Code. `p0_2_keys.py` now waits for Shift too, and a simulated late Shift release confirmed it. MWB's own hotkey code will do the same.

---

## 27. The key test passed: what now?

**Your question**

> what now  i am getting bored of this task man

**My answer**

Fair enough. The key test is done, and it passed:
- Caps Lock: 50 of 50 double taps caught.
- Alt: 50 of 50, with one pair of presses that may have been a too-slow double tap.
- The hold-to-talk shortcut pasted into VS Code.

The full numbers are in `docs/bench/P0-RESULTS-2026-10-12.md`.

The two leftover parts no longer need effort from you:
- **False starts:** one day, leave the test minimised while you work, then send me its Results.
- **Paste into Outlook, Teams and Brave:** Phase 1's own pass test covers this.

What's left before Phase 1 is one task of about 10 minutes, P0-7: reading 20 sentences into your headset. Phase 1 doesn't have to wait for it, though. English dictation was already benchmarked on 11 October, and P0-7 only confirms the accuracy for your own voice. So I can start building Phase 1, the dictation app, whenever you say. Then you'll have something you can actually use instead of more tests.

---

## 28. Phase 1: dictation is built

**Your question**

> go fot phas1 then

**My answer**

Done: MWB now does dictation. Double-click `Start MWB.cmd` and a microphone icon appears in the tray, next to the clock. Click in any text box, double-tap **Caps Lock** and talk. When you pause for 2 seconds, or double-tap again, the text appears where your cursor is.

**What I built, in plain words:**
- **The core** is a small program that sits in the tray. It wakes when you press a key and sleeps the rest of the time. At rest it uses 25 MB of memory.
- **The speech worker** is a separate program that turns speech into text with Parakeet, the same engine AI-App uses. It loads only when needed and closes itself after 15 minutes without use, which gives its 1 GB back. Audio never leaves the laptop.
- **Listening while you talk:** MWB cuts your speech at every half-second pause and sends each piece to the speech worker while you carry on. When you finish, only the last piece is left.
- **Clean-up:** "um" and "uh" are dropped, and repeated words ("I I think") are collapsed. "New line", "bullet point" and "question mark" become layout, and "scratch that" replaces what you just said. Your dictionary fixes names.
- **Pasting:** MWB puts the text on the clipboard, presses Ctrl+V, then puts your own clipboard back. Its text is kept out of Windows' clipboard history (Win+V).
- **The indicator** is a small dark capsule above the taskbar: blue bars while it listens, amber dots while it works, a green tick when the text is in. Clicks go straight through it, and it never takes your cursor.
- **History:** each dictation is saved on the laptop, so it can be searched. The tray's "Copy last dictation" gets the last one back.

I installed the two libraries you approved, Pillow and pystray. Each was checked against PyPI's checksum.

**How it measured (all synthetic speech; your own voice comes next):**

| Pass mark (design) | Result |
|---|---|
| Text within 1.0 s of finishing (median) | 0.98 s, on battery with the laptop busy |
| Word errors | 1.5 % ("sync" heard as "sink") |
| Core memory at rest, at most 60 MB | 25 MB |
| Caps Lock left as it was | Yes |
| The indicator never takes focus | Yes |

**Two things to know:**
1. **The first dictation can be slow.** The speech engine takes 17–40 seconds to load when memory is tight; it took 7.5 s on 11 October with more free memory. It loads when MWB starts if 2 GB is free, and otherwise on your first dictation. After that, text comes in about a second. Switching Wispr Flow off frees 1.5 GB, which is the biggest help.
2. **When less than 1 GB is free, MWB refuses to load the speech engine** and tells you, rather than slowing the whole laptop. That happened several times tonight (0.3–0.9 GB free).

**What you do next:**
1. Try it in Outlook, Teams, VS Code, Brave and one more app, and tell me where it went wrong.
2. Tell me any words it keeps getting wrong, and I'll add them to your dictionary.
3. When you're happy with it, switch Wispr Flow off.

---

## 29. Phase 2: meetings are built

**Your question**

> can we proceed with phase 2?

**My answer**

Yes, and it's built. One thing first: **you still need IT's or your manager's answer on recording colleagues.** Until then, MWB asks before every recording, and on work calls you should choose "Not this one".

**How it works, in plain words:**
- **Finding calls:** Windows notes which app is using the microphone. Every 5 seconds MWB looks at that note. When Teams, Zoom, Meet in a browser tab, or any other app has used the mic for 20 seconds, that's a call. When the app lets go of the mic for a minute, the call is over.
- **Asking:** a small card appears at the bottom right: "Teams is using the microphone. Record this call?", with Record, Not this one, and Never for Teams. It never takes your cursor, so your typing in the call isn't interrupted. MWB asks every time in its first week, and always for personal apps like WhatsApp. If you don't answer within 2 minutes, it doesn't record.
- **Recording:** two "lanes", your mic ("You") and what your speakers play ("Them"). This works the same for every call app. The tray icon and the indicator get an orange ring while it records. **Ctrl+Alt+M** starts or stops a recording by hand.
- **Transcribing:** whisper small, which understands English, Hindi and Hinglish, on this laptop. On mains power it works during the call; on battery, right after it. Each piece of audio is deleted the moment it's transcribed.
- **Reading it:** **Ctrl+Alt+J** opens the Today page in your browser. It lists your meetings, shows each transcript with times and You/Them, has "Copy all", and searches across all of them. Only your laptop can open it.
- **Importing:** if Teams, Zoom or Webex already made a transcript, the tray's "Import a transcript…" reads its file (.vtt, .docx or .txt). That needs no recording and no CPU.

**Two changes from the design, because of what I measured:**
1. **whisper runs once per piece of audio and then exits,** instead of staying loaded. Staying loaded held 2.2 GB; running per piece uses 0.79 GB and gives it back each time.
2. **The pieces are about 25 seconds, not 10.** whisper always processes a 30-second window, so a 4-second piece costs as much as a 28-second one.

**How it tested** (a made-up 1-minute conversation, 12 turns, played through MWB):

| Check | Result |
|---|---|
| Transcript correct, You and Them in order | Yes, all 12 lines |
| Audio left on disk | None |
| Ready within 2 minutes of the end | **No: 355 s.** Only 0.4–0.8 GB was free, below the 0.8 GB whisper needs, so nothing ran during the call |

With enough free memory, each 28-second piece took about 28 seconds, so a transcript about a minute after the call is likely. That's an estimate. **Memory is the real limit on this laptop:** switching Wispr Flow off frees 1.5 GB, and a second memory stick would fix it properly.

**What you do:**
1. Start MWB (`Start MWB.cmd`) and leave it running through your calls for a week. Tell me about any call it missed.
2. Ask IT or your manager about recording colleagues.
3. Try importing a Teams transcript: in Teams, open the meeting's Recap, download the transcript, then use the tray's "Import a transcript…".

---

## 30. Phase 3: understanding is built

**Your question**

> go for next phase

**My answer**

Phase 3 is built. MWB now uses the language model (Groq, with the Qwen model on your laptop as a fallback) to understand what it hears and what you select.

**What's new, in plain words:**
- **Meeting notes:** after a meeting's transcript is ready, MWB writes a short summary, the decisions, and the action items with who owns them and by when. The model only copies down what was said ("by Wednesday"). MWB's own code works out the real date (Wed 14 Oct), because in P0-4 the models got dates wrong.
- **Work or Timepass:** each meeting gets a label with its reasons. Clear cases are decided by simple rules ("Sprint planning" is work, "Diwali celebration" is timepass). Unclear ones are checked against the notes. On the Today page one click confirms or flips the label, and your choice carries over to the same meeting next week.
- **Email (Ctrl+Alt+E):** select an email's text and press the keys. A card explains what they want, the deadlines as real dates, the people, and reply ideas. **Hold** the keys and say the gist ("tell him I'll share the build by Wednesday") to get a draft you can copy, insert, or open as a classic-Outlook draft. **MWB never sends email**; a test checks every line of its code for that.
- **Code (Ctrl+Alt+K):** select code and press. You get what it does, its problems, and a better version, with Replace and a side-by-side diff in VS Code. Hold and describe code ("a Java method that retries with backoff") to have it written at the cursor.
- **Rewrite (Ctrl+Alt+R):** select text, hold, and say "shorter", "more formal" or "translate to Hindi".
- **Asking questions:** the same Caps Lock double tap now *answers* instead of writing when your cursor isn't in a text box, or when you start with "MWB, …". Questions about your day ("What are my open action items?", "What did they say about Kafka?", "What's my next meeting?") are answered from your own meetings, notes and Outlook calendar. Each fact carries a tag like [M3 10:04] showing where it came from, and any tag the model makes up is removed.
- **The local fallback:** if the network, the key or Groq fails, the same request goes to Qwen on your laptop, if there's enough free memory. Background notes wait for mains power and a calm CPU rather than slowing your laptop.

**How it tested:**

| Pass mark (design) | Result |
|---|---|
| 10 questions about your day answered correctly | **10 of 10**, in 0.6–1.7 s each |
| Notes quickly after a call | 3 seconds for a 15-minute test meeting |
| No code path that sends email | Passed |
| 80 % of labels match yours | Needs your first 20 meetings |
| Everything still works with the network off | Built, but not yet tried for real: the local model needs 1.25 GB free and only 0.2–0.8 GB was free tonight |

**Things I found and fixed:**
- Your terminal and VS Code don't tell Windows they're text boxes, so a double tap there would have become a question. They now always write.
- A first version of the cards took the focus from your app, which would break "Replace". They now never take it, and I checked.

**What you do:**
1. Try Ctrl+Alt+E on an email in Outlook on the web, Ctrl+Alt+K on some code, and ask MWB a question with the cursor on the desktop.
2. After meetings, confirm or flip each label on the Today page for your first 20. That's how MWB proves its 80 %.
3. One evening when the laptop is quieter, tell me, and I'll run the network-off test and P0-4's local half together.

---

## 31. The code and flow changed: update the docs

**Your question**

> made some changes in code and flow update docs

**My answer**

Done. First I checked what had changed. No file in the MWB folder was edited after 14 October, 23:50. So the changes are the ones made while building Phases 1 to 3 on 14 October. README, TODO and CLAUDE.md already described them. The design document didn't: it was still Rev F from 12 October, written before any app code existed. If you changed something somewhere else, tell me where and I'll add it.

**What I updated:**

| Document | What changed |
|---|---|
| Design document, now **Rev G** | It describes MWB as built. I checked each point against the code, not only against the notes. It also has the measured numbers from Phase 0 and the build, in a new §6.5, and the 13 October decisions. Things not built yet (the journal, the setup screen, effort levels, the other seven skins) are marked as such. Republished to the same link |
| The interactive demo | Small fixes so it matches the app. Meetings now go through whisper. The clipboard is put back after 400 ms. The API timeout is 20 s. The "Record this call?" card has its real buttons, and the push-to-talk fallback is shown. Republished to the same link |
| README.md, TODO.md | Status 16 October; the "Rev G" item in Phase 0 is ticked |

**The biggest differences between the plan and what was built:**

| The plan (Rev F) | As built (Rev G) | Why |
|---|---|---|
| Meetings through Parakeet, or a whisper server that stays loaded | whisper small through whisper-cli, started once for each piece of audio | Your meetings use Hindi and Hinglish, and Parakeet is English only. The server held 2.2 GB; one whisper-cli run peaks at 0.79 GB and gives it back |
| Pieces of 10 s | Pieces of 22–28 s | whisper always works on a 30-second window, so short pieces cost the same as long ones |
| Transcribe during every call | During the call only on mains power with a calm CPU; on battery, after the call | Measured in P0-8: too slow on battery |
| Push-to-talk on Ctrl+Alt+Space | Ctrl+Shift+Alt+Space on this laptop | Another app, probably Claude's quick entry, owns Ctrl+Alt+Space |
| Clipboard back after 300 ms | 400 ms | P0-2 pasted reliably with 400 ms |
| API timeout of 10 s | 20 s without a word | The value set in the settings (`api_timeout_s`); you can change it there |
| The answer card grows out of the indicator | Every card opens near the mouse pointer, and never takes the focus | So Replace and Insert land in your app |
| `vc_apps.yaml`, Opus audio | `vc_apps.toml`, temporary WAV | Python reads TOML without an extra library; each WAV piece is deleted as soon as it is transcribed, so compressing it isn't worth a library |
| Unknown call apps ask once, then MWB remembers | They ask every time, until you choose "Never" | That's how the card was built |

Six figures were redrawn to match: the block diagram, one round of use, the dictation timeline, the meeting pipeline, the database tables and the plan.

**Nothing new for you to do.** The open items in TODO.md are the same as before: try dictation in your five apps, the call tests, your voice test, and the question to IT about recording colleagues.

---

## 32. Results in the indicator's place, like Wispr Flow

**Your question**

> inspite of opening a diff modal for cut and insert optn like wispr does open in audio place only
>
> also make sure to make it fast and smooth such that it doesnot affect resources of laptop and make it authentic and cool like whispr flow does

**My answer**

Done. Answers, reply drafts, code explanations and rewrites no longer open a separate window near the mouse. They open **in the indicator's place**: a dark panel rises out of the pill at the bottom of the screen, the text streams into it, and the buttons (Copy, Insert, Replace, Open diff in VS Code, Open as Outlook draft) sit at the bottom of the panel. Wispr Flow keeps everything in its bar in the same way. This is also what the original plan said ("the answer card grows out of the indicator"); the first build had put cards near the mouse instead.

**How it behaves:**

| You do | What happens |
|---|---|
| Ask, rewrite, explain | The pill shows three amber dots; the panel fades and rises in above it, and the text streams in |
| Click **Copy**, **Insert** or **Replace** | The panel closes and the pill shows a green tick with "Copied", "Inserted" or "Replaced" for about a second |
| Click **Open diff…** or **Open as Outlook draft** | That opens, and the panel stays, so you can still Replace afterwards |
| Scroll the mouse wheel over a long answer | It scrolls; a soft fade shows there is more above or below |
| Press **Esc**, or click **×** | The panel closes |

Clicking the panel never takes the keyboard focus, so Insert and Replace still paste into the app you were typing in. When no panel is open, clicks go straight through the pill as before.

**Smoother:** the pill now grows and shrinks between its sizes (resting, listening, the tick) instead of jumping, and the voice bars rise quickly and fall gently, so they follow your voice without flickering.

**Light on the laptop** (measured on this laptop):

| | Before | Now |
|---|---|---|
| Resting, nothing happening | No redraws | No redraws |
| One frame while you talk | A new drawing surface made and freed every frame | The surface is kept and reused; drawing takes about 0.3 ms at 30 frames a second |
| Size changes and fades | Not animated | 60 frames a second, only for the 0.2 s they last |
| A long answer streaming in | The Tk window redrew every piece | At most 12 redraws a second, about 4 ms each; each line of text is drawn once and reused |

The old Tk result window is gone from `mwb/ui/cards.py`; the "Record this call?" card is unchanged, because it isn't a result.

**Changed files:** `mwb/ui/indicator.py` (the panel, the mouse, the animation), `mwb/ui/art.py` (drawing the panel, the "Copied" tick, the in-between sizes), `mwb/ui/cards.py` and `mwb/app.py` (results go to the indicator).

**Not done yet:** the design document and the demo still describe cards near the mouse, so they need a small update.

*Update (16 Oct 2026):* the design document and the demo now match. In the design document, §13.3 describes the panel and has a new Figure 13.4 (working, the panel rising out of the pill, the "Inserted" tick), and §8.3, §9 and the Rev G row no longer say "near the mouse". In the demo, the result opens as a dark panel just above the pill; Copy and Replace close it and the pill shows "Copied" or "Replaced", while "Open as Outlook draft" and "Open diff in VS Code" keep it open. Both files are rebuilt here; the two online copies still need republishing.

---

## 33. Glossary

| Term | Meaning |
|---|---|
| Model | A file of learned numbers that turns an input into an output |
| Parameters | The numbers inside a model. "2B" means 2 billion |
| Runtime | The program that runs a model: onnxruntime, whisper.cpp, llama.cpp |
| ASR | Automatic speech recognition: speech in, text out |
| LLM | Large language model: reads and writes text |
| Token | A piece of a word, about three quarters of a word on average |
| Tokens per second | How fast a language model writes |
| WER | Word error rate: the share of words that come out wrong |
| × real time | How many times faster than the audio plays. 5× means a minute of speech takes 12 seconds |
| Quantization | Storing a model's numbers in fewer bits (int8, 4-bit) to save memory |
| GGUF, ONNX | File formats for models |
| VRAM | Memory on a graphics card |
| Memory bandwidth | How fast RAM feeds the CPU. Two sticks in two slots double it |
| Open-weight | A model you can download and run yourself |
| API | A service you call over the internet |
| API key | Your secret password for an API |
| Fallback | The local model MWB uses when the API can't be reached, or for a skill set to local-only |
| Sync check | Saved test prompts sent through both the API and the local model, to make sure the fallback still answers in the same format |
| Thinking mode | Qwen3.5 can reason step by step before it answers. That gives better answers but is much slower on a CPU, so MWB turns it off |
| Local-only | A skill whose text never leaves the laptop |
| Profile | Lean, Balanced, Performance or Workstation, chosen from your hardware |
| Effort level | E1 to E4: how hard MWB works on a device, chosen by you on the setup screen |
| Hardware fingerprint | An ID built from CPU, RAM, GPU and NPU. When it changes, the setup screen runs again |
| VC app | Any video-call app: Teams, Zoom, Google Meet, Webex, Slack huddles, WhatsApp and others |
| Event loop | The part of MWB that sleeps until something happens, handles it in microseconds, and goes back to sleep |
| Double tap | Two quick presses of the same key within 350 ms: Caps Lock to talk or ask, Alt to show or hide the indicator |
| Wake word | A word you start with, "MWB" by default, to make MWB answer instead of typing what you say |
| Answer mode | When MWB replies in a small card instead of typing your words |
| Indicator | The small floating icon at the bottom of the screen that shows what MWB is doing, like Wispr Flow's pill |
| Skin | One look for the indicator: Capsule, Dot, Bars, Ring, Wave, Orb, Mic, Pixel, or your own PNGs |
| Reasoning effort | How long a reasoning model such as gpt-oss "thinks" before it answers: low, medium or high. More thinking is slower, and isn't always better |
| First word | The time from sending a request to the first word of the answer arriving: what makes an assistant feel quick |
| Blind review | Scoring answers without knowing which model wrote them, so you judge only the answer |
| Rate limit | How many requests or tokens an API allows per minute or per day; above it, the API asks you to wait |
| Push-to-talk | Talking only while you hold a key, like a walkie-talkie; letting go means "done" |
| VAD (voice activity detection) | Code that tells speech from silence. MWB uses it to cut your speech at pauses |
| Speech worker | The separate program that turns audio into text. It closes when idle, which is how its memory goes back to Windows |
| Tray | The small icons next to the clock at the bottom right of the screen |
| Finish-to-text | The time from finishing a dictation to the text appearing in your app: Phase 1's main speed number |
| Loopback | Recording what the laptop itself plays, the way MWB hears the other side of a call |
| Lane | One of the two recordings of a call: You (the mic) or Them (the speakers) |
| Echo | Your mic hearing the other side through your speakers; MWB removes those repeated lines |
| Router | The part of MWB that decides where a request goes: the API first, the local model when the API can't answer |
| Fallback | The second choice used when the first fails: here, Qwen on your laptop when Groq can't be reached |
| Citation | A tag such as [M3 10:04] showing which meeting, time or item a fact came from |
| Action item | A task someone agreed to in a meeting, with an owner and, if one was said, a date |
