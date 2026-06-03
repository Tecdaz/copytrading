"""Tests for risk management calculations."""

from __future__ import annotations

from decimal import Decimal

from copytrading.risk import calculate_position_size, validate_trade


class TestCalculatePositionSize:
    def test_default_risk_on_200_usdc(self) -> None:
        result = calculate_position_size(Decimal("200"))
        assert result == Decimal("1.00")

    def test_explicit_risk_pct(self) -> None:
        result = calculate_position_size(Decimal("200"), Decimal("0.01"))
        assert result == Decimal("2.00")

    def test_no_float_drift(self) -> None:
        result = calculate_position_size(Decimal("199.99"))
        # 199.99 * 0.005 = 0.99995 -> rounds to 1.00
        assert result == Decimal("1.00")

    def test_large_equity(self) -> None:
        result = calculate_position_size(Decimal("10000"))
        assert result == Decimal("50.00")

    def test_small_equity(self) -> None:
        result = calculate_position_size(Decimal("10"))
        assert result == Decimal("0.05")

    def test_zero_equity(self) -> None:
        result = calculate_position_size(Decimal("0"))
        assert result == Decimal("0.00")


class TestValidateTrade:
    def test_valid_trade_at_limit(self) -> None:
        assert validate_trade(Decimal("1.00"), Decimal("200")) is True

    def test_valid_trade_under_limit(self) -> None:
        assert validate_trade(Decimal("0.50"), Decimal("200")) is True

    def test_invalid_trade_over_limit(self) -> None:
        assert validate_trade(Decimal("10"), Decimal("200")) is False

    def test_invalid_trade_way_over(self) -> None:
        assert validate_trade(Decimal("100"), Decimal("200")) is False

    def test_exact_boundary(self) -> None:
        # 200 * 0.005 = 1.00, so amount=1.00 should be valid
        assert validate_trade(Decimal("1.00"), Decimal("200")) is True
        # 1.01 should be invalid
        assert validate_trade(Decimal("1.01"), Decimal("200")) is False
