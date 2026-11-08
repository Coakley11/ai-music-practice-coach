"""Custom and Composition style variants from the existing artwork. usage: compose_variants.py ART_DIR

Custom    = custom.svg (green notebook: background, grid, chord-chart sheet, pencil, notes) without its trumpet,
            plus the style's instrument drawings lifted from <genre>.svg in their own colours, and a faint
            watermark of the lead instrument in the body (as custom_blues does with its trumpet).
Composition = composition.svg (navy and gold: staff lines, gold notes, quill, inkwell) without its microphone,
            plus the style's instruments tinted gold-on-navy by a colour filter.
Existing approved variants (custom_blues, custom_pop, composition_blues, composition_classical) are left alone.
"""
import os, re, sys

ART = sys.argv[1]
# Instrument layers per genre (indices of <genre>.svg top-level layers after <defs>), picked from the contact sheet.
PICK = {
    "rock": [6, 7, 8, 9],        # amp head, speaker cabinet, electric guitar, bolts
    "jazz": [6, 11],             # upright bass, saxophone
    "pop": [5],                  # microphone
    "country": [11, 12],         # acoustic guitar, hat
    "soul": [3, 4],              # vinyl record, vintage microphone
    "funk": [4, 5, 6],           # mirror ball, electric guitar, trumpet
    "jewish": [4, 8, 10],        # star, clarinet, shofar
    "classical": [8],            # violin
}
LEAD = {"rock": 8, "jazz": 11, "pop": 5, "country": 11, "soul": 4, "funk": 5, "jewish": 8, "classical": 8}
MAKE = {
    "custom": ["rock", "jazz", "country", "soul", "funk", "jewish", "classical"],
    "composition": ["pop", "rock", "jazz", "country", "soul", "funk", "jewish"],
}
DROP = {"custom": [2], "composition": [5]}  # custom: the trumpet; composition: the default microphone
# Custom styles whose instruments need their own placement so the handwritten chord chart stays visible:
# Soul's record at half size, pushed toward the top-right corner, with the microphone a little smaller in front.
CUSTOM_LAYOUT = {"soul": {3: (.5, 260, 0), 4: (.62, 0, 0)}}
GOLD = ('<filter id="vx_gold" color-interpolation-filters="sRGB" x="-10%" y="-10%" width="120%" height="120%">'
        '<feColorMatrix type="matrix" values=".3 .59 .11 0 0  .3 .59 .11 0 0  .3 .59 .11 0 0  0 0 0 1 0"/>'
        '<feComponentTransfer><feFuncR type="table" tableValues=".04 .45 .91 1"/>'
        '<feFuncG type="table" tableValues=".06 .34 .77 .96"/><feFuncB type="table" tableValues=".16 .14 .42 .8"/>'
        '</feComponentTransfer></filter>')


def top_level(svg: str):
    head_end = svg.index(">", svg.index("<svg")) + 1
    header, body = svg[:head_end], svg[head_end: svg.rindex("</svg>")]
    items, depth, start = [], 0, None
    for m in re.finditer(r"<(/?)([a-zA-Z][\w:-]*)([^>]*?)(/?)>", body):
        closing, selfclose = m.group(1) == "/", m.group(4) == "/"
        if not closing and depth == 0:
            start = m.start()
        if closing:
            depth -= 1
        elif not selfclose:
            depth += 1
        if depth == 0 and start is not None:
            items.append(body[start:m.end()]); start = None
    defs = [x for x in items if x.startswith("<defs")]
    rest = [x for x in items if not x.startswith("<defs")]
    return header, defs, rest


def namespace(text: str, ids, prefix: str) -> str:
    for i in sorted(ids, key=len, reverse=True):
        text = re.sub(rf'id="{re.escape(i)}"', f'id="{prefix}{i}"', text)
        text = re.sub(rf'url\(#{re.escape(i)}\)', f'url(#{prefix}{i})', text)
        text = re.sub(rf'href="#{re.escape(i)}"', f'href="#{prefix}{i}"', text)
    return text


def inner_defs(defs_blocks):
    return "".join(re.sub(r"^<defs[^>]*>|</defs>$", "", d) for d in defs_blocks)


for source, styles in MAKE.items():
    base = open(os.path.join(ART, f"{source}.svg"), encoding="utf-8").read()
    b_head, b_defs, b_rest = top_level(base)
    for style in styles:
        g = open(os.path.join(ART, f"{style}.svg"), encoding="utf-8").read()
        _gh, g_defs, g_rest = top_level(g)
        gdefs = inner_defs(g_defs)
        ids = re.findall(r'id="([^"]+)"', gdefs)
        prefix = f"g{style[:3]}_"
        gdefs = namespace(gdefs, ids, prefix)
        layers = [namespace(g_rest[i], ids, prefix) for i in PICK[style]]
        lead = namespace(g_rest[LEAD[style]], ids, prefix)
        keep = [x for n, x in enumerate(b_rest) if n not in DROP[source]]
        if source == "custom":
            # the pencil rests on the chord-chart sheet, the instruments in front (base: bg, grid, chart, pencil, notes)
            # smaller and anchored at the right edge, so the handwritten chord chart stays the card's subject
            if style in CUSTOM_LAYOUT:
                # per-layer placement: (scale, x shift, y shift) about the top-right corner
                parts = [f'<g transform="translate(1600 40) scale({sc}) translate({-1600 + dx} {-40 + dy})">{namespace(g_rest[i], ids, prefix)}</g>'
                         for i, (sc, dx, dy) in CUSTOM_LAYOUT[style].items()]
                inst = '<g opacity=".97">' + "".join(parts) + "</g>"
            else:
                inst = '<g opacity=".97" transform="translate(1600 40) scale(.72) translate(-1600 -40)">' + "".join(layers) + "</g>"
            hero = keep[:4] + [inst] + keep[4:5]
            body = keep[5:]
            # faint watermark of the lead instrument in the body, like custom_blues' trumpet
            water = f'<g opacity=".14" transform="translate(-260 820) scale(1.1)">{lead}</g>'
            body = body[:3] + [water] + body[3:]
            out = hero + body
            extra_defs = ""
        else:
            # gold-tinted instruments over the staff lines and notes, under the quill and inkwell
            inst = '<g filter="url(#vx_gold)" opacity=".92" transform="translate(1600 40) scale(.88) translate(-1600 -40)">' + "".join(layers) + "</g>"
            out = keep[:5] + [inst] + keep[5:]
            extra_defs = GOLD
        defs = "<defs>" + inner_defs(b_defs) + gdefs + extra_defs + "</defs>"
        svg = b_head + defs + "".join(out) + "</svg>"
        path = os.path.join(ART, f"{source}_{style}.svg")
        open(path, "w", encoding="utf-8").write(svg)
        print(f"{source}_{style}.svg {len(svg)} bytes, {len(layers)} instrument layers")
