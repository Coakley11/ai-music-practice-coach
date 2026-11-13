"""Independent timing/pitch oracle, using ABC tokenizer and tuning frequencies."""
from fractions import Fraction
import re
from tests.bass_oracle import check as frets
from tests.song_oracle import read_tune

def check(plan):
    errors=frets(plan)
    for row in plan['items']:
        tab=row.get('meta',{}).get('bass_tab')
        if not tab:errors.append('missing TAB');continue
        if tab['strings']!=['G','D','A','E'] or tab['tuning_sounding']!=[43,38,33,28]:errors.append('string order/tuning')
        if tab['abc']!=row['abc'].strip() or tab['bpm']!=row['bpm']:errors.append('stale score/tempo')
        actual=read_tune(row['abc']);expected=tab['events']
        if len(actual)!=len(expected):errors.append('event count');continue
        positions=iter(row['meta']['positions'])
        for i,((onset,beats,midi,chord),event) in enumerate(zip(actual,expected)):
            if event['id']!=i or Fraction(*event['onset'])!=onset or Fraction(*event['beats'])!=beats:errors.append('timing')
            if event['bar']!=int(onset//4) or event['beat']!=float(onset%4+1):errors.append('bar/beat')
            if event['rest']!=(midi is None) or event['written_midi']!=midi:errors.append('note/rest/pitch')
            if abs(event['seconds']-float(onset*60/row['bpm']))>1e-9:errors.append('seconds')
            if abs(event['duration_seconds']-float(beats*60/row['bpm']))>1e-9:errors.append('duration seconds')
            if midi is None:
                if event['string'] is not None or event['fret'] is not None:errors.append('fretted rest')
            else:
                p=next(positions)
                if event['string']!=p['string'] or event['fret']!=p['fret'] or event['sounding_midi']!=midi-12:errors.append('position or octave')
        body=' '.join(l for l in row['abc'].splitlines() if l and not re.match(r'^[A-Za-z]:',l))
        body=re.sub(r'"[^"\n]*"','',body)
        bars=[b for b in body.split('|') if re.search('[A-Ga-gz]',re.sub(r'!.*?!','',b))]
        if len(bars)!=tab['bars']:errors.append('bars')
        headers='\n'.join(l for l in row['abc'].splitlines() if re.match(r'^[A-Za-z]:',l))
        for bar in bars:
            if sum(t[1] for t in read_tune(headers+'\n'+bar))!=4:errors.append('barline timing')
    return errors
