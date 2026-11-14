"""Original logical three-piston schematic; never a copied reference chart."""
from html import escape as e
from music_coach_ami.trumpet_fingering_data import validate_record

def description(r):
    return 'Press: '+(', '.join('valve '+k for k,v in r['valve_states'].items() if v) or 'none')+'. Release: '+', '.join('valve '+k for k,v in r['valve_states'].items() if not v)+f". Intended partial {r['partial']} (ordinary slot {r['normal_slot']})."

def svg(value):
    r=validate_record(value);uid='trumpet-fingering-'+r['id'].replace('#','sharp');shapes=[]
    for i in range(1,4):
        pressed=r['valve_states'][str(i)];x=60+(i-1)*120;state='pressed' if pressed else 'released'
        shapes.append(f'<g data-valve="{i}" data-pressed="{str(pressed).lower()}" aria-label="Valve {i}: {state}"><rect x="{x-21}" y="70" width="42" height="87" rx="10" fill="#eee" stroke="#222"/><circle cx="{x}" cy="60" r="25" fill="{"#174ea6" if pressed else "white"}" stroke="#222" stroke-width="2"/><text x="{x}" y="66" text-anchor="middle" font-size="19" fill="{"white" if pressed else "#222"}">{"P" if pressed else "R"}</text><text x="{x}" y="185" text-anchor="middle" font-size="17">Valve {i}</text></g>')
    return f'<svg xmlns="http://www.w3.org/2000/svg" class="ami-trumpet-diagram" data-note="{e(r["id"])}" data-partial="{r["partial"]}" role="img" aria-labelledby="{uid}-title {uid}-desc" viewBox="0 0 360 240" style="display:block;width:100%;max-width:360px;min-width:280px;font-family:Arial"><title id="{uid}-title">Yamaha YTR-2330 written {e(r["id"])} valves and partial</title><desc id="{uid}-desc">{e(description(r))}</desc>'+''.join(shapes)+f'<text x="180" y="224" text-anchor="middle" font-size="18">Partial {r["partial"]} / ordinary slot {r["normal_slot"]}</text></svg>'

def html(records):
    figures=[]
    for value in records:
        r=validate_record(value);uid='trumpet-fingering-'+r['id'].replace('#','sharp')
        figures.append(f'<figure class="ami-fingering ami-trumpet-fingering" data-record="{e(r["id"])}" tabindex="0" aria-label="Yamaha YTR-2330 written {e(r["id"])} valves and partial" aria-describedby="{uid}-caption" style="margin:16px 0;font:15px/1.5 Arial;max-width:100%;outline-offset:2px"><h3 style="font-size:18px">Yamaha YTR-2330 - written {e(r["id"])}</h3><p>Sounds {e(r["sounding_name"])}{r["sounding_octave"]}. Filled P = pressed; outlined R = released.</p>'+svg(r)+f'<figcaption id="{uid}-caption">{e(description(r))}<br>Original logical valve schematic, not a physical placement drawing. Valves select tube length; coordinate lip vibration and airflow with resonance to select the note. Use a comfortable tone; do not force or apply excessive pressure.<br>{e(r["partial_convention"])}<br>Manufacturer/reference-supported; not independently teacher-reviewed or physically tested. <a href="{e(r["sources"][0]["url"])}" target="_blank" rel="noopener">Yamaha manual p.14</a> - <a href="{e(r["sources"][1]["url"])}" target="_blank" rel="noopener">Harmonic chart</a> - <a href="{e(r["sources"][2]["url"])}" target="_blank" rel="noopener">Partial-numbering reference</a></figcaption></figure>')
    return ''.join(figures)
