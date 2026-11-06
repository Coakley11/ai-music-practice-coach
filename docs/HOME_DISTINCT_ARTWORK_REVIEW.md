# Home artwork revision — distinct musical identities

Branch: `codex/home-distinct-artwork-20261104`.
Worktree: `.worktrees/home-integration-20261104`.

Integration is on hold. No push, merge or deployment was performed for this
revision. The previous local replay had completed at `52b91dd1` before the design
change arrived. That candidate includes Grok's `20cc525b` upstream baseline.
The original reviewed branch and safety reference remain at `c0d06291`.

## Visual direction

Each card now has a separate scene rather than sharing interchangeable motifs:

| Area | Visual identity |
| --- | --- |
| Pop | Stage microphone, bright POP wordmark, yellow starburst; canonical blue/indigo/pink Pop gradient |
| Jazz | Central gold saxophone, cool staff lines, italic Jazz identity; canonical midnight/purple Jazz gradient |
| Practice | Open scorebook and learning steps |
| Backing | Headphones and beat sequencer |
| Multitrack | Four recording lanes and a timeline playhead |
| Composition | Quill and flowing musical notation |
| Missions | Instruction checklist, checkpoints and a finish flag |
| Song-Aware Coaching | Song chords connected to a musical response bubble |
| Key Cycling | Circle of fifths, key labels, rotation arrow and keyboard |
| Custom Progressions | Labeled guitar voicing diagrams and harmonic functions |
| Upload Analysis | Recording file and magnified waveform |
| Practice Log | Calendar, history clock and progress graph |
| Entire Catalog | Record collection and catalog tiles |

The Pop microphone and Jazz sax identities/palettes come from the existing
`practice_studio.genre_visual_style` contract. The actual MPC emblem and canonical
action-button icons are retained. There are 13 distinct valid inline SVG scenes,
24,201 bytes total markup, with no new runtime image files, external fetches,
script or animation. Illustrations remain decorative and unfocusable.

## Screenshots

These are the actual revised Home renderer in the lightweight isolated preview.
Recent Practice deliberately uses the honest empty-history state; no historical
song, artist or key is fabricated for the screenshots.

| Capture | Desktop | Mobile |
| --- | --- | --- |
| Complete Home | [Desktop](../evidence/home-distinct-artwork/desktop-full.png) | [Mobile](../evidence/home-distinct-artwork/mobile-full.png) |
| Recent Practice and main workflows | [Desktop](../evidence/home-distinct-artwork/desktop-recent-workflows.png) | [Mobile](../evidence/home-distinct-artwork/mobile-recent-workflows.png) |
| Pop and Jazz | [Desktop](../evidence/home-distinct-artwork/desktop-pop-jazz.png) | [Mobile](../evidence/home-distinct-artwork/mobile-pop-jazz.png) |
| Missions, Coaching, Key Cycling and tools | [Desktop](../evidence/home-distinct-artwork/desktop-tools.png) | [Mobile](../evidence/home-distinct-artwork/mobile-tools.png) |

## Validation

- **172 focused tests and 107 subtests passed**, including all selected Home,
  Catalog/filtering, route, source-preservation, startup and Recent Practice
  checks, plus Grok's 15 navigation/cloud-read safety tests.
- Browser captures passed at 1140 px desktop and 390 px mobile. All 13 cards stay
  inside the viewport; all 13 card buttons retain at least 44 px touch targets;
  no Streamlit rendering exception appeared.
- All 13 SVG scenes parse successfully and have distinct SVG content.
- The only application file changed relative to `52b91dd1` is `home_artwork.py`.
  Routing, Catalog, Recent Practice, initialization and persistence implementation
  files are byte-identical to that candidate. Grok's files are byte-identical to
  `20cc525b`. No navigation behavior change was introduced by the art revision.
- The screenshot helper initially used an HTML-only text API on SVG; this was
  corrected to text_content and the complete capture then passed. No product
  failure was involved.

See [test output](../evidence/home-distinct-artwork/focused-tests.txt),
[browser checks](../evidence/home-distinct-artwork/browser-results.json), and
[SVG audit](../evidence/home-distinct-artwork/artwork-audit.json).

No full app browser startup or full test suite was run. Tests and the lightweight
preview/browser were run sequentially. All task preview/browser processes are
closed. Final sample: 0.77 GB available RAM, 39.34/43.79 GB committed memory,
84.3% CPU and 192.38 GB free disk. Other agents' processes, worktrees, evidence,
Cursor databases and SSD backups were preserved.
