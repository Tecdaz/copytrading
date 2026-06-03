# Spec: risk

## ADDED Requirements

### REQ-RISK-1: Position Sizing
`calculate_position_size(account_equity, risk_pct)` SHALL return the USDC amount to risk.

#### Scenario: Default 0.5% risk on 200 USDC
- **Given** `account_equity = Decimal("200")` and `risk_pct = Decimal("0.005")`
- **When** `calculate_position_size(account_equity, risk_pct)` is called
- **Then** the result MUST be `Decimal("1.00")`

### REQ-RISK-2: Decimal Precision
All calculations SHALL use `Decimal` for exact arithmetic.

#### Scenario: No float drift
- **Given** `account_equity = Decimal("199.99")`
- **When** `calculate_position_size(account_equity)` is called
- **Then** the result MUST be exact (no float rounding errors)

### REQ-RISK-3: Default Risk Percentage
`risk_pct` SHALL default to `Decimal("0.005")` (0.5%).

#### Scenario: Omit risk_pct
- **Given** `account_equity = Decimal("1000")`
- **When** `calculate_position_size(account_equity)` is called with no second arg
- **Then** the result MUST be `Decimal("5.00")`

### REQ-RISK-4: Validate Trade
`validate_trade(amount, equity)` SHALL return True if amount <= equity * 0.005.

#### Scenario: Valid trade
- **Given** `amount = Decimal("1")` and `equity = Decimal("200")`
- **When** `validate_trade(amount, equity)` is called
- **Then** the result MUST be `True`

#### Scenario: Invalid trade (too large)
- **Given** `amount = Decimal("10")` and `equity = Decimal("200")`
- **When** `validate_trade(amount, equity)` is called
- **Then** the result MUST be `False`
