# Spec: polymarket-public-client

## ADDED Requirements

### REQ-POLY-1: Read-Only Interface
`PolyClient` SHALL expose exactly 4 read-only methods: `get_markets`, `get_market`, `get_positions`, `get_orderbook`.

#### Scenario: No write methods exist
- **Given** a `PolyClient` instance
- **When** inspecting its public methods
- **Then** there MUST NOT be any method containing `place`, `cancel`, `create_order`, `post_order`, or `execute`

### REQ-POLY-2: httpx-Based, No Auth
`PolyClient` SHALL use `httpx` for HTTP requests with no authentication.

#### Scenario: Requests have no auth headers
- **Given** a `PolyClient` with a fake HTTP transport
- **When** `get_markets()` is called
- **Then** the request MUST NOT include Authorization, API-Key, or signature headers

### REQ-POLY-3: get_markets
`get_markets()` SHALL return a list of `Market` dataclass instances.

#### Scenario: Fetch active markets
- **Given** the Polymarket CLOB API returns valid JSON
- **When** `get_markets()` is called
- **Then** the result MUST be a list of `Market` objects

### REQ-POLY-4: get_positions
`get_positions(wallet_address)` SHALL return positions for a given wallet.

#### Scenario: Fetch wallet positions
- **Given** a wallet address with open positions
- **When** `get_positions("0xabc...")` is called
- **Then** the result MUST be a list of `Position` objects

### REQ-POLY-5: Error Handling
All methods SHALL raise `PolyClientError` on HTTP failures or invalid responses.

#### Scenario: HTTP error
- **Given** the API returns a 500 status
- **When** any method is called
- **Then** `PolyClientError` MUST be raised with the status code

### REQ-POLY-6: No py-clob-client Import
The module SHALL NOT import `py_clob_client`.

#### Scenario: Import check
- **Given** the `poly_client` module
- **When** it is imported
- **Then** `sys.modules` MUST NOT contain `py_clob_client`
