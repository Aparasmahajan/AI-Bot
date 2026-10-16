"""Pictures for the indicator and the tray, painted with Pillow (design §13.2, §13.3). Colours are the demo's
(docs/src/demo/MWB-Demo.html): blue while listening, amber while working, green when done, grey when paused.
Shapes are drawn at 4x and scaled down, which gives smooth edges at any screen scale."""
import math, re
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont

PILL, PILL_LINE, PILL_FG = (11, 18, 32), (255, 255, 255, 46), (238, 243, 255)
STATE = {'idle': (169, 186, 214), 'listening': (127, 166, 255), 'working': (241, 182, 92), 'done': (112, 212, 156),
         'paused': (125, 138, 161), 'loading': (241, 182, 92)}
COBALT, WHITE = (33, 72, 201), (255, 255, 255)
RECORDING = (255, 141, 85)                  # the demo's --st-rec: every skin adds this ring during a meeting
SS = 4                                      # supersampling factor


def _a(rgb, alpha):
    return (*rgb[:3], alpha)


@lru_cache(maxsize=12)
def font(px, bold=False):
    for name in (('seguisb.ttf', 'segoeuib.ttf') if bold else ()) + ('segoeui.ttf', 'arial.ttf'):
        try:
            return ImageFont.truetype(name, px)
        except OSError:
            continue
    return ImageFont.load_default(px)


def _check(d, cx, cy, s, colour, width):
    d.line([(cx - 5 * s, cy), (cx - 1.5 * s, cy + 3.5 * s), (cx + 5.5 * s, cy - 4 * s)], fill=colour, width=width,
           joint='curve')


def size_of(state, label=''):
    """The pill's size at scale 1 in a state; the indicator eases between sizes."""
    if state in ('idle', 'paused'):
        return 56, 12
    if state == 'done':
        return (round(40 + font(12, True).getlength(label)), 26) if label else (80, 26)
    return 110, 26


@lru_cache(maxsize=48)
def _base(state, scale, w, h, label='', glyph=True):
    """The still part of a pill: shadow, pill, outline and, once the size has settled, the state's glyph. Cached,
    since only the bars and dots move."""
    k, pad = scale * SS, 6                                      # pad: room for the soft shadow
    colour = STATE.get(state, STATE['idle'])
    W, H = round((w + 2 * pad) * k), round((h + 2 * pad) * k)
    img = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = pad * k, pad * k, (pad + w) * k, (pad + h) * k
    d.rounded_rectangle((x0, y0 + 2 * k, x1, y1 + 2 * k), radius=h * k / 2, fill=(0, 0, 0, 60))
    d.rounded_rectangle((x0, y0, x1, y1), radius=h * k / 2, fill=_a(PILL, 235),
                        outline=_a(colour, 255) if state != 'idle' else PILL_LINE, width=max(1, round(1.2 * k)))
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    if glyph and state in ('idle', 'paused'):
        for i in range(5):                          # five short bars at rest
            bx = cx + (i - 2) * 6 * k
            d.rounded_rectangle((bx - 1.2 * k, cy - 1.6 * k, bx + 1.2 * k, cy + 1.6 * k), radius=1.2 * k,
                                fill=_a(colour, 255))
    elif glyph and state == 'done':
        _check(d, x0 + 19 * k if label else cx, cy, k, _a(colour, 255), round(2.4 * k))
    img = img.resize((round(W / SS), round(H / SS)), Image.LANCZOS)
    if glyph and label:                             # "Copied", "Inserted": text is crisper drawn at full size
        f = font(round(12 * scale), True)
        ImageDraw.Draw(img).text(((pad + 30) * scale, (pad + h / 2) * scale), label, font=f, anchor='lm',
                                 fill=_a(PILL_FG, 255))
    return img


def capsule(state, scale=1.0, level=0.0, phase=0.0, size=None, label=''):
    """The Capsule skin in one state, as an RGBA image. phase (seconds) drives the animation; size, while the pill
    grows or shrinks between states, is its current (w, h) at scale 1."""
    (tw, th) = size_of(state, label)
    w, h = size or (tw, th)
    settled = abs(w - tw) < 1 and abs(h - th) < 1
    img = _base(state, scale, round(w), round(h), label if settled else '', settled)
    if not settled or state not in ('listening', 'working', 'loading'):
        return img
    img = img.copy()
    colour, k = STATE[state], scale * 2                          # moving parts at 2x: about 0.3 ms a frame
    lw, lh = round((tw - 12) * k), round((th - 6) * k)
    layer = Image.new('RGBA', (lw, lh), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx, cy = lw / 2, lh / 2
    if state == 'listening':
        for i, b in enumerate((4, 8, 14, 10, 18, 12, 7, 11, 5)):     # bars that follow your voice
            wobble = 0.6 + 0.4 * math.sin(phase * 7 + i * 1.3)
            hh = min(lh / 2, max(1.3 * k, b * (0.2 + 0.8 * min(1.0, level * 1.3)) * wobble * k / 2))
            bx = cx + (i - 4) * 7 * k
            d.rounded_rectangle((bx - 1.5 * k, cy - hh, bx + 1.5 * k, cy + hh), radius=1.5 * k, fill=_a(colour, 255))
    else:
        for i in range(3):                          # three dots taking turns
            a = 0.35 + 0.65 * (0.5 + 0.5 * math.sin(phase * 6 - i * 1.1))
            bx = cx + (i - 1) * 12 * k
            d.ellipse((bx - 3 * k, cy - 3 * k, bx + 3 * k, cy + 3 * k), fill=_a(colour, round(255 * a)))
    layer = layer.resize((round(lw / 2), round(lh / 2)), Image.LANCZOS)
    img.alpha_composite(layer, ((img.width - layer.width) // 2, (img.height - layer.height) // 2 - round(scale)))
    return img


def words_box(text, scale=1.0, max_px=380):
    """The live-words box: the last few words, cut from the left if too long."""
    f = font(round(13 * scale))
    max_w = round(max_px * scale)
    while text and f.getlength(text) > max_w:
        text = text.split(' ', 1)[1] if ' ' in text else text[1:]
        text = text if not text or text.startswith('… ') else '… ' + text.lstrip('… ')
    pad_x, pad_y = round(10 * scale), round(5 * scale)
    tw = round(f.getlength(text)) if text else 0
    asc, desc = f.getmetrics()
    w, h = tw + 2 * pad_x, asc + desc + 2 * pad_y
    img = Image.new('RGBA', (w * SS, h * SS), (0, 0, 0, 0))
    ImageDraw.Draw(img).rounded_rectangle((0, 0, w * SS - 1, h * SS - 1), radius=8 * scale * SS, fill=_a(PILL, 235),
                                          outline=PILL_LINE, width=SS)
    img = img.resize((w, h), Image.LANCZOS)
    ImageDraw.Draw(img).text((pad_x, pad_y), text, font=f, fill=_a(PILL_FG, 255))
    return img


@lru_cache(maxsize=24)
def _ring(w, h, scale):
    """The orange recording ring that goes around the pill, as an overlay of the pill image's size."""
    img = Image.new('RGBA', (w * SS, h * SS), (0, 0, 0, 0))
    k, pad = scale * SS, 6 * scale * SS
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((pad - 3 * k, pad - 3 * k, w * SS - pad + 3 * k, h * SS - pad + 3 * k), radius=(h * SS) / 2,
                        outline=_a(RECORDING, 255), width=round(1.8 * k))
    return img.resize((w, h), Image.LANCZOS)


def with_ring(img, scale):
    img = img.copy()
    img.alpha_composite(_ring(img.width, img.height, scale))
    return img


def tray_icon(state='idle', size=64, recording=False):
    """MWB's mark: a disc with a white microphone; the disc takes the state's colour."""
    k = size * SS / 32
    disc = {'idle': COBALT, 'listening': (47, 102, 235), 'working': (196, 132, 18), 'loading': (196, 132, 18),
            'done': (33, 115, 75), 'paused': (125, 138, 161), 'failed': (207, 63, 10)}.get(state, COBALT)
    img = Image.new('RGBA', (size * SS, size * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((0.5 * k, 0.5 * k, 31.5 * k, 31.5 * k), fill=_a(disc, 255))
    d.rounded_rectangle((12.5 * k, 6 * k, 19.5 * k, 19.5 * k), radius=3.5 * k, fill=WHITE)        # capsule
    d.arc((9 * k, 10 * k, 23 * k, 23.5 * k), start=0, end=180, fill=WHITE, width=round(1.8 * k))  # stand
    d.line([(16 * k, 23.5 * k), (16 * k, 26.5 * k)], fill=WHITE, width=round(1.8 * k))
    d.line([(11.5 * k, 26.5 * k), (20.5 * k, 26.5 * k)], fill=WHITE, width=round(1.8 * k))
    if recording:
        d.ellipse((0.5 * k, 0.5 * k, 31.5 * k, 31.5 * k), outline=_a(RECORDING, 255), width=round(3 * k))
    elif state == 'listening':
        d.ellipse((0.5 * k, 0.5 * k, 31.5 * k, 31.5 * k), outline=(190, 210, 255, 255), width=round(1.6 * k))
    return img.resize((size, size), Image.LANCZOS)


# ---- the result panel (§8.3): answers, drafts and rewrites appear above the pill, in the indicator's place --------

TEXT, DIM, PRIMARY, CODE = (226, 233, 246), (150, 165, 192), (79, 124, 255), (180, 205, 255)
PANEL_W, BODY_LINES = 440, 9


@lru_cache(maxsize=4)
def mono(px):
    for name in ('consola.ttf', 'cour.ttf'):
        try:
            return ImageFont.truetype(name, px)
        except OSError:
            continue
    return font(px)


def wrap(s, f, width):
    """Greedy word wrap by measured width; a word longer than a line is cut by characters."""
    if not s or f.getlength(s) <= width:
        return [s]
    space, lines, cur, cur_w = f.getlength(' '), [], None, 0.0
    for word in s.split(' '):
        ww = f.getlength(word)
        while ww > width:
            n = max(1, int(len(word) * width / ww))
            while n > 1 and f.getlength(word[:n]) > width:
                n -= 1
            if cur is not None:
                lines.append(cur)
                cur = None
            lines.append(word[:n])
            word = word[n:]
            ww = f.getlength(word)
        if cur is None:
            cur, cur_w = word, ww
        elif cur_w + space + ww <= width:
            cur, cur_w = f'{cur} {word}', cur_w + space + ww
        else:
            lines.append(cur)
            cur, cur_w = word, ww
    if cur is not None:
        lines.append(cur)
    return lines


@lru_cache(maxsize=1024)
def _wrapped(s, style, scale):
    """One paragraph, wrapped. Cached, so streaming text re-wraps only its last paragraph."""
    f = mono(round(12 * scale)) if style == 'code' else font(round(13 * scale), style == 'head')
    return tuple((piece, style) for piece in wrap(s, f, round((PANEL_W - 32) * scale)))


@lru_cache(maxsize=256)
def _line_img(line, style, scale):
    """One body line, rendered once: drawing text is the slow part, and streaming redraws the same lines."""
    f = mono(round(12 * scale)) if style == 'code' else font(round(13 * scale), style == 'head')
    asc, desc = f.getmetrics()
    img = Image.new('RGBA', (max(1, math.ceil(f.getlength(line))) + 2, asc + desc), (0, 0, 0, 0))
    ImageDraw.Draw(img).text((0, 0), line, font=f, fill=_a(CODE if style == 'code' else TEXT, 255))
    return img


@lru_cache(maxsize=4)
def layout(text, scale):
    """The body as ((line, style), ...): light Markdown, with code in Consolas and headings in bold."""
    out, code = [], False
    for raw in text.replace('\r', '').strip('\n').split('\n'):
        s = raw.rstrip()
        if s.lstrip().startswith('```'):
            code = not code
            continue
        if code:
            style = 'code'
        else:
            m = re.match(r'#{1,6}\s+(.*)', s)
            style, s = ('head', m.group(1)) if m else ('body', s)
            s = re.sub(r'^(\s*)[-*]\s+', r'\1• ', re.sub(r'\*\*|\*$', '', s))    # *$: half a ** still streaming
        out += _wrapped(s, style, scale)
    return tuple(out)


@lru_cache(maxsize=12)
def _panel_bg(w, h, scale):
    """Shadow and dark card, with a pad of 6 around it like the pill."""
    k, pad = 3, round(6 * scale)
    img = Image.new('RGBA', ((w + 2 * pad) * k, (h + 2 * pad) * k), (0, 0, 0, 0))
    d, r = ImageDraw.Draw(img), 16 * scale * k
    d.rounded_rectangle((pad * k, (pad + 2 * scale) * k, (pad + w) * k, (pad + h + 2 * scale) * k), radius=r,
                        fill=(0, 0, 0, 70))
    d.rounded_rectangle((pad * k, pad * k, (pad + w) * k, (pad + h) * k), radius=r, fill=_a(PILL, 244),
                        outline=PILL_LINE, width=k)
    return img.resize((w + 2 * pad, h + 2 * pad), Image.LANCZOS)


@lru_cache(maxsize=32)
def _chip(w, h, fill, outline=None):
    img = Image.new('RGBA', (w * SS, h * SS), (0, 0, 0, 0))
    ImageDraw.Draw(img).rounded_rectangle((0, 0, w * SS - 1, h * SS - 1), radius=h * SS / 2, fill=fill,
                                          outline=outline, width=SS)
    return img.resize((w, h), Image.LANCZOS)


@lru_cache(maxsize=8)
def _close(size, hover):
    img = Image.new('RGBA', (size * SS, size * SS), (0, 0, 0, 0))
    d, m, c = ImageDraw.Draw(img), size * SS * 0.34, size * SS
    d.ellipse((0, 0, c - 1, c - 1), fill=(255, 255, 255, 40 if hover else 16))
    for a, b in (((m, m), (c - m, c - m)), ((m, c - m), (c - m, m))):
        d.line([a, b], fill=_a(TEXT, 255 if hover else 190), width=round(1.4 * SS * size / 20))
    return img.resize((size, size), Image.LANCZOS)


@lru_cache(maxsize=4)
def _fade(w, h, down):
    """A strip that fades the body into the card at its top or bottom edge, when there is more to scroll."""
    img = Image.new('RGBA', (w, h), _a(PILL, 0))
    d = ImageDraw.Draw(img)
    for y in range(h):
        t = y / h if down else 1 - y / h
        d.line([(0, y), (w, y)], fill=_a(PILL, round(244 * t)))
    return img


def panel(title, note, text, buttons, hover=None, scroll=0, scale=1.0, busy=False):
    """The result panel. Returns (image, regions, max_scroll); regions are [(('button', i) | ('close', 0), box)]
    in the image's pixels. buttons are labels; the last is the main one."""
    s, o = scale, round(6 * scale)                    # o: everything sits inside the shadow's pad
    W, px = round(PANEL_W * s), round(16 * s)
    inner = W - 2 * px
    f_title, f_note, f_chip = font(round(13 * s), True), font(round(11 * s)), font(round(12 * s), True)
    close = round(22 * s)
    note_lines = wrap(note, f_note, inner)[:2] if note else []
    lines = layout(text, s) if text.strip() else (('…', 'body'),)
    lh, nh = round(19 * s), round(15 * s)
    shown = min(len(lines), BODY_LINES)
    max_scroll = max(0, len(lines) - BODY_LINES)
    scroll = min(max(0, scroll), max_scroll)
    y_note = round(32 * s)
    y_body = y_note + len(note_lines) * nh + round(8 * s)
    y_foot = y_body + shown * lh + round(12 * s)
    chip_h = round(28 * s)
    img = _panel_bg(W, y_foot + chip_h + round(12 * s), s).copy()
    d = ImageDraw.Draw(img)
    regions = []

    t = title
    while t and f_title.getlength(t) > inner - close - 8 * s:
        t = t[:-2] + '…' if len(t) > 2 else ''
    d.text((o + px, o + round(12 * s)), t, font=f_title, fill=_a(TEXT, 255))
    cx, cy = o + W - px - close + round(4 * s), o + round(9 * s)
    img.alpha_composite(_close(close, hover == ('close', 0)), (cx, cy))
    regions.append((('close', 0), (cx, cy, cx + close, cy + close)))
    for i, line in enumerate(note_lines):
        d.text((o + px, o + y_note + i * nh), line, font=f_note, fill=_a(DIM, 255))

    for i, (line, style) in enumerate(lines[scroll:scroll + shown]):
        if line.strip():
            img.alpha_composite(_line_img(line, style, s), (o + px, o + y_body + i * lh + round(2 * s)))
    fade = round(14 * s)
    if scroll > 0:
        img.alpha_composite(_fade(inner, fade, False), (o + px, o + y_body))
    if scroll < max_scroll:
        img.alpha_composite(_fade(inner, fade, True), (o + px, o + y_body + shown * lh - fade))

    x, y = o + W - px, o + y_foot
    for i in range(len(buttons) - 1, -1, -1):           # right to left; the main button is last, on the right
        label, main, on = buttons[i], i == len(buttons) - 1, hover == ('button', i)
        cw = round(f_chip.getlength(label) + 26 * s)
        x -= cw
        if main:
            chip = _chip(cw, chip_h, _a(tuple(min(255, c + 24) for c in PRIMARY) if on else PRIMARY, 255))
        else:
            chip = _chip(cw, chip_h, (255, 255, 255, 46 if on else 20), (255, 255, 255, 60))
        img.alpha_composite(chip, (x, y))
        d.text((x + cw / 2, y + chip_h / 2), label, font=f_chip, anchor='mm', fill=_a(WHITE if main else TEXT, 255))
        regions.append((('button', i), (x, y, x + cw, y + chip_h)))
        x -= round(8 * s)
    room = x - (o + px)                                 # the hint goes left of the buttons, if it fits
    for hint in (['Writing…'] if busy else ['Scroll for more  ·  Esc to close', 'Esc to close'] if max_scroll
                 else ['Esc to close']):
        if f_note.getlength(hint) <= room:
            d.text((o + px, y + chip_h // 2), hint, font=f_note, anchor='lm', fill=_a(DIM, 255))
            break
    return img, regions, max_scroll


def stack(images, gaps):
    """Images one above the other, centred; gaps[i] is the space below images[i]. Returns the picture and each
    one's top-left corner."""
    w = max(i.width for i in images)
    out = Image.new('RGBA', (w, sum(i.height for i in images) + sum(gaps[:len(images) - 1])), (0, 0, 0, 0))
    y, corners = 0, []
    for i, g in zip(images, list(gaps) + [0]):
        corners.append(((w - i.width) // 2, y))
        out.alpha_composite(i, corners[-1])
        y += i.height + g
    return out, corners
