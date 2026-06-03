"""Tests for risk management calculations."""

from __future__ import annotations

from decimal import Decimal

from copytrading.risk import calculate_position_size, validate_exposure, validate_trade


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
