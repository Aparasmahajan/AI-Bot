// Generates every SVG figure in the MWB POC spec. Geometry is computed from data so charts stay to scale.
// Colours are CSS classes resolved from the page's theme tokens (see .dg rules in 00-head.html).

const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const f = (n) => String(Math.round(n * 10) / 10);

function wrap(id, w, h, title, body, minw = 640) {
  return `<svg class="dg" viewBox="0 0 ${w} ${h}" style="min-width:${minw}px" role="img" aria-labelledby="${id}-t"><title id="${id}-t">${esc(title)}</title>${body}</svg>`;
}
const T = (x, y, s, cls = '', a = 'start') =>
  `<text x="${f(x)}" y="${f(y)}"${cls ? ` class="${cls}"` : ''}${a !== 'start' ? ` text-anchor="${a}"` : ''}>${esc(s)}</text>`;
const TL = (x, y, lines, cls = '', a = 'start', lh = 15) => lines.map((s, i) => T(x, y + i * lh, s, cls, a)).join('');
const RECT = (x, y, w, h, cls = 'bx', rx = 0) =>
  `<rect x="${f(x)}" y="${f(y)}" width="${f(w)}" height="${f(h)}"${rx ? ` rx="${rx}"` : ''} class="${cls}"/>`;
const LINE = (x1, y1, x2, y2, cls = 'ln') => `<line x1="${f(x1)}" y1="${f(y1)}" x2="${f(x2)}" y2="${f(y2)}" class="${cls}"/>`;
const HEAD = { ln: 'mk-ink', 'ln-c': 'mk-c', 'ln-s': 'mk-s', 'ln-d': 'mk-ink' };

// Polyline with an arrowhead drawn as a polygon at the last point (no <marker>, so theme colours always apply).
function ARR(pts, cls = 'ln', head = true) {
  const p = pts.map(([x, y]) => [x, y]);
  let tip = '';
  if (head) {
    const [x1, y1] = p[p.length - 2];
    const [x2, y2] = p[p.length - 1];
    const len = Math.hypot(x2 - x1, y2 - y1) || 1;
    const ux = (x2 - x1) / len, uy = (y2 - y1) / len, L = 8, W = 4;
    const bx = x2 - ux * L, by = y2 - uy * L;
    p[p.length - 1] = [x2 - ux * (L - 1), y2 - uy * (L - 1)];
    tip = `<polygon points="${f(x2)},${f(y2)} ${f(bx - uy * W)},${f(by + ux * W)} ${f(bx + uy * W)},${f(by - ux * W)}" class="${HEAD[cls] || 'mk-ink'}"/>`;
  }
  return `<polyline points="${p.map(([x, y]) => `${f(x)},${f(y)}`).join(' ')}" class="${cls}"/>` + tip;
}
function LBOX(x, y, w, h, title, lines = [], o = {}) {
  const { cls = 'bx', tcls = 'h', lcls = 'm mid', a = 'start', pad = 12, ty = 22, lh = 15, gap = 17 } = o;
  const tx = a === 'middle' ? x + w / 2 : x + pad;
  return RECT(x, y, w, h, cls) + T(tx, y + ty, title, tcls, a) + TL(tx, y + ty + gap, lines, lcls, a, lh);
}
const fmt = (n) => n.toLocaleString('en-US');

// Figure 3.1 ------------------------------------------------------------------------------------
export function figApp() {
  const ins = [
    ['Your voice', 'mic · push-to-talk', true],
    ['Calls', 'any VC app · loopback', true],
    ['Outlook', 'mail · calendar (COM)', false],
    ['Selected text', 'email · code · any app', false],
    ['Work signals', 'git repos · active window', false],
  ];
  const outs = [
    ['Text at cursor', 'cleaned dictation'],
    ['Meeting notes', 'Work / Timepass · actions'],
    ['Email help', 'explain · draft reply'],
    ['Code help', 'explain · optimise'],
    ['Daily journal', 'commits · meetings · time'],
  ];
  let b = '';
  ins.forEach(([t, s, audio], i) => {
    const y = 20 + i * 56;
    b += LBOX(0, y, 200, 44, t, [s], { cls: audio ? 'bx-s' : 'bx', ty: 18, gap: 16 });
    b += ARR([[200, y + 22], [318, y + 22]], audio ? 'ln-s' : 'ln');
  });
  b += RECT(320, 10, 240, 280, 'bx-c');
  b += T(440, 40, 'MWB', 'h big', 'middle');
  ['hotkeys · tray · pause', 'core · always on · ~40 MB', 'speech worker · on demand', 'language · API or local', 'SQLite · your journal']
    .forEach((c, i) => { const y = 58 + i * 44; b += RECT(338, y, 204, 34, 'bx') + T(440, y + 21.5, c, 'm', 'middle'); });
  outs.forEach(([t, s], i) => {
    const y = 20 + i * 56;
    b += ARR([[560, y + 22], [678, y + 22]], 'ln');
    b += LBOX(680, y, 200, 44, t, [s], { ty: 18, gap: 16 });
  });
  return wrap('fig-app', 880, 300, 'Simplified application diagram: five inputs feed MWB, which produces five outputs', b, 660);
}

// Figure 4.1 ------------------------------------------------------------------------------------
export function figRam() {
  const rows = [['Brave', 30, 3603], ['Claude app', 18, 2908], ['Edge', 27, 2593], ['svchost', 100, 1812], ['Wispr Flow', 11, 1541], ['Defender AV', 1, 462], ['WebView2', 13, 459]];
  const x0 = 150, x1 = 770, max = 4000, sx = (v) => x0 + (v / max) * (x1 - x0), top = 14, rowH = 34;
  const bottom = top + rows.length * rowH;
  let b = '';
  for (let v = 0; v <= max; v += 1000) {
    const x = sx(v);
    b += LINE(x, top - 4, x, bottom + 4, 'grid') + T(x, bottom + 22, v === max ? '4,000 MB' : fmt(v), 'm dim', 'middle');
  }
  rows.forEach(([name, n, mb], i) => {
    const y = top + i * rowH, hl = name === 'Wispr Flow';
    b += T(x0 - 12, y + 15, name, hl ? 'h ts' : 'h', 'end');
    b += T(x0 - 12, y + 29, n > 1 ? `${n} processes` : '1 process', 'm dim', 'end');
    b += RECT(x0, y + 6, sx(mb) - x0, 18, hl ? 'bar-s' : 'bar-w');
    b += T(sx(mb) + 8, y + 20, `${fmt(mb)} MB`, hl ? 'm ts b' : 'm mid');
    if (hl) b += T(sx(mb) + 82, y + 20, 'MWB dictation is built to replace this', 'm ts');
  });
  return wrap('fig-ram', 880, bottom + 32, 'Working set by app: Brave 3,603 MB, Claude app 2,908, Edge 2,593, svchost 1,812, Wispr Flow 1,541, Defender 462, WebView2 459', b, 640);
}

// Figure 6.1 ------------------------------------------------------------------------------------
export function figLat() {
  const groups = [['3 s phrase', 3, 1.66, 0.66], ['5 s phrase', 5, 1.98, 0.91], ['10 s phrase', 10, 2.52, 1.78], ['30 s chunk', 30, 6.53, 5.73]];
  const x0 = 64, x1 = 870, yb = 262, yt = 34, max = 7, sy = (v) => yb - (v / max) * (yb - yt);
  let b = '';
  for (let v = 0; v <= max; v++) b += LINE(x0, sy(v), x1, sy(v), v ? 'grid' : 'axis') + T(x0 - 10, sy(v) + 4, `${v} s`, 'm dim', 'end');
  const gw = (x1 - x0) / groups.length, bw = 56, gap = 10;
  groups.forEach(([lab, secs, v2, v4], i) => {
    const cx = x0 + gw * i + gw / 2, xa = cx - bw - gap / 2, xb = cx + gap / 2;
    b += RECT(xa, sy(v2), bw, yb - sy(v2), 'bar-w') + T(xa + bw / 2, sy(v2) - 7, v2.toFixed(2), 'm mid', 'middle');
    b += RECT(xb, sy(v4), bw, yb - sy(v4), 'bar-c') + T(xb + bw / 2, sy(v4) - 7, v4.toFixed(2), 'm tc b', 'middle');
    b += T(cx, yb + 20, lab, 'h', 'middle');
    b += T(cx, yb + 37, `${(secs / v4).toFixed(1)}× real time on 4 threads`, 'm dim', 'middle');
  });
  b += RECT(x0 + 18, 10, 12, 12, 'bar-c') + T(x0 + 36, 20, '4 threads, proposed for dictation', 'm');
  b += RECT(x0 + 300, 10, 12, 12, 'bar-w') + T(x0 + 318, 20, '2 threads, AI-App default', 'm');
  return wrap('fig-lat', 880, 312, 'Parakeet transcription time by clip length: 2 threads 1.66, 1.98, 2.52, 6.53 s; 4 threads 0.66, 0.91, 1.78, 5.73 s', b, 640);
}

// Figure 6.2 ------------------------------------------------------------------------------------
export function figMem() {
  const st = [['After model load', 992, 984], ['After 10 dictations', 1132, 989], ['62 s in 10 s pieces', 1131, 988], ['62 s in one pass', 1660, 989]];
  const x0 = 70, x1 = 870, yb = 254, yt = 34, max = 1800, sy = (v) => yb - (v / max) * (yb - yt);
  let b = '';
  for (let v = 0; v <= max; v += 300) b += LINE(x0, sy(v), x1, sy(v), v ? 'grid' : 'axis') + T(x0 - 10, sy(v) + 4, v === max ? '1,800' : fmt(v), 'm dim', 'end');
  b += T(x0 - 10, yt - 14, 'MB', 'm dim', 'end');
  const gw = (x1 - x0) / st.length, bw = 56, gap = 10;
  st.forEach(([lab, on, off], i) => {
    const cx = x0 + gw * i + gw / 2, xa = cx - bw - gap / 2, xb = cx + gap / 2;
    b += RECT(xa, sy(on), bw, yb - sy(on), 'bar-c') + T(xa + bw / 2, sy(on) - 7, fmt(on), 'm tc b', 'middle');
    b += RECT(xb, sy(off), bw, yb - sy(off), 'bar-w');
    if (i === 3) {
      // arena off: the single pass peaked at 1,386 MB and was released afterwards
      b += RECT(xb, sy(1386), bw, sy(off) - sy(1386), 'rg-d') + T(xb + bw / 2, sy(1386) - 7, 'peak 1,386', 'm mid', 'middle');
      b += T(xb + bw / 2, sy(off) + 16, fmt(off), 'm knock', 'middle');
    } else {
      b += T(xb + bw / 2, sy(off) - 7, fmt(off), 'm mid', 'middle');
    }
    b += T(cx, yb + 20, lab, 'h', 'middle');
  });
  b += RECT(x0 + 18, 10, 12, 12, 'bar-c') + T(x0 + 36, 20, 'arena on (onnxruntime default)', 'm');
  b += RECT(x0 + 290, 10, 12, 12, 'bar-w') + T(x0 + 308, 20, 'arena off', 'm');
  return wrap('fig-mem', 880, 284, 'Speech process private memory: arena on 992, 1,132, 1,131, 1,660 MB; arena off 984, 989, 988, 989 MB', b, 640);
}

// Figure 8.1 ------------------------------------------------------------------------------------
export function figBlocks() {
  let b = '';
  const ins = [
    ['Keyboard', 'hotkeys', false], ['Microphone', 'your voice', true], ['System audio', 'WASAPI loopback', true],
    ['Mic + camera use', 'any VC app', false], ['Outlook (classic)', 'COM: mail, calendar', false],
    ['Git repos', '27 under New folder', false], ['Foreground window', 'title + idle time', false], ['Selection', 'copied on hotkey', false],
  ];
  ins.forEach(([t, s, audio], i) => {
    const y = 40 + i * 52;
    b += LBOX(0, y, 160, 42, t, [s], { cls: audio ? 'bx-s' : 'bx', ty: 17, gap: 16, pad: 10 });
    b += ARR([[160, y + 21], [198, y + 21]], audio ? 'ln-s' : 'ln');
  });
  // core
  b += RECT(200, 14, 420, 476, 'rg') + T(212, 33, 'mwb-core · always on · 36 MB private, measured', 'm b');
  const cell = (x, y, t, lines, cls = 'bx', h = 54) => LBOX(x, y, 124, h, t, lines, { cls, ty: 20, gap: 16, pad: 10 });
  b += cell(216, 48, 'Hotkeys', ['RegisterHotKey']) + cell(350, 48, 'Tray + toasts', ['state, consent']) + cell(484, 48, 'Event bus', ['in-process']);
  b += cell(216, 114, 'Audio capture', ['mic · loopback', 'VAD, pre-roll'], 'bx-s', 64) + cell(350, 114, 'Sensors', ['meeting detector', 'activity sampler'], 'bx', 64) + cell(484, 114, 'Collectors', ['git', 'Outlook COM'], 'bx', 64);
  b += RECT(216, 190, 392, 116, 'bx-w') + T(228, 210, 'Skills', 'h');
  ['Dictate', 'Rewrite by voice', 'Email', 'Code', 'Meeting notes', 'Daily journal'].forEach((s, i) => {
    const x = 228 + (i % 3) * 126, y = 222 + Math.floor(i / 3) * 40;
    b += RECT(x, y, 116, 32, 'bx') + T(x + 58, y + 20.5, s, 's', 'middle');
  });
  b += cell(216, 318, 'Scheduler', ['priorities', 'power, CPU'], 'bx', 66) + cell(350, 318, 'Model manager', ['profiles, effort', 'memory guard'], 'bx-c', 66) + cell(484, 318, 'LLM router', ['API first', 'local fallback'], 'bx', 66);
  b += LBOX(216, 398, 392, 76, 'Storage', ['SQLite (WAL, FTS5) · journal/*.md', 'temporary audio, deleted after transcription'], { cls: 'bx', ty: 20, gap: 17, pad: 10 });
  // workers
  b += RECT(670, 14, 210, 300, 'rg-d') + T(682, 33, 'workers · on demand', 'm b');
  // Rev G: meetings use whisper-cli once per piece, a process of its own, instead of the speech worker
  b += LBOX(682, 44, 186, 66, 'Speech worker', ['Parakeet int8 · dictation', '~1.0 GB · measured'], { cls: 'bx-c', ty: 20, gap: 16, pad: 10 });
  b += LBOX(682, 116, 186, 66, 'whisper-cli, per piece', ['whisper small · meetings', '0.79 GB peak · measured'], { cls: 'bx-c', ty: 20, gap: 16, pad: 10 });
  b += LBOX(682, 188, 186, 66, 'Language worker', ['llama-server · fallback', '1.3–2.4 GB · measured'], { cls: 'bx-c', ty: 20, gap: 16, pad: 10 });
  b += LBOX(682, 260, 186, 44, 'Diarizer (later)', ['Sortformer · ONNX'], { cls: 'bx-w', ty: 20, gap: 16, pad: 10 });
  b += RECT(670, 328, 210, 56, 'rg-d') + T(682, 351, 'Cloud LLM (default)', 'h') + T(682, 368, 'Groq · text only', 'm mid');
  // core <-> workers
  b += ARR([[620, 92], [668, 92]], 'ln-c') + ARR([[668, 104], [620, 104]], 'ln-c') + T(644, 84, 'HTTP', 'm dim', 'middle');
  b += ARR([[620, 356], [668, 356]], 'ln') + T(644, 348, 'HTTPS', 'm dim', 'middle');
  // outputs
  b += T(682, 418, 'outputs', 'm b');
  const outs = ['Text at cursor', 'Result panel (email, code)', 'Today page (on demand)', 'Outlook drafts (never sent)'];
  b += LINE(620, 470, 646, 470, 'ln') + LINE(646, 447, 646, 573, 'ln');
  outs.forEach((o, i) => { const y = 430 + i * 42; b += ARR([[646, y + 17], [668, y + 17]], 'ln') + RECT(670, y, 210, 34, 'bx') + T(682, y + 21.5, o, 's'); });
  return wrap('fig-blocks', 880, 600, 'Functional block diagram: inputs on the left, the always-on core in the middle, on-demand workers and outputs on the right', b, 760);
}

// Figure 9.1 ------------------------------------------------------------------------------------
export function figDict() {
  const x0 = 140, x1 = 860, tmax = 8, sx = (t) => x0 + (t / tmax) * (x1 - x0);
  const lane = { keys: 36, mic: 80, seg: 124, asr: 168, out: 212, cold: 276 }, lh = 26;
  let b = '';
  [['Keys', lane.keys], ['Microphone', lane.mic], ['Speech segments', lane.seg], ['Speech worker', lane.asr], ['Output', lane.out], ['Cold start', lane.cold]]
    .forEach(([t, y]) => { b += T(0, y + 17, t, 'h'); });
  b += T(sx(0), 22, 'key down', 'm dim', 'middle') + T(sx(6), 22, 'release', 'm dim', 'middle');
  b += LINE(sx(6), 28, sx(6), 246, 'ln-d');
  b += RECT(sx(0), lane.keys, sx(6) - sx(0), lh, 'bx-c') + T(sx(3), lane.keys + 17, 'push-to-talk held (Ctrl+Alt+Space, or Ctrl+Shift+Alt+Space)', 'm', 'middle');
  b += RECT(sx(0), lane.mic, sx(6) - sx(0), lh, 'bx-s') + T(sx(3), lane.mic + 17, 'mic open at its own rate (48 kHz here), pre-roll keeps the first sound', 'm', 'middle');
  b += RECT(sx(0.3), lane.seg, sx(3.2) - sx(0.3), lh, 'bx') + T((sx(0.3) + sx(3.2)) / 2, lane.seg + 17, 'segment 1 · 2.9 s', 'm', 'middle');
  b += T((sx(3.2) + sx(3.9)) / 2, lane.seg + 17, 'pause', 'm dim', 'middle');
  b += RECT(sx(3.9), lane.seg, sx(6) - sx(3.9), lh, 'bx') + T((sx(3.9) + sx(6)) / 2, lane.seg + 17, 'segment 2 · 2.1 s', 'm', 'middle');
  b += ARR([[sx(3.7), lane.seg + lh], [sx(3.7), lane.asr]], 'ln');
  b += ARR([[sx(6.0) + 4, lane.seg + lh], [sx(6.0) + 4, lane.asr]], 'ln');
  b += RECT(sx(3.7), lane.asr, 0.66 * 90, lh, 'bx-c') + T(sx(3.7) + 0.33 * 90, lane.asr + 17, '0.66 s', 'm tc b', 'middle');
  b += RECT(sx(6.0), lane.asr, 0.6 * 90, lh, 'bx-c') + T(sx(6.0) + 0.3 * 90, lane.asr + 17, '0.6 s', 'm tc b', 'middle');
  const tOut = 6.65;
  b += RECT(sx(6.6), lane.out, sx(tOut) - sx(6.6) + 2, lh, 'bx-s');
  b += T(sx(6.6) - 8, lane.out + 17, 'clean-up rules + paste, text appears', 'm', 'end');
  b += LINE(sx(6), 252, sx(tOut), 252, 'ln-s') + LINE(sx(6), 247, sx(6), 257, 'ln-s') + LINE(sx(tOut), 247, sx(tOut), 257, 'ln-s');
  b += T((sx(6) + sx(tOut)) / 2, 268, '≈ 0.65 s after release', 'h ts', 'middle');
  b += RECT(sx(0), lane.cold, 7.5 * 90, lh, 'rg-d') + T(sx(0) + 10, lane.cold + 17, 'if cold: model load starts at key down (7.5 s with memory free, 17–40 s when tight)', 'm mid');
  b += LINE(x0, 314, x1, 314, 'axis');
  for (let t = 0; t <= tmax; t++) b += LINE(sx(t), 314, sx(t), 319, 'axis') + T(sx(t), 333, `${t} s`, 'm dim', 'middle');
  return wrap('fig-dict', 880, 340, 'Dictation timeline: segment 1 is transcribed while speaking, about 0.65 seconds from release to text', b, 700);
}

// Figure 9.2 ------------------------------------------------------------------------------------
export function figMtg() {
  const x0 = 118, slot = (880 - x0) / 5, bw = slot - 16;
  const row = (y, items) => items.map(([t, l1, l2, cls], i) => {
    const x = x0 + i * slot;
    let s = LBOX(x, y, bw, 72, t, [l1, l2], { cls, ty: 22, gap: 17, lh: 15, pad: 11 });
    if (i < items.length - 1) s += ARR([[x + bw, y + 36], [x + slot, y + 36]], 'ln');
    return s;
  }).join('');
  let b = '';
  b += TL(0, 70, ['DURING', 'THE CALL'], 'm b mid');
  b += row(40, [
    ['Detect', 'any VC app on mic', '+ calendar match', 'bx'],
    ['Record 2 lanes', 'You = microphone', 'Them = loopback', 'bx-s'],
    // Rev G: whisper small through whisper-cli, in 22-28 s pieces (whisper always works on a 30 s window)
    ['Pieces', '22–28 s each', 'WAV, temporary', 'bx'],
    ['Transcribe', 'whisper small', '2 thr · low prio', 'bx-c'],
    ['Store', 'segments + times', 'SQLite, FTS5', 'bx'],
  ]);
  b += T(x0 + 4, 134, 'Live only on mains power with a calm CPU; otherwise pieces wait on disk until the call ends', 'm dim');
  const xl = x0 + 4 * slot + bw / 2, xf = x0 + bw / 2;
  b += ARR([[xl, 112], [xl, 160], [xf, 160], [xf, 198]], 'ln');
  b += TL(0, 230, ['AFTER', 'THE CALL'], 'm b mid');
  b += row(200, [
    ['Merge', 'You + Them lanes', 'echo removed', 'bx'],
    ['Map', 'notes for each', '10-min chunk', 'bx-c'],
    ['Reduce', 'summary + actions', 'decisions, owners', 'bx-c'],
    ['Classify', 'Work / Timepass', 'see §10', 'bx-a'],
    ['Notify', 'notice + Today', 'feeds the journal', 'bx'],
  ]);
  return wrap('fig-mtg', 880, 284, 'Meeting pipeline: detect, record two lanes, cut pieces, transcribe with whisper small, store during the call; merge, map, reduce, classify, notify after it', b, 720);
}

// Figure 9.3 ------------------------------------------------------------------------------------
export function figJnl() {
  let b = '';
  ['Git commits', 'Meeting notes', 'Outlook mail', 'Dictation + notes', 'Active window', 'Calendar'].forEach((c, i) => {
    const y = 22 + i * 44;
    b += RECT(0, y, 150, 34, 'bx') + T(12, y + 21.5, c, 's') + LINE(150, y + 17, 172, y + 17, 'ln');
  });
  b += LINE(172, 39, 172, 259, 'ln') + ARR([[172, 150], [198, 150]], 'ln');
  b += LBOX(200, 104, 130, 92, 'Event store', ['SQLite timeline', 'one row per fact'], { cls: 'bx-w' });
  b += LINE(330, 150, 352, 150, 'ln') + LINE(352, 92, 352, 214, 'ln');
  b += ARR([[352, 92], [374, 92]], 'ln') + LBOX(376, 52, 178, 80, 'Facts, by code', ['commit table, SHAs,', 'durations, counts'], {});
  b += ARR([[352, 214], [374, 214]], 'ln-c') + LBOX(376, 174, 178, 80, 'Narrative, by LLM', ['summary, per project,', 'blockers, tomorrow'], { cls: 'bx-c' });
  b += LINE(554, 92, 576, 92, 'ln') + LINE(554, 214, 576, 214, 'ln') + LINE(576, 92, 576, 214, 'ln');
  b += ARR([[576, 153], [596, 153]], 'ln') + LBOX(598, 104, 140, 98, 'Validator', ['every sentence', 'cites an event;', 'SHAs re-checked'], {});
  b += LINE(738, 153, 758, 153, 'ln') + LINE(758, 86, 758, 220, 'ln');
  ['journal .md', 'Today page', 'Outlook draft'].forEach((o, i) => {
    const y = 69 + i * 67;
    b += ARR([[758, y + 17], [778, y + 17]], 'ln') + RECT(780, y, 100, 34, 'bx') + T(790, y + 21.5, o, 's');
  });
  return wrap('fig-jnl', 880, 292, 'Journal pipeline: six collectors feed the event store; facts by code and narrative by the model pass a validator before output', b, 720);
}

// Figure 10.1 -----------------------------------------------------------------------------------
export function figCls() {
  let b = '';
  b += LBOX(0, 30, 200, 140, 'A · Metadata rules', ['title keywords', 'organizer, attendees', 'client domains', 'Outlook category', 'series history'], { lh: 15 });
  b += T(12, 160, 'output: score −1 … +1', 'm tc');
  b += ARR([[200, 100], [236, 100]], 'ln');
  b += '<polygon points="238,100 290,60 342,100 290,140" class="bx"/>' + T(290, 97, '|score|', 'm', 'middle') + T(290, 112, '≥ 0.6 ?', 'm', 'middle');
  b += ARR([[342, 100], [658, 100]], 'ln') + T(356, 92, 'yes: label from rules, instantly', 'm dim');
  b += LBOX(660, 56, 220, 88, 'Label + reason', ['Work · planning · 0.86', 'work 38 min · timepass 7'], { cls: 'bx-a' });
  b += ARR([[290, 140], [290, 188]], 'ln') + T(298, 168, 'no', 'm dim');
  b += LBOX(170, 190, 240, 90, 'B · Transcript check (LLM)', ['tags each 10-min chunk', 'JSON: label, confidence,', 'evidence quotes'], { cls: 'bx-c' });
  b += ARR([[410, 235], [600, 235], [600, 125], [658, 125]], 'ln-c');
  b += LBOX(660, 196, 220, 92, 'C · Your correction', ['one click in Today', 'remembers the series', 'adds few-shot examples'], {});
  b += ARR([[770, 144], [770, 194]], 'ln') + T(778, 173, 'you fix it', 'm dim');
  b += ARR([[770, 288], [770, 312], [100, 312], [100, 172]], 'ln-d');
  b += T(435, 304, 'corrections update the rules and the prompt examples', 'm dim', 'middle');
  return wrap('fig-cls', 880, 324, 'Classification cascade: metadata rules, then a transcript check by the language model when unsure, with user corrections feeding back', b, 720);
}

// Figure 11.1 -----------------------------------------------------------------------------------
export function figLife() {
  const st = (x, y, w, t, s, cls = 'bx') => RECT(x, y, w, 52, cls, 26) + T(x + w / 2, y + 22, t, 'h', 'middle') + T(x + w / 2, y + 39, s, 'm mid', 'middle');
  let b = '';
  b += st(0, 60, 150, 'Cold', '0 MB · no process', 'bx-w');
  b += st(220, 60, 170, 'Loading', '7.5–12 s, measured');
  b += st(460, 60, 170, 'Warm', '~1.0 GB · ready', 'bx-c');
  b += st(700, 60, 180, 'Busy', 'transcribing', 'bx-c');
  b += st(460, 172, 170, 'Exit', 'memory returned', 'bx-s');
  b += ARR([[150, 86], [218, 86]], 'ln') + T(184, 48, 'hotkey down', 'm dim', 'middle');
  b += ARR([[390, 86], [458, 86]], 'ln') + T(424, 48, 'port open', 'm dim', 'middle');
  b += ARR([[630, 78], [698, 78]], 'ln-c') + T(664, 48, 'request', 'm dim', 'middle');
  b += ARR([[698, 96], [632, 96]], 'ln-c') + T(665, 116, 'done', 'm dim', 'middle');
  b += ARR([[545, 112], [545, 170]], 'ln') + TL(556, 137, ['idle 15 min, job done', 'or memory low'], 'm dim');
  b += ARR([[460, 198], [75, 198], [75, 114]], 'ln-s') + T(268, 216, 'process ends, Windows gets the RAM back', 'm dim', 'middle');
  return wrap('fig-life', 880, 232, 'Worker lifecycle: cold, loading, warm, busy, and exit back to cold', b, 700);
}

// Figure 11.2 -----------------------------------------------------------------------------------
// [start, end, GB on the API route, GB if the API is down all day: Qwen3.5 2B for notes and email, 4B for the journal]
export const DAY = [
  ['09:00', '09:30', 0.04, 0.04], ['09:30', '09:45', 1.03, 1.03], ['09:45', '09:49', 0.04, 1.29], ['09:49', '10:05', 0.04, 0.04],
  ['10:05', '10:40', 1.17, 1.17], ['10:40', '11:20', 0.04, 0.04], ['11:20', '11:50', 1.17, 1.17], ['11:50', '11:52', 1.17, 2.42],
  ['11:52', '12:05', 1.17, 1.17], ['12:05', '14:00', 0.04, 0.04], ['14:00', '15:00', 1.03, 1.03], ['15:00', '15:04', 0.04, 1.29],
  ['15:04', '16:10', 0.04, 0.04], ['16:10', '16:40', 1.17, 1.17], ['16:40', '17:30', 0.04, 0.04], ['17:30', '17:45', 1.03, 1.03],
  ['17:45', '17:48', 0.04, 1.29], ['17:48', '18:30', 0.04, 0.04], ['18:30', '18:34', 0.04, 2.46], ['18:34', '19:00', 0.04, 0.04],
];
const hm = (s) => { const [h, m] = s.split(':').map(Number); return h * 60 + m; };
export function dayStats(route = 'api', wispr = 1.54) {
  const k = route === 'local' ? 3 : 2;
  const total = hm('19:00') - hm('09:00');
  const avg = DAY.reduce((s, d) => s + (hm(d[1]) - hm(d[0])) * d[k], 0) / total;
  const above = DAY.reduce((s, d) => s + (d[k] > wispr ? hm(d[1]) - hm(d[0]) : 0), 0);
  const peak = Math.max(...DAY.map((d) => d[k]));
  return { avg, above, total, peak };
}
export function figDay() {
  const x0 = 56, x1 = 852, yb = 262, yt = 36, gmax = 3.5, t0 = hm('09:00'), t1 = hm('19:00');
  const sx = (m) => x0 + ((m - t0) / (t1 - t0)) * (x1 - x0), sy = (g) => yb - (g / gmax) * (yb - yt);
  const api = dayStats('api'), loc = dayStats('local');
  const steps = (k) => DAY.map((d) => ` L${f(sx(hm(d[0])))},${f(sy(d[k]))} L${f(sx(hm(d[1])))},${f(sy(d[k]))}`).join('');
  let b = '';
  for (let g = 0; g <= 3; g++) b += LINE(x0, sy(g), x1, sy(g), g ? 'grid' : 'axis') + T(x0 - 8, sy(g) + 4, `${g} GB`, 'm dim', 'end');
  for (let h = 9; h <= 19; h++) { const x = sx(h * 60); b += LINE(x, yb, x, yb + 5, 'axis') + T(x, yb + 19, `${String(h).padStart(2, '0')}:00`, 'm dim', 'middle'); }
  // The dashed local-fallback line goes first, so the API area hides it wherever the two are equal.
  b += `<path d="M${f(sx(t0))},${f(sy(DAY[0][3]))}${steps(3)}" class="ln-d"/>`;
  b += `<path d="M${f(sx(t0))},${f(yb)}${steps(2)} L${f(sx(t1))},${f(yb)} Z" class="area-c"/>`;
  // Labels sit where no line crosses them: 12:10-14:00 is flat. The local peak is labelled beside its own spike.
  b += LINE(x0, sy(1.54), x1, sy(1.54), 'ln-s dash') + T(sx(hm('12:10')), sy(1.54) - 7, 'Wispr Flow · 1.54 GB', 'm ts');
  const top = DAY.reduce((a, d) => (d[3] > a[3] ? d : a));
  const onRight = sx(hm(top[1])) < 600;
  b += T(onRight ? sx(hm(top[1])) + 6 : sx(hm(top[0])) - 6, sy(top[3]) + 12, `local fallback peak · ${top[3].toFixed(2)} GB`, 'm', onRight ? 'start' : 'end');
  b += T(sx(hm('15:00')) - 6, sy(1.03) - 8, 'meeting · 1.03 GB', 'm', 'end');
  b += T(sx(hm('16:25')), sy(1.17) - 8, 'dictation · 1.17 GB', 'm', 'middle');
  b += RECT(x0 + 4, 7, 12, 12, 'area-c') + T(x0 + 22, 17, 'API route: speech worker only', 'm');
  b += LINE(x0 + 4, 33, x0 + 16, 33, 'ln-d') + T(x0 + 22, 37, 'API down: local Qwen3.5', 'm');
  b += T(x1, 17, `API route: average ${api.avg.toFixed(2)} GB, peak ${api.peak.toFixed(2)} GB`, 'h tc', 'end');
  b += T(x1, 37, `local: average ${loc.avg.toFixed(2)} GB, ${loc.above} min above Wispr`, 'm mid', 'end');
  return wrap('fig-day', 880, 290, `Modelled day: on the API route MWB averages ${api.avg.toFixed(2)} GB against Wispr Flow's constant 1.54 GB`, b, 700);
}

// Figure 12.1 -----------------------------------------------------------------------------------
export function figTiers() {
  const base = 300, w = 208, gap = 16;
  const tiers = [
    ['Lean', 'this EliteBook today', ['16 GB · 1 channel · CPU', 'speech: Parakeet on CPU', 'LLM: API first, for now', 'local 2B: 10.3 tok/s'], 140, 'bx-c'],
    ['Balanced', '+ one 16 GB stick', ['32 GB · 2 channels · CPU', 'LLM 4B warm all day', 'diarization on', 'LLM speed ≈ 12 tok/s (4B)'], 175, 'bx'],
    ['Performance', 'next laptop', ['32–64 GB + 8–16 GB GPU', 'speech on GPU, live text', 'LLM 9B · coder MoE', 'LLM speed 40–80 tok/s'], 210, 'bx'],
    ['Workstation', 'desk machine', ['64 GB+ · 24 GB+ VRAM', '26–31B class models', 'search months of notes', 'LLM speed 100+ tok/s'], 245, 'bx'],
  ];
  let b = '';
  tiers.forEach(([t, sub, lines, h, cls], i) => {
    const x = i * (w + gap), y = base - h;
    b += RECT(x, y, w, h, cls) + T(x + 14, y + 27, t, 'h big') + T(x + 14, y + 45, sub, 'm mid') + TL(x + 14, y + 70, lines, 's', 'start', 17);
  });
  b += T(14, base - 140 - 12, 'YOU ARE HERE', 'm tc b');
  return wrap('fig-tiers', 880, 304, 'Four hardware profiles from Lean to Workstation', b, 700);
}

// Figure 13.1 -----------------------------------------------------------------------------------
export function figKeys() {
  const k = 52, gap = 6;
  const fn = { W: 'start', E: 'email', R: 'rewrite', P: 'pause', J: 'today', K: 'code', N: 'note', M: 'meeting' };
  const rows = [
    [20, [['Tab', 80], ...'QWERTYUIOP'.split('').map((c) => [c, k]), ['[', k], [']', k], ['\\', 80]]],
    [78, [['Caps', 96], ...'ASDFGHJKL'.split('').map((c) => [c, k]), [';', k], ["'", k], ['Enter', 122]]],
    [136, [['Shift', 124], ...'ZXCVBNM'.split('').map((c) => [c, k]), [',', k], ['.', k], ['/', k], ['Shift', 152]]],
    [194, [['Ctrl*', 70], ['Win', 60], ['Alt*', 70], ['Space', 330], ['Alt', 70], ['Fn', 60], ['Ctrl', 70]]],
  ];
  let b = '';
  rows.forEach(([y, keys]) => {
    let x = 0;
    keys.forEach(([lab, w]) => {
      const mod = lab.endsWith('*'), name = mod ? lab.slice(0, -1) : lab;
      if (name === 'Caps') {
        // Rev D: double-tap Caps Lock = talk (write or ask)
        b += RECT(x, y, w, k, 'key-s') + T(x + 8, y + 21, 'Caps Lock', 'm ts b') + T(x + 8, y + 42, '2×: talk / ask', 'm k10 ts');
      } else if (name === 'Alt' && !mod) {
        // Rev D: double-tap Alt = show or hide the indicator (either Alt works)
        b += RECT(x, y, w, k, 'key-hl') + T(x + 8, y + 21, 'Alt', 'm tc b') + T(x + 8, y + 41, '2×: icon', 'm k10 tc');
      } else if (name === 'Space') {
        b += RECT(x, y, w, k, 'key-hl') + T(x + w / 2, y + 22, 'Space', 'm tc b', 'middle') + T(x + w / 2, y + 40, 'with Ctrl+Alt held: push-to-talk', 'm tc', 'middle');
      } else if (mod) {
        b += RECT(x, y, w, k, 'key-hl') + T(x + 8, y + 21, name, 'm tc b') + T(x + 8, y + 41, 'held', 'm k10 tc');
      } else if (fn[name]) {
        b += RECT(x, y, w, k, 'key-hl') + T(x + 7, y + 21, name, 'm tc b') + T(x + 6, y + 42, fn[name], 'm k10 tc');
      } else {
        b += RECT(x, y, w, k, 'key') + T(x + 8, y + 21, name, 'm dim');
      }
      x += w + gap;
    });
  });
  return wrap('fig-keys', 880, 252, 'Keyboard map: Ctrl and Alt held with Space to dictate, and W, E, R, P, J, K, N, M for the other actions', b, 700);
}

// Figure 13.2 -----------------------------------------------------------------------------------
export function figTray() {
  const slot = 880 / 6, cy = 32;
  const icons = [
    ['Idle', 'nothing loaded', (cx) => `<circle cx="${f(cx)}" cy="${cy}" r="12" class="ring"/>`],
    ['Listening', 'dictation running', (cx) => `<circle cx="${f(cx)}" cy="${cy}" r="13" class="dot-c"/>` + [-5, 0, 5].map((d, i) => RECT(cx + d - 1.5, cy - [4, 7, 4][i], 3, [8, 14, 8][i], 'knock')).join('')],
    ['Recording', 'meeting capture on', (cx) => `<circle cx="${f(cx)}" cy="${cy}" r="14" class="ring-s"/><circle cx="${f(cx)}" cy="${cy}" r="7" class="dot-s"/>`],
    ['Working', 'notes or journal', (cx) => [-10, 0, 10].map((d) => `<circle cx="${f(cx + d)}" cy="${cy}" r="4" class="dot-a"/>`).join('')],
    ['Paused', 'mic + sensors off', (cx) => `<circle cx="${f(cx)}" cy="${cy}" r="13" class="dot-g"/>` + RECT(cx - 5, cy - 6, 3.5, 12, 'knock') + RECT(cx + 1.5, cy - 6, 3.5, 12, 'knock')],
    ['Needs you', 'error or consent', (cx) => `<polygon points="${f(cx)},${cy - 14} ${f(cx + 14)},${cy + 11} ${f(cx - 14)},${cy + 11}" class="ring-s"/>` + T(cx, cy + 8, '!', 'h ts', 'middle')],
  ];
  let b = '';
  icons.forEach(([t, s, draw], i) => {
    const cx = slot * i + slot / 2;
    b += draw(cx) + T(cx, 74, t, 'h', 'middle') + T(cx, 92, s, 'm mid', 'middle');
  });
  return wrap('fig-tray', 880, 102, 'Tray states: idle, listening, recording, working, paused, needs you', b, 640);
}

// Figure 14.1 -----------------------------------------------------------------------------------
export function figEr() {
  const cw = 270;
  const tbl = (x, y, name, fields, cls = 'bx') => {
    let s = RECT(x, y, cw, 28 + fields.length * 15 + 10, cls) + RECT(x, y, cw, 28, 'er-h') + T(x + 10, y + 19, name, 'h');
    fields.forEach((fl, i) => { s += T(x + 10, y + 44 + i * 15, fl, fl.includes('→') ? 'm tc' : 'm'); });
    return s;
  };
  const rowY = (y, i) => y + 40 + i * 15; // vertical centre of field row i
  // Rev G: the tables as built in Phases 1 to 3 (mwb/store/schema.sql); the journal's tables follow in Phase 4.
  let b = '';
  b += tbl(0, 0, 'segments', ['id', 'meeting_id → meetings', 'speaker  You | Them | name', 'start_s, end_s', 'text  (FTS5 search)']);
  b += tbl(0, 130, 'action_items', ['id', 'meeting_id → meetings', 'owner  You | name', 'what', 'due_text  as said', 'due_date  worked out by code', 'done']);
  b += tbl(0, 290, 'meeting_labels', ['meeting_id → meetings', 'label, subtype, confidence', 'work_min, timepass_min', 'reasons', 'stage  A | B | C', 'model_label, series']);
  b += tbl(305, 0, 'meetings', ['id', 'app_id, app_name', 'title', 'started, ended', 'status  recording | … | ready', 'source  recorded | imported', 'language', 'pieces, pieces_done', 'camera'], 'bx-c');
  b += tbl(305, 205, 'meeting_notes', ['meeting_id → meetings', 'status  waiting | ready | failed', 'summary, decisions', 'chunks  10-minute parts', 'route, model']);
  b += tbl(610, 0, 'dictations', ['id', 'ts, app  (never the title)', 'raw_text, final_text  (FTS5)', 'latency_ms, audio_s, pieces', 'trigger, inserted_by']);
  b += tbl(610, 130, 'app_policy', ['app_id', 'policy  record | ask | never', 'decided']);
  b += tbl(610, 230, 'api_log', ['id, ts, skill', 'route  api | local, model', 'chars_in, chars_out  (sizes only)', 'seconds, ok']);
  // foreign keys into meetings.id
  const mId = rowY(0, 0);
  [rowY(0, 1), rowY(130, 1), rowY(290, 0)].forEach((y) => { b += LINE(270, y, 287, y, 'ln-c'); });
  b += LINE(287, mId, 287, rowY(290, 0), 'ln-c') + ARR([[287, mId], [303, mId]], 'ln-c');
  b += ARR([[440, 205], [440, 175]], 'ln-c');
  // Phase 4, not built yet
  b += T(0, 438, 'Phase 4 adds the journal\'s tables (not built yet):', 'm b');
  b += tbl(0, 448, 'events', ['ts_start, ts_end, kind', 'ref_id → meetings | …', 'project_id → projects'], 'bx-w');
  b += tbl(305, 448, 'commits · activity · emails', ['sha, repo, branch, ts, message', 'app, window title, idle', 'subject, counterpart'], 'bx-w');
  b += tbl(610, 448, 'journal · projects', ['date, facts_json', 'narrative_md, edited_md', 'repo_paths, title_patterns'], 'bx-w');
  return wrap('fig-er', 880, 540, 'Entity relationship diagram of the MWB database as built in Phases 1 to 3, with the Phase 4 tables below', b, 760);
}

// Figure 17.1 -----------------------------------------------------------------------------------
export function figPlan() {
  // Rev B: P2 +2 days (every VC app), P5 +2 days (effort governor, re-tune on another laptop).
  // Rev C: P5 +1 day (setup screen where the user chooses the effort level).
  // Rev D: P1 +1 (double-tap Caps, indicator), P3 +1 (answer mode), P5 +1 (skins and indicator settings).
  const x0 = 222, x1 = 840, dmax = 48, sx = (d) => x0 + (d / dmax) * (x1 - x0);
  const rows = [
    // Rev G: status on 16 Oct. P1 to P3 were built on 14 Oct; their checks with real use are still open.
    ['P0', 'Spikes & calibration', 0, 3, 'measure before building · 4 of 8 tests finished'],
    ['P1', 'Dictation MVP', 3, 11, 'M1 · Wispr Flow can be switched off · built 14 Oct'],
    ['P2', 'Meeting capture', 11, 20, 'M2 · auto-recorded calls in any VC app · built 14 Oct'],
    ['P3', 'Understanding', 20, 30, 'M3 · notes, labels, answers, email, code · built 14 Oct'],
    ['P4', 'Daily journal', 30, 37, 'M4 · first automatic journal'],
    ['P5', 'Profiles & effort', 37, 48, 'M5 · POC sign-off'],
  ];
  const top = 32, rh = 42, bottom = top + rows.length * rh;
  let b = '';
  for (let w = 0; w <= 6; w++) {
    const x = sx(w * 7);
    b += LINE(x, top - 6, x, bottom, 'grid');
    const xe = sx(Math.min((w + 1) * 7, dmax));
    b += T((x + xe) / 2, top - 12, `W${w + 1}`, 'm dim', 'middle');
  }
  b += LINE(sx(dmax), top - 6, sx(dmax), bottom, 'grid');
  rows.forEach(([id, name, a, z, ms], i) => {
    const y = top + i * rh;
    b += T(0, y + 17, `${id} · ${name}`, 'h') + T(0, y + 32, `${z - a} days`, 'm dim');
    b += RECT(sx(a), y + 6, sx(z) - sx(a), 16, i === 0 ? 'bx-w' : 'bar-c');
    if (i > 0) b += `<polygon points="${f(sx(z))},${y + 6} ${f(sx(z) + 8)},${y + 14} ${f(sx(z))},${y + 22} ${f(sx(z) - 8)},${y + 14}" class="mk-s"/>`;
    b += T(sx(a), y + 37, ms, 'm mid');
  });
  b += LINE(x0, bottom + 4, x1, bottom + 4, 'axis');
  [0, 7, 14, 21, 28, 35, 42].forEach((d) => { b += LINE(sx(d), bottom + 4, sx(d), bottom + 9, 'axis') + T(sx(d), bottom + 23, `day ${d}`, 'm dim', 'middle'); });
  return wrap('fig-plan', 880, bottom + 30, 'Plan timeline: six phases over forty-eight days with five milestones', b, 700);
}

// Figure 12.2 -----------------------------------------------------------------------------------
export function figEffort() {
  let b = '';
  const ins = [['Hardware profile', 'sets the ceiling'], ['Power source', 'AC or battery %'], ['CPU load', '30 s average'], ['Free memory', 'right now'], ['Your choice', 'at setup or in Settings']];
  ins.forEach(([t, s], i) => {
    const y = 20 + i * 52;
    b += LBOX(0, y, 200, 40, t, [s], { ty: 17, gap: 15, i: 0 }) + LINE(200, y + 20, 222, y + 20, 'ln');
  });
  b += LINE(222, 40, 222, 248, 'ln') + ARR([[222, 144], [244, 144]], 'ln');
  b += LBOX(246, 99, 180, 90, 'Effort governor', ['picks E1 to E4', 're-checks every 30 s', 'and on any change'], { cls: 'bx-c' });
  b += ARR([[426, 144], [450, 144]], 'ln-c');
  b += RECT(452, 70, 120, 140, 'rg-d');
  [['E4 · max', 'bx'], ['E3 · high', 'bx'], ['E2 · normal', 'bx-c'], ['E1 · low', 'bx']].forEach(([t, cls], i) => {
    const y = 78 + i * 32;
    b += RECT(462, y, 100, 26, cls) + T(512, y + 17, t, cls === 'bx-c' ? 'm tc b' : 'm', 'middle');
  });
  b += T(512, 230, 'Lean starts at E2', 'm dim', 'middle');
  const knobs = ['threads for speech and LLM', 'speech model, beam size', 'diarization on or off', 'language model size',
    'LLM passes: draft, check, polish', 'warm models or load on demand', 'live captions, rolling notes', 'night second pass (AC, idle)'];
  b += LINE(572, 144, 596, 144, 'ln') + LINE(596, 24, 596, 276, 'ln');
  knobs.forEach((k, i) => {
    const y = 10 + i * 36;
    b += ARR([[596, y + 14], [616, y + 14]], 'ln') + RECT(618, y, 262, 28, 'bx') + T(630, y + 18.5, k, 's');
  });
  return wrap('fig-effort', 880, 300, 'Effort governor: hardware, power, CPU load, free memory and your setting choose a level from E1 to E4, which sets eight knobs', b, 720);
}

// Figure 12.3 -----------------------------------------------------------------------------------
export function figMove() {
  let b = '';
  b += LBOX(0, 24, 150, 60, 'Start', ['read hardware', 'fingerprint'], { ty: 20, gap: 16 });
  b += ARR([[150, 54], [180, 54]], 'ln');
  b += '<polygon points="182,54 232,16 282,54 232,92" class="bx"/>' + T(232, 51, 'hardware', 'm', 'middle') + T(232, 66, 'changed?', 'm', 'middle');
  b += ARR([[282, 54], [560, 54]], 'ln') + T(296, 46, 'no: same machine as last time', 'm dim');
  b += LBOX(562, 24, 180, 60, 'Use saved settings', ['profile + effort', 'from last start'], { ty: 20, gap: 16 });
  b += ARR([[742, 54], [766, 54]], 'ln');
  b += LBOX(768, 24, 112, 60, 'Ready', ['same hotkeys'], { cls: 'bx-c', ty: 20, gap: 16 });
  b += ARR([[232, 92], [232, 122]], 'ln-c') + T(240, 112, 'yes: new laptop or upgrade', 'm dim');
  // Rev C: the user chooses the effort level in a setup screen before any model is fetched.
  b += LBOX(100, 124, 159, 64, 'Calibrate · ~60 s', ['speech + LLM speed', 'free memory, GPU'], { cls: 'bx-c', ty: 20, gap: 16 });
  b += ARR([[259, 156], [285, 156]], 'ln-c');
  b += LBOX(287, 124, 159, 64, 'Suggest', ['profile + effort', 'for this machine'], { cls: 'bx-c', ty: 20, gap: 16 });
  b += ARR([[446, 156], [472, 156]], 'ln-c');
  b += LBOX(474, 124, 159, 64, 'You choose', ['auto range or fixed', 'per feature, battery'], { cls: 'bx', tcls: 'h tc', ty: 20, gap: 16 });
  b += ARR([[633, 156], [659, 156]], 'ln-c');
  b += LBOX(661, 124, 159, 64, 'Fetch models', ['for your choice,', 'after you confirm'], { cls: 'bx-c', ty: 20, gap: 16 });
  b += ARR([[820, 156], [846, 156], [846, 86]], 'ln-c');
  return wrap('fig-move', 880, 196, 'First start on any laptop: same machine uses saved settings; a new machine is calibrated, MWB suggests a profile and effort, you choose, then it fetches models', b, 720);
}

// Figure 8.2 -----------------------------------------------------------------------------------
export function figLoop() {
  let b = '';
  [['Double-tap watch', 'Caps Lock + Alt only, every 15 ms'], ['Hotkeys', 'Ctrl+Alt+… through Windows'], ['Windows events', 'power, audio device, lock'], ['Tray icon', 'clicks and menu']]
    .forEach(([t, s], i) => {
      const y = 40 + i * 56;
      b += LBOX(0, y, 250, 44, t, [s], { ty: 18, gap: 16 }) + LINE(250, y + 22, 274, y + 22, 'ln');
    });
  b += LINE(274, 62, 274, 230, 'ln') + ARR([[274, 150], [298, 150]], 'ln');
  [['every 5 s', 'which app holds the mic?'], ['every 10 s', 'active window, idle time'], ['every 30 s', 'effort: power, CPU, memory'], ['at 18:30', 'write the journal'], ['after idle time', 'close speech / LLM workers']]
    .forEach(([t, s], i) => {
      const y = 30 + i * 50;
      b += LBOX(630, y, 250, 40, t, [s], { ty: 16, gap: 15 }) + LINE(606, y + 20, 630, y + 20, 'ln');
    });
  b += LINE(606, 50, 606, 250, 'ln') + ARR([[606, 150], [582, 150]], 'ln');
  b += RECT(300, 96, 280, 108, 'bx-c', 54) + T(440, 132, 'Core event loop', 'h big', 'middle')
    + T(440, 154, 'one thread, asleep until an', 'm mid', 'middle') + T(440, 169, 'event arrives or a timer fires', 'm mid', 'middle')
    + T(440, 189, 'idle CPU ≈ 0 %', 'm tc b', 'middle');
  b += LINE(440, 204, 440, 282, 'ln') + LINE(170, 282, 710, 282, 'ln');
  [['Workers', 'start or stop'], ['Indicator', 'and tray icon'], ['Notifications', 'when needed'], ['Database', 'SQLite writes']].forEach(([t, s], i) => {
    const x = 95 + i * 180;
    b += ARR([[x + 75, 282], [x + 75, 298]], 'ln') + LBOX(x, 300, 150, 44, t, [s], { ty: 18, gap: 16, a: 'middle' });
  });
  return wrap('fig-loop', 880, 352, 'The core event loop: key taps, hotkeys, Windows events and tray clicks wake it; timers run on the right; it starts workers and updates the indicator, notifications and database', b, 720);
}

// Figure 8.3 -----------------------------------------------------------------------------------
export function figTap() {
  let b = '';
  b += RECT(0, 95, 110, 50, 'bx-w', 25) + T(55, 116, 'Idle', 'h', 'middle') + T(55, 133, '~0 % CPU', 'm mid', 'middle');
  b += ARR([[110, 120], [158, 120]], 'ln-c') + T(134, 110, '2× Caps', 'm tc b', 'middle');
  b += LBOX(160, 85, 160, 70, 'Listening', ['mic on, worker warms', 'pieces transcribed'], { cls: 'bx-c' });
  b += ARR([[320, 120], [368, 120]], 'ln') + T(344, 76, '2× Caps or 2 s pause', 'm dim', 'middle');
  b += LBOX(370, 85, 140, 70, 'Finish', ['text in ~1 s', 'clean-up rules'], {});
  b += ARR([[510, 120], [544, 120]], 'ln');
  b += '<polygon points="546,120 600,74 654,120 600,166" class="bx"/>' + TL(600, 108, ['text box', 'focused, no', 'wake word?'], 'm', 'middle', 13);
  b += ARR([[654, 120], [676, 120], [676, 50], [698, 50]], 'ln') + T(681, 96, 'yes', 'm dim');
  b += LBOX(700, 20, 180, 60, 'Write', ['paste at the cursor', 'indicator shows done'], { tcls: 'h tc', ty: 20, gap: 16 });
  b += ARR([[600, 166], [600, 190], [698, 190]], 'ln') + T(608, 184, 'no', 'm dim');
  b += LBOX(700, 160, 180, 60, 'Answer', ['panel above the pill', 'API, or local fallback'], { tcls: 'h tc', ty: 20, gap: 16 });
  b += ARR([[790, 20], [790, 8], [55, 8], [55, 93]], 'ln-d') + T(420, 23, 'back to idle', 'm dim', 'middle');
  b += ARR([[790, 220], [790, 238], [55, 238], [55, 147]], 'ln-d') + T(420, 232, 'back to idle', 'm dim', 'middle');
  b += ARR([[240, 155], [240, 205], [90, 205], [90, 147]], 'ln-d') + T(165, 221, 'Esc: cancel', 'm dim', 'middle');
  return wrap('fig-tap', 880, 250, 'One round: double-tap Caps Lock to listen, finish with another double tap or a pause, then MWB writes at the cursor or answers in a panel above the indicator', b, 720);
}

// Figure 13.3 ----------------------------------------------------------------------------------
export function figSkins() {
  const states = ['Idle', 'Listening', 'Working', 'Done'];
  const x0 = 130, colW = (880 - x0) / 4, top = 30, rowH = 56;
  const cxs = states.map((_, i) => x0 + colW * i + colW / 2);
  const P = (d, cls) => `<path d="${d}" class="${cls}"/>`;
  const C = (x, y, r, cls) => `<circle cx="${f(x)}" cy="${f(y)}" r="${f(r)}" class="${cls}"/>`;
  const R = (x, y, w, h, rx, cls) => `<rect x="${f(x)}" y="${f(y)}" width="${f(w)}" height="${f(h)}" rx="${f(rx)}" class="${cls}"/>`;
  const check = (x, y, cls = 'o-ok') => `<polyline points="${f(x - 6)},${f(y)} ${f(x - 2)},${f(y + 4)} ${f(x + 6)},${f(y - 5)}" class="${cls} cap"/>`;
  const bars = (x, y, hs, w, gap, cls, ops) => {
    const total = hs.length * w + (hs.length - 1) * gap;
    return hs.map((h, i) => R(x - total / 2 + i * (w + gap), y - h / 2, w, h, w / 2, cls + (ops ? ` ${ops[i]}` : ''))).join('');
  };
  const sine = (x, y, w, a, cyc) => {
    let d = '';
    for (let i = 0; i <= 48; i++) { const t = i / 48; d += `${i ? 'L' : 'M'}${f(x - w / 2 + t * w)},${f(y + Math.sin(t * Math.PI * 2 * cyc) * a)} `; }
    return d.trim();
  };
  const arc = (x, y, r, a0, a1) => {
    const p = (a) => [x + r * Math.cos(a), y + r * Math.sin(a)];
    const [sx0, sy0] = p(a0), [ex, ey] = p(a1);
    return `M${f(sx0)},${f(sy0)} A${r},${r} 0 ${a1 - a0 > Math.PI ? 1 : 0} 1 ${f(ex)},${f(ey)}`;
  };
  const mic = (x, y, cls) => R(x - 5, y - 13, 10, 16, 5, cls)
    + P(`M${f(x - 9)},${f(y - 2)} A9,9 0 0 0 ${f(x + 9)},${f(y - 2)}`, cls)
    + P(`M${f(x)},${f(y + 7)} L${f(x)},${f(y + 11)} M${f(x - 5)},${f(y + 11)} L${f(x + 5)},${f(y + 11)}`, cls + ' cap');
  const sq = (x, y, cls, s = 5) => R(x - s / 2, y - s / 2, s, s, 0, cls);
  const dots3 = (x, y, cls) => [-12, 0, 12].map((d, i) => C(x + d, y, 3, `${cls} ${['op35', 'op65', ''][i]}`)).join('');
  const skins = [
    ['Capsule', 'default · like Wispr', [
      (x, y) => R(x - 28, y - 6, 56, 12, 6, 'o-i'),
      (x, y) => R(x - 55, y - 13, 110, 26, 13, 'o-c f-cw') + bars(x, y, [4, 8, 14, 10, 18, 12, 7, 11, 5], 3, 4, 'f-c'),
      (x, y) => R(x - 55, y - 13, 110, 26, 13, 'o-a f-aw') + dots3(x, y, 'f-a'),
      (x, y) => R(x - 40, y - 13, 80, 26, 13, 'o-ok') + check(x, y),
    ]],
    ['Dot', 'smallest', [
      (x, y) => C(x, y, 4, 'f-i'),
      (x, y) => C(x, y, 16, 'o-c op3') + C(x, y, 11, 'o-c op5') + C(x, y, 6, 'f-c'),
      (x, y) => C(x, y, 5, 'f-a') + P(arc(x, y, 12, -Math.PI / 2, Math.PI), 'o-a cap'),
      (x, y) => C(x, y, 11, 'o-ok') + check(x, y),
    ]],
    ['Bars', 'equalizer', [
      (x, y) => bars(x, y, [4, 4, 4, 4, 4], 4, 4, 'f-i'),
      (x, y) => bars(x, y, [10, 20, 28, 16, 8], 4, 4, 'f-c'),
      (x, y) => bars(x, y, [8, 12, 16, 12, 8], 4, 4, 'f-a', ['op35', 'op65', '', 'op65', 'op35']),
      (x, y) => bars(x - 10, y, [6, 6, 6, 6], 4, 4, 'f-ok') + check(x + 16, y),
    ]],
    ['Ring', 'progress ring', [
      (x, y) => C(x, y, 9, 'o-i'),
      (x, y) => C(x, y, 9, 'o-c') + P(arc(x, y, 14, -Math.PI / 2, Math.PI * 0.9), 'o-c cap'),
      (x, y) => C(x, y, 11, 'o-a op3') + P(arc(x, y, 11, -Math.PI / 2, 0), 'o-a cap'),
      (x, y) => C(x, y, 11, 'o-ok') + check(x, y),
    ]],
    ['Wave', 'voice line', [
      (x, y) => P(`M${f(x - 30)},${f(y)} L${f(x + 30)},${f(y)}`, 'o-i cap'),
      (x, y) => P(sine(x, y, 80, 8, 2), 'o-c cap'),
      (x, y) => P(sine(x, y, 80, 4, 3), 'o-a cap dash2'),
      (x, y) => P(`M${f(x - 30)},${f(y)} L${f(x - 8)},${f(y)}`, 'o-ok cap') + check(x, y),
    ]],
    ['Orb', 'soft glow', [
      (x, y) => C(x, y, 7, 'f-i op35') + C(x, y, 3.5, 'f-i'),
      (x, y) => C(x, y, 17, 'f-c op15') + C(x, y, 11, 'f-c op35') + C(x, y, 6, 'f-c'),
      (x, y) => C(x, y, 14, 'o-a op3') + C(x, y, 6, 'f-a') + C(x + 12, y - 7, 2.5, 'f-a'),
      (x, y) => C(x, y, 11, 'f-ok') + check(x, y, 'o-k'),
    ]],
    ['Mic', 'classic glyph', [
      (x, y) => mic(x, y, 'o-i'),
      (x, y) => mic(x, y, 'o-c') + R(x - 5, y - 13, 10, 16, 5, 'f-c') + bars(x - 22, y, [6, 12], 3, 3, 'f-c') + bars(x + 22, y, [12, 6], 3, 3, 'f-c'),
      (x, y) => mic(x - 10, y, 'o-a') + [6, 14, 22].map((d, i) => C(x + d, y, 2.5, `f-a ${['op35', 'op65', ''][i]}`)).join(''),
      (x, y) => mic(x - 10, y, 'o-ok') + check(x + 14, y),
    ]],
    ['Pixel', '8-bit blocks', [
      (x, y) => [-8, 0, 8].map((d) => sq(x + d, y, 'f-i')).join(''),
      (x, y) => [1, 3, 4, 2, 3, 1].map((h, j) => Array.from({ length: h }, (_, k) => sq(x - 17.5 + j * 7, y + 10 - k * 6, 'f-c')).join('')).join(''),
      (x, y) => [-15, -9, -3, 3, 9, 15].map((d, i) => sq(x + d, y, `f-a ${['op15', 'op35', 'op65', '', 'op65', 'op35'][i]}`)).join(''),
      (x, y) => [[-8, 0], [-4, 4], [0, 8], [4, 4], [8, 0], [12, -4], [16, -8]].map(([dx, dy]) => sq(x - 4 + dx, y - 1 + dy, 'f-ok', 4)).join(''),
    ]],
  ];
  let b = '';
  states.forEach((s, i) => { b += T(cxs[i], 17, s, 'm b mid', 'middle'); });
  b += LINE(0, top - 4, 880, top - 4, 'grid');
  skins.forEach(([name, sub, draws], i) => {
    const y = top + i * rowH, cy = y + rowH / 2;
    b += T(0, cy - 3, name, 'h') + T(0, cy + 13, sub, 'm dim');
    draws.forEach((d, j) => { b += d(cxs[j], cy); });
    b += LINE(0, y + rowH, 880, y + rowH, 'grid');
  });
  return wrap('fig-skins', 880, top + skins.length * rowH + 6, 'Eight indicator skins, each shown idle, listening, working and done', b, 720);
}

// Figure 13.4 ----------------------------------------------------------------------------------
// The result panel in the indicator's place. The pill and panel keep their real dark colours in both themes.
export function figPanel() {
  const R = (x, y, w, h, rx, cls) => `<rect x="${f(x)}" y="${f(y)}" width="${f(w)}" height="${f(h)}" rx="${f(rx)}" class="${cls}"/>`;
  const C = (x, y, r, cls) => `<circle cx="${f(x)}" cy="${f(y)}" r="${f(r)}" class="${cls}"/>`;
  const pill = (cx, cy, w, h) => R(cx - w / 2, cy - h / 2, w, h, h / 2, 'pnl');
  const frames = [
    ['1 · Working: three amber dots', (x, cy) => pill(x, cy, 110, 26) + [-12, 0, 12].map((d, i) => C(x + d, cy, 3, `f-ad ${['op35', 'op65', ''][i]}`)).join('')],
    ['2 · The panel rises out of the pill', (x, cy) => {
      const px = x - 120, py = 72, w = 240;
      let s = R(px, py, w, 164, 14, 'pnl') + T(px + 14, py + 24, 'Reply draft', 'pnl-t b') + T(px + w - 18, py + 24, '×', 'pnl-d', 'middle');
      s += TL(px + 14, py + 50, ['Hi Sam,', "I'll share the build by Wednesday.", 'I still need Kafka access for the', 'last test. Thanks!'], 'pnl-t', 'start', 17);
      s += T(px + 14, py + 143, 'Esc to close', 'pnl-d');
      s += R(px + w - 14 - 54, py + 128, 54, 22, 11, 'pnl-main') + T(px + w - 14 - 27, py + 143, 'Insert', 'pnl-w b', 'middle');
      s += R(px + w - 14 - 54 - 8 - 46, py + 128, 46, 22, 11, 'pnl-chip') + T(px + w - 14 - 54 - 8 - 23, py + 143, 'Copy', 'pnl-t b', 'middle');
      return s + pill(x, cy, 56, 12);
    }],
    ['3 · After Insert: a tick for 1.2 s', (x, cy) => pill(x, cy, 96, 26)
      + `<polyline points="${f(x - 32)},${f(cy)} ${f(x - 28)},${f(cy + 4)} ${f(x - 20)},${f(cy - 5)}" class="o-okd cap"/>` + T(x - 12, cy + 4.5, 'Inserted', 'pnl-t b')],
  ];
  let b = '';
  frames.forEach(([label, draw], i) => {
    const x0 = i * 300, cx = x0 + 140;
    b += T(x0, 16, label, 'm b');
    b += R(x0, 28, 280, 252, 0, 'bx-w') + R(x0, 280, 280, 16, 0, 'tb');
    b += draw(cx, 256);
  });
  return wrap('fig-panel', 880, 300, 'A result in the indicator\'s place: the pill works, the panel rises out of it with the buttons in its footer, and after Insert the pill shows a green tick', b, 720);
}

export const FIGS = {
  app: figApp, ram: figRam, lat: figLat, mem: figMem, blocks: figBlocks, dict: figDict, mtg: figMtg, jnl: figJnl,
  cls: figCls, life: figLife, day: figDay, tiers: figTiers, keys: figKeys, tray: figTray, er: figEr, plan: figPlan,
  effort: figEffort, move: figMove, loop: figLoop, tap: figTap, skins: figSkins, panel: figPanel,
};
