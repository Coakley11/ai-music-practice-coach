"""Lightweight, decorative Home illustrations using canonical feature identities."""
import html
from music_feature_icons import FEATURE_ICONS, page_feature_icon

FEATURE_BY_CARD = {
    'more_missions': 'mission', 'more_sbi': 'song_aware_coaching',
    'more_keycycle': 'key_cycle', 'more_analysis': 'upload_analysis',
    'more_log': 'practice_log',
}


def destination_icon(dest):
    feature = FEATURE_BY_CARD.get(dest.key)
    return FEATURE_ICONS[feature] if feature else page_feature_icon(dest.page)


def card_art(dest):
    """Pure markup; no image downloads, script, animation or session writes."""
    key = dest.key
    shapes = ''
    if 'practice' in key or 'missions' in key:
        shapes = '<circle cx="210" cy="87" r="51"/><circle cx="210" cy="87" r="33"/><circle cx="210" cy="87" r="12"/><path d="M216 80l51-47m-26 0h26v26"/>'
    elif 'backing' in key or 'multitrack' in key or 'analysis' in key:
        shapes = ''.join(f'<rect x="{170+i*17}" y="{90-h/2}" width="8" height="{h}" rx="4"/>' for i,h in enumerate([28,62,94,48,112,72,36,58]))
    elif 'composer' in key or 'custom' in key or 'log' in key:
        shapes = '<rect x="166" y="30" width="118" height="116" rx="12"/><path d="M186 60h70m-70 22h47m-47 22h60m-60 22h35"/><path d="M255 127l43-51 9 8-43 51-15 5z"/>'
    elif 'keycycle' in key or 'sbi' in key:
        shapes = '<circle cx="225" cy="88" r="55"/><path d="M189 89l60-28-19 60z"/><path d="M225 19v13m0 113v13m-69-70h13m113 0h13"/>'
    else:
        shapes = '<path d="M184 116V49l70-13v66m-70-37l70-13"/><ellipse cx="172" cy="119" rx="15" ry="10"/><ellipse cx="242" cy="105" rx="15" ry="10"/>'
    palette = 'jazz' if 'jazz' in key else 'pop' if 'pop' in key else dest.page
    return (f'<div class="home-art home-art-{html.escape(palette)}" aria-hidden="true">'
            '<svg viewBox="0 0 340 176" preserveAspectRatio="xMidYMid slice" focusable="false">'
            '<circle class="home-art-orbit" cx="280" cy="30" r="110"/>'
            '<circle class="home-art-orbit" cx="280" cy="30" r="140"/>'
            f'<g class="home-art-drawing">{shapes}</g></svg>'
            f'<span class="home-art-icon">{html.escape(destination_icon(dest))}</span>'
            '<span class="home-art-spark">✦</span></div>')

ART_CSS = """
.home-art {height:176px;position:relative;overflow:hidden;border-radius:11px;margin:0 0 1rem;
 background:linear-gradient(125deg,#312e81,#6366f1);color:#fef08a;}
.home-art svg {width:100%;height:100%;display:block;}
.home-art-orbit {fill:none;stroke:#ffffff;stroke-width:1;opacity:.18;}
.home-art-drawing {fill:none;stroke:currentColor;stroke-width:3;stroke-linecap:round;stroke-linejoin:round;opacity:.8;}
.home-art-icon {position:absolute;left:24px;top:42px;font-size:64px;line-height:1.2;filter:drop-shadow(0 8px 12px #0f172a33);}
.home-art-spark {position:absolute;left:116px;top:26px;color:#facc15;font-size:22px;}
.home-art-backing,.home-art-analysis {background:linear-gradient(125deg,#172554,#2563eb);color:#bfdbfe;}
.home-art-multitrack {background:linear-gradient(125deg,#312e81,#7c3aed);color:#ddd6fe;}
.home-art-composer,.home-art-custom {background:linear-gradient(125deg,#4338ca,#7c3aed);color:#fef08a;}
.home-art-pop {background:linear-gradient(125deg,#fef08a,#facc15);color:#4338ca;}
.home-art-jazz {background:linear-gradient(125deg,#172554,#312e81);color:#93c5fd;}
.home-art-log {background:linear-gradient(125deg,#dbeafe,#a5b4fc);color:#312e81;}
[class*="st-key-home_card_"] {transition:box-shadow .15s ease;}
[class*="st-key-home_card_"]:hover {box-shadow:0 8px 24px #312e8118;}
[class*="st-key-home_card_"] button:focus-visible {outline:3px solid #4338ca;outline-offset:3px;}
@media(max-width:640px) {.home-art {height:156px;} .home-art-icon {font-size:58px;top:34px;}}
@media(prefers-reduced-motion:reduce) {[class*="st-key-home_card_"] {transition:none;}}
"""
