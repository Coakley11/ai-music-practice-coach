"""Central song system: session state, form ordering, database bridge."""

from .form import (
    chord_blocks_for_backing,
    form_timeline_rows,
    section_order,
)
from .bpm_state import (
    BPM_WIDGET_KEY,
    request_backing_bpm,
    sync_backing_bpm_before_widget,
)
from .key_state import (
    BACKING_NEEDS_REGEN,
    clear_backing_needs_regen,
    invalidate_backing_cache,
    note_display_key_change,
    on_cpl_jump_home_key,
    prepare_cpl_jump_home,
    request_display_key,
    sync_display_key_before_widget,
)
from .music_source import (
    ACTIVE_MUSIC_SOURCE_KEY,
    SOURCE_CATALOG,
    SOURCE_CUSTOM,
    active_source_banner,
    build_active_chart_bundle,
    display_key_context,
    ensure_active_music_source,
    is_custom_progression,
    note_active_source_change,
    set_catalog_source,
    set_custom_source,
)
from .state import (
    ACTIVE_CATALOG_PICK_KEY,
    SELECTED_SONG_STATE_KEY,
    apply_pick_key,
    ensure_master_song_initialized,
    get_song_context,
    sync_matching_song_dropdown_before_widget,
)

__all__ = [
    "ACTIVE_MUSIC_SOURCE_KEY",
    "SOURCE_CATALOG",
    "SOURCE_CUSTOM",
    "active_source_banner",
    "build_active_chart_bundle",
    "display_key_context",
    "ensure_active_music_source",
    "is_custom_progression",
    "note_active_source_change",
    "set_catalog_source",
    "set_custom_source",
    "ACTIVE_CATALOG_PICK_KEY",
    "SELECTED_SONG_STATE_KEY",
    "apply_pick_key",
    "ensure_master_song_initialized",
    "get_song_context",
    "sync_matching_song_dropdown_before_widget",
    "chord_blocks_for_backing",
    "form_timeline_rows",
    "section_order",
    "BPM_WIDGET_KEY",
    "request_backing_bpm",
    "sync_backing_bpm_before_widget",
    "BACKING_NEEDS_REGEN",
    "clear_backing_needs_regen",
    "invalidate_backing_cache",
    "note_display_key_change",
    "on_cpl_jump_home_key",
    "prepare_cpl_jump_home",
    "request_display_key",
    "sync_display_key_before_widget",
]
