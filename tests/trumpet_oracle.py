"""Independent equal-tempered target check from harmonic frequency ratios, not generator tables."""
import math
from tests.test_abc_bar_accidentals import read_abc

WINDOWS={"Beginner":(58,74),"Intermediate":(55,79),"Advanced":(54,84)}
SHIFTS={"open":0,"1":2,"2":1}


def check(plan):
    errors=[];s=plan["spec"];r=plan["items"][0]
    if s["valve"] not in SHIFTS:return ["unknown valve"]
    allowed={n:round(60+12*math.log2(n/2))-SHIFTS[s["valve"]] for n in (2,3,4,5,6,8)}
    lo,hi=WINDOWS[s["level"]]
    written=r["written_midi"];partials=r["partial_numbers"]
    if len(written)!=len(partials):errors.append("partial count")
    if any(allowed.get(n)!=m for n,m in zip(partials,written)):errors.append("harmonic membership")
    if any(not lo<=m<=hi for m in written):errors.append("level range")
    if r["sounding_midi"]!=[m-2 for m in written]:errors.append("Bb offset")
    if read_abc(r["abc"])!=written:errors.append("notation pitches")
    body=r["abc"].split("K:",1)[1].split("\n",1)[1]
    groups=r["slur_groups"]
    expected=len({g for g in groups if g and groups.count(g)>=2})
    if body.count("(")!=expected or body.count(")")!=expected:errors.append("slur marks")
    if s["style"]=="tongued" and (expected or any(groups)):errors.append("tongued slur")
    return errors
