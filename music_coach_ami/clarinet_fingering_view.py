"""Original accessible clarinet finger-action schematic; no reference artwork."""
from html import escape as e
from music_coach_ami.clarinet_fingering_data import validate_record,HOLES,KEYS

def description(r):
    covered=', '.join(label for k,label in HOLES if r['holes'][k]) or 'none'
    opened=', '.join(label for k,label in HOLES if not r['holes'][k]) or 'none'
    pressed=', '.join(label for k,label in KEYS if r['keys'][k]) or 'none'
    released=', '.join(label for k,label in KEYS if not r['keys'][k]) or 'none'
    return f'Cover: {covered}. Open: {opened}. Press: {pressed}. Release: {released}. All other standard finger controls released.'

def svg(value):
    r=validate_record(value);uid='clarinet-fingering-'+r['id'];shapes=[]
    positions={'L1':(80,50),'L2':(80,110),'L3':(80,170),'R1':(280,50),'R2':(280,110),'R3':(280,170),'T':(50,255),'Register':(180,255),'A':(310,255),'L_EB':(90,350),'R_FC':(270,350)}
    for kind,items in [('hole',HOLES),('key',KEYS)]:
        for k,label in items:
            state=r['holes' if kind=='hole' else 'keys'][k];x,y=positions[k]
            marker=('C' if state else 'O') if kind=='hole' else ('P' if state else 'R')
            action=('covered' if state else 'open') if kind=='hole' else ('pressed' if state else 'released')
            fill='#174ea6' if state else 'white';attrs=f'data-hole="{k}" data-covered="{str(state).lower()}"' if kind=='hole' else f'data-key="{k}" data-pressed="{str(state).lower()}"'
            shape=f'<circle cx="{x}" cy="{y}" r="20"' if kind=='hole' else f'<rect x="{x-22}" y="{y-20}" width="44" height="40" rx="5"'
            labels=[label] if k not in ('L_EB','R_FC') else [('Left' if k=='L_EB' else 'Right')+' little finger', 'E/B key' if k=='L_EB' else 'F/C key']
            shapes.append(f'<g {attrs} aria-label="{e(label)}: {action}">{shape} fill="{fill}" stroke="#222" stroke-width="2"/><text x="{x}" y="{y+6}" font-size="18" text-anchor="middle" fill="{"white" if state else "#222"}">{marker}</text>'+''.join(f'<text x="{x}" y="{y+37+i*18}" font-size="14" text-anchor="middle">{e(line)}</text>' for i,line in enumerate(labels))+'</g>')
    return f'<svg xmlns="http://www.w3.org/2000/svg" class="ami-clarinet-diagram" data-note="{r["id"]}" role="img" aria-labelledby="{uid}-title {uid}-desc" viewBox="0 0 360 415" style="display:block;width:100%;max-width:360px;min-width:280px;font-family:Arial"><title id="{uid}-title">Yamaha YCL-255 written {r["id"]} finger holes and keys</title><desc id="{uid}-desc">{e(description(r))}</desc>'+''.join(shapes)+'</svg>'

def html(records):
    out=[]
    for value in records:
        r=validate_record(value);uid='clarinet-fingering-'+r['id']
        out.append(f'<figure class="ami-fingering ami-clarinet-fingering" data-record="{r["id"]}" tabindex="0" aria-label="Yamaha YCL-255 written {r["id"]} fingering" aria-describedby="{uid}-caption" style="margin:16px 0;font:15px/1.5 Arial;max-width:100%;outline-offset:2px"><h3 style="font-size:18px">Yamaha YCL-255 - written {r["id"]}</h3><p>Sounds {e(r["sounding_name"])}{r["sounding_octave"]}. Holes: C covered / O open. Keys: P pressed / R released.</p>'+svg(r)+f'<figcaption id="{uid}-caption">{e(description(r))}<br>{e(r["little_finger_choice"])}. Logical finger-action schematic, not pad or physical placement states. Pressing the register key opens its vent; the thumb hole is a separate control.<br>Standard Boehm 17 keys, 6 rings. Reference-supported; not teacher-reviewed or physically tested. <a href="{e(r["sources"][0]["url"])}" target="_blank" rel="noopener">Yamaha model</a> - <a href="{e(r["sources"][1]["url"])}" target="_blank" rel="noopener">WFG fingering</a> - <a href="{e(r["sources"][2]["url"])}" target="_blank" rel="noopener">Key legend</a></figcaption></figure>')
    return ''.join(out)
