"""Original accessible logical-control schematics; not copies of source charts."""
from html import escape as e
from music_coach_ami.fingering_data import KEYS, validate_record


def svg(value):
    if value.get('family')=='trumpet-valve-partial':
        from music_coach_ami.trumpet_fingering_view import svg as trumpet_svg
        return trumpet_svg(value)
    r=validate_record(value);uid='fingering-'+r['id']
    shapes=[]
    for key,label in KEYS:
        x=85 if key.startswith('L') or key=='O' else 275
        y=285 if key=='O' else 55+70*(int(key[1])-1)
        pressed=r['key_states'][key];state='pressed' if pressed else 'released'
        shapes.append(f'<g data-key="{key}" data-pressed="{str(pressed).lower()}" aria-label="{e(label)}: {state}"><circle cx="{x}" cy="{y}" r="22" fill="{"#174ea6" if pressed else "white"}" stroke="#222" stroke-width="2"/><text x="{x}" y="{y+6}" text-anchor="middle" font-size="18" fill="{"white" if pressed else "#222"}">{"P" if pressed else "R"}</text><text x="{x}" y="{y+39}" text-anchor="middle" font-size="14">{e(label)}</text></g>')
    return f'<svg xmlns="http://www.w3.org/2000/svg" class="ami-fingering-diagram" data-note="{r["id"]}" role="img" aria-labelledby="{uid}-title {uid}-desc" viewBox="0 0 360 335" style="display:block;width:100%;max-width:360px;min-width:280px;font-family:Arial;color:#111"><title id="{uid}-title">Yamaha YAS-280 written {r["id"]} fingering</title><desc id="{uid}-desc">P means pressed, R means released. '+e(description(r))+f'</desc><text x="85" y="18" text-anchor="middle" font-size="16">LEFT HAND</text><text x="275" y="18" text-anchor="middle" font-size="16">RIGHT HAND</text>'+''.join(shapes)+'<text x="230" y="275" text-anchor="middle" font-size="14">Auxiliary controls</text><text x="230" y="295" text-anchor="middle" font-size="14">released</text></svg>'


def description(r):
    pressed=', '.join(label for key,label in KEYS if r['key_states'][key]) or 'none'
    released=', '.join(label for key,label in KEYS if not r['key_states'][key]) or 'none'
    return f'Press: {pressed}. Release: {released}. Leave auxiliary finger controls released.'


def html(records):
    records=list(records)
    if records and all(r.get("family")=="trumpet-valve-partial" for r in records):
        from music_coach_ami.trumpet_fingering_view import html as trumpet_html
        return trumpet_html(records)
    figures=[]
    for value in records:
        r=validate_record(value)
        figures.append(f'<figure class="ami-fingering" data-record="{r["id"]}" tabindex="0" aria-describedby="fingering-{r['id']}-caption" aria-label="{e(r["model"])} written {r["id"]} fingering" style="margin:16px 0;font:15px/1.5 Arial;max-width:100%;outline-offset:2px"><h3 style="font-size:18px">{e(r["model"])} - written {r["id"]}</h3><p>Sounds {e(r["sounding_name"])}{r["sounding_octave"]}. Filled P = pressed; outlined R = released.</p>'+svg(r)+f'<figcaption id="fingering-{r['id']}-caption">{e(description(r))}<br>Logical finger-control schematic, not a physical key-placement drawing. These are finger controls, not pad-open/closed states.<br>{e(r["keywork"])}.<br>Manufacturer/reference-supported; not independently teacher-reviewed. <a href="{e(r["sources"][0]["url"],quote=True)}" target="_blank" rel="noopener">Yamaha manual</a> - <a href="{e(r["sources"][-1]["url"],quote=True)}" target="_blank" rel="noopener">Written-octave reference</a></figcaption></figure>')
    return ''.join(figures)
