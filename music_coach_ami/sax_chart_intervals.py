"""Chord-tone interval cells on the authoritative song timeline; no chord parser.

Pairs are spelled generic intervals with conventional qualities. Connections between
pairs follow the harmony; they are not claimed to retain the requested interval.
Chromatic neighbours resolve inside a cell and are explicitly non-chord tones.
"""
from fractions import Fraction
from music_coach_ami import warmup_engine as we, warmup_song as ws, warmup_chordline as wc
from music_coach_ami import scale_pattern_harmony as sph

QUALITIES = {'seconds': (1, 2), 'thirds': (3, 4), 'fourths': (5,), 'fifths': (7,),
             'sixths': (8, 9), 'sevenths': (10, 11), 'octaves': (12,)}
LETTERS = 'CDEFGAB'


def staff_step(name, midi):
    return 7 * sph.octave_for(name, midi) + LETTERS.index(name[0])


def pair_ok(a, b, interval, direction):
    sign = -1 if direction == 'descending' else 1
    return (staff_step(b[1], b[0]) - staff_step(a[1], a[0]) == sign * we.INTERVALS[interval]
            and (b[0] - a[0]) * sign in QUALITIES[interval])


def candidates(seg, lo, hi, interval, direction):
    tones = wc.tones_of(seg.info)
    pool = [(m, t.name, t.role) for m in range(lo, hi + 1) for t in tones if m % 12 == t.pc]
    return [(a, b) for a in pool for b in pool if pair_ok(a, b, interval, direction)]


def build(player, level, song, section, bars, options):
    segs, first, last = ws.build_timeline(song, section, bars, player.offset, player.semitones)
    from music_coach_ami.flexible_single import _window
    lo, hi = _window(player, level, options.get('register', 'middle'))
    cycle = options.get('interval_cycle') or [options['interval']]
    interval = options['interval']; approach = options.get('chart_approach', False)
    unit = Fraction(1, 4) if level == 'Advanced' else Fraction(1, 2) if level == 'Intermediate' else Fraction(1)
    if options.get('rhythm'):
        unit = we._DUR_BEATS[options['rhythm']]
    if options.get('mixed'):
        raise we.WarmupUnavailable('mixed-duration chart interval cells are not verified; no timing was changed')
    cell = unit * (4 if approach else 2)
    notes = []; records = []; pairs = []; previous = None; previous_pair = None
    for seg in segs:
        if not seg.ok:
            raise we.WarmupUnavailable(f'{seg.chord}, bar {seg.src_bar}: {seg.reason}; no partial substitute was generated')
        if seg.beats % cell:
            raise we.WarmupUnavailable(f'{seg.chord}, bar {seg.src_bar}: that rhythm does not fit its exact harmonic duration')
        for k in range(int(seg.beats / cell)):
            interval=cycle[len(pairs)%len(cycle)]
            direction = options.get('direction', 'ascending')
            if direction == 'alternating': direction = 'descending' if len(pairs) % 2 else 'ascending'
            choices = candidates(seg, lo, hi, interval, direction)
            if not choices:
                raise we.WarmupUnavailable(f'{seg.chord}, bar {seg.src_bar}: no {direction} {interval} using only its available chord tones in this register. Ask for a clearly scale-based interval drill instead')
            # Stay near the previous endpoint while varying the actual chord-tone pair.
            centre = (lo + hi) / 2
            choices.sort(key=lambda p: (p == previous_pair, abs(p[0][0] - (previous if previous is not None else centre)), abs(p[1][0] - centre), p))
            chosen = None
            pcs = {(pc + player.offset) % 12 for pc in sph.chord_tone_roles(seg.chord)}
            for a, b in choices:
                neighbour = None
                if approach:
                    # Resolve to a, after the interval a-b; never call this neighbour a chord tone.
                    for delta in (-1, 1):
                        name = wc.near_name(a[1], delta)
                        if name and lo <= a[0] + delta <= hi and (a[0] + delta) % 12 not in pcs:
                            neighbour = (a[0] + delta, name, 'approach'); break
                    if neighbour is None: continue
                chosen = (a, b, neighbour); break
            if chosen is None:
                raise we.WarmupUnavailable(f'{seg.chord}: no non-chord chromatic neighbour fits this interval and register')
            a, b, neighbour = chosen
            start = len(notes)
            pairs.append({'indices': [start, start + 1], 'interval': interval, 'direction': direction})
            values = [a, b] + ([neighbour, a] if approach else [])
            for j, (m, name, role) in enumerate(values):
                beat = seg.beat + k * cell + j * unit
                notes.append(we.Note(name, sph.octave_for(name, m), wc._DUR_NAME[unit], chord=seg.info['symbol_written'] if k == 0 and j == 0 else ''))
                records.append({'bar': seg.src_bar, 'beat': float(beat), 'beats': float(unit), 'concert': seg.chord,
                                'written_chord': seg.info['symbol_written'], 'name': name, 'midi': m, 'role': role})
            previous = values[-1][0]; previous_pair = (a, b)
    if not notes: raise we.WarmupUnavailable('the selected chart has no interval cells')
    interval=' and '.join(cycle)
    how = [f'Play {interval} as chord-tone pairs on each actual chart chord. The connections between pairs follow the changing harmony and need not be {interval}.',
           'Chord symbols above the staff are written for this saxophone. Changes occur at the chart beat, including split measures.']
    if approach: how.append('After each interval pair, a non-chord chromatic neighbour resolves by one semitone to the first chord tone of that cell; this is an in-chord approach, not an anticipation of the next chord.')
    title = f"Chord-tone {interval}{' with chromatic approaches' if approach else ''} - {song['title']} - {section}"
    b = we.Built(notes, {'Beginner': 52, 'Intermediate': 72, 'Advanced': 80}[level], title, how, [],
                 {'window': [lo, hi], 'sax_chart': True, 'chart_records': records, 'interval_pairs': pairs,
                  'chart_section': section, 'chart_bars': [first, last], 'chart_hash': song['hash']})
    return b


def verify(player, level, built, diag, song):
    """Re-evaluate emitted notes at their actual time, independently of pair selection."""
    meta = built.meta
    segs, first, last = ws.build_timeline(song, meta['chart_section'], tuple(meta['chart_bars']), player.offset, player.semitones)
    events = []; onset = Fraction(0)
    for note in built.notes:
        active = next((s for s in segs if Fraction((s.src_bar-first)*4)+s.beat <= onset < Fraction((s.src_bar-first)*4)+s.beat+s.beats), None)
        if note.rest or active is None or onset + note.beats > Fraction((active.src_bar-first)*4)+active.beat+active.beats:
            raise we.WarmupUnavailable('an interval note crosses a harmonic boundary or lacks a chord')
        events.append((onset, note, active)); onset += note.beats
    if onset != sum((s.beats for s in segs), Fraction()):
        raise we.WarmupUnavailable('the interval line does not fill the selected chart exactly')
    approach_indices = {i for i,r in enumerate(meta['chart_records']) if r['role']=='approach'}
    if len(events) != len(meta['chart_records']): raise we.WarmupUnavailable('stored chart events differ from notes')
    for i, (t, n, seg) in enumerate(events):
        pcs = set(sph.chord_tone_roles(seg.chord))
        pc = (n.midi - player.offset) % 12
        if i in approach_indices:
            if pc in pcs or i+1 == len(events) or abs(events[i+1][1].midi-n.midi)!=1 or events[i+1][2].index!=seg.index:
                raise we.WarmupUnavailable('a chromatic neighbour does not resolve inside its actual chord')
        elif pc not in pcs:
            raise we.WarmupUnavailable(f'{n.spelled} is not a chord tone of {seg.chord} at beat {t}')
        r = meta['chart_records'][i]
        if n.midi != r['midi'] or n.spelled != r['name'] or n.beats != Fraction(r['beats']) or r['bar'] != seg.src_bar or Fraction(r['beat']) != t - (seg.src_bar-first)*4:
            raise we.WarmupUnavailable('stored chart explanation differs from the actual events')
    for pair in meta['interval_pairs']:
        a,b = [built.notes[i] for i in pair['indices']]
        if not pair_ok((a.midi,a.spelled),(b.midi,b.spelled),pair['interval'],pair['direction']):
            raise we.WarmupUnavailable('an actual interval differs from its label')
    checks = we.verify(player, level, built, *we.practical_key(*we.split_key(player.written_key)), diag, allowed_pcs=set(range(12)))
    checks.append({'name':'chart_intervals_at_actual_beats','ok':True,'detail':'actual chord membership, spelled interval pairs and chromatic resolutions verified'})
    return checks


def explain(row):
    lines = [f"Exercise: {row['title']}. Tempo {row['bpm']} BPM; {row['reps']} repetitions.", *row['how']]
    for r in row['meta']['chart_records']:
        lines.append(f"Bar {r['bar']}, beat {r['beat']+1:g}: concert {r['concert']} / written {r['written_chord']}: {r['name']}{sph.octave_for(r['name'],r['midi'])}, {r['beats']:g} beats, {'chromatic approach' if r['role']=='approach' else 'chord tone '+r['role']}.")
    return '\n'.join(lines)
