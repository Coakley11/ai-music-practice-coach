"""Issue 64 slice 5: the whole point of the feature, driven through a real browser.

Record against one song in one key, go and work on another song in another key, come
back, find the right project, reopen it and keep overdubbing - without losing a take or
having one quietly reassigned. Everything below is that sentence, broken into gates.

Layers are supplied through each slot's **file uploader** rather than the microphone,
because a headless browser has no instrument in front of it. The uploader is the same
code path that stores a take, stamps its recording key and marks it unsaved, so what is
exercised is the real thing. The WAVs are generated here and are disposable.

Usage:
  MUSIC_APP_DATA_DIR=<disposable dir> streamlit run streamlit_music_practice_app.py \
      --server.port 8561
  python scripts/_accept_issue64_multitrack_projects.py http://127.0.0.1:8561
"""

from __future__ import annotations

import json
import math
import re
import struct
import sys
import tempfile
import wave
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT))

from walk_creative_backing_matrix import (  # noqa: E402
    click_nav,
    expand_sidebar,
    wait_idle,
)
from walk_guitar_shape_key import pick_song  # noqa: E402
from _walk_core_key_coherence import set_songs_practice_key  # noqa: E402
from _walk_custom_practice_key import pk_val  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8561"
OUT = SCRIPTS / "evidence-issue64"
OUT.mkdir(parents=True, exist_ok=True)
AUDIO = Path(tempfile.mkdtemp(prefix="issue64-takes-"))

GATES: dict[str, bool] = {}
NOTES: list[str] = []


def log(msg: str) -> None:
    NOTES.append(msg)
    print(msg.encode("ascii", "replace").decode("ascii"), flush=True)


def mark(gate: str, ok: bool, detail: str = "") -> None:
    GATES[gate] = bool(ok)
    log(f"[{'PASS' if ok else 'FAIL'}] {gate}  {detail}")


def settle(page: Page, seconds: float = 2.5) -> None:
    wait_idle(page, int(seconds * 1000))


def shot(page: Page, name: str) -> str:
    body = page.inner_text("body") or ""
    (OUT / f"{name}.txt").write_text(body[:30000], encoding="utf-8")
    page.screenshot(path=str(OUT / f"{name}.png"), full_page=True)
    return body


def low(s: str) -> str:
    return (s or "").lower().replace("♯", "#").replace("♭", "b")


def key_token(s: str) -> str:
    """Normalise a key as the app may word it, so "B♭ major" matches "Bb".

    The sidebar spells the key differently from page to page - the Backing page says
    "B♭ major" where elsewhere it is "Bb" - and an exact string compare read that
    as the wrong key. Minor is kept as a suffix so Bb and Bbm stay distinct.
    """
    t = low(s).strip()
    if t.endswith(" minor"):
        return t[: -len(" minor")].strip().replace(" ", "") + "m"
    if t.endswith(" major"):
        return t[: -len(" major")].strip().replace(" ", "")
    return t.replace(" ", "")


# --------------------------------------------------------------------------
# Disposable audio
# --------------------------------------------------------------------------
def make_wav(name: str, *, freq: float = 440.0, seconds: float = 1.0,
             rate: int = 22050) -> Path:
    """A short distinguishable tone. Two calls at the same length differ in content,
    which is exactly the case the fingerprint has to notice."""
    path = AUDIO / name
    frames = bytearray()
    for i in range(int(rate * seconds)):
        value = int(12000 * math.sin(2 * math.pi * freq * i / rate))
        frames += struct.pack("<h", value)
    with wave.open(str(path), "wb") as fh:
        fh.setnchannels(1)
        fh.setsampwidth(2)
        fh.setframerate(rate)
        fh.writeframes(bytes(frames))
    return path


# --------------------------------------------------------------------------
# Page helpers
# --------------------------------------------------------------------------
def wait_for_app(page: Page, timeout_s: float = 120.0) -> bool:
    """Wait until the app has actually rendered something.

    A freshly started server takes a while over its first page, and a fixed delay is not
    a wait: one run opened the page, read an 11-character body and declared the app up,
    then failed to find the song picker that had not been drawn yet.
    """
    waited = 0.0
    while waited < timeout_s:
        body = page.inner_text("body") or ""
        if len(body.strip()) > 400 and "PAGES" in body.upper():
            return True
        settle(page, 3)
        waited += 3
    return False


def on_multitrack(page: Page) -> bool:
    """The page identifies itself by its own title; ``data-studio-page`` is not on body."""
    body = page.inner_text("body") or ""
    return "multitrack session workspace" in low(body)


def goto_multitrack(page: Page) -> bool:
    if on_multitrack(page):
        return True
    click_nav(page, "Multitrack")
    settle(page, 4)
    return on_multitrack(page)


def slot_class(slot: str) -> str:
    """Streamlit's own key-to-class rewrite: spaces and slashes become hyphens."""
    return slot.replace(" ", "-").replace("/", "-")


def expand_layer(page: Page, slot: str) -> bool:
    """Open this layer's controls. Reports whether it is actually open.

    The click matters beyond opening the panel: Streamlit hands a queued upload to the
    script on the next real interaction, so a run that merely waited after dropping the
    file watched a slot it had already filled report itself empty.

    Driven through a dispatched event rather than ``locator.click``, which times out on
    a busy machine when the summary is scrolled out of view or briefly covered - and
    whose failure was silent enough to look like a broken upload.
    """
    opened = page.evaluate(
        """(slot) => {
          const want = ('Layer controls — ' + slot).toLowerCase();
          const all = [...document.querySelectorAll('details')];
          const el = all.find((d) => {
            const sum = d.querySelector('summary');
            return sum && (sum.innerText || '').toLowerCase().includes(want);
          });
          if (!el) return 'not-found';
          const sum = el.querySelector('summary');
          sum.scrollIntoView({block: 'center'});
          if (!el.hasAttribute('open')) {
            ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click'].forEach((t) => {
              sum.dispatchEvent(new MouseEvent(t, {bubbles: true, cancelable: true, view: window}));
            });
          } else {
            // Already open: a click would close it, so nudge the page instead so the
            // queued upload still gets a frontend interaction to ride in on.
            sum.dispatchEvent(new MouseEvent('mousemove', {bubbles: true, view: window}));
          }
          return el.hasAttribute('open') ? 'open' : 'clicked';
        }""",
        slot,
    )
    settle(page, 3)
    state = page.evaluate(
        """(slot) => {
          const want = ('Layer controls — ' + slot).toLowerCase();
          const all = [...document.querySelectorAll('details')];
          const el = all.find((d) => {
            const sum = d.querySelector('summary');
            return sum && (sum.innerText || '').toLowerCase().includes(want);
          });
          return el ? (el.hasAttribute('open') ? 'open' : 'closed') : 'not-found';
        }""",
        slot,
    )
    log(f"  {slot}: layer controls {opened} -> {state}")
    return state == "open"


def slot_state(page: Page, slot: str) -> str:
    """Whether this slot reports a take, read from the page's own status line.

    Each layer header prints the slot name then "HAS AUDIO" or "EMPTY", so the state is
    read where the musician reads it rather than inferred from a tool call succeeding.
    """
    body = page.inner_text("body") or ""
    lines = [ln.strip() for ln in body.splitlines()]
    for i, line in enumerate(lines):
        if line == slot:
            for nxt in lines[i + 1:i + 4]:
                if "HAS AUDIO" in nxt:
                    return "has_audio"
                if "EMPTY" in nxt:
                    return "empty"
    return "unknown"


def slot_uploader(page: Page, slot: str, idx: int):
    """This slot's own dropzone input, found by where it sits in the DOM.

    Three approaches were tried. Indexing every dropzone on the page by slot order
    worked until a save added an uploader earlier in the DOM, after which the Guitar
    take went nowhere. Scoping by Streamlit's key class matched an element, but not the
    input Streamlit actually listens to - the file registered nowhere at all. What is
    reliable is the structure that was verified by hand: each uploader lives inside its
    own "Layer controls - <slot>" expander. So the index is computed in the browser from
    that containment, and used against the same dropzone list that did work.
    """
    found = page.evaluate(
        """(slot) => {
          const want = ('Layer controls — ' + slot).toLowerCase();
          const details = [...document.querySelectorAll('details')].find((d) => {
            const sum = d.querySelector('summary');
            return sum && (sum.innerText || '').toLowerCase().includes(want);
          });
          if (!details) return -1;
          const all = [...document.querySelectorAll(
            '[data-testid="stFileUploaderDropzoneInput"]')];
          return all.findIndex((el) => details.contains(el));
        }""",
        slot,
    )
    inputs = page.locator('[data-testid="stFileUploaderDropzoneInput"]')
    if isinstance(found, int) and found >= 0:
        return inputs.nth(found)
    if idx < inputs.count():
        log(f"  {slot}: not found by containment, falling back to uploader #{idx}")
        return inputs.nth(idx)
    return None


def upload_layer(page: Page, slot: str, wav: Path) -> bool:
    """Put a take into one slot through its uploader, and wait for the slot to say so.

    The uploaders carry no text of their own, so they are addressed by position - the
    slot order the page renders them in - and success is read from the slot's own
    "HAS AUDIO" line rather than from the tool call returning.
    """
    try:
        from multitrack_slots import MULTITRACK_SLOTS

        idx = list(MULTITRACK_SLOTS).index(slot)
    except Exception as exc:
        log(f"  unknown slot {slot!r}: {exc}")
        return False
    # The uploader lives inside this layer's "Layer controls" expander, and the dropzone
    # has to be live on the frontend before it will take a file. Opening the expander is
    # not enough on the first render: the file goes nowhere and the slot sits empty,
    # which is how an earlier run reported an empty slot it had just uploaded to. So the
    # drop is retried, re-querying the input each time.
    for attempt in range(1, 4):
        if not expand_layer(page, slot) and attempt == 3:
            log(f"  {slot}: layer controls never opened")
        settle(page, 2)
        target = slot_uploader(page, slot, idx)
        if target is None:
            log(f"  no uploader found for {slot}")
            return False
        try:
            target.set_input_files(str(wav))
        except Exception as exc:
            log(f"  upload into {slot} failed: {exc}")
            return False
        for _ in range(4):
            settle(page, 3)
            if slot_state(page, slot) == "has_audio":
                log(f"  {slot}: take registered (attempt {attempt})")
                return True
        # The take usually *has* landed by now and the layer header simply has not
        # caught up: only the first upload of a browser session re-renders the status
        # line, and a reload reveals the rest. Reload to observe rather than conclude
        # the upload failed - an earlier run called three landed takes "empty".
        log(f"  {slot}: status still empty, reloading to check")
        try:
            page.reload(wait_until="domcontentloaded")
            settle(page, 8)
            goto_multitrack(page)
        except Exception as exc:
            log(f"  reload failed: {exc}")
        if slot_state(page, slot) == "has_audio":
            log(f"  {slot}: take was registered, the page had not re-rendered")
            return True
    log(f"  {slot}: still {slot_state(page, slot)!r} after 3 attempts")
    return False


def layer_has_audio(page: Page, slot: str) -> bool:
    return slot_state(page, slot) == "has_audio"


def prompt_visible(page: Page) -> bool:
    body = low(page.inner_text("body") or "")
    return "would affect your current recording" in body


def prompt_buttons(page: Page):
    """Only the held-move prompt's own buttons.

    Scoped by its widget keys. The Project Library has its own "Save Changes" and
    "Save as New Project" buttons, and a run that matched on button text alone reported
    those as the prompt's choices on a page where no prompt existed at all.
    """
    return page.locator('[class*="st-key-mt_switch_"] button')


def prompt_choices(page: Page) -> list[str]:
    if not prompt_visible(page):
        return []
    loc = prompt_buttons(page)
    out = []
    for i in range(loc.count()):
        try:
            text = (loc.nth(i).inner_text() or "").strip()
        except Exception:
            continue
        if text and text not in out:
            out.append(text)
    return out


def answer_prompt(page: Page, choice: str) -> bool:
    loc = prompt_buttons(page)
    for i in range(loc.count()):
        el = loc.nth(i)
        try:
            if (el.inner_text() or "").strip() != choice:
                continue
            el.scroll_into_view_if_needed()
            el.click(timeout=8000)
            settle(page, 5)
            return True
        except Exception:
            continue
    log(f"  prompt choice {choice!r} not clickable; offered {prompt_choices(page)}")
    return False


def sidebar_pk(page: Page) -> str:
    return pk_val(page)


def wait_for_sidebar_key(page: Page, expect: str, *, timeout_s: float = 60.0) -> str:
    """Poll the sidebar key until it reaches `expect`, nudging a rerun between looks.

    A project load commits its key to the durable store and *requests* a display key for
    the next render - the hydration-safe route, which deliberately does not touch the
    widget already on screen. So the sidebar catches up a rerun or two later, and reading
    it straight after the click reads the old key. Three runs scored the key restore as
    broken on exactly that, and the later mixed-key gate then saw the restored "Bb" and
    reported it as a key invented out of nowhere.

    The nudges are counted, because "stable across reruns" means something different if
    the key only appears after a navigation.
    """
    want = key_token(expect)
    waited = 0.0
    nudges = 0
    seen = sidebar_pk(page)
    while waited < timeout_s:
        if key_token(seen) == want:
            log(f"  sidebar key reached {seen!r} after {waited:.0f}s, "
                f"{nudges} navigation nudge(s)")
            return seen
        settle(page, 3)
        waited += 3
        if waited % 9 == 0:
            # A real navigation. goto_multitrack returns immediately when already on
            # the page, so using it here produced no script run at all - which made two
            # earlier measurements report a key that never arrived when in fact nothing
            # had asked the app to re-render.
            click_nav(page, "Backing")
            settle(page, 3)
            click_nav(page, "Multitrack")
            nudges += 1
        seen = sidebar_pk(page)
    log(f"  sidebar key still {seen!r} after {waited:.0f}s, {nudges} nudge(s)")
    return seen


_LEADING_GLYPHS = re.compile(r"^[^0-9A-Za-z]+")


def click_exact(page: Page, label: str) -> bool:
    """Click the button whose whole label is this, ignoring any leading icon.

    "New Project" as a substring also matches "Save New Project" and "Save as New
    Project": an earlier run meant to press New Project, pressed Save instead, and left
    three stray projects in the library before anyone noticed.
    """
    buttons = page.locator("button")
    for i in range(buttons.count()):
        el = buttons.nth(i)
        try:
            text = (el.inner_text() or "").strip()
        except Exception:
            continue
        if text != label and _LEADING_GLYPHS.sub("", text).strip() != label:
            continue
        try:
            el.scroll_into_view_if_needed()
            el.click(timeout=8000)
            settle(page, 4)
            return True
        except Exception:
            continue
    return False


def click_load_for_project(page: Page, *, wants: str, avoids: str = "") -> bool:
    """Load the project row whose own summary says what we are looking for.

    Clicking the first "Load Project" on the page is not the same as loading a chosen
    project. This run saves two projects for the same song - one recorded in B flat and
    one genuinely mixed across three keys - and the library, ranking for a song whose
    live key matches neither, put the mixed one first. The key gate then "failed" by
    loading a mixed-key project and correctly not restoring a single key from it.
    """
    index = page.evaluate(
        """([wants, avoids]) => {
          const buttons = [...document.querySelectorAll('button')].filter(
            (b) => (b.innerText || '').trim().replace(/^[^0-9A-Za-z]+/, '') === 'Load Project');
          for (let i = 0; i < buttons.length; i++) {
            let node = buttons[i];
            for (let up = 0; up < 6 && node; up++) node = node.parentElement;
            const text = (node ? node.innerText : '') || '';
            if (!text.includes(wants)) continue;
            if (avoids && text.includes(avoids)) continue;
            return i;
          }
          return -1;
        }""",
        [wants, avoids],
    )
    if not isinstance(index, int) or index < 0:
        log(f"  no Load Project row matching {wants!r} (avoiding {avoids!r})")
        return False
    buttons = page.get_by_role("button", name="Load Project", exact=False)
    if index >= buttons.count():
        return False
    try:
        buttons.nth(index).scroll_into_view_if_needed()
        buttons.nth(index).click(timeout=8000)
        settle(page, 6)
        return True
    except Exception as exc:
        log(f"  clicking the matched Load Project failed: {exc}")
        return False


def open_project_library(page: Page) -> bool:
    loc = page.locator("details").filter(has_text="Project Library")
    for i in range(loc.count()):
        el = loc.nth(i)
        try:
            if el.get_attribute("open") is None:
                el.locator("summary").first.click(timeout=5000)
                settle(page, 3)
            return True
        except Exception:
            continue
    return False


# --------------------------------------------------------------------------
# Gates
# --------------------------------------------------------------------------
def gate_setup(page: Page) -> bool:
    page.goto(URL, wait_until="domcontentloaded")
    settle(page, 4)
    ready = wait_for_app(page)
    body = shot(page, "01-home")
    mark("G1 app renders", ready and len(body.strip()) > 400, f"{len(body)} chars")
    ok = pick_song(page, NOTES, "All the Things You Are", "jazz")
    settle(page, 3)
    mark("G2 song selected", bool(ok))
    set_songs_practice_key(page, "Bb")
    settle(page, 3)
    pk = sidebar_pk(page)
    mark("G3 practice key Bb", key_token(pk) == "bb", f"sidebar={pk!r}")
    return bool(ok)


def gate_first_take(page: Page) -> bool:
    if not goto_multitrack(page):
        mark("G4 multitrack page", False)
        return False
    mark("G4 multitrack page", True)
    wav = make_wav("flute-bb-take1.wav", freq=466.0, seconds=1.0)
    ok = upload_layer(page, "Sax / winds", wav)
    body = shot(page, "02-first-take")
    mark("G5 take uploaded", ok, f"slot={slot_state(page, 'Sax / winds')}")
    return ok


def gate_key_change_is_held(page: Page) -> bool:
    """The core protection: an unsaved take must stop a Practice Key change."""
    before = sidebar_pk(page)
    set_songs_practice_key(page, "E")
    settle(page, 4)
    held = prompt_visible(page)
    choices = prompt_choices(page)
    shot(page, "03-key-change-held")
    mark("G6 key change held", held, f"choices={choices}")
    mark("G7 save-changes not offered for an unsaved take",
         held and "Save Changes" not in choices, f"choices={choices}")
    if not held:
        return False
    answer_prompt(page, "Cancel")
    after = sidebar_pk(page)
    shot(page, "04-after-cancel")
    mark("G8 cancel restores the key", key_token(after) == key_token(before),
         f"{before!r} -> {after!r}")
    # Setting the key is done from the Songs page, which is where the prompt appeared -
    # good evidence that the sidebar prompt reaches every page, but it means the layer
    # status has to be read back on the Multitrack page, not here.
    still_open = prompt_visible(page)
    goto_multitrack(page)
    kept = layer_has_audio(page, "Sax / winds")
    mark("G9 cancel keeps the take", kept and not still_open,
         f"sax={slot_state(page, 'Sax / winds')} prompt_open={still_open}")
    return True


def gate_save_through_prompt(page: Page) -> bool:
    """Save as New Project from the prompt, then the move goes ahead."""
    set_songs_practice_key(page, "E")
    settle(page, 4)
    if not prompt_visible(page):
        mark("G10 prompt reappears for the same change", False)
        return False
    mark("G10 prompt reappears for the same change", True)
    ok = answer_prompt(page, "Save as New Project")
    settle(page, 6)
    body = shot(page, "05-after-save-and-switch")
    pk = sidebar_pk(page)
    mark("G11 save then switch", ok and not prompt_visible(page), f"key now {pk!r}")
    mark("G12 key actually changed after saving", key_token(pk).startswith("e"), f"key={pk!r}")
    # The Project Library lives on the Multitrack page; the key was changed from the
    # Songs page, so go back before looking for it.
    goto_multitrack(page)
    open_project_library(page)
    lib = shot(page, "05b-library-after-save")
    mark("G13 project recorded",
         "Load Project" in lib or "Currently loaded" in lib,
         "library lists a saved row")
    return bool(ok)


def gate_second_song(page: Page) -> bool:
    ok = pick_song(page, NOTES, "Eleanor Rigby", "pop")
    settle(page, 4)
    held = prompt_visible(page)
    mark("G14 clean switch is not interrupted", not held)
    if held:
        answer_prompt(page, "Discard")
    set_songs_practice_key(page, "Em")
    settle(page, 3)
    if not goto_multitrack(page):
        return False
    wav = make_wav("guitar-em.wav", freq=330.0, seconds=1.0)
    ok_up = upload_layer(page, "Guitar", wav)
    shot(page, "06-second-song-take")
    mark("G15 second song take uploaded", ok_up)
    # Save it, so the library holds two projects. Without a second row there is nothing
    # to Load, and the load-guard gates were failing on their own setup rather than on
    # the guard: "Load Project" never appears beside the project that is already open.
    open_project_library(page)
    if click_exact(page, "Save as New Project") or click_exact(page, "Save New Project"):
        settle(page, 8)
        mark("G15b second project saved", True)
    else:
        mark("G15b second project saved", False, "no save button found")
    return ok_up


def gate_library_shows_both(page: Page) -> bool:
    open_project_library(page)
    body = shot(page, "07-library")
    has_key_label = any(t in body for t in ("Bb", "B♭", "Recording key"))
    mark("G16 library lists projects with a key label", has_key_label)
    # The project just saved is legitimately the open one. What must not happen is a
    # *different* project opening on its own, so every other row must still offer Load.
    mark("G17 another project is offered, not opened", "Load Project" in body)
    return True


def gate_new_project_is_held(page: Page) -> bool:
    """Starting a new project clears the workspace, so it must ask first."""
    if not goto_multitrack(page):
        return False
    # The guard only fires when something would be lost, so give it something. After the
    # earlier save nothing was at risk and the prompt correctly stayed away - which an
    # earlier run scored as a failure of the guard rather than of its own setup.
    wav = make_wav("extra-take.wav", freq=294.0, seconds=1.0)
    if not upload_layer(page, "Extra layer", wav):
        mark("G20 new project held", False, "could not create unsaved work to protect")
        return False
    open_project_library(page)
    if not click_exact(page, "New Project"):
        mark("G20 new project held", False, "New Project button not found")
        return False
    settle(page, 4)
    held = prompt_visible(page)
    shot(page, "09-new-project-held")
    mark("G20 new project held", held, f"choices={prompt_choices(page)}")
    if held:
        answer_prompt(page, "Cancel")
        mark("G21 cancel keeps the layers",
             slot_state(page, "Sax / winds") == "has_audio"
             or slot_state(page, "Guitar") == "has_audio")
    return held


def gate_load_is_held(page: Page) -> bool:
    """Loading a project replaces the workspace, so it must ask first too."""
    open_project_library(page)
    body = page.inner_text("body") or ""
    if "Load Project" not in body:
        mark("G22 project load held", False, "no loadable row in the library")
        return False
    before_sax = slot_state(page, "Sax / winds")
    if not click_exact(page, "Load Project"):
        mark("G22 project load held", False, "Load Project click failed")
        return False
    settle(page, 5)
    held = prompt_visible(page)
    shot(page, "10-load-held")
    mark("G22 project load held", held, f"choices={prompt_choices(page)}")
    if held:
        answer_prompt(page, "Cancel")
        after_sax = slot_state(page, "Sax / winds")
        mark("G23 cancel does not load", after_sax == before_sax,
             f"{before_sax} -> {after_sax}")
    return held


def gate_return_and_resume(page: Page) -> bool:
    """The twelve-step point of the feature: come back and carry on overdubbing."""
    # Clear the bench deliberately so the load is a real restore, not what is already here.
    open_project_library(page)
    if click_exact(page, "New Project"):
        settle(page, 4)
        if prompt_visible(page):
            answer_prompt(page, "Discard")
            settle(page, 4)
    pick_song(page, NOTES, "All the Things You Are", "jazz")
    settle(page, 4)
    if prompt_visible(page):
        answer_prompt(page, "Discard")
    goto_multitrack(page)
    open_project_library(page)
    body = shot(page, "11-back-at-song-one")
    mark("G24 the project is listed for this song again",
         "Load Project" in body or "Currently loaded" in body)

    # The B flat project specifically, not whichever row the library ranked first.
    if not click_load_for_project(page, wants="Bb", avoids="Mixed keys"):
        mark("G25 project loads on an explicit click", False,
             "no single-key Bb row offered")
        return False
    settle(page, 8)
    if prompt_visible(page):                      # nothing should be at risk now
        mark("G25 project loads on an explicit click", False,
             "held although the workspace was cleared")
        answer_prompt(page, "Discard")
        settle(page, 6)
    body = shot(page, "12-after-load")
    restored = slot_state(page, "Sax / winds") == "has_audio"
    mark("G25 project loads on an explicit click", restored,
         f"sax={slot_state(page, 'Sax / winds')}")
    pk = wait_for_sidebar_key(page, "Bb")
    mark("G26 the recording key came back, not the live key", key_token(pk) == "bb",
         f"key={pk!r}")

    # A restored project is saved, so moving on must not be interrupted.
    mark("G27 a restored project is not reported as unsaved", not prompt_visible(page))

    # The key has to survive more than the render that set it. A store-backed commit
    # should hold across reruns and navigation; a widget poke would not.
    if key_token(pk) == "bb":
        click_nav(page, "Backing")
        settle(page, 5)
        after_nav = sidebar_pk(page)
        goto_multitrack(page)
        settle(page, 4)
        back_again = sidebar_pk(page)
        shot(page, "12b-key-after-navigation")
        mark("G29 the restored key survives page navigation",
             key_token(after_nav) == "bb" and key_token(back_again) == "bb",
             f"backing={after_nav!r} multitrack={back_again!r}")

        page.reload(wait_until="domcontentloaded")
        settle(page, 10)
        wait_for_app(page)
        after_reload = sidebar_pk(page)
        shot(page, "12c-key-after-reload")
        mark("G30 the restored key survives a reload",
             key_token(after_reload) == "bb", f"key={after_reload!r}")
    return restored


def gate_mixed_key_project(page: Page) -> bool:
    """A project recorded across several keys must not be given one invented key."""
    goto_multitrack(page)
    open_project_library(page)
    body = page.inner_text("body") or ""
    if "Mixed keys" not in body:
        mark("G31 a mixed-key project is labelled as mixed", False,
             "no mixed-key project in the library to check")
        return False
    mark("G31 a mixed-key project is labelled as mixed", True)

    # The label must name the keys rather than pick one, and the layers must be listed.
    import re as _re

    labels = _re.findall(r"Mixed keys \(([^)]*)\)", body)
    named = labels[0] if labels else ""
    mark("G32 the mixed label names more than one key",
         len([k for k in named.split(",") if k.strip()]) > 1, f"label={named!r}")

    listing = shot(page, "14-library-before-mixed-load")
    mark("G34 the individual recorded keys are shown in the listing",
         "Guitar - " in listing or "saxophone (Eb) - " in listing,
         "per-layer instrument - key lines present")

    # Let whatever the previous gate committed finish landing, or its key gets blamed
    # on this load.
    settle(page, 4)
    goto_multitrack(page)
    before = sidebar_pk(page)
    if not click_load_for_project(page, wants="Mixed keys"):
        mark("G33 loading a mixed project invents no key", False, "could not load it")
        return False
    settle(page, 10)
    goto_multitrack(page)
    after = sidebar_pk(page)
    shot(page, "15-mixed-key-loaded")
    mark("G33 loading a mixed project invents no key", key_token(after) == key_token(before),
         f"{before!r} -> {after!r} (unchanged is correct)")
    return True


def gate_equal_length_rerecord(page: Page) -> bool:
    """A second take of the same length is a change, and has to be noticed."""
    first = make_wav("retake-a.wav", freq=466.0, seconds=1.0)
    second = make_wav("retake-b.wav", freq=392.0, seconds=1.0)
    assert first.stat().st_size == second.stat().st_size, "fixture lengths differ"
    log(f"  both takes are {first.stat().st_size} bytes")
    goto_multitrack(page)
    if not upload_layer(page, "Piano / Keys", first):
        mark("G28 equal-length re-record detected", False, "first take did not land")
        return False
    open_project_library(page)
    if click_exact(page, "Save Changes"):
        settle(page, 6)
    # Re-record the same slot with different audio of identical length.
    if not upload_layer(page, "Piano / Keys", second):
        mark("G28 equal-length re-record detected", False, "second take did not land")
        return False
    set_songs_practice_key(page, "F")
    settle(page, 4)
    held = prompt_visible(page)
    shot(page, "13-equal-length-retake")
    mark("G28 equal-length re-record detected", held,
         "a same-length retake still counts as an unsaved change")
    if held:
        answer_prompt(page, "Cancel")
    return held


def gate_mobile(page: Page, width: int) -> bool:
    page.set_viewport_size({"width": width, "height": 844})
    settle(page, 3)
    body = shot(page, f"08-mobile-{width}")
    scrolls = page.evaluate(
        "() => document.documentElement.scrollWidth > document.documentElement.clientWidth"
    )
    mark(f"G18-{width} no horizontal scroll", not scrolls)
    mark(f"G19-{width} page still renders", len(body.strip()) > 200)
    page.set_viewport_size({"width": 1400, "height": 900})
    settle(page, 2)
    return not scrolls


def main() -> int:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        page.set_default_timeout(20000)
        try:
            gate_setup(page)
            if gate_first_take(page):
                gate_key_change_is_held(page)
                gate_save_through_prompt(page)
                gate_second_song(page)
                gate_library_shows_both(page)
                gate_new_project_is_held(page)
                gate_load_is_held(page)
                gate_return_and_resume(page)
                gate_mixed_key_project(page)
                gate_equal_length_rerecord(page)
            for width in (390, 360):
                gate_mobile(page, width)
        finally:
            shot(page, "99-final")
            browser.close()

    report = {
        "url": URL,
        "gates": GATES,
        "passed": sum(1 for v in GATES.values() if v),
        "failed": sorted(k for k, v in GATES.items() if not v),
        "notes": NOTES,
    }
    (OUT / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    log(f"\n{report['passed']}/{len(GATES)} gates passed")
    if report["failed"]:
        log("FAILED: " + ", ".join(report["failed"]))
    return 0 if not report["failed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
