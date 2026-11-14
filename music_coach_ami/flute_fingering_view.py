"""Original accessible flute finger-action diagrams; no chart artwork copied."""
from html import escape as e
from music_coach_ami.flute_fingering_data import validate_record,KEYS

def description(r):
    return 'Press: '+(', '.join(label for k,label in KEYS if r['key_states'][k]) or 'none')+'. Release: '+(', '.join(label for k,label in KEYS if not r['key_states'][k]) or 'none')+'. B-natural thumb lever selected; no octave key is present.'

def svg(value):
    r=validate_record(value);uid='flute-fingering-'+r['id'];shapes=[]
    pos={'B_thumb':(85,45),'Bb_thumb':(275,45),'L1':(85,125),'L2':(85,205),'L3':(85,285),'R1':(275,125),'R2':(275,205),'R3':(275,285),'G_sharp':(85,365),'Eb':(275,365),'Bb_trill':(65,455),'D_trill':(180,455),'Eb_trill':(295,455),'low_C_sharp':(95,545),'low_C':(265,545)}
    for k,label in KEYS:
        pressed=r['key_states'][k];x,y=pos[k];state='pressed' if pressed else 'released'
        shapes.append(f'<g data-key="{k}" data-pressed="{str(pressed).lower()}" aria-label="{e(label)}: {state}"><circle cx="{x}" cy="{y}" r="21" fill="{"#174ea6" if pressed else "white"}" stroke="#222" stroke-width="2"/><text x="{x}" y="{y+6}" text-anchor="middle" font-size="18" fill="{"white" if pressed else "#222"}">{"P" if pressed else "R"}</text><text x="{x}" y="{y+40}" text-anchor="middle" font-size="14">{e(label)}</text></g>')
    return f'<svg xmlns="http://www.w3.org/2000/svg" class="ami-flute-diagram" data-note="{r["id"]}" role="img" aria-labelledby="{uid}-title {uid}-desc" viewBox="0 0 360 600" style="display:block;width:100%;max-width:360px;min-width:300px;font-family:Arial"><title id="{uid}-title">Yamaha YFL-222 written {r["id"]} key actions</title><desc id="{uid}-desc">{e(description(r))}</desc>'+''.join(shapes)+'</svg>'

def html(records):
    result=[]
    for value in records:
        r=validate_record(value);uid='flute-fingering-'+r['id']
        result.append(f'<figure class="ami-fingering ami-flute-fingering" data-record="{r["id"]}" tabindex="0" aria-label="Yamaha YFL-222 written {r["id"]} fingering" aria-describedby="{uid}-caption" style="margin:16px 0;font:15px/1.5 Arial;max-width:100%;outline-offset:2px"><h3 style="font-size:18px">Yamaha YFL-222 - written {r["id"]}</h3><p>Sounds {r["id"]} (concert C flute). P pressed / R released.</p>'+svg(r)+f'<figcaption id="{uid}-caption">{e(description(r))}<br>Covered keys, offset G, C footjoint, no split-E mechanism. Logical finger-action schematic, not physical key placement or linked pad states. Corresponding verified octave fingerings are identical; the register change involves air-jet/embouchure control, not an octave-key action.<br>Reference-supported; not teacher-reviewed or physically tested. <a href="{e(r["sources"][0]["url"])}" target="_blank" rel="noopener">Yamaha model</a> - <a href="{e(r["sources"][1]["url"])}" target="_blank" rel="noopener">WFG fingering</a> - <a href="{e(r["sources"][2]["url"])}" target="_blank" rel="noopener">Key legend</a></figcaption></figure>')
    body=''.join(result)
    return '<div class="ami-flute-comparison" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px;align-items:start">'+body+'</div>' if len(records)>1 else body
