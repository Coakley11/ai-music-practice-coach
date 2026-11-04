"""Distinct, lightweight Home illustrations. Decorative markup only; no state writes."""
import html
import math

from music_feature_icons import FEATURE_ICONS, page_feature_icon

FEATURE_BY_CARD = {
    'more_missions': 'mission', 'more_sbi': 'song_aware_coaching',
    'more_keycycle': 'key_cycle', 'more_analysis': 'upload_analysis',
    'more_log': 'practice_log',
}


def destination_icon(dest):
    feature = FEATURE_BY_CARD.get(dest.key)
    if dest.creative_dest == 'creative::Missions':
        feature = 'mission'
    elif dest.creative_dest in {'creative::SBI', 'creative::Song-Aware Coaching'}:
        feature = 'song_aware_coaching'
    return FEATURE_ICONS[feature] if feature else page_feature_icon(dest.page)


def _practice():
    return '''<path d="M37 149h279" stroke="#c7d2fe" stroke-width="2"/>
<path d="M81 44Q121 25 166 45v101q-45-20-85-2z" fill="#fff" stroke="#4338ca" stroke-width="2"/>
<path d="M166 45q43-20 85-1v100q-42-17-85 2z" fill="#eef2ff" stroke="#4338ca" stroke-width="2"/>
<path d="M166 47v96M98 68h49m-49 12h49m-49 12h49m-49 12h49" stroke="#a5b4fc" stroke-width="2"/>
<path d="M123 78v30m0-28 15-4v27" fill="none" stroke="#4338ca" stroke-width="3"/>
<ellipse cx="118" cy="108" rx="6" ry="4" fill="#4338ca"/><ellipse cx="133" cy="103" rx="6" ry="4" fill="#4338ca"/>
<path d="M187 119h17V99h23V77h23V54h23" fill="none" stroke="#4338ca" stroke-width="4" stroke-linejoin="round"/>
<circle cx="204" cy="99" r="7" fill="#93c5fd"/><circle cx="250" cy="54" r="8" fill="#facc15"/>
<path d="m246 54 3 3 5-6" fill="none" stroke="#312e81" stroke-width="2"/>
<text x="197" y="145" fill="#4338ca" font-size="9" letter-spacing="2">LEARN · PLAY · GROW</text>'''


def _backing():
    cells = ''.join(f'<rect x="{178+i*16}" y="{49+j*25}" width="10" height="15" rx="3" fill="{("#facc15" if (i+j*2)%4==0 else "#93c5fd" if (i+j)%3==0 else "#ffffff")}" opacity="{1 if (i+j*2)%4==0 else .65 if (i+j)%3==0 else .14}"/>' for j in range(3) for i in range(8))
    return '''<path d="M59 105V80a43 43 0 0 1 86 0v25" fill="none" stroke="#bfdbfe" stroke-width="11"/>
<rect x="52" y="82" width="22" height="47" rx="10" fill="#93c5fd"/>
<rect x="130" y="82" width="22" height="47" rx="10" fill="#facc15"/>
<path d="M79 113q22 17 46 0" fill="none" stroke="#60a5fa" stroke-width="2"/>
<rect x="168" y="35" width="145" height="100" rx="12" fill="#0f172a" stroke="#60a5fa" stroke-opacity=".4"/>
''' + cells + '''<path d="M178 147h128" stroke="#93c5fd" stroke-width="2"/>
<g fill="#bfdbfe" font-size="10"><text x="178" y="163">1</text><text x="211" y="163">2</text><text x="245" y="163">3</text><text x="278" y="163">4</text></g>
<circle cx="183" cy="147" r="4" fill="#facc15"/>'''


def _multitrack():
    lanes = ''
    for i, color in enumerate(('#93c5fd', '#facc15', '#c4b5fd', '#f9a8d4')):
        y = 30 + i*33
        points = ' '.join(f'{81+j*7},{y+11+((j*13+i*7)%19-9)}' for j in range(28))
        lanes += f'<rect x="62" y="{y-3}" width="238" height="28" rx="6" fill="{color}" opacity=".13"/><rect x="43" y="{y+2}" width="8" height="18" rx="3" fill="{color}"/><polyline points="{points}" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round"/>'
    return lanes + '''<path d="M215 19v145" stroke="#fff" stroke-width="2"/><path d="m209 17 6 7 6-7z" fill="#fff"/>
<g fill="#c4b5fd" font-size="8" letter-spacing="1"><text x="67" y="174">01</text><text x="133" y="174">02</text><text x="199" y="174">03</text><text x="265" y="174">04</text></g>'''


def _composition():
    return '''<path d="M75 73q92-38 222-5m-222 16q92-38 222-5m-222 16q92-38 222-5m-222 16q92-38 222-5m-222 16q92-38 222-5" fill="none" stroke="#c4b5fd" stroke-width="1.5" opacity=".6"/>
<path d="M141 140q4-58 85-112-6 58-85 112z" fill="#facc15"/>
<path d="M130 154 213 45m-49 65 24 1m-9-22 24 1m-47 31-1-19" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round"/>
<path d="M245 64v36m0-35 22-4v34" fill="none" stroke="#fff" stroke-width="3"/>
<ellipse cx="239" cy="101" rx="8" ry="5" fill="#fff"/><ellipse cx="261" cy="96" rx="8" ry="5" fill="#fff"/>
<path d="m86 43 4-9 4 9 9 4-9 4-4 9-4-9-9-4z" fill="#93c5fd"/>
<path d="M238 144q30 8 57-3" fill="none" stroke="#facc15" stroke-width="3" stroke-linecap="round"/>'''


def _pop():
    return '''<circle cx="115" cy="79" r="82" fill="#f9a8d4" opacity=".18"/>
<path d="m65 38 23 12-4-26 22 20 10-24 7 27 25-13-12 26 28 6-26 12 20 22-28-2 4 29-22-19-11 25-6-27-25 13 11-26-28-7 27-11-20-22z" fill="#facc15"/>
<g transform="rotate(-23 121 91)"><rect x="103" y="79" width="34" height="73" rx="9" fill="#312e81"/><rect x="106" y="82" width="7" height="64" rx="3" fill="#6366f1"/>
<rect x="92" y="28" width="56" height="66" rx="27" fill="#fff"/><path d="M98 45h44m-48 10h52m-51 10h50m-45 10h40" stroke="#a5b4fc" stroke-width="3"/>
<path d="M120 151v19" stroke="#312e81" stroke-width="4"/></g>
<text x="188" y="105" fill="#f9a8d4" font-size="57" font-weight="900" letter-spacing="-3">POP</text>
<text x="184" y="101" fill="#fff" font-size="57" font-weight="900" letter-spacing="-3">POP</text>
<rect x="187" y="121" width="123" height="22" rx="11" fill="#facc15"/>
<text x="249" y="136" text-anchor="middle" fill="#312e81" font-size="9" font-weight="800" letter-spacing="1.5">HOOKS + ENERGY</text>
<path d="m307 28-12 23h13l-12 23 30-32h-16l9-14z" fill="#facc15"/>'''


def _jazz():
    return '''<path d="M31 128q140-79 300-48m-300 60q140-79 300-48m-300 60q140-79 300-48" fill="none" stroke="#93c5fd" stroke-width="1" opacity=".24"/>
<circle cx="250" cy="58" r="67" fill="#93c5fd" opacity=".07"/>
<text x="33" y="65" fill="#dbeafe" font-size="29" font-style="italic" font-family="Georgia,serif" letter-spacing="3">JAZZ</text>
<path d="M242 36q-25-18-31 8-2 9 5 24l24 53q9 25-16 30-17 3-26-17l-18-36" fill="none" stroke="#eab308" stroke-width="18" stroke-linecap="round"/>
<path d="M239 37q-21-13-23 9 0 9 6 23l24 51q7 22-16 26" fill="none" stroke="#fef08a" stroke-width="5" stroke-linecap="round"/>
<path d="m165 82 31-10-10 38-15 4z" fill="#facc15"/>
<ellipse cx="180" cy="79" rx="18" ry="7" transform="rotate(-17 180 79)" fill="#854d0e" stroke="#fde68a" stroke-width="3"/>
<path d="m238 32 17 6" stroke="#0f172a" stroke-width="8" stroke-linecap="round"/>
<g fill="#fef3c7" stroke="#a16207" stroke-width="1.5"><circle cx="220" cy="76" r="4"/><circle cx="226" cy="90" r="4"/><circle cx="232" cy="104" r="4"/><circle cx="238" cy="118" r="4"/></g>
<path d="M279 70v-23l15-4v22" fill="none" stroke="#93c5fd" stroke-width="2"/><ellipse cx="274" cy="71" rx="6" ry="4" fill="#93c5fd"/><ellipse cx="289" cy="66" rx="6" ry="4" fill="#93c5fd"/>
<circle cx="128" cy="112" r="3" fill="#93c5fd"/><circle cx="143" cy="105" r="3" fill="#facc15"/>'''


def _missions():
    return '''<path d="M51 123H111V69h71v56h73V49h49" fill="none" stroke="#a5b4fc" stroke-width="3" stroke-dasharray="5 6" stroke-linejoin="round"/>
<circle cx="71" cy="123" r="17" fill="#4338ca"/><circle cx="146" cy="69" r="17" fill="#4338ca"/>
<path d="m64 123 5 5 9-11m61-48 5 5 9-11" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round"/>
<circle cx="218" cy="125" r="19" fill="#facc15"/><text x="218" y="130" fill="#312e81" text-anchor="middle" font-size="14" font-weight="800">3</text>
<path d="M285 83V23l39 15-39 15" fill="#facc15" stroke="#312e81" stroke-width="2" stroke-linejoin="round"/>
<rect x="44" y="26" width="58" height="47" rx="6" fill="#fff" stroke="#c7d2fe"/>
<path d="m52 38 3 3 5-6m-8 15 3 3 5-6m-8 15 3 3 5-6" fill="none" stroke="#4338ca" stroke-width="2"/>
<path d="M68 38h24m-24 12h24m-24 12h16" stroke="#a5b4fc" stroke-width="2"/>
<text x="123" y="166" fill="#4338ca" font-size="9" letter-spacing="2">ONE GOAL AT A TIME</text>'''


def _coaching():
    return '''<rect x="43" y="42" width="105" height="95" rx="8" fill="#eef2ff"/>
<path d="M57 57h61m-61 7h75" stroke="#a5b4fc" stroke-width="2"/>
<g font-size="10" font-weight="800" fill="#4338ca"><text x="57" y="88">Am7</text><text x="98" y="88">D7</text><text x="57" y="113">Gmaj7</text></g>
<path d="M121 105q26 0 36-19" fill="none" stroke="#facc15" stroke-width="3" stroke-dasharray="4 4"/>
<path d="M174 29h132q15 0 15 15v57q0 15-15 15h-79l-28 23 6-23h-31q-15 0-15-15V44q0-15 15-15z" fill="#6366f1" stroke="#c4b5fd" stroke-width="2"/>
<path d="M180 81q22-35 43-11t43-4q15-21 34-3" fill="none" stroke="#facc15" stroke-width="3" stroke-linecap="round"/>
<g fill="#fef08a"><circle cx="184" cy="76" r="4"/><circle cx="223" cy="71" r="4"/><circle cx="266" cy="66" r="4"/><circle cx="297" cy="62" r="4"/></g>
<path d="M179 49h49m-49 9h29" stroke="#ddd6fe" stroke-width="2" opacity=".7"/>
<text x="182" y="165" fill="#dbeafe" font-size="9" letter-spacing="2">HEAR · RESPOND</text>'''


def _key_cycle():
    labels = ('C','G','D','A','E','B','F♯','D♭','A♭','E♭','B♭','F')
    ring = ''
    for i, label in enumerate(labels):
        angle = math.radians(-90+i*30)
        x,y = 234+67*math.cos(angle),90+67*math.sin(angle)
        color = '#facc15' if i in (0,1,2) else '#bfdbfe'
        ring += f'<path d="M234 90 {x:.1f} {y:.1f}" stroke="#60a5fa" stroke-width="1" opacity=".2"/><text x="{x:.1f}" y="{y+4:.1f}" text-anchor="middle" font-size="10" font-weight="700" fill="{color}">{label}</text>'
    grid = ''.join(f'<path d="M{x} 18v144"/>' for x in range(149,319,17)) + ''.join(f'<path d="M149 {y}h170"/>' for y in range(22,166,17))
    return f'<g stroke="#60a5fa" stroke-width=".5" opacity=".15">{grid}</g>' + '''<circle cx="234" cy="90" r="52" fill="none" stroke="#60a5fa" stroke-width="1.5"/>
<path d="M231 38a52 52 0 0 1 47 31" fill="none" stroke="#facc15" stroke-width="3"/><path d="m272 65 7 6 1-10" fill="none" stroke="#facc15" stroke-width="2"/>
''' + ring + '''<rect x="209" y="76" width="50" height="29" rx="3" fill="#eff6ff"/>
<path d="M219 76v29m10-29v29m10-29v29m10-29v29" stroke="#312e81" stroke-width="1"/>
<path d="M217 76v15m11-15v15m21-15v15" stroke="#172554" stroke-width="5"/>
<text x="40" y="67" fill="#93c5fd" font-size="10" letter-spacing="2">AROUND</text><text x="40" y="89" fill="#fff" font-size="19" font-weight="800">THE KEYS</text>
<path d="M42 109h69m-10-6 10 6-10 6" fill="none" stroke="#facc15" stroke-width="2"/>'''


def _custom():
    result = ''
    for i,(label,roman,dots,mutes) in enumerate((('Cmaj7','I',((1,3),(2,2)),(0,)),('Am7','vi',((2,2),(4,1)),(0,)),('Dm7','ii',((3,2),(4,1),(5,1)),(0,1)))):
        x=48+i*91
        result += f'<rect x="{x}" y="26" width="82" height="124" rx="9" fill="#fff" stroke="#c7d2fe"/><text x="{x+41}" y="46" text-anchor="middle" fill="#312e81" font-size="12" font-weight="800" stroke="none">{label}</text>'
        result += ''.join(f'<path d="M{x+16+s*10} 62v48"/>' for s in range(6))
        result += ''.join(f'<path d="M{x+16} {62+f*12}h50"/>' for f in range(5))
        result += ''.join(f'<circle cx="{x+16+s*10}" cy="{62+(f-.5)*12}" r="4" fill="#4338ca" stroke="none"/>' for s,f in dots)
        result += ''.join(f'<path d="m{x+13+s*10} 53 6 6m-6 0 6-6" stroke="#94a3b8"/>' for s in mutes)
        result += f'<rect x="{x+27}" y="124" width="28" height="17" rx="8" fill="#fef08a" stroke="none"/><text x="{x+41}" y="136" text-anchor="middle" font-size="10" font-weight="800" fill="#4338ca" stroke="none">{roman}</text>'
    return f'<g stroke="#a5b4fc" stroke-width="1">{result}</g>'


def _analysis():
    return '''<path d="M55 28h53l23 23v95H55z" fill="#eff6ff"/><path d="M108 28v23h23" fill="#bfdbfe"/>
<path d="M69 91h8l5-14 8 29 8-42 8 27h10" fill="none" stroke="#6366f1" stroke-width="3" stroke-linejoin="round"/>
<path d="M141 69h31m-7-6 7 6-7 6" fill="none" stroke="#c4b5fd" stroke-width="2"/>
<circle cx="234" cy="80" r="43" fill="#172554" stroke="#facc15" stroke-width="7"/>
<path d="m266 112 31 31" stroke="#facc15" stroke-width="14" stroke-linecap="round"/>
<path d="M205 82h7l4-13 8 29 8-43 8 39 7-22 6 10h9" fill="none" stroke="#93c5fd" stroke-width="3" stroke-linejoin="round"/>
<path d="M162 141v-13m12 13v-21m12 21v-30m12 30v-17m12 17v-9m12 9v-18" stroke="#a5b4fc" stroke-width="5" stroke-linecap="round"/>
<text x="58" y="166" fill="#dbeafe" font-size="9" letter-spacing="2">LISTEN CLOSER</text>'''


def _log():
    cells = ''.join(f'<rect x="{71+i*26}" y="{69+j*22}" width="18" height="15" rx="3" fill="{("#facc15" if j*4+i in (0,1,4,6,9) else "#e0e7ff")}"/>' for j in range(3) for i in range(4))
    return '''<rect x="55" y="32" width="137" height="119" rx="10" fill="#fff"/><path d="M55 47q0-15 15-15h107q15 0 15 15v12H55z" fill="#6366f1"/>
<path d="M82 24v17m81-17v17" stroke="#312e81" stroke-width="5" stroke-linecap="round"/>
''' + cells + '''<path d="M214 141h96m-96 0V77" fill="none" stroke="#a5b4fc" stroke-width="2"/>
<path d="m224 130 21-18 19 5 18-31 20-13" fill="none" stroke="#4338ca" stroke-width="4" stroke-linejoin="round"/>
<g fill="#facc15" stroke="#4338ca" stroke-width="2"><circle cx="224" cy="130" r="5"/><circle cx="264" cy="117" r="5"/><circle cx="302" cy="73" r="5"/></g>
<circle cx="277" cy="40" r="19" fill="#fff" stroke="#a5b4fc" stroke-width="2"/><path d="M277 28v13l8 4" fill="none" stroke="#4338ca" stroke-width="2"/>
<text x="219" y="164" fill="#4338ca" font-size="9" letter-spacing="1.5">SMALL WINS ADD UP</text>'''


def _catalog():
    return '''<rect x="99" y="35" width="100" height="121" rx="6" transform="rotate(-12 149 95)" fill="#93c5fd"/>
<rect x="128" y="28" width="100" height="128" rx="6" transform="rotate(8 178 95)" fill="#facc15"/>
<rect x="153" y="49" width="103" height="110" rx="7" fill="#eef2ff"/>
<circle cx="204" cy="101" r="36" fill="#312e81"/><circle cx="204" cy="101" r="24" fill="none" stroke="#818cf8" stroke-width="1"/><circle cx="204" cy="101" r="12" fill="#facc15"/><circle cx="204" cy="101" r="3" fill="#312e81"/>
<path d="M62 148h237" stroke="#a5b4fc" stroke-width="2"/>
<g fill="#c4b5fd"><rect x="282" y="47" width="12" height="12" rx="2"/><rect x="300" y="47" width="12" height="12" rx="2"/><rect x="282" y="65" width="12" height="12" rx="2"/><rect x="300" y="65" width="12" height="12" rx="2"/></g>'''


_ILLUSTRATIONS = {
    'journey_practice': _practice, 'journey_backing': _backing,
    'journey_multitrack': _multitrack, 'journey_composer': _composition,
    'discover_pop': _pop, 'discover_jazz': _jazz, 'discover_all': _catalog,
    'more_missions': _missions, 'more_sbi': _coaching, 'more_keycycle': _key_cycle,
    'more_custom': _custom, 'more_analysis': _analysis, 'more_log': _log,
}

_BACKGROUNDS = {
    'journey_practice': 'linear-gradient(135deg,#f8fafc,#e0e7ff)',
    'journey_backing': 'linear-gradient(135deg,#172554,#1d4ed8)',
    'journey_multitrack': 'linear-gradient(135deg,#1e1b4b,#4c1d95)',
    'journey_composer': 'linear-gradient(145deg,#4338ca,#7c3aed)',
    'discover_all': 'linear-gradient(145deg,#312e81,#6366f1)',
    'more_missions': 'linear-gradient(135deg,#eef2ff,#ddd6fe)',
    'more_sbi': 'linear-gradient(135deg,#172554,#312e81)',
    'more_keycycle': 'linear-gradient(135deg,#0f172a,#1e3a8a)',
    'more_custom': 'linear-gradient(135deg,#dbeafe,#c4b5fd)',
    'more_analysis': 'linear-gradient(135deg,#312e81,#581c87)',
    'more_log': 'linear-gradient(135deg,#eff6ff,#bfdbfe)',
}


def card_art(dest):
    """Render a section-specific scene, retaining the product's canonical badge."""
    key = dest.key
    icon = destination_icon(dest)
    background = _BACKGROUNDS.get(key, _BACKGROUNDS['discover_all'])
    if dest.genre:
        # Shared identities used by Songs, Backing and genre pills: Pop mic, Jazz sax.
        from practice_studio import genre_visual_style
        genre = genre_visual_style(dest.genre)
        icon, background = genre['emoji'], genre['gradient']
    illustration = _ILLUSTRATIONS.get(key, _catalog)()
    return (
        f'<div class="home-art home-art-{html.escape(key)}" data-home-art-kind="{html.escape(key)}" '
        f'style="--home-art-background:{html.escape(background, quote=True)}" aria-hidden="true">'
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 360 180" '
        'preserveAspectRatio="xMidYMid meet" focusable="false">'
        f'{illustration}</svg><span class="home-art-badge">{html.escape(icon)}</span></div>'
    )


ART_CSS = """
.home-art {height:190px;position:relative;overflow:hidden;border-radius:11px;margin:0 0 1rem;
 background:var(--home-art-background,linear-gradient(135deg,#312e81,#6366f1));}
.home-art svg {width:100%;height:100%;display:block;font-family:system-ui,sans-serif;}
.home-art-badge {position:absolute;left:10px;bottom:10px;width:32px;height:32px;display:grid;
 place-items:center;border:1px solid #ffffffa6;background:#ffffffed;border-radius:10px;
 font-size:21px;line-height:1;box-shadow:0 2px 6px #17255412;}
[class*="st-key-home_card_"] {transition:box-shadow .15s ease;}
[class*="st-key-home_card_"]:hover {box-shadow:0 8px 24px #312e8118;}
[class*="st-key-home_card_"] button:focus-visible {outline:3px solid #4338ca;outline-offset:3px;}
@media(max-width:640px) {.home-art {height:170px;}}
@media(prefers-reduced-motion:reduce) {[class*="st-key-home_card_"] {transition:none;}}
"""
