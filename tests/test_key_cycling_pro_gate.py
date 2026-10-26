"""Tests for Key Cycling Pro feature gate."""
from __future__ import annotations

import pytest

from monetization_entitlements import (
    AccessDecision,
    Entitlement,
    Feature,
    Plan,
    StaticEntitlementProvider,
    SubscriptionStatus,
    access_decision,
    can_use,
    feature_definition,
)


def _entitlement(plan: Plan, status: SubscriptionStatus) -> Entitlement:
    return Entitlement(plan=plan, status=status, source="test", is_test=True)


# ------------------------------------------------------------------
# Feature catalog
# ------------------------------------------------------------------


class TestKeyCyclingInFeatureCatalog:
    def test_key_cycling_is_a_known_feature(self) -> None:
        defn = feature_definition(Feature.KEY_CYCLING)
        assert defn.key is Feature.KEY_CYCLING

    def test_key_cycling_requires_pro(self) -> None:
        defn = feature_definition(Feature.KEY_CYCLING)
        assert defn.required_plan is Plan.PRO

    def test_key_cycling_has_a_name_and_summary(self) -> None:
        defn = feature_definition(Feature.KEY_CYCLING)
        assert defn.name
        assert defn.summary


# ------------------------------------------------------------------
# Access decisions
# ------------------------------------------------------------------


class TestKeyCyclingAccessDecision:
    def test_free_user_cannot_use_key_cycling(self) -> None:
        free = _entitlement(Plan.FREE, SubscriptionStatus.AUTHENTICATED_FREE)
        assert not can_use(Feature.KEY_CYCLING, entitlement=free)

    def test_free_user_reason_is_upgrade_required(self) -> None:
        free = _entitlement(Plan.FREE, SubscriptionStatus.AUTHENTICATED_FREE)
        decision = access_decision(Feature.KEY_CYCLING, entitlement=free)
        assert not decision.allowed
        assert decision.reason == "upgrade_required"

    @pytest.mark.parametrize(
        "status",
        [
            SubscriptionStatus.TRIALING,
            SubscriptionStatus.ACTIVE,
            SubscriptionStatus.CANCELED_PERIOD_END,
            SubscriptionStatus.DEVELOPMENT,
        ],
    )
    def test_pro_user_can_use_key_cycling(self, status: SubscriptionStatus) -> None:
        pro = _entitlement(Plan.PRO, status)
        assert can_use(Feature.KEY_CYCLING, entitlement=pro)

    def test_past_due_locks_key_cycling(self) -> None:
        past_due = _entitlement(Plan.PRO, SubscriptionStatus.PAST_DUE)
        decision = access_decision(Feature.KEY_CYCLING, entitlement=past_due)
        assert not decision.allowed
        assert decision.reason == "payment_past_due"

    def test_expired_locks_key_cycling(self) -> None:
        expired = _entitlement(Plan.PRO, SubscriptionStatus.EXPIRED)
        decision = access_decision(Feature.KEY_CYCLING, entitlement=expired)
        assert not decision.allowed
        assert decision.reason == "subscription_expired"


# ------------------------------------------------------------------
# Dev/test bypass (rollout off = default)
# ------------------------------------------------------------------


class TestDevModeKeyCyclingBypass:
    def test_rollout_off_allows_key_cycling_for_free_user(self) -> None:
        """Default dev environment: billing rollout is off, so all features are allowed."""
        decision = access_decision(
            Feature.KEY_CYCLING,
            session_state={},
            environ={},
        )
        assert decision.allowed
        assert decision.reason == "billing_rollout_disabled"

    def test_foundation_free_with_no_billing_env_allows_key_cycling(self) -> None:
        decision = access_decision(
            Feature.KEY_CYCLING,
            session_state={},
            environ={},
        )
        assert decision.allowed


# ------------------------------------------------------------------
# start_key_cycle gate
# ------------------------------------------------------------------


class TestStartKeyCycleGate:
    def _minimal_session(self) -> dict:
        """Session with enough state for start_key_cycle to run."""
        from backing_key_cycle import (
            BACKING_KEY_CYCLE_UI_OWNER_KEY,
        )

        return {
            BACKING_KEY_CYCLE_UI_OWNER_KEY: "catalog",
            "backing_owner_identity": "catalog",
            "saved_practice_key": "C",
            "practice_key": "C",
        }

    def test_free_user_start_returns_empty_and_no_mutation(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from backing_key_cycle import start_key_cycle, is_cycle_active

        # Simulate enforcement ON so rollout bypass does not apply.
        monkeypatch.setenv("MUSIC_BILLING_ROLLOUT", "test")
        session = self._minimal_session()

        result = start_key_cycle(
            session,
            start_key="C",
        )

        assert result == {}
        assert not is_cycle_active(session)

    def test_pro_user_start_creates_cycle(self) -> None:
        from backing_key_cycle import start_key_cycle, is_cycle_active

        session = self._minimal_session()

        # Default rollout=off means start_key_cycle is allowed
        result = start_key_cycle(
            session,
            start_key="C",
        )

        assert result != {}
        assert result.get("enabled") is True
        assert is_cycle_active(session)

    def test_dev_mode_default_allows_start(self) -> None:
        """Without any entitlement env vars (default), KC starts normally."""
        from backing_key_cycle import start_key_cycle, is_cycle_active

        session = self._minimal_session()
        result = start_key_cycle(session, start_key="C")
        assert result != {}
        assert is_cycle_active(session)


# ------------------------------------------------------------------
# render gate (source code structure)
# ------------------------------------------------------------------


class TestRenderGateStructure:
    def test_render_function_checks_entitlement_before_radio(self) -> None:
        """The render function must check access_decision before showing the Off/On radio."""
        import inspect
        from backing_key_cycle import render_backing_key_cycle_controls

        source = inspect.getsource(render_backing_key_cycle_controls)
        gate_pos = source.find("access_decision")
        radio_pos = source.find("st.radio")
        assert gate_pos != -1, "render function must call access_decision"
        assert radio_pos != -1, "render function must have st.radio"
        assert gate_pos < radio_pos, "entitlement check must come before the radio widget"

    def test_render_function_calls_render_locked_feature_when_denied(self) -> None:
        import inspect
        from backing_key_cycle import render_backing_key_cycle_controls

        source = inspect.getsource(render_backing_key_cycle_controls)
        assert "render_locked_feature" in source
