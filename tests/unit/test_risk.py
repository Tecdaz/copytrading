"""Tests for risk management calculations."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from copytrading.risk import (
    is_position_fresh,
    total_exposure,
    trade_value,
    validate_entry_price,
    validate_exposure,
)


class TestValidateExposure:
    def test_no_exposure_allows_trade(self) -> None:
        # 200 * 0.10 = 20 max exposure, adding 1.00 is fine
        assert validate_exposure(Decimal("0"), Decimal("1.00"), Decimal("200")) is True

    def test_at_limit_rejects_new_trade(self) -> None:
        # 200 * 0.10 = 20, already at 20, adding 1.00 exceeds
        assert validate_exposure(Decimal("20"), Decimal("1.00"), Decimal("200")) is False

    def test_near_limit_allows_small_trade(self) -> None:
        # 200 * 0.10 = 20, at 19.50, adding 0.50 = 20.00 exactly, should pass
        assert validate_exposure(Decimal("19.50"), Decimal("0.50"), Decimal("200")) is True

    def test_near_limit_rejects_large_trade(self) -> None:
        # 200 * 0.10 = 20, at 19.50, adding 1.00 = 20.50 exceeds
        assert validate_exposure(Decimal("19.50"), Decimal("1.00"), Decimal("200")) is False

    def test_over_limit_rejects_any_trade(self) -> None:
        # Already over 10%, any new trade should be rejected
        assert validate_exposure(Decimal("25"), Decimal("0.01"), Decimal("200")) is False

    def test_zero_equity_rejects_all(self) -> None:
        # 0 * 0.10 = 0, no exposure allowed
        assert validate_exposure(Decimal("0"), Decimal("1.00"), Decimal("0")) is False

    def test_exact_boundary(self) -> None:
        # 200 * 0.10 = 20, adding exactly to reach 20 should pass
        assert validate_exposure(Decimal("19"), Decimal("1.00"), Decimal("200")) is True
        # But 20.01 should fail
        assert validate_exposure(Decimal("19"), Decimal("1.01"), Decimal("200")) is False


class TestTradeValue:
    def test_basic_calculation(self) -> None:
        # $1 at 0.50 entry = $0.50 equity at stake
        assert trade_value(Decimal("1.00"), Decimal("0.50")) == Decimal("0.50")

    def test_high_price(self) -> None:
        # $1 at 0.95 entry = $0.95 equity at stake
        assert trade_value(Decimal("1.00"), Decimal("0.95")) == Decimal("0.95")

    def test_zero_price(self) -> None:
        assert trade_value(Decimal("1.00"), Decimal("0")) == Decimal("0.00")


class TestTotalExposure:
    def test_empty_list(self) -> None:
        assert total_exposure([]) == Decimal("0")

    def test_sums_size_times_entry_price(self) -> None:
        @dataclass
        class T:
            size: Decimal
            entry_price: Decimal

        trades = [
            T(Decimal("1.00"), Decimal("0.50")),  # 0.50
            T(Decimal("1.00"), Decimal("0.80")),  # 0.80
            T(Decimal("1.00"), Decimal("0.20")),  # 0.20
        ]
        # 0.50 + 0.80 + 0.20 = 1.50
        assert total_exposure(trades) == Decimal("1.50")


class TestIsPositionFresh:
    def test_exact_match_is_fresh(self) -> None:
        assert is_position_fresh(Decimal("0.50"), Decimal("0.50")) is True

    def test_within_half_percent_is_fresh(self) -> None:
        assert is_position_fresh(Decimal("1.00"), Decimal("1.005")) is True

    def test_at_one_percent_boundary_is_fresh(self) -> None:
        assert is_position_fresh(Decimal("1.00"), Decimal("1.01")) is True

    def test_over_one_percent_is_not_fresh(self) -> None:
        assert is_position_fresh(Decimal("1.00"), Decimal("1.02")) is False

    def test_avg_price_zero_returns_false(self) -> None:
        assert is_position_fresh(Decimal("0"), Decimal("0.50")) is False


class TestValidateEntryPrice:
    def test_midpoint_at_exactly_half_percent_passes(self) -> None:
        # 200 * 0.005 = 1.00
        assert validate_entry_price(Decimal("1.00"), Decimal("200")) is True

    def test_midpoint_under_half_percent_passes(self) -> None:
        assert validate_entry_price(Decimal("0.50"), Decimal("200")) is True

    def test_midpoint_over_half_percent_fails(self) -> None:
        assert validate_entry_price(Decimal("1.01"), Decimal("200")) is False

    def test_zero_equity_fails(self) -> None:
        assert validate_entry_price(Decimal("1.00"), Decimal("0")) is False
