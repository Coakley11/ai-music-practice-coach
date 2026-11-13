"""Real-app browser acceptance on a newly started, verified loopback server.

Uses an isolated headless Chrome, the real Music application and its normal UI.
The launcher observes results only; it does not seed app state or replace solvers.
"""
from __future__ import annotations
import argparse, copy, json, os, re, socket, subprocess, sys, time, uuid
from pathlib import Path
from urllib.request import urlopen
from urllib.parse import urlparse
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from playwright.sync_api import sync_playwright
from streamlit.proto.ForwardMsg_pb2 import ForwardMsg
from tests.test_abc_bar_accidentals import read_abc
parser=argparse.ArgumentParser()
parser.add_argument("--out",type=Path,required=True)
parser.add_argument("--port",type=int,default=8596)
parser.add_argument("--probe",action="store_true")
parser.add_argument("--song-only",action="store_true")
parser.add_argument("--technique-only",action="store_true")
parser.add_argument("--technique-parser-only",action="store_true")
parser.add_argument("--trumpet-only",action="store_true")
parser.add_argument("--bass-only",action="store_true")
parser.add_argument("--bass-context-only",action="store_true")
parser.add_argument("--bass-tab-only",action="store_true")
parser.add_argument("--sax-only",action="store_true")
parser.add_argument("--mobile",action="store_true")
args=parser.parse_args()
OUT=args.out.resolve();OUT.mkdir(parents=True,exist_ok=True)
ORIGIN=f"http://127.0.0.1:{args.port}"
RUN=uuid.uuid4().hex
results=[]
RUNS={"finished":0,"running":False,"events":[]}

def watch_socket(ws):
    def received(payload):
        if not isinstance(payload,bytes):return
        try:
            msg=ForwardMsg();msg.ParseFromString(payload)
            kind=msg.WhichOneof("type")
            if kind=="script_finished":
                RUNS["finished"]+=1
                RUNS["events"].append({"finished":RUNS["finished"],"time_ns":time.time_ns()})
            elif kind=="session_status_changed":
                RUNS["running"]=msg.session_status_changed.script_is_running
        except Exception:pass
    ws.on("framereceived",received)

def finish(page,before,label):
    deadline=time.monotonic()+90
    while time.monotonic()<deadline:
        if RUNS["finished"]>before and not RUNS["running"]:
            idle(page)
            return
        page.wait_for_timeout(50)
    raise AssertionError("No completed Streamlit rerun after "+label+"; state="+str(RUNS))

def address(page):
    u=urlparse(page.url)
    assert u.scheme=="http" and u.hostname=="127.0.0.1" and u.port==args.port, page.url

def idle(page):
    page.get_by_role("button",name="Stop",exact=True).wait_for(state="hidden",timeout=90000)
    assert page.locator('[data-testid="stException"]').count()==0

def select(page,label,value):
    address(page)
    print("SELECT "+label+"="+value,flush=True)
    boxes=page.get_by_test_id("stSelectbox").filter(has_text=re.compile(r"^[^A-Za-z]*(?:Practice\s+)?"+re.escape(label)+r"\b",re.I))
    visible=[boxes.nth(i) for i in range(boxes.count()) if boxes.nth(i).is_visible()]
    assert visible, f"No visible {label} selectbox"
    box=visible[-1]  # Practice's canonical quick controls; sidebar may also expose one.
    if re.search(r"(?:^|\s)"+re.escape(value)+r"\s*$",box.inner_text(),re.I):return
    box.scroll_into_view_if_needed()
    box.get_by_role("combobox").click()
    option=page.get_by_role("option",name=re.compile(r"(?:^|\s)"+re.escape(value)+r"$",re.I))
    before=RUNS["finished"]
    if option.last.get_attribute("aria-selected")=="true":
        page.keyboard.press("Escape")
        return
    option.last.click()
    finish(page,before,"select "+label)

def request(page,q,cue,tag):
    address(page)
    print("REQUEST "+tag,flush=True)
    field=page.get_by_test_id("stMainBlockContainer").get_by_role("textbox",name="Question",exact=True)
    field.fill(q)
    before=RUNS["finished"]
    field.press("Tab")
    finish(page,before,"commit request text")
    started=time.time_ns()
    ask_finished_before=RUNS["finished"]
    before_panels=page.locator('[class*="st-key-music_coach_insight_panel_"]').all_text_contents()
    page.get_by_test_id("stMainBlockContainer").get_by_role("button",name=re.compile("Ask the Music Coach",re.I)).click()
    immediate_panels=page.locator('[class*="st-key-music_coach_insight_panel_"]').all_text_contents()
    record=None
    deadline=time.monotonic()+90
    while time.monotonic()<deadline:
        path=OUT/"last-submit.json"
        if path.exists():
            try:
                candidate=json.loads(path.read_text(encoding="utf-8"))
                if candidate["run_id"]==RUN and candidate["question"]==q and candidate["time_ns"]>=started:
                    record=candidate;break
            except (ValueError,OSError): pass
        time.sleep(.2)
    assert record is not None, f"No fresh backend result for {q}"
    finish(page,ask_finished_before,"submit "+tag)
    panel=page.locator('[class*="st-key-music_coach_insight_panel_"]').filter(has_text=q).last
    panel.wait_for(state="visible",timeout=90000)
    panel.get_by_text(re.compile(re.escape(cue),re.I)).first.wait_for(timeout=90000)
    idle(page)
    address(page)
    assert record["response"], "Request took the legacy fallback"
    # Rendering is inspected in the actual card iframe, not just parsed from stored ABC.
    staff=[]
    panel.locator("iframe").first.wait_for(state="attached",timeout=45000)
    for iframe in panel.locator("iframe").all():
        frame=iframe.element_handle().content_frame()
        frame.locator("svg").first.wait_for(timeout=45000)
        frame.wait_for_function("window.__amiActualRenders && window.__amiActualRenders.length",timeout=45000)
        staff.extend(frame.evaluate("""() => {
            const out=[];
            for (const r of window.__amiActualRenders) {
                const notes=[];
                for (const tune of r.tunes) for (const line of (tune.lines||[]))
                for (const st of (line.staff||[])) for (const voice of (st.voices||[]))
                for (const e of voice) {
                    if (e.el_type!=='note' || !e.pitches || !e.pitches.length) continue;
                    notes.push({duration:e.duration,decoration:e.decoration,startSlur:e.startSlur,endSlur:e.endSlur,pitches:e.pitches.map(p=>({pitch:p.pitch,verticalPos:p.verticalPos,accidental:p.accidental,startSlur:p.startSlur,endSlur:p.endSlur})),
                                headPitches:((e.abselem&&e.abselem.heads)||[]).map(h=>h.pitch)});
                }
                out.push({abc:r.abc,notes});
            }
            return out;
        }"""))
    (OUT/(tag+"-render-observed.json")).write_text(json.dumps(staff,indent=2),encoding="utf-8")
    expected=record["response"].get("notation_abc_sections") or [record["response"]["notation_abc"]]
    assert len(staff)==len(expected), "Rendered score count differs from the response"
    for actual,abc in zip(staff,expected):
        assert actual["abc"]==abc
        assert len(actual["notes"])==len(read_abc(re.sub(r'"[^"\n]*"', "", abc))), "Drawn note count differs from independent ABC reading"
    if record.get("plan"):
        view=record.get("history",{}).get("view",{})
        visible_rows=record["plan"]["items"]
        if view.get("mode")=="item":visible_rows=[visible_rows[view["index"]]]
        for actual,row in zip(staff,visible_rows):
            if row.get("written_notes"):
                expected_positions=[]
                for name in row["written_notes"]:
                    octave=int(re.search(r"(-?\d+)$",name)[1])
                    expected_positions.append("CDEFGAB".index(name[0])+7*(octave-4))
                drawn_positions=[n["pitches"][0]["pitch"] for n in actual["notes"]]
                assert drawn_positions==expected_positions, "Staff positions differ from stored written octaves"
    record["browser_sync"]={"before_panels":before_panels,"immediate_panels":immediate_panels,"matched_question":q,"finished_runs":RUNS["finished"]}
    panel.screenshot(path=str(OUT/(tag+".png")))
    (OUT/(tag+".txt")).write_text(panel.inner_text(),encoding="utf-8")
    (OUT/(tag+".json")).write_text(json.dumps({**record,"rendered_staff":staff},indent=2),encoding="utf-8")
    assert not (OUT/"forbidden-api-call.txt").exists()
    results.append({"tag":tag,"question":q,"solver":record["response"]["source_solver"],"staff_count":len(staff),"history":record["history"]})
    (OUT/"results.json").write_text(json.dumps(results,indent=2),encoding="utf-8")
    print("PASS "+tag,flush=True)
    return record,staff

sock=socket.socket();sock.settimeout(.3)
occupied=sock.connect_ex(("127.0.0.1",args.port))==0;sock.close()
assert not occupied,"Refusing to attach to an existing server"
log=(OUT/"server.log").open("w",encoding="utf-8")
env=dict(os.environ);env["PYTHONPATH"]=str(ROOT)
cmd=[sys.executable,str(ROOT/"scripts/ami_flexible_browser_launcher.py"),"--port",str(args.port),"--data-dir",str(OUT/"data"),"--evidence-dir",str(OUT),"--run-id",RUN]
server=subprocess.Popen(cmd,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW if os.name=="nt" else 0)
try:
    deadline=time.monotonic()+120
    while time.monotonic()<deadline:
        assert server.poll() is None,"Test server exited during startup"
        try:
            with urlopen(ORIGIN+"/_stcore/health",timeout=1) as r:
                if r.status==200 and r.read().strip()==b"ok":break
        except OSError:time.sleep(.3)
    else:raise AssertionError("No healthy local test server")
    (OUT/"server-identity.json").write_text(json.dumps({"run_id":RUN,"pid":server.pid,"origin":ORIGIN,"command":cmd,"python":sys.version},indent=2),encoding="utf-8")
    with sync_playwright() as pw:
        browser=pw.chromium.launch(channel="chrome",headless=True)
        context=browser.new_context(viewport={"width":390 if args.mobile else 1440,"height":844 if args.mobile else 1000},is_mobile=args.mobile,has_touch=args.mobile)
        context.add_init_script("""(() => { let value;Object.defineProperty(window,'ABCJS',{configurable:true,get(){return value},set(v){value=v;if(v&&typeof v.renderAbc==='function'){const original=v.renderAbc;v.renderAbc=function(...args){const tunes=original.apply(this,args);(window.__amiActualRenders||(window.__amiActualRenders=[])).push({abc:args[1],tunes});return tunes}}}})})()""")
        page=context.new_page()
        page.on("websocket",watch_socket)
        page.on("pageerror",lambda e:(OUT/"page-errors.txt").open("a",encoding="utf-8").write(getattr(e,"stack",str(e))+"\n"))
        try:
            page.goto(ORIGIN+"/?suite_workspace=guest",wait_until="domcontentloaded")
            page.get_by_role("heading",name="Daniel Cohen Music Practice Coach AI",exact=True).wait_for(timeout=120000)
            idle(page);address(page)
            before=RUNS['finished']
            page.locator('.st-key-studio_quick_nav_btn_practice button:visible').first.click()
            finish(page,before,'open Practice')
            page.get_by_test_id("stMainBlockContainer").get_by_role("textbox",name="Question",exact=True).wait_for(timeout=90000)
            idle(page)
            (OUT/"practice-start.txt").write_text(page.locator("body").inner_text(),encoding="utf-8")
            if args.sax_only:
                from ami_sax_browser_cases import run
                run(page,request,select,OUT,probe=args.probe)
            elif args.bass_tab_only:
                from ami_bass_tab_browser_cases import run
                run(page,request,select,OUT,mobile=args.mobile,probe=args.probe)
            elif args.bass_only or args.bass_context_only:
                from ami_bass_browser_cases import run
                run(page,request,select,OUT,context_only=args.bass_context_only)
            elif args.trumpet_only:
                from ami_trumpet_browser_cases import run
                run(page,request,select,probe=args.probe)
            elif args.technique_parser_only:
                from ami_technique_browser_cases import run_parser
                run_parser(page,request,select)
            elif args.technique_only:
                from ami_technique_browser_cases import run
                run(page,request,select)
            else:
                if not args.song_only:
                    select(page,"Instrument","Flute")
                    select(page,"Level","Beginner")
                    a,staff=request(page,"Give me a slow ascending A major scale for flute.","Concert key A","01-scale")
                    row=a["plan"]["items"][0]
                    assert row["written_midi"]==[69,71,73,74,76,78,80,81]
                    assert read_abc(row["abc"])==row["written_midi"]
                    if not args.probe:
                        b,_=request(page,"Now make it descending.","Concert key A","02-descending")
                        assert b["plan"]["items"][0]["written_midi"]==row["written_midi"][::-1]
                        assert b["history"]["versions"]==a["history"]["versions"]+1
                        request(page,"Undo.","Restored the exact stored version","03-undo")
                        request(page,"Redo.","Restored the exact stored version","04-redo")
                        tones,_=request(page,"Give me three long tones for flute.","3 Long tones","05-tones")
                        assert len(tones["plan"]["items"])==1 and len(tones["plan"]["items"][0]["written_midi"])==3

                        select(page,"Instrument","Saxophone")
                        select(page,"Level","Intermediate")
                        buster,_=request(page,"Give me a difficult A-flat major seventh finger-buster for alto sax.","Finger-buster","06-buster")
                        br=buster["plan"]["items"][0]
                        assert buster["plan"]["level"]=="Advanced" and buster["settings"]["level"]=="Intermediate"
                        assert {m%12 for m in br["sounding_midi"]}=={8,0,3,7}
                        assert "sixteenth" in br["durations"]
                        assert max(abs(b-a) for a,b in zip(br["written_midi"],br["written_midi"][1:]))>=12
                        tenor,_=request(page,"Give me a tenor saxophone exercise.","Tenor Saxophone","07-tenor-override")
                        assert tenor["plan"]["player"]["offset"]==14
                        tr=tenor["plan"]["items"][0]
                        assert all(w-c==14 for w,c in zip(tr["written_midi"],tr["sounding_midi"]))
                        assert tenor["settings"]==buster["settings"]
                        explanation,_=request(page,"Explain why these notes work.","These are the written notes","08-single-explain")
                        assert explanation["plan"]==tenor["plan"] and explanation["history"]==tenor["history"]
                        select(page,"Level","Advanced")
                        high,_=request(page,"Give me high-register flute exercises.","high register","09-high-flute")
                        assert high["plan"]["player"]["key"]=="flute"
                        assert min(high["plan"]["items"][0]["written_midi"])>=84
                        low,_=request(page,"Make them lower.","low register","10-low-flute")
                        assert max(low["plan"]["items"][0]["written_midi"])<=72
                        assert low["settings"]==high["settings"]
                if args.song_only:
                    select(page,"Level","Advanced")
                    request(page,"Give me high-register flute exercises.","high register","song-precondition-single")
                if not args.probe:
                    import walk_guitar_shape_key as catalog_ui
                    import walk_creative_backing_matrix as existing_ui
                    catalog_ui.OUT=OUT/"catalog";existing_ui.OUT=OUT/"catalog"
                    catalog_ui.OUT.mkdir(exist_ok=True)
                    assert catalog_ui.pick_song(page,[],"Blue Bossa","Jazz"), "Could not select actual catalog Blue Bossa"
                    address(page)
                    before=RUNS["finished"]
                    page.locator('.st-key-studio_quick_nav_btn_practice button:visible').first.click()
                    finish(page,before,"return to Practice after catalog selection")
                    select(page,"Instrument","Saxophone")
                    select(page,"Level","Intermediate")
                    select(page,"Focus","Tone")
                    mixed,_=request(page,"Warm me up for soloing over Blue Bossa.","Built from","11-blue-bossa-mixed")
                    assert mixed["plan"]["player"]["key"]=="alto" and mixed["plan"]["level"]=="Intermediate"
                    assert mixed["plan"]["spec"]["song"]["title"]=="Blue Bossa"
                    why,_=request(page,"Explain why these notes work.","Why these notes work","12-blue-bossa-explain")
                    assert why["plan"]==mixed["plan"] and why["history"]==mixed["history"]
                    assert "chord tones:" in why["response"]["direct_answer"]
                    assert "Each approach and what it resolves to" in why["response"]["direct_answer"]
                    print("EXPLAIN_IMMEDIATE_PREVIOUS_CARD="+str(any("Warm me up for soloing" in text for text in why["browser_sync"]["immediate_panels"])),flush=True)
                    arp,_=request(page,"Give me a difficult arpeggio exercise over Blue Bossa.","one chart pass","13-blue-bossa-arpeggio")
                    ap=arp["plan"];assert ap["spec"]["single_song"] and len(ap["items"])==1 and ap["items"][0]["reps"]==1
                    from tests import song_oracle as oracle
                    from music_coach_ami import warmup_song as ws
                    song=ap["spec"]["song"];section=ap["spec"]["song_sel"]["section"]
                    assert oracle.check_chordline(ap["items"][0]["abc"],ws.section_slots(song,section),9,approach=False)==[]
                    tone,_=request(page,"Give me a warmup.","warmup","14-tone-focus")
                    assert set(tone["plan"]["spec"]["families"])=={"long_tones","scale"}
                    select(page,"Focus","Articulation")
                    articulation,_=request(page,"Give me a warmup.","warmup","15-articulation-focus")
                    assert set(articulation["plan"]["spec"]["families"])=={"articulation","scale"}
        except Exception:
            for i,frame in enumerate(page.frames):
                try:(OUT/f"failure-frame-{i}.html").write_text(frame.content(),encoding="utf-8")
                except Exception:pass
            page.screenshot(path=str(OUT/"failure.png"),full_page=True)
            (OUT/"failure-body.txt").write_text(page.locator("body").inner_text(),encoding="utf-8")
            raise
        finally:
            browser.close()
except Exception:
    (OUT/"failure.json").write_text(json.dumps({"error":__import__("traceback").format_exc(),"results":results},indent=2),encoding="utf-8")
    raise
finally:
    if os.name=="nt":
        subprocess.run(["taskkill","/PID",str(server.pid),"/T","/F"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
    else:server.terminate()
    log.close()

