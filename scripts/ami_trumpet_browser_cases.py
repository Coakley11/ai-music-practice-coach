"""Real trumpet requests against the application's verified local browser driver."""
from tests.trumpet_oracle import check


def run(page,request,select,probe=False):
    def ask(q,cue,tag):
        r,staff=request(page,q,cue,'trumpet-'+tag)
        if r['plan'] and r['plan']['spec'].get('trumpet'):
            assert check(r['plan'])==[],check(r['plan'])
            # ABCJS must recognize the actual slur starts/ends, not just display a label.
            starts=ends=0
            for score in staff:
                for note in score['notes']:
                    for x in [note,*note['pitches']]:
                        for field in ['startSlur','endSlur']:
                            value=x.get(field);n=len(value) if isinstance(value,list) else int(bool(value))
                            if field=='startSlur':starts+=n
                            else:ends+=n
            assert starts==ends,(starts,ends)
            if r['plan']['spec']['style']=='tongued':assert starts==0
            else:assert starts>0,'ABCJS did not recognize slur curves'
        return r
    def notes(r):return r['plan']['items'][0]['written_midi']
    select(page,'Instrument','Trumpet');select(page,'Level','Beginner');select(page,'Focus','Tone')
    if probe:
        select(page,'Level','Intermediate')
        p=ask('Give me a trumpet exercise using open-valve partials.','open (no valves pressed)','23-hyphenated')
        assert notes(p)==[67,72,76]*2
        return
    a=ask('Give me a beginner trumpet lip-slur exercise.','lip-slur partial','01-beginner')
    assert notes(a)==[60,67]*2
    added=ask('Add another partial.','lip-slur partial','02-add')
    assert notes(added)==[60,67,72]*2
    undo=ask('Undo.','Restored the exact stored version','03-undo');assert undo['plan']==a['plan']
    changed=ask('Use a different valve combination.','valve 2 pressed','04-valve2');assert notes(changed)==[59,66]*2
    down=ask('Now make it descending.','lip-slur partial','05-descending');assert notes(down)==[66,59]*2
    why=ask('Explain what this exercise is practicing.','fixed tube length','06-explain')
    assert why['plan']==down['plan'] and why['history']==down['history']
    rhythm=ask('Make the rhythm more difficult.','lip-slur partial','07-rhythm')
    assert notes(rhythm)==notes(down) and 'eighth' in rhythm['plan']['items'][0]['durations']
    easy=ask('Make it easier.','lip-slur partial','08-easier');assert easy['plan']['level']=='Beginner'
    select(page,'Level','Intermediate')
    opened=ask('Give me a trumpet exercise using open valves.','open (no valves pressed)','09-open')
    assert notes(opened)==[67,72,76]*2
    lower=ask('Move it lower.','lip-slur partial','10-lower');assert notes(lower)==[60,67,72]*2
    flex=ask('Give me a flexibility exercise moving between harmonic partials.','lip-slur partial','11-flexibility')
    smooth=ask('Give me an exercise for moving smoothly between notes without changing valves.','lip-slur partial','12-smooth')
    advanced=ask('Give me an advanced trumpet lip-slur finger-buster.','finger-buster','13-advanced')
    assert set(advanced['plan']['items'][0]['partial_numbers'])=={2,3,4,5,6,8}
    assert advanced['plan']['level']=='Advanced' and advanced['settings']['level']=='Intermediate'
    valve1=ask('Use valve 1.','valve 1 pressed','14-valve1');assert max(notes(valve1))==82
    tongue=ask('Use staccato.','tongued partial drill','15-tongued');assert notes(tongue)==notes(valve1)
    pairs=ask('Use slur two.','finger-buster','16-paired-slurs');assert notes(pairs)==notes(tongue)
    undo=ask('Undo.','Restored the exact stored version','17-undo');assert undo['plan']==tongue['plan']
    redo=ask('Redo.','Restored the exact stored version','18-redo');assert redo['plan']==pairs['plan']
    warm=ask('Give me a trumpet warmup to improve my upper register.','upper-register preparation','19-upper-prep')
    assert len(warm['plan']['items'][0]['stages'])==3 and max(notes(warm))<=79
    full=ask('Give me a beginner trumpet warmup.','Beginner','20-full-warmup');assert not full['plan']['spec'].get('single')
    select(page,'Instrument','Flute')
    override=ask('Give me a beginner trumpet lip-slur exercise.','lip-slur partial','21-override')
    assert override['settings']['instrument']=='Flute' and override['plan']['player']['offset']==2
    bad=ask('Use valve 3.','Only open, valve 1 and valve 2','22-invalid')
    assert bad['plan']==override['plan'] and bad['history']==override['history']
