"""Shared Streamlit surfaces for plans, pricing, and locked features."""

from __future__ import annotations

import html
import os
from typing import Any, Mapping

import requests

from monetization_entitlements import (
    DEV_PLAN_ENV,
    DEV_SESSION_PLAN_KEY,
    FEATURE_CATALOG,
    AccessDecision,
    Feature,
    Plan,
    access_decision,
    development_overrides_enabled,
    feature_definition,
    resolve_entitlement,
)


PRICING_SURFACE_OPEN_KEY = "_monetization_pricing_open"
PRICING_RETURN_PAGE_KEY = "_monetization_pricing_return_page"
PRICING_FEATURE_KEY = "_monetization_pricing_feature"
CHECKOUT_URL_KEY = "_monetization_checkout_url"
CHECKOUT_ERROR_KEY = "_monetization_checkout_error"

_MONETIZATION_SESSION_KEYS = frozenset(
    {
        DEV_SESSION_PLAN_KEY,
        PRICING_SURFACE_OPEN_KEY,
        PRICING_RETURN_PAGE_KEY,
        PRICING_FEATURE_KEY,
        CHECKOUT_URL_KEY,
        CHECKOUT_ERROR_KEY,
    }
)


def open_pricing_surface(
    session_state: dict[str, Any],
    *,
    feature: Feature | str | None = None,
    return_page: str = "",
) -> None:
    """Open pricing without changing the underlying studio route or music state."""
    page = str(return_page or session_state.get("studio_page") or "practice").strip() or "practice"
    session_state[PRICING_SURFACE_OPEN_KEY] = True
    session_state[PRICING_RETURN_PAGE_KEY] = page
    if feature is None:
        session_state.pop(PRICING_FEATURE_KEY, None)
    else:
        session_state[PRICING_FEATURE_KEY] = feature_definition(feature).key.value


def close_pricing_surface(session_state: dict[str, Any]) -> str:
    """Close pricing and return the untouched underlying studio page id."""
    page = str(
        session_state.get(PRICING_RETURN_PAGE_KEY)
        or session_state.get("studio_page")
        or "practice"
    ).strip() or "practice"
    session_state.pop(PRICING_SURFACE_OPEN_KEY, None)
    session_state.pop(PRICING_RETURN_PAGE_KEY, None)
    session_state.pop(PRICING_FEATURE_KEY, None)
    return page


def pricing_surface_is_open(session_state: Mapping[str, Any]) -> bool:
    return bool(session_state.get(PRICING_SURFACE_OPEN_KEY))


def pricing_surface_should_render(session_state: dict[str, Any]) -> bool:
    """Let ordinary studio navigation leave pricing without hijacking the route."""
    if not pricing_surface_is_open(session_state):
        return False
    origin = str(session_state.get(PRICING_RETURN_PAGE_KEY) or "").strip()
    current = str(session_state.get("studio_page") or "").strip()
    if origin and current and origin != current:
        close_pricing_surface(session_state)
        return False
    return True


def monetization_session_keys() -> frozenset[str]:
    """Keys the M1 UI is permitted to mutate (used by state-safety tests)."""
    return _MONETIZATION_SESSION_KEYS


def locked_feature_view_model(decision: AccessDecision) -> dict[str, str]:
    feature = decision.feature
    return {
        "feature_key": feature.key.value,
        "title": f"{feature.name} is included with Pro",
        "summary": feature.summary,
        "required_plan": feature.required_plan.value,
        "action_label": "Compare Free and Pro",
        "reason": decision.reason,
    }


def development_controls_visible(environ: Mapping[str, str] | None = None) -> bool:
    """UI control is available only in an explicitly local/test server runtime."""
    return development_overrides_enabled(os.environ if environ is None else environ)


def _sync_development_plan_default(
    session_state: dict[str, Any],
    environ: Mapping[str, str] | None = None,
) -> None:
    env = os.environ if environ is None else environ
    value = str(session_state.get(DEV_SESSION_PLAN_KEY) or env.get(DEV_PLAN_ENV) or Plan.FREE.value)
    session_state[DEV_SESSION_PLAN_KEY] = (
        Plan.PRO.value if value.strip().lower() == Plan.PRO.value else Plan.FREE.value
    )


def render_development_entitlement_control(st: Any, *, sidebar: bool = False) -> bool:
    """Render the server-gated Free/Pro simulator; return whether it was shown."""
    if not development_controls_visible():
        return False
    _sync_development_plan_default(st.session_state)
    ui = st.sidebar if sidebar else st
    ui.selectbox(
        "Entitlement preview",
        options=[Plan.FREE.value, Plan.PRO.value],
        format_func=lambda value: str(value).title(),
        key=DEV_SESSION_PLAN_KEY,
        help=(
            "Local/test simulation only. Production access will come from trusted "
            "account and subscription records."
        ),
    )
    ui.caption("Development simulation — no payment has occurred.")
    return True


def render_entitlement_sidebar(st: Any) -> None:
    """Compact plan status and entry point to the pricing surface."""
    entitlement = resolve_entitlement(st.session_state)
    from monetization_config import BillingConfig

    config = BillingConfig.from_environ()
    label = "Open access" if not config.enforcement_enabled else ("Pro" if entitlement.grants_pro else "Free")
    st.sidebar.markdown("**Membership**")
    st.sidebar.caption(f"Current access: **{label}**")
    if st.sidebar.button(
        "View plans",
        key="monetization_sidebar_view_plans",
        use_container_width=True,
    ):
        open_pricing_surface(st.session_state)
        st.rerun()
    if development_controls_visible():
        with st.sidebar.expander("Entitlement preview (dev)", expanded=False):
            render_development_entitlement_control(st)


def render_locked_feature(
    st: Any,
    feature: Feature | str,
    *,
    decision: AccessDecision | None = None,
) -> AccessDecision:
    """Shared non-destructive locked state for a premium feature."""
    value = decision or access_decision(feature, session_state=st.session_state)
    model = locked_feature_view_model(value)
    st.markdown(
        f"""
<div data-monetization-locked-feature="{html.escape(model['feature_key'])}" style="
  border: 1px solid rgba(79,70,229,.28);
  border-radius: 18px;
  padding: 1.15rem 1.25rem;
  margin: .35rem 0 .8rem;
  background: linear-gradient(135deg,#eef2ff 0%,#ffffff 72%);
  box-shadow: 0 12px 34px -25px rgba(49,46,129,.55);">
  <div style="font-size:.74rem;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:#4f46e5;">
    Pro workspace
  </div>
  <div style="font-size:1.35rem;font-weight:850;color:#111827;margin-top:.2rem;">
    {html.escape(model['title'])}
  </div>
  <div style="color:#475569;margin-top:.35rem;line-height:1.55;">
    {html.escape(model['summary'])}
  </div>
  <div style="color:#64748b;margin-top:.55rem;font-size:.88rem;">
    Your current song, Practice Key, backing owner, and navigation state are unchanged.
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )
    if st.button(
        model["action_label"],
        key=f"monetization_unlock_{model['feature_key']}",
        type="primary",
    ):
        open_pricing_surface(st.session_state, feature=feature)
        st.rerun()
    st.caption("Checkout is not connected in M1. Viewing plans does not start or complete a payment.")
    return value


def _feature_names(plan: Plan) -> list[str]:
    if plan is Plan.FREE:
        return [
            "Practice, charts, tuner, and transposition",
            "Songs, custom progressions, and Backing Studio",
            "Creative Entry & Jam, Missions, and Phrase / Motif",
            "Core Practice Log",
        ]
    return [
        "Everything in Free",
        FEATURE_CATALOG[Feature.COMPOSITION_STUDIO].name,
        "Advanced upload analysis and analytics",
        "Multitrack export and advanced AI coaching",
        "Advanced karaoke and setlist workflows",
    ]


def request_checkout(
    session_state: Mapping[str, Any],
    *,
    interval: str,
    environ: Mapping[str, str] | None = None,
) -> str:
    """Ask the separate billing service for a Checkout URL using the user JWT."""
    from monetization_config import BillingConfig
    from suite_auth import AUTH_TOKENS_KEY

    config = BillingConfig.from_environ(os.environ if environ is None else environ)
    tokens = session_state.get(AUTH_TOKENS_KEY) or {}
    access_token = str(tokens.get("access_token") or "") if isinstance(tokens, Mapping) else ""
    if not config.checkout_enabled or not config.billing_service_url or not access_token:
        raise RuntimeError("Subscription checkout is not available for this deployment or session.")
    response = requests.post(
        f"{config.billing_service_url}/billing/checkout",
        json={"interval": interval},
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=12,
    )
    if not response.ok:
        raise RuntimeError("Subscription checkout could not be started.")
    payload = response.json()
    url = str(payload.get("url") or "") if isinstance(payload, Mapping) else ""
    if not url.startswith("https://"):
        raise RuntimeError("The billing service returned an invalid Checkout URL.")
    return url


def _render_plan_card(st: Any, plan: Plan, *, current: bool) -> None:
    title = "Free" if plan is Plan.FREE else "Pro"
    kicker = "Build a durable practice habit" if plan is Plan.FREE else "Create, analyze, and go deeper"
    current_badge = " · Current" if current else ""
    st.markdown(f"### {title}{current_badge}")
    st.caption(kicker)
    for name in _feature_names(plan):
        st.markdown(f"✓ {name}")
    if plan is Plan.FREE:
        st.button(
            "Current free access" if current else "Free access included",
            key="monetization_free_plan_action",
            disabled=True,
            use_container_width=True,
        )
    else:
        from monetization_config import BillingConfig

        config = BillingConfig.from_environ()
        if current:
            st.button("Current Pro access", disabled=True, use_container_width=True)
        elif config.checkout_enabled and config.billing_service_url:
            if st.button("Start monthly Pro", key="monetization_pro_checkout", use_container_width=True):
                try:
                    st.session_state[CHECKOUT_URL_KEY] = request_checkout(
                        st.session_state,
                        interval="monthly",
                    )
                    st.session_state.pop(CHECKOUT_ERROR_KEY, None)
                except RuntimeError as exc:
                    st.session_state[CHECKOUT_ERROR_KEY] = str(exc)
            checkout_url = str(st.session_state.get(CHECKOUT_URL_KEY) or "")
            if checkout_url:
                st.link_button("Continue to secure checkout", checkout_url, use_container_width=True)
            error = str(st.session_state.get(CHECKOUT_ERROR_KEY) or "")
            if error:
                st.warning(error)
        else:
            st.button(
                "Checkout not enabled",
                key="monetization_pro_checkout_placeholder",
                disabled=True,
                use_container_width=True,
                help="This deployment has not enabled subscription checkout.",
            )


def render_pricing_surface(st: Any) -> bool:
    """Render pricing/upgrade UI over the current route without changing it."""
    if not pricing_surface_should_render(st.session_state):
        return False

    entitlement = resolve_entitlement(st.session_state)
    requested_key = str(st.session_state.get(PRICING_FEATURE_KEY) or "").strip()
    try:
        requested = FEATURE_CATALOG.get(Feature(requested_key)) if requested_key else None
    except ValueError:
        requested = None

    st.markdown(
        '<div data-monetization-pricing="m2" style="font-size:.76rem;font-weight:800;'
        'letter-spacing:.08em;text-transform:uppercase;color:#4f46e5;">Membership</div>',
        unsafe_allow_html=True,
    )
    st.title("Practice freely. Go Pro when you need deeper tools.")
    from monetization_config import BillingConfig

    config = BillingConfig.from_environ()
    if config.checkout_enabled:
        st.caption("Checkout is created by the trusted billing service; access changes only after a verified webhook.")
    else:
        st.caption("Billing enforcement and checkout are not enabled for this deployment.")
    if requested is not None:
        st.info(f"You opened plans from **{requested.name}**. {requested.summary}")

    free_col, pro_col = st.columns(2)
    with free_col:
        with st.container(border=True):
            _render_plan_card(st, Plan.FREE, current=not entitlement.grants_pro)
    with pro_col:
        with st.container(border=True):
            _render_plan_card(st, Plan.PRO, current=entitlement.grants_pro)

    if development_controls_visible():
        st.caption("Use **Entitlement preview (dev)** in the sidebar to switch Free / Pro access.")

    return_page = str(st.session_state.get(PRICING_RETURN_PAGE_KEY) or "practice").strip()
    return_label = return_page.replace("_", " ").title()
    if return_page == "composer":
        return_label = "Composition Studio"
    if st.button(
        f"← Return to {return_label}",
        key="monetization_pricing_return",
        use_container_width=False,
    ):
        close_pricing_surface(st.session_state)
        st.rerun()
    return True


__all__ = (
    "PRICING_FEATURE_KEY",
    "PRICING_RETURN_PAGE_KEY",
    "PRICING_SURFACE_OPEN_KEY",
    "CHECKOUT_ERROR_KEY",
    "CHECKOUT_URL_KEY",
    "close_pricing_surface",
    "development_controls_visible",
    "locked_feature_view_model",
    "monetization_session_keys",
    "open_pricing_surface",
    "pricing_surface_is_open",
    "pricing_surface_should_render",
    "request_checkout",
    "render_development_entitlement_control",
    "render_entitlement_sidebar",
    "render_locked_feature",
    "render_pricing_surface",
)
