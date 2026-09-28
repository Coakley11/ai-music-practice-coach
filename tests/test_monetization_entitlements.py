from __future__ import annotations

import copy
from datetime import datetime, timezone

import pytest

from monetization_entitlements import (
    DEV_CONTROLS_ENV,
    DEV_RUNTIME_ENV,
    DEV_SESSION_PLAN_KEY,
    Entitlement,
    Feature,
    Plan,
    StaticEntitlementProvider,
    SubscriptionStatus,
    access_decision,
    can_use,
    development_overrides_enabled,
    resolve_entitlement,
)
from monetization_ui import (
    close_pricing_surface,
    locked_feature_view_model,
    monetization_session_keys,
    open_pricing_surface,
    pricing_return_button_label,
    pricing_surface_should_render,
)
from music_feature_icons import FEATURE_ICONS, page_feature_icon


def _entitlement(plan: Plan, status: SubscriptionStatus) -> Entitlement:
    return Entitlement(plan=plan, status=status, source="test", is_test=True)


def test_free_user_keeps_core_access_and_composition_is_locked() -> None:
    free = _entitlement(Plan.FREE, SubscriptionStatus.AUTHENTICATED_FREE)

    assert can_use(Feature.PRACTICE_BASICS, entitlement=free)
    assert can_use(Feature.SONG_LIBRARY, entitlement=free)
    assert can_use(Feature.BACKING_STUDIO, entitlement=free)
    assert can_use(Feature.MISSIONS, entitlement=free)
    assert not can_use(Feature.COMPOSITION_STUDIO, entitlement=free)


@pytest.mark.parametrize(
    "status",
    [
        SubscriptionStatus.TRIALING,
        SubscriptionStatus.ACTIVE,
        SubscriptionStatus.CANCELED_PERIOD_END,
        SubscriptionStatus.DEVELOPMENT,
    ],
)
def test_pro_access_states_allow_premium_features(status: SubscriptionStatus) -> None:
    pro = _entitlement(Plan.PRO, status)

    assert can_use(Feature.COMPOSITION_STUDIO, entitlement=pro)
    assert can_use(Feature.MULTITRACK_EXPORT, entitlement=pro)


@pytest.mark.parametrize(
    "status, reason",
    [
        (SubscriptionStatus.PAST_DUE, "payment_past_due"),
        (SubscriptionStatus.EXPIRED, "subscription_expired"),
    ],
)
def test_non_entitled_subscription_states_fail_closed(
    status: SubscriptionStatus,
    reason: str,
) -> None:
    decision = access_decision(
        Feature.COMPOSITION_STUDIO,
        entitlement=_entitlement(Plan.PRO, status),
    )

    assert not decision.allowed
    assert decision.reason == reason


def test_period_end_cancellation_retains_access_and_metadata() -> None:
    period_end = datetime(2027, 1, 2, tzinfo=timezone.utc)
    entitlement = Entitlement(
        plan=Plan.PRO,
        status=SubscriptionStatus.CANCELED_PERIOD_END,
        source="billing_database",
        current_period_end=period_end,
    )

    decision = access_decision(Feature.COMPOSITION_STUDIO, entitlement=entitlement)

    assert decision.allowed
    assert decision.entitlement.current_period_end == period_end


def test_unknown_feature_fails_closed() -> None:
    with pytest.raises(KeyError):
        can_use("not_a_real_feature", entitlement=_entitlement(Plan.PRO, SubscriptionStatus.ACTIVE))


def test_injected_provider_is_the_only_non_development_paid_boundary() -> None:
    provider = StaticEntitlementProvider(
        _entitlement(Plan.PRO, SubscriptionStatus.ACTIVE)
    )

    entitlement = resolve_entitlement({}, provider=provider, environ={})

    assert entitlement.grants_pro
    assert can_use(Feature.COMPOSITION_STUDIO, provider=provider, session_state={})


def test_session_plan_flag_is_ignored_without_server_owned_dev_gate() -> None:
    session = {DEV_SESSION_PLAN_KEY: Plan.PRO.value}

    disabled = resolve_entitlement(session, environ={})
    incomplete = resolve_entitlement(
        session,
        environ={DEV_CONTROLS_ENV: "1", DEV_RUNTIME_ENV: "production"},
    )

    assert disabled.plan is Plan.FREE
    assert incomplete.plan is Plan.FREE
    assert not development_overrides_enabled({DEV_CONTROLS_ENV: "1"})


def test_development_entitlement_transitions_free_to_pro_and_back() -> None:
    env = {DEV_CONTROLS_ENV: "1", DEV_RUNTIME_ENV: "test"}
    session = {DEV_SESSION_PLAN_KEY: Plan.FREE.value}

    assert not can_use(Feature.COMPOSITION_STUDIO, session_state=session, environ=env)
    session[DEV_SESSION_PLAN_KEY] = Plan.PRO.value
    assert can_use(Feature.COMPOSITION_STUDIO, session_state=session, environ=env)
    session[DEV_SESSION_PLAN_KEY] = Plan.FREE.value
    assert not can_use(Feature.COMPOSITION_STUDIO, session_state=session, environ=env)


def test_locked_feature_copy_is_centralized() -> None:
    decision = access_decision(
        Feature.COMPOSITION_STUDIO,
        entitlement=_entitlement(Plan.FREE, SubscriptionStatus.ANONYMOUS),
    )

    view = locked_feature_view_model(decision)

    assert view["feature_key"] == "composition_studio"
    assert view["required_plan"] == "pro"
    assert "included with Pro" in view["title"]
    assert view["action_label"] == "Compare Free and Pro"


def test_opening_and_closing_pricing_does_not_mutate_music_or_navigation_state() -> None:
    session = {
        "studio_page": "composer",
        "pick_key": "Pop::Trial Song",
        "display_key": "F#",
        "instrument": "Bb Clarinet",
        "active_backing_owner": "mission",
        "active_musical_workflow_envelope": {"practice_key": "F#", "owner": "mission"},
        "studio_nav_back": [{"page": "creative", "snapshot": {}}],
        "studio_nav_forward": [],
    }
    before = copy.deepcopy(session)

    open_pricing_surface(session, feature=Feature.COMPOSITION_STUDIO)
    assert pricing_surface_should_render(session)
    return_page = close_pricing_surface(session)

    assert return_page == "composer"
    for key, value in before.items():
        assert session[key] == value
    assert set(session) - set(before) <= monetization_session_keys()


def test_navigating_elsewhere_closes_pricing_without_rewriting_the_route() -> None:
    session = {"studio_page": "composer", "display_key": "E"}
    open_pricing_surface(session, feature=Feature.COMPOSITION_STUDIO)
    session["studio_page"] = "practice"

    assert not pricing_surface_should_render(session)
    assert session["studio_page"] == "practice"
    assert session["display_key"] == "E"


@pytest.mark.parametrize(
    ("page_id", "destination"),
    [
        ("practice", "Practice"),
        ("composer", "Composition Studio"),
        ("picker", "Song Selection"),
        ("backing", "Backing Track"),
        ("creative", "Creative Lab"),
        ("custom", "Custom Progression"),
    ],
)
def test_pricing_return_button_includes_established_page_icon(
    page_id: str, destination: str
) -> None:
    icon = page_feature_icon(page_id)
    assert icon
    assert icon == FEATURE_ICONS[
        {
            "practice": "practice",
            "composer": "composition",
            "picker": "songs",
            "backing": "backing",
            "creative": "creative",
            "custom": "custom",
        }[page_id]
    ]
    label = pricing_return_button_label(page_id)
    assert label.startswith(f"{icon} ")
    assert f"Return to {destination}" in label

