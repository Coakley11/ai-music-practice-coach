"""Bass TAB event projection: one source of notes, timing and selected positions."""
from __future__ import annotations
import copy
import re
from fractions import Fraction
from music_coach_ami import warmup_engine as we


def timeline(built, level, bpm, abc):
    """Project the EXACT notes rendered by warmup_engine, including every rest."""
    events,bars=we.to_events(built.notes)
    positions=iter(built.meta['positions']);out=[];onset=Fraction(0)
    for i,(event,note) in enumerate(zip(events,built.notes)):
        item={'id':i,'bar':event.bar_index,'beat':event.beat,'onset':[onset.numerator,onset.denominator],
              'beats':[note.beats.numerator,note.beats.denominator],'duration':note.dur,'rest':note.rest,
              'chord':event.chord,'articulation':event.articulation,'slur_group':event.slur_group,
              'seconds':float(onset*60/bpm),'duration_seconds':float(note.beats*60/bpm),
              'written_midi':None,'sounding_midi':None,'string':None,'fret':None,'diatonic':None}
        if not note.rest:
            pos=next(positions)
            if pos['written_midi']!=note.midi or pos['sounding_midi']!=note.midi-12:
                raise we.WarmupUnavailable('TAB position differs from its canonical note')
            item.update(written_midi=note.midi,sounding_midi=note.midi-12,string=pos['string'],fret=pos['fret'],
                        diatonic='CDEFGAB'.index(note.spelled[0])+7*(note.octave-4))
        out.append(item);onset+=note.beats
    if next(positions,None) is not None:raise we.WarmupUnavailable('extra bass positions')
    return {'version':1,'abc':abc.strip(),'strings':['G','D','A','E'],'tuning_sounding':[43,38,33,28],
            'offset':12,'level':level,'bpm':bpm,'bars':bars,'events':out,'ties_supported':False}


def sections(rows):
    return [copy.deepcopy(r['meta']['bass_tab']) for r in rows if r.get('meta',{}).get('bass_tab')]


def rules_from(q):
    q=q.lower();rules={}
    m=re.search(r'\b(?:on|use|using)\s+(?:the\s+)?([eadg])[- ]string\b|\bon\s+string\s+([1-4])\b',q)
    if m:rules['string']={'e':4,'a':3,'d':2,'g':1}[m[1]] if m[1] else int(m[2])
    m=re.search(r'\bposition\s+(\d+)\b|\b(\d+)(?:st|nd|rd|th)?\s+position\b|\b(first|second|third|fourth|fifth|sixth|seventh)\s+position\b',q)
    if m:rules['position']=int(m[1] or m[2]) if m[1] or m[2] else ['first','second','third','fourth','fifth','sixth','seventh'].index(m[3])+1
    if 'open strings' in q:rules['prefer_open']=True
    if re.search(r'only (?:the )?open strings|open strings only',q):rules['open_only']=True
    return rules


def valid_path(path,written,level,rules=None):
    from music_coach_ami.bass_technique import OPEN,POLICY
    rules=rules or {};cap,width,shift=POLICY[level];opened={s:m for s,_,m in OPEN}
    if not path or len(path)!=len(written):return False
    for p,w in zip(path,written):
        s,f,a,b=p['string'],p['fret'],p['hand_low'],p['hand_high']
        if s not in opened or not 0<=f<=cap or opened[s]+f!=w-12:return False
        if p['written_midi']!=w or p['sounding_midi']!=w-12:return False
        if not 1<=a<=b<=cap or b-a!=width or f and not a<=f<=b:return False
        if rules.get('string') and s!=rules['string']:return False
        if rules.get('position') and a!=rules['position']:return False
        if rules.get('open_only') and f:return False
    return all(abs(a['hand_low']-b['hand_low'])<=shift for a,b in zip(path,path[1:]))


def handle(question,session,ami_ctx=None):
    from music_coach_ami import warmup_plan as wp,bass_technique as bass,flexible_single as fs
    q=question.lower().strip(' .!?');plan=wp.current(session)
    show=bool(re.fullmatch(r'(?:please )?(?:show(?: me)?|display)(?: the| my)? (?:bass )?(?:tab|tablature)',q))
    specific=bool(rules_from(q) or re.search(r'different string|more string crossings|rhythm faster|faster rhythm',q))
    if not show and not specific:return None
    if re.search(r'\b(?:give|generate|create|build|want|need)\b',q) and not show:return None
    if not plan or plan['player']['key']!='bass':
        return fs._reply('Generate a verified bass exercise first; TAB is available only for its four-string model.',failed='no_bass_tab')
    def reply(p,lead=''):
        if p['spec'].get('single'):return bass.response(p,session,lead)
        return wp._plan_response(p,lead=lead,view=wp.history(session).get('view'),session_ref=session)
    if show and not all(r.get('meta',{}).get('bass_tab') for r in plan['items']):return reply(plan,'This stored version predates canonical TAB timing. Generate a fresh bass exercise; no notes or history changed. ')
    if show:return reply(plan,'Staff and timing-aware four-string TAB show the same stored passage. No notes, fingering or history changed. ')
    if 'ties' in q or 'tied' in q:return reply(plan,'Ties are not represented by the current bass event model; no exercise changed. ')
    spec=copy.deepcopy(plan['spec']);view=wp.history(session).get('view',{})
    if len(plan['items'])>1 and view.get('mode')!='item':return reply(plan,'Open one warmup exercise first so the fingering change has an unambiguous target. ')
    row=plan['items'][view.get('index',0) if view.get('mode')=='item' else 0];uid=row['uid'];level=row.get('item_level',plan['level'])
    if re.search(r'rhythm faster|faster rhythm',q):
        if not spec.get('single'):return reply(plan,'For this chart or timed warmup, use its existing tempo/difficulty revision; I will not rescale a chart timeline. ')
        current=spec.get('rhythm') or {'Beginner':'quarter','Intermediate':'eighth','Advanced':'sixteenth'}[level]
        units=['whole','half','quarter','eighth','sixteenth'];index=units.index(current)
        if index==4:return reply(plan,'Already using the fastest supported note value; no new version. ')
        spec['rhythm']=units[index+1]
    else:
        record=copy.deepcopy(spec.get('bass_fingering',{}).get(uid,{}));rules=record.get('rules',{});rules.update(rules_from(q))
        old=row['meta']['positions'];different='different string' in q;cross='more string crossings' in q
        if different:rules.pop('string',None)
        if cross:rules['crossings']=True
        try:path=bass.assign(row['written_midi'],level,rules=rules,previous=old if different else None,different=different)
        except we.WarmupUnavailable as exc:return reply(plan,f'That fingering is not feasible without changing pitches: {exc}. No exercise changed. ')
        if rules.get('prefer_open') and not any(p['fret']==0 for p in path):return reply(plan,'None of these pitches has a usable open-string path at this level. No exercise changed. ')
        crossings=lambda p:sum(a['string']!=b['string'] for a,b in zip(p,p[1:]))
        if cross and crossings(path)<=crossings(old):return reply(plan,'No path with more string crossings fits these pitches and level. No exercise changed. ')
        record={'rules':rules,'positions':path,'written':list(row['written_midi'])}
        spec.setdefault('bass_fingering',{})[uid]=record
    try:
        new=bass.build(spec) if spec.get('single') else wp._rebuild(plan,spec,replan=False)
    except (we.WarmupUnavailable,ValueError) as exc:return reply(plan,f'That revision exceeds the verified bass limits: {exc}. No exercise changed. ')
    if new==plan:return reply(plan,'Already at that valid fingering; no new version. ')
    wp._commit(session,new,question)
    return reply(new,'Updated the stored passage and synchronized staff/TAB; pitches stay fixed for fingering-only changes. ')
