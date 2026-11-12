"""Independent bass oracle: frequencies, equal-tempered frets and ABC pitches.

No import of production tuning, fretting solver or policies. Open-string MIDI
is independently recovered from standard tuning frequencies relative to A440.
"""
import math
import re
from tests.test_abc_bar_accidentals import read_abc
FREQUENCIES={4:41.2034446141,3:55.0,2:73.4161919794,1:97.9988589954}
LIMITS={'Beginner':(5,2,1,40,60),'Intermediate':(7,3,3,40,62),'Advanced':(12,3,5,40,67)}

def check(plan):
    errors=[]
    for row in plan['items']:
        level=row.get('item_level',plan['level']);cap,width,shift,lo,hi=LIMITS[level]
        written=row['written_midi'];sounding=row['sounding_midi'];path=row.get('meta',{}).get('positions',[])
        if 'clef=bass' not in row['abc']:errors.append('clef')
        if read_abc(re.sub(r'"[^"\n]*"','',row['abc']))!=written:errors.append('ABC pitches')
        if not len(path)==len(written)==len(sounding):errors.append('note count');continue
        for w,s,p in zip(written,sounding,path):
            if w-s!=12 or w!=p['written_midi'] or s!=p['sounding_midi']:errors.append('octave')
            if not lo<=w<=hi:errors.append('register')
            string=p['string'];fret=p['fret']
            if p['name']!={4:'E',3:'A',2:'D',1:'G'}.get(string):errors.append('string label')
            if string not in FREQUENCIES:errors.append('string');continue
            if not 0<=fret<=cap:errors.append('fret')
            hz=FREQUENCIES[string]*2**(fret/12)
            note=round(69+12*math.log2(hz/440))
            if note!=s:errors.append('fretted pitch')
            a,b=p['hand_low'],p['hand_high']
            if not 1<=a<=b<=cap or b-a!=width:errors.append('hand window')
            if fret and not a<=fret<=b:errors.append('unreachable fret')
        for a,b in zip(path,path[1:]):
            if abs(a['hand_low']-b['hand_low'])>shift:errors.append('shift')
    return errors
