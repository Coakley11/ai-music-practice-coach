"""Launch the real Music app locally, with paid AMI transport blocked and optional read-only evidence."""
from __future__ import annotations
import argparse, copy, functools, json, os, sys, time
from dataclasses import asdict
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
parser=argparse.ArgumentParser()
parser.add_argument("--port",type=int,default=8596)
parser.add_argument("--data-dir",type=Path,required=True)
parser.add_argument("--evidence-dir",type=Path)
parser.add_argument("--run-id",default="local")
args=parser.parse_args()
os.environ["AMI_CLAUDE_ENABLED"]="false"
os.environ["AMI_CLAUDE_INTERPRET_ENABLED"]="false"
os.environ["MUSIC_APP_DATA_DIR"]=str(args.data_dir.resolve())
from music_coach_ami.claude_client import AnthropicTransport
def forbidden(*a,**kw):
    if args.evidence_dir:
        args.evidence_dir.mkdir(parents=True,exist_ok=True)
        (args.evidence_dir/"forbidden-api-call.txt").write_text("Blocked AMI transport invocation",encoding="utf-8")
    raise RuntimeError("Paid AMI API disabled for local acceptance")
AnthropicTransport.complete=forbidden
if args.evidence_dir:
    from music_coach_ami import pipeline, warmup_plan
    from instrument_transposition import SELECTED_TRANSPOSING_INSTRUMENT_KEY
    settings_keys=("instrument","level","focus",SELECTED_TRANSPOSING_INSTRUMENT_KEY,"_suite_active_workspace_id","display_key","concert_key","backing_track_bpm")
    original=pipeline.run_coach_submit
    @functools.wraps(original)
    def observed(question,session_state=None,*,ami_ctx=None):
        before_settings={k:session_state.get(k) for k in settings_keys} if session_state is not None else {}
        result=original(question,session_state,ami_ctx=ami_ctx)
        # Context-only probes use an empty mapping; only capture the real app session.
        if session_state is not None and session_state.get("_suite_active_workspace_id"):
            plan=warmup_plan.current(session_state)
            record={"run_id":args.run_id,"time_ns":time.time_ns(),"question":question,
                    "response":asdict(result[1]) if result[1] else None,
                    "trumpet_fingering_context":copy.deepcopy(session_state.get("_ami_conv_trumpet_fingering")),"fingering_context":copy.deepcopy(session_state.get("_ami_conv_fingering")),"plan":copy.deepcopy(plan),"history":warmup_plan.history(session_state),"before_settings":before_settings,
                    "settings":{k:session_state.get(k) for k in settings_keys}}
            args.evidence_dir.mkdir(parents=True,exist_ok=True)
            (args.evidence_dir/"last-submit.json").write_text(json.dumps(record,default=str,indent=2),encoding="utf-8")
            with (args.evidence_dir/"submits.jsonl").open("a",encoding="utf-8") as f: f.write(json.dumps(record,default=str)+"\n")
        return result
    pipeline.run_coach_submit=observed
    import applied_math_return_insight as card
    def record_card(phase, st, insight=None):
        pending=insight if isinstance(insight,dict) else st.session_state.get(card.SESSION_PENDING_KEY)
        if isinstance(pending,dict):
            event={"phase":phase,"run_id":args.run_id,"time_ns":time.time_ns(),"question":pending.get("question"),"insight_id":pending.get("insight_id"),"question_id":pending.get("question_id")}
            with (args.evidence_dir/"cards.jsonl").open("a",encoding="utf-8") as f:f.write(json.dumps(event)+"\n")
    stage_original=card.stage_pending_insight
    @functools.wraps(stage_original)
    def observed_stage(st,insight,**kw):
        result=stage_original(st,insight,**kw)
        record_card("staged",st)
        return result
    card.stage_pending_insight=observed_stage
    render_original=card.render_applied_math_insight_panel
    @functools.wraps(render_original)
    def observed_render(st,**kw):
        record_card("render_started",st,kw.get("insight"))
        result=render_original(st,**kw)
        record_card("render_completed",st,kw.get("insight"))
        return result
    card.render_applied_math_insight_panel=observed_render
from streamlit.web.cli import main
os.chdir(ROOT)
sys.argv=["streamlit","run",str(ROOT/"streamlit_music_practice_app.py"),f"--server.port={args.port}","--server.address=127.0.0.1","--server.headless=true","--browser.gatherUsageStats=false"]
main()
