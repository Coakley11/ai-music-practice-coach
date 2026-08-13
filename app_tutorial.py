"""Musician-facing guided tutorial for the music practice studio.

Describes the real current product on ``dev`` — not developer internals, and not
feature-branch-only AMI capabilities.
"""

from __future__ import annotations

import html
from typing import Any, Callable

TUTORIAL_DISMISSED_KEY = "tutorial_dismissed"
TUTORIAL_OPEN_KEY = "tutorial_open"
TUTORIAL_STEP_KEY = "tutorial_step"
TUTORIAL_DISMISS_CHECKBOX_KEY = "tutorial_dismiss_checkbox"

# Valid studio page ids that tutorial "Open …" buttons may navigate to.
_VALID_NAV_PAGE_IDS = frozenset(
    {
        "practice",
        "picker",
        "backing",
        "custom",
        "composer",
        "creative",
        "multitrack",
        "analysis",
        "log",
        "openai",
    }
)

TUTORIAL_STEPS: list[dict[str, Any]] = [
    {
        "id": "welcome",
        "page_id": "",
        "icon": "🎵",
        "title": "What this app is for",
        "summary": (
            "A connected practice workspace: choose music, set your setup and key, "
            "practice with focused tools, create and improvise, record, get feedback, "
            "and come back later with your musical context still available."
        ),
        "when": "Start here if you are new — then follow First 5 minutes below.",
        "bullets": [
            "This is **not** a pile of unrelated tools. Your **active song**, "
            "**instrument**, **level**, **focus**, and **Practice / Concert Key** "
            "carry into Practice, Backing, Creative Lab, Karaoke (Voice), "
            "Music Coach, and recording workflows where the app supports it.",
            "**Why that matters:** instead of hunting for a chart, a metronome, "
            "a backing track, a notebook, and a generic AI elsewhere, you keep "
            "working around one musical context.",
            "Use the tour to learn **musical goal → tool → next step**, not just page names.",
        ],
        "tip": (
            "First 5 minutes: set Instrument / Level / Focus → pick a catalog song → "
            "set a comfortable Practice Key → open Backing Track → Generate → Play."
        ),
        "sections": [
            {
                "title": "Suggested first path",
                "bullets": [
                    "1. Practice Setup in the sidebar (Instrument, Level, Focus).",
                    "2. Song Selection — pick a song you know.",
                    "3. Set Practice / Concert Key to a comfortable sounding key.",
                    "4. Backing Track — Generate, then Play.",
                    "5. Ask Music Coach: *How should I practice this song?*",
                    "6. Quick-save a Practice Log entry so tomorrow continues from today.",
                ],
            },
            {
                "title": "When you are ready to go deeper",
                "bullets": [
                    "Edit a personal chart or lyrics on Song Selection.",
                    "Build a Custom Progression and make it active.",
                    "Explore Creative Lab (Harmony Map, Missions, Jam Session Generator).",
                    "Upload one take for feedback, or layer parts in Multitrack.",
                    "Use Practice Analysis to spot patterns in your history.",
                ],
            },
        ],
    },
    {
        "id": "setup",
        "page_id": "practice",
        "icon": "🎚️",
        "title": "Practice Setup — Instrument, Level, Focus",
        "summary": (
            "Three choices personalize the whole studio: "
            "**who you are playing as**, **how complex the material should be**, "
            "and **what you want to improve**."
        ),
        "when": "Change these anytime — you do not need a new song to change focus.",
        "bullets": [
            "**Instrument = how / what you play.** Options include Piano, Guitar, Bass, "
            "Saxophone, Flute, Trumpet, Clarinet, Voice, and Other. Changing instrument "
            "can change Practice Focus choices, notation/register, written-key / "
            "transposition UI, Guitar capo controls, and Voice Karaoke workflows.",
            "**Level = how complex the material should be** (Beginner, Intermediate, "
            "Advanced). Use Beginner for narrower, clearer targets; Advanced when you "
            "want richer options and denser practice ideas.",
            "**Practice Focus = what you want to improve** — not the song. Focus lists "
            "**change by instrument** (for example Walking Bass on Bass, Breath Control "
            "on Voice, Lead Guitar on Guitar).",
            "Mental model: **Instrument × Level × Focus** + active song + Practice Key "
            "+ section → more relevant practice and coaching.",
        ],
        "tip": (
            "Example: Flute + Intermediate + Tone steers you toward tone-oriented work; "
            "Bass + Beginner + Walking Bass favors simple supportive lines."
        ),
        "sections": [
            {
                "title": "Instrument adaptations (current app)",
                "bullets": [
                    "**Voice** unlocks Karaoke Performance Setlist on Song Selection and "
                    "Vocal Performance Mode on Backing Track.",
                    "**Saxophone** exposes Alto / Tenor / Soprano / Baritone types — "
                    "written transposition and register differ by subtype.",
                    "**Clarinet / Trumpet / Saxophone** can show charts in written key "
                    "via *Show chart in written key for instrument*.",
                    "**Guitar** can use Capo Shape Mode so sounding Practice Key and "
                    "chord shapes stay clearly separated.",
                    "**Bass** includes groove / Walking Bass style focuses; other "
                    "instruments can still work on supportive bass-role ideas in coaching "
                    "where that workflow exists.",
                ],
            },
        ],
    },
    {
        "id": "music",
        "page_id": "picker",
        "icon": "🎼",
        "title": "Choose your music — Catalog vs Custom",
        "summary": (
            "Catalog songs are ready-made charts. Custom Progressions are your own "
            "material. Both can become the active song that feeds practice elsewhere."
        ),
        "when": "Catalog for repertoire; Custom for originals, lesson progressions, or exercises.",
        "bullets": [
            "**Catalog:** browse/search on Song Selection, pick a song, check the "
            "active song card (genre, keys, form).",
            "**Personal catalog edits (your copy, not a global rewrite):** "
            "*Edit Song Chart* → Enable editing → Save corrected chart; "
            "*Lyrics & Cues* → Save Lyrics & Cues. Use Revert when you want the "
            "catalog version back.",
            "**Custom Progression Lab:** build sections and chords, **Save to library**, "
            "**Set as Active Song**, and reopen later with **Load selected**.",
            "**Finish Song** marks a custom form ready for practice — then use it like "
            "any active song in Practice, Backing, or Creative Lab.",
        ],
        "tip": "Editing a catalog chart saves *your* corrected chart — it does not rewrite the master library for everyone.",
        "sections": [
            {
                "title": "Active song continuity",
                "bullets": [
                    "Once a song or custom progression is active, Practice, Backing, "
                    "Creative Lab, Karaoke (Voice), Multitrack, and Music Coach can use "
                    "that context where each page supports it.",
                    "Switch songs from Song Selection when you want a new context.",
                ],
            },
        ],
    },
    {
        "id": "keys",
        "page_id": "picker",
        "icon": "🔑",
        "title": "Original Key vs Practice / Concert Key",
        "summary": (
            "Original Key is the song’s source key. Practice / Concert Key is the "
            "sounding key you want to practice in right now."
        ),
        "when": "Change Practice Key to make a song more comfortable without rewriting the original.",
        "bullets": [
            "**Original Key** stays with the song/chart identity.",
            "**Practice / Concert Key** (sidebar) is non-destructive transposition for practice.",
            "Changing Practice Key does **not** mean you permanently rewrote the original catalog song.",
            "**Written key** (Clarinet, Trumpet, Saxophone): sounding Practice Key can "
            "differ from what you read. Example: Concert C → Bb Clarinet reads in D; "
            "Alto Sax reads in A. Use *Show chart in written key for instrument* when "
            "you want charts in written spelling.",
            "**Saxophone type** (Alto / Tenor / Soprano / Baritone) matters — subtypes "
            "do not all read the same way.",
            "**Guitar Capo Shape Mode:** sounding Practice Key and capo shape key can "
            "legitimately differ — each is labeled for a different job.",
        ],
        "tip": "Singers: set Instrument to Voice, then move Practice Key to a comfortable singing key before Karaoke.",
    },
    {
        "id": "practice",
        "page_id": "practice",
        "icon": "🎯",
        "title": "Practice — your working area",
        "summary": (
            "Practice is where you warm up, read the chart, work technique, and use "
            "coaching tools on the active song."
        ),
        "when": "Daily work on repertoire, sections, tone, time, and reading.",
        "bullets": [
            "Open the **Practice tools** launcher for the main groups:",
            "**Harmony & technique** → Chord & song coach.",
            "**Time & pitch** → Metronome, Tuner & Tone.",
            "**Charts & lyrics** → Chart & notation, Lyrics & phrasing.",
            "**Reference** → Transpose helpers (and Guitar capo helper when relevant).",
            "Use **section focus** (Verse, Chorus, etc.) to loop one part at a time.",
            "Music Coach sits alongside Practice so you can ask for a plan without leaving the room.",
        ],
        "tip": "Pick one section + one focus (for example Tone) and stay there until it feels cleaner — then raise tempo or widen the section.",
        "sections": [
            {
                "title": "What problems these tools solve",
                "bullets": [
                    "Tuner & Tone — start in tune; build tone before speed.",
                    "Metronome — lock time on a section or the full form.",
                    "Chord / song coach — understand what to play over the harmony.",
                    "Chart & notation / TAB — read the material you are practicing.",
                    "Lyrics & phrasing — singers and anyone tracking cues.",
                    "Transpose helpers — sounding key, written key, or guitar shapes.",
                ],
            },
        ],
    },
    {
        "id": "backing",
        "page_id": "backing",
        "icon": "🎧",
        "title": "Backing Track",
        "summary": "Play along with accompaniment built from your active song’s harmony and groove.",
        "when": "You want to practice melody, improv, groove, or form against the song — not alone with a metronome.",
        "bullets": [
            "Uses the **active song** (catalog or custom).",
            "Choose **full song** or a **section** to loop; check **BPM** and **groove**.",
            "**Generate** builds the audio; **Play** starts it; stop when finished.",
            "Different from **Jam Session Generator** (creates a new practice situation) "
            "and from **Multitrack** (layering your own recordings).",
        ],
        "tip": "Generate once, then nudge BPM in small steps when a section is clean three times in a row.",
    },
    {
        "id": "karaoke",
        "page_id": "backing",
        "icon": "🎤",
        "title": "Voice & Karaoke",
        "summary": (
            "When Instrument is Voice, Song Selection becomes a Karaoke setlist workflow "
            "and Backing Track opens as Vocal Performance Mode."
        ),
        "when": "Sing through a song with lyrics/cues and accompaniment; rehearse entrances and form.",
        "bullets": [
            "**Path:** set Instrument → **Voice** → Song Selection (*Karaoke Performance Setlist*) "
            "→ add songs / start the set → open **Backing Track**, which becomes "
            "**Vocal Performance Mode** for Voice.",
            "Karaoke uses your **active song**, **lyrics/cues**, and **Practice / Concert Key** "
            "so you can rehearse in a comfortable singing key.",
            "Voice Practice Focus options include Breath Control, Phrasing, Pitch Accuracy, "
            "Emotional Delivery, Harmony Singing, Vibrato, Dynamics, and Ear Training.",
            "There is no separate “Karaoke” studio page — Voice turns Song Selection + Backing "
            "into the karaoke workflow.",
        ],
        "tip": "Comfortable Practice Key first, then Karaoke — analysis of a recorded vocal take still belongs in Upload Analysis.",
        "sections": [
            {
                "title": "Karaoke vs other tools",
                "bullets": [
                    "**Karaoke / Vocal Performance** — sing the song with lyrics and accompaniment.",
                    "**Backing Track (non-Voice)** — instrumental play-along for the active song.",
                    "**Upload Analysis** — feedback on one finished take (including vocals).",
                    "**Multitrack** — layer several recorded parts.",
                    "**Jam / Jam Session Generator** — creative/generated practice contexts, not the Karaoke setlist.",
                ],
            },
            {
                "title": "Singer setup example",
                "bullets": [
                    "Instrument = Voice; Focus = Phrasing (or Breath Control / Pitch Accuracy).",
                    "Pick a song; set Practice Key to a comfortable singing key.",
                    "Use Lyrics & Cues if you need personal cue edits.",
                    "Practice in Karaoke / Vocal Performance Mode; log the session afterward.",
                ],
            },
        ],
    },
    {
        "id": "creative",
        "page_id": "creative",
        "icon": "🎨",
        "title": "Creative Lab — improvise & explore",
        "summary": (
            "Creative Lab is a multi-tool improv workspace around your active harmony: "
            "entry modes, live coaching, motifs, missions, and harmony views."
        ),
        "when": "You want to improvise, understand the progression, or take a focused mission — not only read the chart.",
        "bullets": [
            "**Entry & Jam** — choose how you enter: Song-Based Improvisation, "
            "Style Jam Mode, or Jam Session Generator.",
            "**Live Coach** — scales, chord tones, and tips for the chord you are on.",
            "**Phrase / Motif** — build, transform, and notate melodic ideas.",
            "**Missions** — focused practice challenges with instructions (and examples when available).",
            "**Harmony Map** — see section progressions and tap chords for tones/context.",
            "**Deep Harmony** — slower guided harmonic lessons.",
            "**Metrics & AI** — choose what Upload Analysis should weigh for mission-style scoring.",
        ],
        "tip": "Try Harmony Map once on a song you already know — it turns chord names into musical jobs.",
        "sections": [
            {
                "title": "Entry modes under Entry & Jam",
                "bullets": [
                    "**Song-Based Improvisation** — improvise from the active song or a custom progression.",
                    "**Style Jam Mode** — choose a style/groove-oriented jam context "
                    "(useful when you want feel/style first, not a specific catalog tune).",
                    "**Jam Session Generator** — quickly generate a practice jam situation "
                    "instead of hand-building every progression.",
                ],
            },
            {
                "title": "How Creative tools differ",
                "bullets": [
                    "**Backing** — accompaniment for the current active song.",
                    "**Style Jam Mode** — style-first jam entry inside Creative Lab.",
                    "**Jam Session Generator** — generated jam material to practice over.",
                    "**Missions** — targeted improvisation challenges, not “play the whole song casually.”",
                    "**Harmony Map** — understanding; **chord chart** — reading the form.",
                    "**Custom Progression** — authoring your own harmony; Creative — playing/exploring it.",
                ],
            },
            {
                "title": "Example Creative flow",
                "bullets": [
                    "Set an active song or custom progression.",
                    "Entry & Jam → Song-Based (or generate a jam).",
                    "Harmony Map → notice chord function.",
                    "Pick a Mission → play with backing if available.",
                    "Ask Music Coach what to improve next; log the work.",
                ],
            },
        ],
    },
    {
        "id": "composer",
        "page_id": "composer",
        "icon": "🎹",
        "title": "Composition Studio",
        "summary": "A place to develop song ideas — vision, structure, chords, melody, lyrics, and review.",
        "when": "You are writing or shaping a song, not only practicing repertoire.",
        "bullets": [
            "Phases include Song Vision, Song Structure, Chords, Melody, Lyrics, and Review.",
            "Use it when Custom Progression is not enough structure for a full song idea.",
            "You can still practice composed material with Backing / Creative once it is active in your workflow.",
        ],
        "tip": "Start with a short form (verse/chorus) before adding dense harmony.",
    },
    {
        "id": "coach",
        "page_id": "practice",
        "icon": "🤖",
        "title": "Music Coach",
        "summary": (
            "Ask normal musician questions. The coach can use your current setup and "
            "active song context where the app supports it."
        ),
        "when": "You want a plan, technique help, song advice, or help finding the right page/tool.",
        "bullets": [
            "Open **Music Coach** from the sidebar (also available near Practice).",
            "Useful question types on the current app include practice planning, "
            "technique, song coaching, theory/scales, improvisation coaching, "
            "app navigation, and feature recommendations.",
            "Context the coach may use: instrument, level, focus, active song, "
            "section, Practice Key, and practice-log history where wired.",
            "Example questions: *What should I practice for 20 minutes today?* · "
            "*How should I practice this song?* · *Where do I upload a take for feedback?* · "
            "*Should I use Upload Analysis or Multitrack?* · "
            "*How do I edit this chart?*",
            "You can also ask for supportive **bass-line** ideas over the active song "
            "when that coaching path is available.",
        ],
        "tip": "Ask the way you would ask a teacher — plain musical language works better than “prompt tricks.”",
        "sections": [
            {
                "title": "What this tutorial does not claim (yet)",
                "bullets": [
                    "Advanced lick / multi-bar pattern generation from newer AMI work "
                    "may arrive after merge; this tour describes the current Music Coach surface.",
                    "If a question is about app navigation, ask it — the coach can point you to the right page.",
                ],
            },
        ],
    },
    {
        "id": "recording",
        "page_id": "analysis",
        "icon": "🎙️",
        "title": "Recording decision guide",
        "summary": "Pick the recording path that matches your goal — logging, one-take feedback, or layered parts.",
        "when": "Anytime you want evidence of practice or feedback on a performance.",
        "bullets": [
            "**I want to remember that I practiced** → Practice Log (Quick Save or Add Session Manually).",
            "**I have one take and want feedback** → Upload Analysis (Upload & AI Coach).",
            "**I want several parts / overdubs** → Multitrack, then optionally Send to Upload Analysis.",
            "**I’m on a Mission** → use the Mission’s play/record options when shown, then analyze if you captured a take.",
        ],
        "tip": "Upload Analysis = coach the take. Multitrack = build the arrangement. Practice Log = keep the diary.",
        "sections": [
            {
                "title": "Upload Analysis",
                "bullets": [
                    "Page: **Upload Analysis** (*Upload & AI Coach*).",
                    "Drop/upload a recording (or use available mic capture).",
                    "Review timing, pitch, tone/technique-style feedback and next-step suggestions.",
                    "Workflow modes include single recording vs multitrack-oriented handoff.",
                ],
            },
            {
                "title": "Multitrack",
                "bullets": [
                    "Page: **Multitrack** (*Multitrack Session Workspace*).",
                    "Layer parts with monitor backing, mute/solo/volume, transport, mix/export where available.",
                    "Synced to your active song context for practice arranging.",
                ],
            },
        ],
    },
    {
        "id": "log",
        "page_id": "log",
        "icon": "📓",
        "title": "Practice Log & Practice Analysis",
        "summary": (
            "The Log answers what you practiced. Practice Analysis looks for patterns "
            "and what to work on next."
        ),
        "when": "End of a session — or weekly when you want smarter continuity.",
        "bullets": [
            "**Quick Save Practice Session** for a fast entry; **Add Session Manually** for full detail.",
            "Record song, instrument, keys, BPM, duration, section, focus, ratings "
            "(focus/confidence/accuracy/groove/tone/difficulty), notes, and next step.",
            "Edit, delete, and filter history as needed.",
            "**Analyze My Practice** opens **Practice Analysis** — trends and coaching-style recommendations.",
            "Keeping the log current helps Music Coach continue from real work when history is available.",
        ],
        "tip": "Thirty seconds of honest notes beats a perfect empty diary.",
    },
    {
        "id": "saving",
        "page_id": "picker",
        "icon": "💾",
        "title": "Saving & returning later",
        "summary": "Know what needs an explicit Save versus what follows your active song and Practice Key.",
        "when": "Before you leave — and when you reopen tomorrow.",
        "bullets": [
            "**Practice Key** — practice transposition; does not rewrite Original Key.",
            "**Catalog chart / lyrics edits** — use Save corrected chart / Save Lyrics & Cues "
            "(Revert returns toward catalog material).",
            "**Custom songs** — Save to library, then Load selected / Set as Active Song later.",
            "**Practice Log** — Quick Save or manual add; not every page auto-logs practice.",
            "**Multitrack / uploads** — save/export using the controls on those pages when you need the files later.",
            "Return via Song Selection (catalog or saved custom), your last active song context, and Practice Log history.",
        ],
        "tip": "If you edited chords or lyrics, look for an explicit Save before switching songs.",
    },
    {
        "id": "which_tool",
        "page_id": "",
        "icon": "🧭",
        "title": "Which tool should I use?",
        "summary": "A compact decision guide from musical goal → page.",
        "when": "Whenever you feel stuck choosing a page.",
        "bullets": [
            "**Practice an existing song** → Song Selection + Practice.",
            "**Create my own progression** → Custom Progression.",
            "**Write a fuller song idea** → Composition Studio.",
            "**Accompaniment for this song** → Backing Track.",
            "**Sing with lyrics / setlist** → Voice + Karaoke / Vocal Performance Mode.",
            "**Generated jam situation** → Creative Lab → Jam Session Generator (or Style Jam Mode).",
            "**Focused improv challenge** → Creative Lab → Missions.",
            "**Understand the progression** → Harmony Map (and Deep Harmony when you want a lesson pace).",
            "**Feedback on one take** → Upload Analysis.",
            "**Layer several recordings** → Multitrack.",
            "**Remember what I practiced** → Practice Log.",
            "**Guidance / next plan** → Music Coach.",
        ],
        "tip": "Same song, different job: Backing to play along, Missions to challenge improv, Upload Analysis to judge a take.",
        "sections": [
            {
                "title": "Two complete workflows",
                "bullets": [
                    "**Catalog song:** Setup → pick song → Practice Key → section → "
                    "Practice tools / Backing → Upload Analysis → Log → Music Coach.",
                    "**Custom idea:** Custom Progression → Save → Set Active → Creative "
                    "(Harmony Map / Jam / Mission) → practice or record → Log.",
                    "**Singer:** Voice + Focus → song → comfortable Practice Key → "
                    "Karaoke / Vocal Performance → optional Upload Analysis → Log.",
                ],
            },
        ],
    },
]

TOTAL_STEPS = len(TUTORIAL_STEPS)


def init_tutorial_state(session_state: dict) -> None:
    session_state.setdefault(TUTORIAL_DISMISSED_KEY, False)
    session_state.setdefault(TUTORIAL_OPEN_KEY, False)
    session_state.setdefault(TUTORIAL_STEP_KEY, 0)


def tutorial_entry_visible(session_state: dict) -> bool:
    """Top Tutorial button — hidden after finish or opt-out."""
    return not bool(session_state.get(TUTORIAL_DISMISSED_KEY))


def open_tutorial(session_state: dict, *, reset_step: bool = False) -> None:
    """Open tutorial; by default resumes the last step."""
    session_state[TUTORIAL_OPEN_KEY] = True
    if reset_step:
        session_state[TUTORIAL_STEP_KEY] = 0
    else:
        session_state[TUTORIAL_STEP_KEY] = _clamp_step(
            session_state.get(TUTORIAL_STEP_KEY, 0)
        )


def close_tutorial(session_state: dict) -> None:
    """Close panel but keep the top Tutorial button available."""
    session_state[TUTORIAL_OPEN_KEY] = False


def complete_tutorial(session_state: dict) -> None:
    """Finish or opt out — no auto-start, hide top Tutorial button."""
    session_state[TUTORIAL_DISMISSED_KEY] = True
    session_state[TUTORIAL_OPEN_KEY] = False


def _clamp_step(step: int) -> int:
    return max(0, min(int(step), TOTAL_STEPS - 1))


def step_index_for_page(page_id: str) -> int | None:
    """Map a studio page to a tutorial chapter (first matching chapter wins)."""
    pid = str(page_id or "").strip()
    if not pid:
        return None
    for i, step in enumerate(TUTORIAL_STEPS):
        if step.get("page_id") == pid:
            return i
    return None


def tutorial_nav_page_ids() -> list[str]:
    """Page ids used by Open buttons — for tests."""
    return [
        str(s.get("page_id") or "")
        for s in TUTORIAL_STEPS
        if str(s.get("page_id") or "").strip()
    ]


def tutorial_chapter_ids() -> list[str]:
    return [str(s.get("id") or "") for s in TUTORIAL_STEPS]


def _quick_start_html() -> str:
    return (
        "<ol class='tutorial-quick-start'>"
        "<li>Set <strong>Instrument / Level / Focus</strong> in the sidebar.</li>"
        "<li>Pick a song on <strong>Song Selection</strong>.</li>"
        "<li>Set a comfortable <strong>Practice / Concert Key</strong>.</li>"
        "<li>Open <strong>Backing Track</strong> → <strong>Generate</strong> → <strong>Play</strong>.</li>"
        "<li>Ask <strong>Music Coach</strong> what to practice next, then <strong>Quick Save</strong> a log entry.</li>"
        "</ol>"
    )


def _decision_strip_html() -> str:
    return (
        "<div class='tutorial-decision-strip'>"
        "<p><strong>Practice setup</strong> → Choose music → Set key / section → "
        "Choose tool (Practice / Backing / Karaoke / Creative) → "
        "Record / Analyze → Log / Continue</p>"
        "</div>"
    )


def render_tutorial_walkthrough(
    st_module: Any,
    session_state: dict,
    *,
    rerun_fn: Callable[[], None],
    navigate_fn: Callable[[str], None] | None = None,
) -> None:
    """Guided tour panel (shown above page content when tutorial_open is True)."""
    step = _clamp_step(session_state.get(TUTORIAL_STEP_KEY, 0))
    data = TUTORIAL_STEPS[step]
    progress_pct = int((step + 1) / TOTAL_STEPS * 100)
    title = html.escape(str(data.get("title") or ""))
    summary = html.escape(str(data.get("summary") or ""))
    when = html.escape(str(data.get("when") or ""))

    st_module.markdown(
        f"""
<div class="tutorial-hero">
  <div class="tutorial-hero-head">
    <span class="tutorial-hero-icon">{data.get("icon") or "🎵"}</span>
    <div>
      <p class="tutorial-kicker">Musician tutorial</p>
      <h2 class="tutorial-title">Your practice workspace</h2>
      <p class="tutorial-sub">Chapter {step + 1} of {TOTAL_STEPS} — {title}</p>
    </div>
  </div>
  <div class="tutorial-progress-track" aria-hidden="true">
    <div class="tutorial-progress-fill" style="width:{progress_pct}%;"></div>
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )

    if step == 0:
        st_module.markdown(
            '<div class="tutorial-quick-card">'
            '<p class="tutorial-quick-title">⚡ First 5 minutes</p>'
            f"{_quick_start_html()}"
            f"{_decision_strip_html()}"
            "</div>",
            unsafe_allow_html=True,
        )

    st_module.markdown(
        f'<div class="tutorial-step-card">'
        f'<p class="tutorial-step-label">Chapter {step + 1} of {TOTAL_STEPS}</p>'
        f'<h3 class="tutorial-step-title">{data.get("icon") or ""} {title}</h3>'
        f'<p class="tutorial-sub">{summary}</p>'
        f"</div>",
        unsafe_allow_html=True,
    )
    if when:
        st_module.markdown(f"**When to use this:** {when}")

    for bullet in data.get("bullets") or []:
        st_module.markdown(f"- {bullet}")
    if data.get("tip"):
        st_module.info(data["tip"])

    for section in data.get("sections") or []:
        with st_module.expander(str(section.get("title") or "More"), expanded=False):
            for bullet in section.get("bullets") or []:
                st_module.markdown(f"- {bullet}")

    # Chapter jump list (scannable on phone)
    with st_module.expander("All chapters", expanded=False):
        for i, ch in enumerate(TUTORIAL_STEPS):
            mark = "→ " if i == step else ""
            st_module.markdown(f"{mark}**{i + 1}. {ch.get('title')}**")
            if st_module.button(
                f"Go to chapter {i + 1}",
                key=f"tutorial_jump_{i}",
                use_container_width=True,
            ):
                session_state[TUTORIAL_STEP_KEY] = i
                rerun_fn()

    nav1, nav2, nav3, nav4 = st_module.columns([1, 1, 1, 1])
    with nav1:
        if st_module.button(
            "← Back",
            key="tutorial_back",
            disabled=step <= 0,
            use_container_width=True,
        ):
            session_state[TUTORIAL_STEP_KEY] = step - 1
            rerun_fn()
    with nav2:
        _next_label = "Finish tour ✓" if step >= TOTAL_STEPS - 1 else "Next →"
        if st_module.button(
            _next_label,
            key="tutorial_next",
            type="primary",
            use_container_width=True,
        ):
            if step >= TOTAL_STEPS - 1:
                complete_tutorial(session_state)
            else:
                session_state[TUTORIAL_STEP_KEY] = step + 1
            rerun_fn()
    with nav3:
        page_id = str(data.get("page_id") or "").strip()
        open_label = f"Open {data['title']}" if page_id else "Stay in tutorial"
        if page_id and page_id in _VALID_NAV_PAGE_IDS and navigate_fn:
            if st_module.button(open_label, key="tutorial_go_page", use_container_width=True):
                idx = step_index_for_page(page_id)
                if idx is not None:
                    session_state[TUTORIAL_STEP_KEY] = idx
                session_state[TUTORIAL_OPEN_KEY] = False
                navigate_fn(page_id)
        else:
            st_module.button(
                open_label,
                key="tutorial_go_page",
                disabled=True,
                use_container_width=True,
            )
    with nav4:
        if st_module.button("Close", key="tutorial_close", use_container_width=True):
            close_tutorial(session_state)
            rerun_fn()

    st_module.divider()
    c1, c2, c3 = st_module.columns([2, 1, 1])
    with c1:

        def _on_dismiss_toggle() -> None:
            if session_state.get(TUTORIAL_DISMISS_CHECKBOX_KEY):
                complete_tutorial(session_state)
                rerun_fn()

        st_module.checkbox(
            "Don't show again on startup",
            key=TUTORIAL_DISMISS_CHECKBOX_KEY,
            on_change=_on_dismiss_toggle,
        )
    with c2:
        if st_module.button("Finish tour", key="tutorial_finish", use_container_width=True):
            complete_tutorial(session_state)
            rerun_fn()
    with c3:
        if st_module.button("Start over", key="tutorial_restart", use_container_width=True):
            session_state[TUTORIAL_STEP_KEY] = 0
            rerun_fn()

    st_module.caption(
        "Use **Open …** to jump into a real page, **Close** to keep working, "
        "or **All chapters** to skip ahead — your place in the tour is saved."
    )
