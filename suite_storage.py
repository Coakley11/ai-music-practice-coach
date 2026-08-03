"""
Storage API shim for Music deploy.

The full ``suite_storage`` module (SQLite + Supabase) ships in Command Center.
Music Streamlit Cloud uses Supabase only via ``suite_storage_supabase``; this
shim preserves the shared ``import suite_storage`` contract used by
``suite_account`` and activity clients.
"""

from __future__ import annotations

from suite_storage_supabase import (
    append_event,
    invalidate_app_resume_items,
    invalidate_resume_item,
    invalidate_saved_item,
    load_active_resume_items,
    load_current_state_for_app,
    load_current_state_meta_for_app,
    load_current_states,
    load_current_states_summary,
    load_events,
    load_saved_items,
    load_user_settings,
    ping,
    record_activity,
    save_current_state,
    save_current_state_conditional_cas,
    save_user_settings,
    upsert_resume_item,
    upsert_saved_item,
)

__all__ = [
    "append_event",
    "invalidate_app_resume_items",
    "invalidate_resume_item",
    "invalidate_saved_item",
    "load_active_resume_items",
    "load_current_state_for_app",
    "load_current_state_meta_for_app",
    "load_current_states",
    "load_current_states_summary",
    "load_events",
    "load_saved_items",
    "load_user_settings",
    "ping",
    "record_activity",
    "save_current_state",
    "save_current_state_conditional_cas",
    "save_user_settings",
    "upsert_resume_item",
    "upsert_saved_item",
]
