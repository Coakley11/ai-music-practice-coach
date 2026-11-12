"""Flute/clarinet real-app cases; called by the verified loopback browser driver."""
import copy


def run(page,request,select):
    def ask(q,cue,tag):return request(page,q,cue,"tech-"+tag)[0]
    def notes(record):return record["plan"]["items"][0]["written_midi"]
    select(page,"Instrument","Flute")
    select(page,"Level","Advanced")
    high=ask("Give me high-register flute exercises.","high register","01-high")
    assert min(notes(high))>=84
    select(page,"Level","Intermediate")
    low=ask("Give me three low-register long tones.","3 Long tones","02-low-tones")
    assert len(notes(low))==3 and max(notes(low))<=74
    octave=ask("Give me octave jumps from low D to high D.","Octave jumps","03-octave")
    assert notes(octave)==[62,74]*4
    wider=ask("Use wider intervals.","Two-octave jumps","04-wider")
    assert notes(wider)==[62,86]*4
    restored=ask("Undo.","Restored the exact stored version","05-undo")
    assert restored["plan"]==octave["plan"]
    higher=ask("Make it higher.","Octave jumps","06-higher")
    assert notes(higher)==[74,86]*4
    slower=ask("Make it slower.","Octave jumps","07-slower")
    assert notes(slower)==notes(higher) and slower["plan"]["items"][0]["bpm"]<higher["plan"]["items"][0]["bpm"]
    down=ask("Now descend.","Octave jumps","08-descend")
    assert notes(down)==[86,74]*4
    fewer=ask("Give me fewer notes.","Octave jumps","09-fewer")
    assert notes(fewer)==[86,74]*3
    art=ask("Keep the notes but change the articulation.","staccato","10-articulation")
    assert notes(art)==notes(fewer)
    assert art["plan"]["items"][0]["durations"]==fewer["plan"]["items"][0]["durations"]
    explain=ask("Explain what this exercise develops.","Develop accurate octave placement","11-explain")
    assert explain["plan"]==art["plan"] and explain["history"]==art["history"]
    undo=ask("Undo.","Restored the exact stored version","12-undo-art")
    assert undo["plan"]==fewer["plan"]
    redo=ask("Redo.","Restored the exact stored version","13-redo-art")
    assert redo["plan"]==art["plan"]
    fingers=ask("Give me a difficult flute fingering exercise.","Flute octave and finger coordination","14-flute-fingers")
    assert fingers["plan"]["level"]=="Advanced" and "sixteenth" in fingers["plan"]["items"][0]["durations"]
    assert fingers["settings"]["level"]=="Intermediate"
    tone=ask("Give me a tone warmup for intermediate flute.","warmup","15-flute-warmup")
    assert tone["plan"]["level"]=="Intermediate" and not tone["plan"]["spec"].get("single")
    # Explicit clarinet overrides the still-selected flute without editing it.
    clarinet=ask("Give me a clarinet octave exercise from F to F.","Octave jumps","16-clarinet-override")
    assert notes(clarinet)==[65,77]*4
    assert clarinet["plan"]["items"][0]["sounding_midi"]==[63,75]*4
    assert clarinet["settings"]["instrument"]=="Flute"
    select(page,"Instrument","Clarinet")
    crossing=ask("Give me an exercise for crossing the register break.","register-break crossing","17-break")
    assert notes(crossing)==[69,70,71,72]*4
    raised=ask("Make it higher.","register-break crossing","18-break-higher")
    assert notes(raised)==[70,71,72,74]*4
    harder=ask("Make it harder.","register-break crossing","19-break-harder")
    assert harder["plan"]["level"]=="Advanced" and "eighth" in harder["plan"]["items"][0]["durations"]
    finger=ask("Give me a challenging clarinet fingering exercise.","throat-to-clarion coordination","20-clarinet-fingers")
    assert finger["plan"]["level"]=="Advanced"
    twelfth=ask("Give me a clarinet twelfth exercise.","perfect twelfths","21-twelfths")
    assert notes(twelfth)==[55,74]*4
    why=ask("Explain what this exercise develops.","19 semitones","22-twelfth-explain")
    assert why["plan"]==twelfth["plan"] and why["history"]==twelfth["history"]
    warm=ask("Give me a beginner clarinet warmup.","Beginner","23-clarinet-warmup")
    assert warm["plan"]["level"]=="Beginner" and warm["plan"]["player"]["key"]=="clarinet"



def run_parser(page,request,select):
    select(page,"Instrument","Flute")
    select(page,"Level","Intermediate")
    lower,_=request(page,"give me a clarinet octave exercise from g to g.","Octave jumps","parser-01-lowercase")
    assert lower["plan"]["items"][0]["written_midi"]==[67,79]*4
    assert lower["settings"]["instrument"]=="Flute"
    down,_=request(page,"Give me descending flute octave jumps from low D to high D.","Octave jumps","parser-02-descending")
    assert down["plan"]["items"][0]["written_midi"]==[74,62]*4
    bad,_=request(page,"Give me a clarinet octave exercise from F to H.","valid written endpoint","parser-03-invalid")
    assert bad["plan"]==down["plan"] and bad["history"]==down["history"]
    assert bad["response"]["diagnostics"]["single_exercise_failed"]
