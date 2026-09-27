"""Product-level plans, features, and entitlement decisions.

M1 deliberately keeps payment-provider details out of application pages.  UI code
asks :func:`can_use` (or :func:`access_decision`) about a product feature.  A
future trusted provider can implement :class:`EntitlementProvider` using billing
state stored in Supabase; Stripe objects never need to leak into page code.

Development overrides are accepted only when the server process explicitly opts
in with ``MUSIC_ENTITLEMENT_DEV_CONTROLS=1``.  Session state alone can never turn
the production foundation provider into a paid entitlement.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Mapping, Protocol


class Plan(str, Enum):
    FREE = "free"
    PRO = "pro"


class SubscriptionStatus(str, Enum):
    ANONYMOUS = "anonymous"
    AUTHENTICATED_FREE = "authenticated_free"
    TRIALING = "trialing"
    ACTIVE = "active"
    CANCELED_PERIOD_END = "canceled_period_end"
    PAST_DUE = "past_due"
    EXPIRED = "expired"
    DEVELOPMENT = "development"


class Feature(str, Enum):
    PRACTICE_BASICS = "practice_basics"
    SONG_LIBRARY = "song_library"
    BACKING_STUDIO = "backing_studio"
    CUSTOM_PROGRESSIONS = "custom_progressions"
    CREATIVE_ENTRY_JAM = "creative_entry_jam"
    MISSIONS = "missions"
    PHRASE_MOTIF = "phrase_motif"
    INSTRUMENT_TOOLS = "instrument_tools"
    PRACTICE_LOG = "practice_log"
    COMPOSITION_STUDIO = "composition_studio"
    UPLOAD_ANALYSIS = "upload_analysis"
    MULTITRACK_EXPORT = "multitrack_export"
    ADVANCED_AI_COACHING = "advanced_ai_coaching"
    ADVANCED_ANALYTICS = "advanced_analytics"
    KARAOKE_SETLISTS = "karaoke_setlists"


@dataclass(frozen=True)
class FeatureDefinition:
    key: Feature
    name: str
    required_plan: Plan
    summary: str


FEATURE_CATALOG: dict[Feature, FeatureDefinition] = {
    Feature.PRACTICE_BASICS: FeatureDefinition(
        Feature.PRACTICE_BASICS,
        "Practice basics",
        Plan.FREE,
        "Core practice controls, charts, metronome, tone, and tuner.",
    ),
    Feature.SONG_LIBRARY: FeatureDefinition(
        Feature.SONG_LIBRARY,
        "Songs and library",
        Plan.FREE,
        "Browse the catalog and keep an active song across the studio.",
    ),
    Feature.BACKING_STUDIO: FeatureDefinition(
        Feature.BACKING_STUDIO,
        "Backing Studio",
        Plan.FREE,
        "Generate and practice with source-aware backing tracks.",
    ),
    Feature.CUSTOM_PROGRESSIONS: FeatureDefinition(
        Feature.CUSTOM_PROGRESSIONS,
        "Custom Progressions",
        Plan.FREE,
        "Build and practice custom chord progressions.",
    ),
    Feature.CREATIVE_ENTRY_JAM: FeatureDefinition(
        Feature.CREATIVE_ENTRY_JAM,
        "Creative Entry & Jam",
        Plan.FREE,
        "Explore improvisation with the core Entry & Jam tools.",
    ),
    Feature.MISSIONS: FeatureDefinition(
        Feature.MISSIONS,
        "Missions",
        Plan.FREE,
        "Use guided improvisation missions and mission backing.",
    ),
    Feature.PHRASE_MOTIF: FeatureDefinition(
        Feature.PHRASE_MOTIF,
        "Phrase and Motif",
        Plan.FREE,
        "Develop short musical ideas with phrase and motif tools.",
    ),
    Feature.INSTRUMENT_TOOLS: FeatureDefinition(
        Feature.INSTRUMENT_TOOLS,
        "Instrument and transposition tools",
        Plan.FREE,
        "Use written-key, capo, and instrument-aware practice views.",
    ),
    Feature.PRACTICE_LOG: FeatureDefinition(
        Feature.PRACTICE_LOG,
        "Practice Log",
        Plan.FREE,
        "Save and review core practice sessions.",
    ),
    Feature.COMPOSITION_STUDIO: FeatureDefinition(
        Feature.COMPOSITION_STUDIO,
        "Composition Studio",
        Plan.PRO,
        "Develop complete songs with form, harmony, melody, and playback tools.",
    ),
    Feature.UPLOAD_ANALYSIS: FeatureDefinition(
        Feature.UPLOAD_ANALYSIS,
        "Advanced upload analysis",
        Plan.PRO,
        "Analyze recordings with richer coaching and retained history.",
    ),
    Feature.MULTITRACK_EXPORT: FeatureDefinition(
        Feature.MULTITRACK_EXPORT,
        "Multitrack and export",
        Plan.PRO,
        "Build layered practice recordings and export mixes.",
    ),
    Feature.ADVANCED_AI_COACHING: FeatureDefinition(
        Feature.ADVANCED_AI_COACHING,
        "Advanced AI coaching",
        Plan.PRO,
        "Use higher-cost personalized coaching workflows.",
    ),
    Feature.ADVANCED_ANALYTICS: FeatureDefinition(
        Feature.ADVANCED_ANALYTICS,
        "Advanced analytics",
        Plan.PRO,
        "Unlock longitudinal reports and deeper performance insights.",
    ),
    Feature.KARAOKE_SETLISTS: FeatureDefinition(
        Feature.KARAOKE_SETLISTS,
        "Advanced karaoke and setlists",
        Plan.PRO,
        "Build longer performance setlists and advanced karaoke workflows.",
    ),
}


@dataclass(frozen=True)
class EntitlementSubject:
    user_id: str = ""
    authenticated: bool = False


@dataclass(frozen=True)
class Entitlement:
    plan: Plan
    status: SubscriptionStatus
    source: str
    subject: EntitlementSubject = EntitlementSubject()
    current_period_end: datetime | None = None
    is_test: bool = False

    @property
    def grants_pro(self) -> bool:
        if self.plan is not Plan.PRO:
            return False
        return self.status in {
            SubscriptionStatus.TRIALING,
            SubscriptionStatus.ACTIVE,
            SubscriptionStatus.CANCELED_PERIOD_END,
            SubscriptionStatus.DEVELOPMENT,
        }


@dataclass(frozen=True)
class AccessDecision:
    feature: FeatureDefinition
    entitlement: Entitlement
    allowed: bool
    reason: str


class EntitlementProvider(Protocol):
    """Trusted boundary implemented by the M2 server/database integration."""

    def entitlement_for(self, subject: EntitlementSubject) -> Entitlement:
        ...


@dataclass(frozen=True)
class StaticEntitlementProvider:
    """Deterministic provider for unit tests and server-owned local tooling."""

    entitlement: Entitlement

    def entitlement_for(self, subject: EntitlementSubject) -> Entitlement:
        value = self.entitlement
        if value.subject == EntitlementSubject() and subject != value.subject:
            return Entitlement(
                plan=value.plan,
                status=value.status,
                source=value.source,
                subject=subject,
                current_period_end=value.current_period_end,
                is_test=value.is_test,
            )
        return value


DEV_CONTROLS_ENV = "MUSIC_ENTITLEMENT_DEV_CONTROLS"
DEV_RUNTIME_ENV = "MUSIC_ENTITLEMENT_RUNTIME"
DEV_PLAN_ENV = "MUSIC_ENTITLEMENT_DEV_PLAN"
DEV_SESSION_PLAN_KEY = "_monetization_dev_plan"


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def development_overrides_enabled(environ: Mapping[str, str] | None = None) -> bool:
    """Server-owned switch for local/test entitlement simulation."""
    env = os.environ if environ is None else environ
    runtime = str(env.get(DEV_RUNTIME_ENV) or "").strip().lower()
    return _truthy(env.get(DEV_CONTROLS_ENV)) and runtime in {"local", "test"}


def entitlement_subject(session_state: Mapping[str, Any] | None = None) -> EntitlementSubject:
    """Resolve account identity without treating workspace/profile ids as auth."""
    session = session_state or {}
    try:
        from suite_auth import (
            AUTH_USER_ID_KEY,
            is_auth_enabled,
            is_authenticated,
        )

        if is_auth_enabled() and is_authenticated(dict(session)):
            return EntitlementSubject(
                user_id=str(session.get(AUTH_USER_ID_KEY) or "").strip(),
                authenticated=True,
            )
    except Exception:
        pass
    return EntitlementSubject()


def _foundation_entitlement(subject: EntitlementSubject) -> Entitlement:
    status = (
        SubscriptionStatus.AUTHENTICATED_FREE
        if subject.authenticated
        else SubscriptionStatus.ANONYMOUS
    )
    return Entitlement(
        plan=Plan.FREE,
        status=status,
        source="foundation",
        subject=subject,
    )


def _development_entitlement(
    subject: EntitlementSubject,
    plan_value: Any,
) -> Entitlement:
    plan = Plan.PRO if str(plan_value or "").strip().lower() == Plan.PRO.value else Plan.FREE
    return Entitlement(
        plan=plan,
        status=SubscriptionStatus.DEVELOPMENT,
        source="development_override",
        subject=subject,
        is_test=True,
    )


def resolve_entitlement(
    session_state: Mapping[str, Any] | None = None,
    *,
    provider: EntitlementProvider | None = None,
    environ: Mapping[str, str] | None = None,
) -> Entitlement:
    """Resolve a single product entitlement for the current request/session."""
    session = session_state or {}
    subject = entitlement_subject(session)
    if provider is not None:
        return provider.entitlement_for(subject)

    env = os.environ if environ is None else environ
    if development_overrides_enabled(env):
        override = session.get(DEV_SESSION_PLAN_KEY) or env.get(DEV_PLAN_ENV)
        if str(override or "").strip().lower() in {Plan.FREE.value, Plan.PRO.value}:
            return _development_entitlement(subject, override)
    # Production billing reads only a server-derived row protected by Supabase
    # RLS. The browser/session cannot supply a plan or subscription state.
    try:
        from monetization_config import BillingConfig

        config = BillingConfig.from_environ(env)
        if config.enforcement_enabled and subject.authenticated:
            from suite_auth import AUTH_TOKENS_KEY
            from monetization_supabase import SupabaseEntitlementProvider

            tokens = session.get(AUTH_TOKENS_KEY) or {}
            access_token = str(tokens.get("access_token") or "") if isinstance(tokens, Mapping) else ""
            if config.supabase_url and config.supabase_anon_key and access_token:
                return SupabaseEntitlementProvider(config, access_token).entitlement_for(subject)
            return Entitlement(
                Plan.FREE,
                SubscriptionStatus.AUTHENTICATED_FREE,
                "billing_unavailable",
                subject,
            )
    except Exception:
        if subject.authenticated:
            return Entitlement(
                Plan.FREE,
                SubscriptionStatus.AUTHENTICATED_FREE,
                "billing_unavailable",
                subject,
            )
    return _foundation_entitlement(subject)


def feature_definition(feature: Feature | str) -> FeatureDefinition:
    try:
        key = feature if isinstance(feature, Feature) else Feature(str(feature))
    except ValueError as exc:
        raise KeyError(f"Unknown monetization feature: {feature!r}") from exc
    return FEATURE_CATALOG[key]


def access_decision(
    feature: Feature | str,
    *,
    entitlement: Entitlement | None = None,
    session_state: Mapping[str, Any] | None = None,
    provider: EntitlementProvider | None = None,
    environ: Mapping[str, str] | None = None,
) -> AccessDecision:
    definition = feature_definition(feature)
    value = entitlement or resolve_entitlement(
        session_state,
        provider=provider,
        environ=environ,
    )
    env = os.environ if environ is None else environ
    rollout_open = False
    if definition.required_plan is Plan.PRO and value.source == "foundation":
        try:
            from monetization_config import billing_enforcement_enabled

            rollout_open = not billing_enforcement_enabled(env)
        except Exception:
            # The safest rollout failure is to preserve the pre-commerce product.
            rollout_open = True
    allowed = definition.required_plan is Plan.FREE or value.grants_pro or rollout_open
    if allowed:
        if definition.required_plan is Plan.FREE:
            reason = "included_in_free"
        elif rollout_open:
            reason = "billing_rollout_disabled"
        else:
            reason = "pro_entitled"
    elif value.status is SubscriptionStatus.PAST_DUE:
        reason = "payment_past_due"
    elif value.status is SubscriptionStatus.EXPIRED:
        reason = "subscription_expired"
    else:
        reason = "upgrade_required"
    return AccessDecision(definition, value, allowed, reason)


def can_use(
    feature: Feature | str,
    *,
    entitlement: Entitlement | None = None,
    session_state: Mapping[str, Any] | None = None,
    provider: EntitlementProvider | None = None,
    environ: Mapping[str, str] | None = None,
) -> bool:
    """The reusable application access-check API."""
    return access_decision(
        feature,
        entitlement=entitlement,
        session_state=session_state,
        provider=provider,
        environ=environ,
    ).allowed


def features_for_plan(plan: Plan | str) -> tuple[FeatureDefinition, ...]:
    value = plan if isinstance(plan, Plan) else Plan(str(plan))
    if value is Plan.PRO:
        return tuple(FEATURE_CATALOG.values())
    return tuple(item for item in FEATURE_CATALOG.values() if item.required_plan is Plan.FREE)


__all__ = (
    "AccessDecision",
    "DEV_CONTROLS_ENV",
    "DEV_PLAN_ENV",
    "DEV_RUNTIME_ENV",
    "DEV_SESSION_PLAN_KEY",
    "Entitlement",
    "EntitlementProvider",
    "EntitlementSubject",
    "FEATURE_CATALOG",
    "Feature",
    "FeatureDefinition",
    "Plan",
    "StaticEntitlementProvider",
    "SubscriptionStatus",
    "access_decision",
    "can_use",
    "development_overrides_enabled",
    "entitlement_subject",
    "feature_definition",
    "features_for_plan",
    "resolve_entitlement",
)
