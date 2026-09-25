"""BPM round-trip dual-buffer replace: Play → new BPM → Play → back → Play.

Proves audible duration + follow-timeline bar timing change with Tempo, not just
generate_saved / URL churn. Captures __kcApplyTrace reasons per Play.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT)]
for k in ("KC_SHORT_PASS_BARS", "KC_SHORT_PASS_LOOPS", "KC_SHORT_PASS_FORCE", "KC_SHORT_PASS_SECS"):
    os.environ.pop(k, None)

from proof_key_cycle_seamless_8510 import wait_kc_audio
from proof_key_cycle_ux_8510 import click_play, click_playbar, set_cycle_mode
from proof_kc_bpm_feel_scope_8510 import open_advanced_visible, wait_controls_ready
from proof_kc_finish_five_8510 import (
    clear_pause_hold,
    force_commit_bpm,
    mean_bar_seconds,
    wait_idle,
)
from proof_kc_manual_review_gaps_8510 import wav_duration_from_url
from proof_kc_settings_focused_8510 import set_loops, set_practice_key, set_scope_selected_section
from proof_kc_stop_resume_sequence_8510 import open_sheet, set_descending_whole_tone
from walk_creative_backing_matrix import expand_pages_nav, expand_sidebar
from walk_practice_loop_backing import goto_studio

OUT = ROOT / "scripts" / "evidence-key-cycle"
BASE = "http://127.0.0.1:8510"
TRACE = ROOT / "_runtime_key_cycle_8510" / "_play_trace.jsonl"


def audio_snap(page) -> dict:
    return page.evaluate(
        """() => {
          const dual = window.__kcDual || {};
          const a0 = document.getElementById('kc-buf-0');
          const a1 = document.getElementById('kc-buf-1');
          const act = document.getElementById(dual.active === 1 ? 'kc-buf-1' : 'kc-buf-0')
            || [a0, a1].find((el) => el && el.style && el.style.display !== 'none' && el.src)
            || a0 || a1;
          const tl = window.__kcFollowTimeline || [];
          const last = tl.length ? tl[tl.length - 1] : null;
          const unmuted = [a0, a1].filter(
            (a) => a && !a.paused && !a.muted && Number(a.volume || 0) > 0.01
              && Number(a.currentTime || 0) > 0.05
          );
          return {
            src: act ? (act.getAttribute('data-kc-url') || act.src || '') : '',
            currentSrc: act ? String(act.currentSrc || '') : '',
            dur: act ? Number(act.duration) || 0 : 0,
            t: act ? Number(act.currentTime) || 0 : 0,
            paused: act ? !!act.paused : true,
            muted: act ? !!act.muted : true,
            volume: act ? Number(act.volume || 0) : 0,
            ready: act ? Number(act.readyState) || 0 : 0,
            sounding: act
              ? String(act.getAttribute('data-kc-sounding') || window.__kcLastSounding || '')
              : '',
            playingUrl: String(dual.playingUrl || ''),
            active: dual.active,
            unmuted: unmuted.length,
            unmutedIds: unmuted.map((a) => a.id),
            tlEnd: last ? Number(last.end_time || 0) : 0,
            tlLen: tl.length,
            applyTrace: (window.__kcApplyTrace || []).slice(-16),
            remount: (window.__kcRemountLog || []).slice(-8),
          };
        }"""
    )


def clear_traces(page) -> None:
    page.evaluate(
        """() => {
          window.__kcApplyTrace = [];
          window.__kcRemountLog = [];
          // Allow the next forcePlay slot/bridge apply even when Streamlit
          // rewrites an identical arrangement URL payload.
          window.__kcCmdPollSeen = '';
          window.__kcCmdForceArmedUntil = 0;
          window.__kcCmdForceRetryAt = 0;
        }"""
    )


def last_gen_bpm(*, after_offset: int = 0) -> int | None:
    if not TRACE.is_file():
        return None
    raw = TRACE.read_bytes()
    if after_offset > 0:
        raw = raw[after_offset:]
    text = raw.decode("utf-8", errors="replace")
    for line in reversed(text.splitlines()[-80:]):
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if obj.get("event") != "generate_saved":
            continue
        sig = str(obj.get("sig") or "")
        m = re.search(r", (\d+), '4/4'", sig)
        if m:
            return int(m.group(1))
    return None


def trace_size() -> int:
    return TRACE.stat().st_size if TRACE.is_file() else 0


def play_and_measure(page, *, label: str, expect_bpm: int, prev_src: str = "") -> dict:
    clear_pause_hold(page)
    clear_traces(page)
    t0 = time.time()
    # Only count generate_saved lines written after this Play click.
    gen_offset = trace_size()
    gen_before = last_gen_bpm(after_offset=max(0, gen_offset - 4096))
    clicked = click_play(page)
    deadline = time.time() + 160
    snap = audio_snap(page)
    saw_gen = False
    peak_unmuted = 0
    peak_ids: list = []
    live_snap = snap
    replay_clicked = False
    while time.time() < deadline:
        snap = audio_snap(page)
        u = int(snap.get("unmuted") or 0)
        if u > peak_unmuted:
            peak_unmuted = u
            peak_ids = list(snap.get("unmutedIds") or [])
            live_snap = snap
        src = str(snap.get("src") or "")
        dur = float(snap.get("dur") or 0)
        src_ok = bool(src) and (not prev_src or src != prev_src)
        gb = last_gen_bpm(after_offset=gen_offset)
        if gb is not None and abs(int(gb) - int(expect_bpm)) <= 3:
            saw_gen = True
        if (
            snap.get("ready", 0) >= 2
            and dur > 0.5
            and src_ok
            and not snap.get("paused")
            and u == 1
            and (saw_gen or (not prev_src and gb))
        ):
            live_snap = snap
            break
        # Generate finished but buffer still on prior WAV — one ordinary re-Play
        # (not a JS handler fallback) after a short grace period.
        if (
            saw_gen
            and prev_src
            and src == prev_src
            and not replay_clicked
            and time.time() - t0 > 40
        ):
            clear_pause_hold(page)
            clear_traces(page)
            click_play(page)
            replay_clicked = True
        page.wait_for_timeout(400)
    # Final snap in case replace landed just as the loop exited.
    snap = audio_snap(page)
    u = int(snap.get("unmuted") or 0)
    if u >= peak_unmuted and (
        not prev_src or str(snap.get("src") or "") != prev_src
    ):
        if u > 0:
            peak_unmuted = u
            peak_ids = list(snap.get("unmutedIds") or [])
            live_snap = snap
    # Audible proof is during Play — pause mutes buffers by design.
    bar = mean_bar_seconds(page)
    file_secs = wav_duration_from_url(str(live_snap.get("src") or ""))
    reasons = [str(x.get("reason") or "") for x in (live_snap.get("applyTrace") or [])]
    gen_bpm = last_gen_bpm(after_offset=gen_offset)
    gen_matched = gen_bpm is not None and abs(int(gen_bpm) - int(expect_bpm)) <= 3
    try:
        click_playbar(page, "pause")
    except Exception:
        pass
    page.wait_for_timeout(600)
    out = {
        "label": label,
        "expect_bpm": expect_bpm,
        "gen_bpm": gen_bpm,
        "gen_matched": gen_matched,
        "play_clicked": bool(clicked),
        "replay_clicked": bool(replay_clicked),
        "src": str(live_snap.get("src") or ""),
        "currentSrc": str(live_snap.get("currentSrc") or "")[-48:],
        "dur": live_snap.get("dur"),
        "file_secs": file_secs,
        "bar_s": bar,
        "tlEnd": live_snap.get("tlEnd"),
        "tlLen": live_snap.get("tlLen"),
        "unmuted": peak_unmuted,
        "unmutedIds": peak_ids,
        "muted": live_snap.get("muted"),
        "volume": live_snap.get("volume"),
        "paused": live_snap.get("paused"),
        "playingUrl": str(live_snap.get("playingUrl") or "")[-40:],
        "reasons": reasons,
        "has_replace": "replace" in reasons or "set_src_paused_replace" in reasons,
        "has_set_src": "set_src" in reasons or "set_src_paused_replace" in reasons,
        "has_reject": any("reject" in r for r in reasons),
        "has_pause_hold": "pause_hold" in reasons,
        "elapsed_s": round(time.time() - t0, 1),
        "remount": live_snap.get("remount"),
        "gen_before": gen_before,
        "src_changed": bool(prev_src and str(live_snap.get("src") or "") != prev_src),
    }
    print(
        f"{label}: gen={gen_bpm} dur={out['dur']} file={file_secs} bar={bar} "
        f"unmuted={out['unmuted']} muted={out.get('muted')} reasons={reasons} "
        f"src_changed={out['src_changed']} replay={replay_clicked}",
        flush=True,
    )
    return out


def boot(page) -> None:
    page.goto(f"{BASE}/?dev=1", wait_until="domcontentloaded", timeout=180000)
    page.wait_for_timeout(2000)
    clear_pause_hold(page)
    expand_sidebar(page)
    expand_pages_nav(page)
    goto_studio(page, "Songs")
    page.wait_for_timeout(400)
    page.evaluate(
        """() => {
          const t = [...document.querySelectorAll('button,label,div')].find((el) =>
            /Shape of You/i.test(el.innerText || '')
          );
          if (t) t.click();
        }"""
    )
    goto_studio(page, "Backing")
    page.wait_for_timeout(1200)
    set_practice_key(page, "Bm")
    wait_idle(page)
    set_scope_selected_section(page, "Verse")
    set_loops(page, 1)
    wait_idle(page)
    set_cycle_mode(page, True)
    wait_idle(page)
    set_descending_whole_tone(page)
    wait_idle(page)
    open_sheet(page)
    clear_pause_hold(page)


def main() -> int:
    report: dict = {
        "ok": False,
        "revision": "31d363d+ bpm roundtrip replace",
        "browser": {},
        "failures": [],
    }
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        try:
            boot(page)
            wait_controls_ready(page)
            open_advanced_visible(page)

            # 1) Initial Play at song-ish tempo (commit 100 then play)
            c100 = force_commit_bpm(page, 100)
            wait_idle(page)
            report["browser"]["commit_100"] = {
                "ok": c100.get("ok"),
                "canon": c100.get("canon_bpm"),
            }
            if not c100.get("ok") or abs(int(c100.get("canon_bpm") or 0) - 100) > 1:
                report["failures"].append("commit_100")
                raise SystemExit(1)
            try:
                click_playbar(page, "pause")
            except Exception:
                pass
            wait_idle(page)
            # Re-read canon at Play time — remounts can drift ±1–3 from commit.
            from proof_kc_bpm_feel_scope_8510 import read_server as _rs

            def _canon() -> int:
                return int(_rs(page).get("bpm_canon") or 0)

            def _pending() -> bool:
                return bool(
                    page.evaluate(
                        """() => /Pending Play|settings pending Play/i.test(
                          document.body.innerText||''
                        )"""
                    )
                )

            def _ensure_bpm(target: int) -> int:
                """Commit then re-check immediately before Play; recover drift."""
                got = force_commit_bpm(page, int(target))
                wait_idle(page, 8000)
                cur = _canon()
                if abs(cur - int(target)) > 2:
                    got = force_commit_bpm(page, int(target))
                    wait_idle(page, 8000)
                    cur = int(got.get("canon_bpm") or _canon())
                return cur

            expect_a = _canon() or int(c100.get("canon_bpm") or 100)
            if abs(expect_a - 100) > 3:
                expect_a = _ensure_bpm(100)
            a = play_and_measure(page, label="play_100", expect_bpm=expect_a)
            report["browser"]["play_100"] = a

            # 2) Substantial BPM up → Play
            wait_controls_ready(page)
            open_advanced_visible(page)
            expect_b = _ensure_bpm(140)
            page.wait_for_timeout(600)
            pending140 = _pending()
            report["browser"]["commit_140"] = {
                "ok": abs(expect_b - 140) <= 2,
                "canon": expect_b,
                "pending": pending140,
            }
            if abs(expect_b - 140) > 2:
                report["failures"].append("commit_140")
                raise SystemExit(1)
            b = play_and_measure(
                page, label="play_140", expect_bpm=expect_b, prev_src=str(a.get("src") or "")
            )
            report["browser"]["play_140"] = b

            # 3) Back down → Play
            wait_controls_ready(page)
            open_advanced_visible(page)
            expect_c = _ensure_bpm(100)
            page.wait_for_timeout(600)
            pending100 = _pending()
            report["browser"]["commit_100b"] = {
                "ok": abs(expect_c - 100) <= 2,
                "canon": expect_c,
                "pending": pending100,
            }
            if abs(expect_c - 100) > 2:
                report["failures"].append("commit_100b")
                raise SystemExit(1)
            c = play_and_measure(
                page, label="play_100b", expect_bpm=expect_c, prev_src=str(b.get("src") or "")
            )
            report["browser"]["play_100b"] = c

            def pair_ok(slow: dict, fast: dict) -> dict:
                slow_bpm = int(slow.get("gen_bpm") or slow.get("expect_bpm") or 0)
                fast_bpm = int(fast.get("gen_bpm") or fast.get("expect_bpm") or 0)
                if slow_bpm < 40 or fast_bpm < 40 or fast_bpm <= slow_bpm:
                    return {
                        "src_changed": False,
                        "one_audible": False,
                        "delivered": False,
                        "wav_ratio": None,
                        "bar_ratio": None,
                        "expect_ratio": None,
                        "slow_bpm": slow_bpm,
                        "fast_bpm": fast_bpm,
                        "ok": False,
                    }
                expect_r = float(fast_bpm) / float(slow_bpm)
                d_s = float(slow.get("file_secs") or slow.get("dur") or 0)
                d_f = float(fast.get("file_secs") or fast.get("dur") or 0)
                b_s = float(slow.get("bar_s") or 0)
                b_f = float(fast.get("bar_s") or 0)
                wr = (d_s / d_f) if d_s > 1 and d_f > 1 else None
                br = (b_s / b_f) if b_s > 0.2 and b_f > 0.2 else None
                src_changed = bool(slow.get("src") and fast.get("src") and slow["src"] != fast["src"])
                one = (
                    (int(slow.get("unmuted") or 0) <= 1 and int(fast.get("unmuted") or 0) <= 1)
                    and d_s > 1
                    and d_f > 1
                )
                delivered = bool(
                    fast.get("has_set_src")
                    or fast.get("has_replace")
                    or (src_changed and not fast.get("has_reject"))
                )
                ratio_ok = (wr and abs(wr - expect_r) / expect_r < 0.28) or (
                    br and abs(br - expect_r) / expect_r < 0.28
                )
                gen_ok = bool(
                    slow.get("gen_bpm")
                    and fast.get("gen_bpm")
                    and abs(int(slow["gen_bpm"]) - int(slow.get("expect_bpm") or 0)) <= 3
                    and abs(int(fast["gen_bpm"]) - int(fast.get("expect_bpm") or 0)) <= 3
                    and int(fast["gen_bpm"]) - int(slow["gen_bpm"]) >= 25
                )
                return {
                    "src_changed": src_changed,
                    "one_audible": one,
                    "delivered": delivered,
                    "wav_ratio": wr,
                    "bar_ratio": br,
                    "expect_ratio": expect_r,
                    "slow_bpm": slow_bpm,
                    "fast_bpm": fast_bpm,
                    "ok": bool(src_changed and one and delivered and ratio_ok and gen_ok),
                }

            if abs(int(a.get("gen_bpm") or 0) - int(a.get("expect_bpm") or 0)) > 3:
                report["failures"].append("play_100_wrong_gen_bpm")
            if abs(int(b.get("gen_bpm") or 0) - int(b.get("expect_bpm") or 0)) > 3:
                report["failures"].append("play_140_wrong_gen_bpm")
            if abs(int(c.get("gen_bpm") or 0) - int(c.get("expect_bpm") or 0)) > 3:
                report["failures"].append("play_100b_wrong_gen_bpm")

            up = pair_ok(a, b)
            down = pair_ok(c, b)
            report["browser"]["up_100_to_140"] = up
            report["browser"]["down_140_to_100"] = down

            if not up.get("ok"):
                report["failures"].append("replace_100_to_140")
            if not down.get("ok"):
                report["failures"].append("replace_140_to_100")
            if b.get("has_reject") and not (b.get("has_set_src") or b.get("has_replace")):
                report["failures"].append("play_140_rejected_without_set_src")
            if c.get("has_reject") and not (c.get("has_set_src") or c.get("has_replace")):
                report["failures"].append("play_100b_rejected_without_set_src")

            report["ok"] = not report["failures"]
        except SystemExit:
            pass
        except Exception as exc:
            report["error"] = repr(exc)
            report["failures"].append("exception")
        finally:
            try:
                set_cycle_mode(page, False)
                wait_idle(page)
            except Exception:
                pass
            browser.close()

    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "bpm_roundtrip_replace_8510.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2)[:5000])
    print(f"wrote {path} ok={report.get('ok')}")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
