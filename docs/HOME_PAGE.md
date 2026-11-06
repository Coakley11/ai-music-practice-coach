# Home

Home is the default landing page when no saved or explicit destination wins
(`ea12085d`). Returning workspaces, deep links and explicit navigation retain
priority. A new workspace still initializes its catalog song; it simply has no
misleading "No saved song selection" warning (`7edf982e`).

Home reads musical state. It never selects a song, changes Practice Key, or saves
a Practice Log entry merely because the user visits. Navigation uses
`app_ui.navigate_studio_page`. Explicit Home button presses reset the automatic
rerun guard so repeated visits to the same destination work.

## Artwork

`home_artwork.py` supplies inline SVG/CSS illustrations and canonical icons from
`music_feature_icons.py`. The existing optimized official MPC emblem remains in
use. Art is decorative (`aria-hidden`), buttons retain accessible text, and touch
targets are at least 44 pixels. The real `home_page` Streamlit container scopes
the responsive column rules; Markdown tags cannot wrap Streamlit columns.

## Discovery and routing

Home discovery queues a view request. Before Songs widgets mount,
`songs.picker_session.apply_home_catalog_request` clears unrelated Search,
Genres, Favorites-only and temporary exclusions, then contributes the requested
genre or every catalog genre. Favorites themselves are preserved.

The separate `_home_catalog_browse` view bypasses source-toggle hydration and
stale dropdown reconciliation. Custom and Composition retain ownership until
the musician explicitly selects a catalog result. "Return to active song view"
exits that view. Ordinary Songs filtering remains Search union Genres union
Favorites; Clear Filters still produces an empty discovery list.

Missions commits its canonical Creative tool selection. Song-Aware Coaching uses
`studio_page_state.request_song_aware_coaching`, the current dedicated tab.
Upload Analysis opens the analysis page with its existing recording context.
Key Cycling opens Backing's Advanced playback settings without enabling or
starting a cycle.

## Recent Practice

`home_recent_session.py` compares persisted Practice Log rows with version-2
`practice_session_started` activity records. Activity reads are scoped to the
current workspace, through the existing cloud event reader and scoped local
fallback. Navigation, uploads and unversioned activity do not establish practice.

Practice date determines log chronology, with recorded creation time resolving
same-day ordering when available; later edits do not make old practice newest.
Day labels use America/New_York. Song, artist, instrument and keys come only
from saved history. Missing historical keys are omitted rather than borrowed
from the live workspace. A recorded start is evidence of a start, not completion.

Buttons say "Go to [destination]" and retain the current musical context.
`apply_music_resume_payload` supports genuine restoration, but requires a valid
workspace and source identity plus source-specific artifacts. Older Practice Log
entries are not complete resume payloads; Home therefore makes no Resume promise.
A transactional, separately tested Resume slice remains future work.

See [handoff review and evidence](HOME_HANDOFF_REVIEW.md).
