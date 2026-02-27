# GhostPayments — Build Plan

> Self-hosted, non-custodial crypto payment processor for BSC & Polygon.  
> Part of the Ghost ecosystem: GhostWire · GhostGate · GhostPass · **GhostPayments**

---

## Name

**GhostPayments** — verified unique in the open-source crypto processor space. Fits the Ghost* brand family cleanly.

---

## What It Does

- Merchant provides a **main wallet mnemonic** (HD source for unique deposit addresses)
- Merchant provides a **fee wallet mnemonic** (Trust Wallet phrase; BNB + POL used for gas)
- Accepts **USDT (BEP-20), USDT (Polygon), BNB, POL** via public RPC — no full node required
- Each invoice gets a **unique HD-derived deposit address** (BIP-44)
- On payment detected: fee wallet auto-sends gas to deposit address → tokens swept to main wallet
- Webhooks notify your app on confirmation
- Beautiful payment page with QR code, live status, countdown timer

---

## Stack

| Layer | Choice |
|---|---|
| Language | Python 3.11+ |
| Web framework | Flask |
| WSGI server | Waitress |
| Blockchain | web3.py |
| HD wallet | eth-account + mnemonic (bip-utils or hdwallet) |
| Scheduler | APScheduler (background polling) |
| Database | **sqlite3** (stdlib) — WAL mode, `PRAGMA foreign_keys=ON`, `user_version` migrations |
| HTTP client | aiohttp (auto-update, same as GhostWire) |
| IDs | nanoid (Python port), size=20 |
| Binary build | PyInstaller (one-file, ubuntu-22.04) |
| Config | python-dotenv |
| Frontend fonts | Syne (display) + DM Mono (data/amounts) |
| Frontend style | Dark terminal-meets-luxury: deep navy/charcoal, electric green accents, subtle grid texture |

---

## Project Structure

```
ghostpayments/
├── app/
│   ├── __init__.py              # Flask app factory, APScheduler init
│   ├── config.py                # Env-based config class
│   ├── db.py                    # SQLite WAL + WAL2, PRAGMA foreign_keys, migrations
│   ├── extensions.py            # scheduler singleton
│   │
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── payment.py           # GET /pay/<invoice_id> — public payment UI
│   │   ├── api.py               # REST API + API-key auth middleware
│   │   └── admin.py             # Dashboard, keys, invoice detail, settings (paths/wallets/tuning)
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── wallet.py            # HD derivation: mnemonic → child address + privkey
│   │   ├── chains.py            # BSC + Polygon Web3 clients, token ABIs
│   │   ├── monitor.py           # APScheduler job: poll pending invoices
│   │   ├── sweeper.py           # Gas pump logic + token/native sweep
│   │   └── env_writer.py        # Read/write .env preserving comments + ordering
│   │
│   ├── static/
│   │   ├── css/main.css
│   │   ├── js/
│   │   │   ├── pay.js           # Payment page: QR, countdown, status polling
│   │   │   ├── qrcode.min.js    # vendored
│   │   │   └── admin.js
│   │   └── img/
│   │       ├── ghost-logo.svg
│   │       ├── bnb.svg
│   │       ├── pol.svg
│   │       └── usdt.svg
│   │
│   └── templates/
│       ├── base.html
│       ├── pay.html             # ← main design focus
│       ├── success.html
│       ├── expired.html
│       └── admin/
│           ├── dashboard.html
│           ├── keys.html        # API key create / revoke
│           ├── settings.html    # Tabbed: URI Paths / Wallets & RPC / Tuning
│           └── detail.html
│
├── updater.py                   # Auto-update: GitHub releases, SHA-256, os.execv restart
├── run.py                       # Waitress entrypoint + CLI (update / --version / --help)
├── init_db.py                   # First-run: calls db.init_db()
├── .env.example
├── requirements.txt
├── docker-compose.yml
├── Dockerfile
├── build/
│   ├── build.sh                 # PyInstaller → dist/ghostpayments + .sha256
│   └── Dockerfile               # Build container
├── scripts/
│   ├── install.sh               # Interactive one-command installer
│   └── uninstall.sh
├── systemd/
│   └── ghostpayments.service
├── tests/
│   ├── test_invoice_api.py      # Create invoice, check status, cancel
│   ├── test_wallet_derivation.py
│   └── test_db_migrations.py
└── .github/
    └── workflows/
        ├── ci.yml               # Push/PR: run tests + build on ubuntu-22.04
        ├── release.yml          # Manual dispatch: build + publish GitHub release
        └── benchmark.yml        # Manual dispatch: functional payment flow benchmark
```

---

## Database (`app/db.py`) — sqlite3, WAL mode, Migrations

Uses Python's stdlib `sqlite3` directly — no ORM. Opens with WAL journal mode and foreign keys on every connection.

```python
import sqlite3, os

DB_PATH = os.getenv("DB_PATH", "data/ghost.db")
SCHEMA_VERSION = 1   # bump when adding migrations

def get_db() -> sqlite3.Connection:
    db = sqlite3.connect(DB_PATH, check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA busy_timeout=5000")
    return db

def init_db():
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    db = get_db()
    version = db.execute("PRAGMA user_version").fetchone()[0]
    if version == 0:
        _apply_initial_schema(db)
    _run_migrations(db, version)
    db.close()

def _apply_initial_schema(db):
    db.executescript("""
        CREATE TABLE IF NOT EXISTS invoices (
            id              TEXT PRIMARY KEY,
            chain           TEXT NOT NULL CHECK(chain IN ('BSC','POLYGON')),
            token           TEXT NOT NULL CHECK(token IN ('USDT','BNB','POL')),
            amount_native   TEXT NOT NULL,
            amount_usd      REAL,
            deposit_address TEXT NOT NULL,
            hd_index        INTEGER NOT NULL,
            status          TEXT NOT NULL DEFAULT 'pending'
                            CHECK(status IN ('pending','underpaid','confirming',
                                             'sweeping','completed','expired','failed')),
            tx_in_hash      TEXT,
            gas_tx_hash     TEXT,
            tx_out_hash     TEXT,
            webhook_url     TEXT,
            metadata        TEXT,               -- JSON blob
            created_at      TEXT NOT NULL,      -- ISO-8601
            expires_at      TEXT NOT NULL,
            confirmed_at    TEXT,
            completed_at    TEXT
        );

        CREATE TABLE IF NOT EXISTS api_keys (
            id              TEXT PRIMARY KEY,
            label           TEXT NOT NULL,
            key_hash        TEXT NOT NULL UNIQUE,  -- SHA-256 hex of plaintext key
            key_prefix      TEXT NOT NULL,          -- first 8 chars for display
            is_active       INTEGER NOT NULL DEFAULT 1,
            created_at      TEXT NOT NULL,
            last_used_at    TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_invoices_status    ON invoices(status);
        CREATE INDEX IF NOT EXISTS idx_invoices_chain     ON invoices(chain);
        CREATE INDEX IF NOT EXISTS idx_invoices_created   ON invoices(created_at);
        CREATE INDEX IF NOT EXISTS idx_api_keys_hash      ON api_keys(key_hash);

        PRAGMA user_version = 1;
    """)
    db.commit()

def _run_migrations(db, current_version):
    # Migration v1 → v2 example (add when needed):
    # if current_version < 2:
    #     db.execute("ALTER TABLE invoices ADD COLUMN retry_count INTEGER DEFAULT 0")
    #     db.execute("PRAGMA user_version = 2")
    #     db.commit()
    pass
```

**Connection handling:** Flask `g`-object pattern — `get_db()` called per request, `db.close()` in `teardown_appcontext`. APScheduler jobs open their own connection from `get_db()`.

---

## Data Models

Rows map directly to the sqlite3 schema above. Helper functions return `sqlite3.Row` objects (dict-like). No ORM — raw SQL throughout.

### Invoice columns
```
id              TEXT PK    — nanoid(20)
chain           TEXT       — 'BSC' | 'POLYGON'
token           TEXT       — 'USDT' | 'BNB' | 'POL'
amount_native   TEXT       — exact string to avoid float precision issues ("10.50")
amount_usd      REAL       — display only
deposit_address TEXT       — BIP-44 derived child address
hd_index        INTEGER    — child index for key re-derivation at sweep time
status          TEXT       — see CHECK constraint above
tx_in_hash      TEXT
gas_tx_hash     TEXT
tx_out_hash     TEXT
webhook_url     TEXT
metadata        TEXT       — JSON string
created_at      TEXT       — ISO-8601 UTC
expires_at      TEXT       — ISO-8601 UTC
confirmed_at    TEXT
completed_at    TEXT
```

### ApiKey columns
```
id              TEXT PK    — nanoid(20)
label           TEXT       — "GhostGate Production"
key_hash        TEXT UNIQUE — SHA-256(plaintext_key) — never store plaintext
key_prefix      TEXT       — first 8 chars e.g. "gp_V3mKpX"
is_active       INTEGER    — 1 = active, 0 = revoked
created_at      TEXT
last_used_at    TEXT       — updated on each successful auth
```

Key format: `gp_` + nanoid(32), e.g. `gp_V3mKpXq2nLwRtY8uZe5AbCdEfGhIj`

---

## Environment Variables (`.env.example`)

```env
# Merchant wallets (BIP-39 mnemonic phrases)
MAIN_MNEMONIC="word1 word2 ... word12"      # HD source for deposit addresses
FEE_MNEMONIC="word1 word2 ... word12"       # Trust Wallet phrase for gas funding

# Main wallet destination (all sweeps go here)
MAIN_WALLET_ADDRESS=0xYourMainWalletAddress

# RPC endpoints (free public or your own)
BSC_RPC_URL=https://bsc-dataseed.binance.org
POLYGON_RPC_URL=https://polygon-rpc.com

# Security
# Security (URI path prefixes — generated at install time via --generate-token)
# Admin panel:    https://yourhost/{ADMIN_PATH}/
# Payment pages:  https://yourhost/{PAYMENT_PATH}/pay/<id>
# All other paths → 404 empty body
ADMIN_PATH=aBcDeFgHiJkLmNoPqRsT      # nanoid(20) — ghostpayments --generate-token
PAYMENT_PATH=pQrStUvWxYzAbCdEfGhIj   # nanoid(20) — ghostpayments --generate-token

# Auto-update
AUTO_UPDATE=true
UPDATE_CHECK_INTERVAL=300            # Seconds between background update checks
UPDATE_CHECK_ON_STARTUP=true         # Check for update immediately on launch
UPDATE_HTTP_PROXY=                   # Optional proxy for update downloads only
UPDATE_HTTPS_PROXY=                  # Optional: http://127.0.0.1:8080

# Optional tuning
INVOICE_TTL_MINUTES=30
BSC_CONFIRMATIONS=3
POLYGON_CONFIRMATIONS=1
GAS_BUFFER_PERCENT=20                       # Extra gas sent (safety margin)
POLL_INTERVAL_SECONDS=20
PORT=5000
```

---

## Service Logic

### `wallet.py` — HD Derivation

```
derive_address(mnemonic, index) → (address, private_key)
  Uses BIP-44 path: m/44'/60'/0'/0/{index}
  Both BSC and Polygon use Ethereum's derivation (chainId differs, path same)
  Returns checksummed address + hex private key

get_fee_address(mnemonic, chain) → (address, private_key)
  chain='BSC'  → index 0 of fee mnemonic (BNB address)
  chain='POL'  → index 0 of fee mnemonic (same address works on both EVM chains)
  (Trust Wallet uses the same address across all EVM chains)
```

### `chains.py` — Blockchain Clients

```
BSC_W3  = Web3(HTTPProvider(BSC_RPC_URL))
POL_W3  = Web3(HTTPProvider(POLYGON_RPC_URL))

USDT_ABI = [minimal ERC-20 ABI: balanceOf, transfer, decimals]

USDT_CONTRACTS = {
  'BSC':     '0x55d398326f99059fF775485246999027B3197955',  # USDT BEP-20
  'POLYGON': '0xc2132D05D31c914a87C6611C10748AEb04B58e8F',  # USDT Polygon
}

get_native_balance(chain, address) → Wei
get_token_balance(chain, address, token) → smallest unit
get_block_number(chain) → int
send_native(chain, from_privkey, to_address, value_wei) → tx_hash
send_token(chain, from_privkey, token, to_address, amount) → tx_hash
estimate_token_transfer_gas(chain, token) → gas_units  (~65000 for USDT)
get_gas_price(chain) → Wei
wait_for_receipt(chain, tx_hash, timeout=120) → receipt
```

### `monitor.py` — APScheduler Background Job

Runs every `POLL_INTERVAL_SECONDS`. For each `pending` invoice:

```
1. Get current block on invoice's chain
2. For USDT invoices:
     Query USDT contract for balance at deposit_address
     If balance >= invoice.amount_native:
       Check tx confirmations (scan recent Transfer events)
       If confirmed: set status='confirming', record tx_in_hash
       Trigger sweeper.sweep_token(invoice)

3. For BNB/POL invoices:
     Check native balance at deposit_address
     If balance >= invoice.amount_native:
       Confirm via block count
       Set status='confirming', trigger sweeper.sweep_native(invoice)

4. For all: check expires_at → set 'expired' if past
```

### `sweeper.py` — Gas Pump + Sweep

#### For token invoices (USDT):

```
sweep_token(invoice):
  1. Get deposit address privkey via derive_address(MAIN_MNEMONIC, invoice.hd_index)
  2. Get fee wallet privkey via get_fee_address(FEE_MNEMONIC, invoice.chain)
  3. Estimate gas needed:
       gas_units = estimate_token_transfer_gas(chain, 'USDT')  # ~65000
       gas_price = get_gas_price(chain)
       gas_cost_wei = gas_units * gas_price * (1 + GAS_BUFFER_PERCENT/100)
  4. Check deposit address native balance
  5. If native balance < gas_cost_wei:
       deficit = gas_cost_wei - current_native_balance
       tx = send_native(chain, fee_privkey, deposit_address, deficit)
       wait_for_receipt(chain, tx)
       set invoice.gas_tx_hash = tx
  6. Send token: send_token(chain, deposit_privkey, 'USDT', MAIN_WALLET_ADDRESS, balance)
  7. set invoice.tx_out_hash, status='completed', completed_at=now
  8. Fire webhook
```

#### For native invoices (BNB / POL):

```
sweep_native(invoice):
  1. Get deposit address privkey
  2. gas_cost = 21000 * get_gas_price(chain) * buffer
  3. sweep_amount = balance - gas_cost
  4. send_native(chain, deposit_privkey, MAIN_WALLET_ADDRESS, sweep_amount)
  5. set tx_out_hash, status='completed'
  6. Fire webhook
```

---

## API Routes (`api.py`)

Invoice routes require `X-GhostPay-Key: {api_key}` header (keys created in admin, stored hashed).  
Admin routes are guarded by the secret `ADMIN_PATH` URI prefix only — no key in URL or header.  
The master key and API keys are **separate** — master key never works on invoice endpoints.

**Auth middleware:**
```python
def require_api_key(f):
    # Hash incoming key → lookup in ApiKey table → check is_active
    # On success: update last_used_at
    # On failure: 401
```

### `POST /api/invoice`
```json
Request:
{
  "chain": "BSC",
  "token": "USDT",
  "amount_native": "10.00",
  "amount_usd": 10.00,
  "webhook_url": "https://yourapp.com/webhook",
  "metadata": {"order_id": "abc123"}
}

Response 201:
{
  "invoice_id": "V3mKpXq2nLwRtY8uZe5A",
  "deposit_address": "0x...",
  "chain": "BSC",
  "token": "USDT",
  "amount_native": "10.00",
  "payment_url": "https://yourhost/pay/V3mKpXq2nLwRtY8uZe5A",
  "expires_at": "2025-01-01T12:30:00Z",
  "status": "pending"
}
```

### `GET /api/invoice/<invoice_id>`
Returns current invoice status + tx hashes. No auth required (used by payment page polling).

### `POST /api/invoice/<invoice_id>/cancel`
Marks invoice expired (requires API key).

### `GET /api/invoices`
Paginated invoice list with filters (requires API key).

### `GET /api/wallets`
Fee wallet + main wallet balances (requires API key).

---

## Admin Routes (`admin.py`)

All admin routes live under the `/{ADMIN_PATH}/` prefix. No key in URL or header — the secret path itself is the access control layer (same as GhostWire panel). Within the prefix, Flask routes normally. Errors within the prefix render styled HTML error pages.

### `GET /{ADMIN_PATH}/` — Dashboard
Invoice stats, volume by token, fee wallet balances.

### `GET /{ADMIN_PATH}/keys` — API Key List
### `POST /{ADMIN_PATH}/keys` — Create API Key
```
Form: label (string)
Action:
  1. Generate key: "gp_" + nanoid(32)
  2. Store SHA-256 hash + first 8 chars prefix + label
  3. Return plaintext key ONCE in response (flash message)
  4. Never stored in DB in plaintext
```
### `POST /{ADMIN_PATH}/keys/<key_id>/revoke` — Revoke Key
Sets `is_active = False`. Immediate effect.

### `GET /{ADMIN_PATH}/invoice/<invoice_id>` — Invoice Detail
Full timeline: created → detected → gas pumped → swept, with all tx hashes and block explorer links.

### `GET /{ADMIN_PATH}/settings` — Settings Page
Tabbed settings UI — three sections:

**Tab 1 — URI Paths**
- Current ADMIN_PATH and PAYMENT_PATH shown (masked, with reveal button)
- "Regenerate Admin Path" button → calls `ghostpayments --generate-token` equivalent inline → shows new value in flash, writes to `.env`, **requires service restart to take effect** (warning shown)
- "Regenerate Payment Path" button → same flow
- Manual override: text inputs to paste your own nanoid(20) values

**Tab 2 — Wallets & RPC**
- Main wallet mnemonic: masked text field (reveal toggle) — save writes to `.env`
- Fee wallet mnemonic: masked text field (reveal toggle)
- Main wallet address: plain text field
- BSC RPC URL: text field with "Test" button (fires test call to chain, shows block number or error)
- Polygon RPC URL: same
- Save button → writes changed fields to `.env`, shows restart-required banner

**Tab 3 — Tuning**
- Invoice TTL (minutes)
- BSC confirmations
- Polygon confirmations  
- Gas buffer percent
- Poll interval (seconds)
- Auto-update toggle (true/false)
- Update check interval
- Save → writes to `.env`, no restart needed for most (APScheduler picks up poll interval live)

### `POST /{ADMIN_PATH}/settings/paths` — Save Path Changes
```
Form: admin_path, payment_path
Validation: must be 10–40 chars, alphanumeric + hyphens only, not equal to each other
Action: write to .env, return success + restart-required warning
```

### `POST /{ADMIN_PATH}/settings/wallets` — Save Wallet Changes
```
Form: main_mnemonic, fee_mnemonic, main_wallet_address, bsc_rpc_url, pol_rpc_url
Action: validate address format (0x + 40 hex chars), write to .env
Mnemonics are write-only in the form — never pre-filled in HTML for security
```

### `POST /{ADMIN_PATH}/settings/tuning` — Save Tuning Changes
```
Form: invoice_ttl_minutes, bsc_confirmations, pol_confirmations,
      gas_buffer_percent, poll_interval_seconds, auto_update,
      update_check_interval
Action: validate types/ranges, write to .env
```

### `POST /{ADMIN_PATH}/settings/test-rpc` — Test RPC Endpoint (AJAX)
```
Form: chain (BSC|POLYGON), url
Action: attempt web3.eth.block_number call, return {ok: true, block: N} or {ok: false, error: "..."}
Used by the "Test" buttons on the Wallets tab
```

**`.env` write helper:**
```python
def write_env(updates: dict):
    """Read .env, apply updates dict, write back. Preserves comments and ordering."""
    env_path = os.getenv("ENV_PATH", "/etc/ghostpayments/.env")
    lines = open(env_path).readlines() if os.path.exists(env_path) else []
    result = []
    written = set()
    for line in lines:
        key = line.split("=")[0].strip()
        if key in updates:
            result.append(f"{key}={updates[key]}\n")
            written.add(key)
        else:
            result.append(line)
    for key, val in updates.items():
        if key not in written:
            result.append(f"{key}={val}\n")
    open(env_path, "w").writelines(result)
```
Note: changes to `ADMIN_PATH`, `PAYMENT_PATH`, mnemonics, or RPC URLs require a service restart. GhostPayments reads all config from `.env` at startup only. A yellow "Restart required" banner is shown after these saves.

---

## Frontend Design — Payment Page (`pay.html`)

**Aesthetic direction: Dark Terminal Luxury**

- Background: near-black `#0a0d12` with a very subtle dot-grid pattern (SVG background)
- Primary accent: electric emerald `#00e87a` (the "ghost glow")
- Secondary: cool slate blue `#1e2a3a` for card surfaces
- Fonts: **Syne** (700) for headings/amounts, **DM Mono** for addresses/hashes
- Card: floating glassmorphism panel with a thin `1px` emerald border, `backdrop-filter: blur`
- Logo: animated ghost silhouette (pure CSS, subtle float animation)

**Layout (single vertical card, 480px max-width, centered):**

```
┌─────────────────────────────────────┐
│  👻 GhostPayments        [EXPIRED?] │  ← header with countdown timer
│─────────────────────────────────────│
│  Chain selector tabs:               │
│  [USDT BSC] [USDT POL] [BNB] [POL] │
│─────────────────────────────────────│
│  Send exactly:                      │
│  ████ 10.00 USDT          [copy]    │  ← Syne font, large
│                                     │
│  To this address:                   │
│  ████ 0x1a2b...3c4d       [copy]    │  ← DM Mono, truncated
│                                     │
│        ┌──────────────┐             │
│        │   QR CODE    │             │  ← qrcode.js, styled
│        └──────────────┘             │
│─────────────────────────────────────│
│  ● Waiting for payment...           │  ← animated status bar
│  Expires in 28:44                   │  ← live countdown
└─────────────────────────────────────┘
```

**Status transitions (JS polling `/{PAYMENT_PATH}/api/invoice/<id>` every 10s):**
- `pending` → pulsing green dot, "Waiting for payment..."
- `confirming` → spinning ring, "Transaction detected, confirming..."
- `sweeping` → chain animation, "Forwarding to main wallet..."
- `completed` → full-screen success with ghost animation + confetti burst
- `expired` → grayed out, "Invoice expired"

---

## Admin Dashboard (`admin/dashboard.html`)

Minimal dark dashboard — shared sidebar with nav links:
- **Dashboard** — invoice stats, fee wallet balances, volume chart
- **Invoices** — filterable table with status badges
- **API Keys** — create / revoke
- **Settings** — URI Paths / Wallets & RPC / Tuning tabs

**Dashboard page:**
- Header: GhostPayments logo + fee wallet balances (BNB: X.XX, POL: X.XX)
- Stats row: Total | Completed | Pending | Expired | Total Volume (USDT)
- Invoice table: ID | Chain | Token | Amount | Status | Created | Actions

**API Keys page (`admin/keys.html`):**
- Table: Label | Key prefix (`gp_V3mKpX...`) | Created | Last used | Status badge
- "Create Key" form: label input + submit → success flash with full key (shown once)
- "Revoke" button per key → confirm modal → instant revoke
- Revoked keys shown grayed-out, not deleted (audit trail)

**Settings page (`admin/settings.html`):**
Three tabs rendered client-side (no page reload between tabs):

*URI Paths tab:*
- Admin path: `[••••••••••••••••••••] [👁 Reveal] [🔄 Regenerate]`
- Payment path: same pattern
- Regenerate replaces value in-place and writes `.env`; shows yellow "Restart required" banner

*Wallets & RPC tab:*
- Main mnemonic: write-only masked input (placeholder "Enter new value to change")
- Fee mnemonic: same
- Main wallet address: plain text input, pre-filled
- BSC RPC URL: text input + [Test] button → AJAX → shows "✓ Block 12345678" or "✗ Error"
- Polygon RPC URL: same
- [Save Wallets] → writes only non-empty fields to `.env`

*Tuning tab:*
- Number inputs for all tuning vars with sensible min/max/step
- Auto-update: toggle switch
- [Save Tuning] → writes to `.env`; no restart needed for most values

Auth: secret `ADMIN_PATH` URI prefix only — no key in URL or header. The path is the lock.

---

## `updater.py` — Auto-Update (GhostWire-identical pattern)

Mirrors GhostWire's `updater.py` exactly, adapted for GhostPayments:

```python
GITHUB_REPO = "Parham125/ghostpayments"
COMPONENT   = "ghostpayments"

class Updater:
    def __init__(self, check_interval=300, check_on_startup=True,
                 http_proxy="", https_proxy=""):
        self.check_interval      = check_interval
        self.check_on_startup    = check_on_startup
        self.http_proxy          = http_proxy
        self.https_proxy         = https_proxy
        self.current_version     = self._get_current_version()
        self.binary_url          = f"https://github.com/{GITHUB_REPO}/releases/latest/download/{COMPONENT}"
        self.check_url           = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

    def _get_current_version(self):
        # Returns "dev" when running from source; version baked in by PyInstaller
        script_path = Path(sys.argv[0])
        if script_path.name == COMPONENT:
            return "v0.1.0"   # bumped by build workflow
        return "dev"

    async def http_get(self, url, timeout):
        # aiohttp GET with proxy routing (https_proxy for https:// urls)
        ...

    async def http_download(self, url, output_path, timeout):
        # Streaming download via aiohttp, 64KB chunks
        ...

    async def check_for_update(self):
        # GET check_url → parse tag_name → compare to current_version
        ...

    def verify_checksum(self, binary_path, expected):
        # SHA-256 compare, same as GhostWire
        ...

    async def download_update(self, new_version):
        # Download to /tmp/ghostpayments-update-{pid}/ghostpayments
        # Verify .sha256 checksum
        # os.execv restart (replace process in-place, systemd catches the restart)
        ...

    async def manual_update(self):
        # CLI `ghostpayments update` flow:
        # - reads HTTP_PROXY / HTTPS_PROXY env vars if not set in config
        # - prints current version, checks, downloads, moves binary, restarts service
        ...

    async def update_loop(self, shutdown_event):
        # Background task started from run.py main()
        # check_on_startup → immediate check
        # then asyncio.sleep(check_interval) loop
        # on update found: download_update() → shutdown_event.set()
        ...
```

**Key behaviors matching GhostWire:**
- Proxy selection: `https_proxy` used for `https://` URLs, `http_proxy` for `http://`
- `manual_update()` falls back to `HTTP_PROXY`/`HTTPS_PROXY` environment variables if config proxies are empty
- Binary replaced via `os.execv("/bin/bash", ["/bin/bash", "-c", f"sleep 0.5; mv old new; exec new {args}"])` — same trick as GhostWire
- SHA-256 checksum downloaded as `{binary_url}.sha256`, verified before replace
- Service restart: `systemctl restart ghostpayments` in `manual_update()`; automatic via systemd in background loop

---

## `run.py` — CLI Entry Point + Waitress

```python
def main():
    # ── Subcommand: ghostpayments update ──────────────────────────────────
    if len(sys.argv) >= 2 and sys.argv[1] == "update":
        # Load proxies from .env if present
        load_dotenv()
        asyncio.run(Updater(
            http_proxy=os.getenv("UPDATE_HTTP_PROXY", ""),
            https_proxy=os.getenv("UPDATE_HTTPS_PROXY", ""),
        ).manual_update())
        sys.exit(0)

    # ── Flags ─────────────────────────────────────────────────────────────
    parser = argparse.ArgumentParser(description="GhostPayments — Crypto Payment Processor")
    parser.add_argument("--version", action="store_true", help="Print version and exit")
    parser.add_argument("--generate-token", action="store_true",
                        help="Print a new nanoid(20) token to stdout and exit")
    args = parser.parse_args()

    if args.version:
        print(Updater().current_version)
        sys.exit(0)

    if args.generate_token:
        from nanoid import generate
        print(generate(size=20))   # bare token to stdout — same as ghostwire --generate-token
        sys.exit(0)

    # ── Normal startup ────────────────────────────────────────────────────
    load_dotenv()
    from app.db import init_db
    init_db()

    from app import create_app
    app = create_app()

    # Start auto-update background loop (threading, not asyncio — Flask is sync)
    auto_update = os.getenv("AUTO_UPDATE", "true").lower() == "true"
    if auto_update:
        import threading
        shutdown_event = asyncio.Event()
        updater = Updater(
            check_interval=int(os.getenv("UPDATE_CHECK_INTERVAL", 300)),
            check_on_startup=os.getenv("UPDATE_CHECK_ON_STARTUP","true").lower()=="true",
            http_proxy=os.getenv("UPDATE_HTTP_PROXY", ""),
            https_proxy=os.getenv("UPDATE_HTTPS_PROXY", ""),
        )
        def _run_update_loop():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(updater.update_loop(shutdown_event))
        t = threading.Thread(target=_run_update_loop, daemon=True)
        t.start()

    from waitress import serve
    serve(app, host="0.0.0.0", port=int(os.getenv("PORT", 5000)),
          threads=8, channel_timeout=120)

if __name__ == "__main__":
    main()
```

**CLI commands summary:**
```
ghostpayments                    # Start server (reads .env)
ghostpayments update             # Check for update, download, restart service
ghostpayments --version          # Print current version
ghostpayments --generate-token   # Print a nanoid(20) to stdout — use for ADMIN_PATH, PAYMENT_PATH, etc.
ghostpayments --help             # argparse auto-generated help
```

---

## `docker-compose.yml`

```yaml
version: '3.9'
services:
  ghostpayments:
    build: .
    restart: unless-stopped
    ports:
      - "5000:5000"
    volumes:
      - ./data:/app/data          # SQLite DB persisted here
    env_file: .env
    environment:
      - DB_PATH=/app/data/ghost.db
```

---

## `requirements.txt`

```
Flask>=3.0
waitress>=3.0
web3>=7.0
eth-account>=0.12
mnemonic>=0.21
bip-utils>=2.9              # BIP-44 HD derivation
APScheduler>=3.10
aiohttp>=3.9                # Auto-updater HTTP client (same as GhostWire)
python-dotenv>=1.0
nanoid>=2.0
requests>=2.31              # Webhook delivery
PyInstaller>=6.0            # Build only (not runtime dep)
```

No SQLAlchemy — pure `sqlite3` from Python stdlib.

---

## `build/build.sh` — PyInstaller Binary

```bash
#!/bin/bash
set -e
echo "Building GhostPayments binary..."
cd "$(dirname "$0")/.."

python3.11 -m PyInstaller \
    --onefile \
    --name ghostpayments \
    --add-data "app/static:app/static" \
    --add-data "app/templates:app/templates" \
    run.py

echo "Generating checksums..."
cd dist
sha256sum ghostpayments > ghostpayments.sha256
cd ..
echo "Build complete!"
ls -lh dist/
```

Ubuntu 22.04 compatibility: built on `ubuntu-22.04` runner, Python 3.11 (available on 22.04 via `deadsnakes/ppa` or `setup-python`). The resulting binary runs on Ubuntu 22.04+.

---

## GitHub Workflows (`.github/workflows/`)

### `ci.yml` — Continuous Integration

Runs on every push to `main` and every pull request.

```yaml
name: CI
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-22.04
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -r requirements.txt
      - name: Init test DB
        run: |
          DB_PATH=/tmp/test-ghost.db python init_db.py
      - name: Run tests
        run: |
          DB_PATH=/tmp/test-ghost.db pytest tests/ -v

  build-linux:
    runs-on: ubuntu-22.04
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install deps
        run: |
          python -m pip install --upgrade pip
          python -m pip install -r requirements.txt
      - name: Build
        run: bash build/build.sh
      - name: Upload artifacts
        uses: actions/upload-artifact@v4
        with:
          name: ghostpayments-linux
          path: |
            dist/ghostpayments
            dist/ghostpayments.sha256
```

### `release.yml` — Manual Release Publisher

Triggered manually via GitHub Actions UI. Takes a version string, builds binary, creates GitHub release with binary + checksum attached.

```yaml
name: Release
on:
  workflow_dispatch:
    inputs:
      version:
        description: "Version to release (e.g. 0.1.0 or v0.1.0)"
        required: true
        type: string
permissions:
  contents: write

jobs:
  release:
    runs-on: ubuntu-22.04
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Normalize version
        id: ver
        run: |
          ver="${{ inputs.version }}"
          ver="${ver#v}"
          echo "version=$ver" >> "$GITHUB_OUTPUT"
      - name: Install deps
        run: |
          python -m pip install --upgrade pip
          python -m pip install -r requirements.txt
      - name: Patch version into updater.py
        run: |
          sed -i "s/return \"v0.1.0\"/return \"v${{ steps.ver.outputs.version }}\"/" updater.py
      - name: Build
        run: bash build/build.sh
      - name: Create release
        uses: ncipollo/release-action@v1
        with:
          tag: v${{ steps.ver.outputs.version }}
          name: v${{ steps.ver.outputs.version }}
          artifacts: dist/ghostpayments,dist/ghostpayments.sha256
          allowUpdates: true
          generateReleaseNotes: true
```

**Auto-update flow:** installer puts the binary at `/usr/local/bin/ghostpayments`. On next `update_loop` tick (or `ghostpayments update`), updater fetches GitHub releases API → compares tag → downloads `ghostpayments` + `ghostpayments.sha256` → verifies SHA-256 → `os.execv` replaces the running binary → systemd restarts the service.

### `benchmark.yml` — Functional Payment Flow Test (manual dispatch)

```yaml
name: Payment Flow Benchmark
on:
  workflow_dispatch:

jobs:
  benchmark:
    runs-on: ubuntu-22.04
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -r requirements.txt
      - name: Run invoice lifecycle test
        run: |
          DB_PATH=/tmp/bench-ghost.db pytest tests/test_invoice_api.py -v --tb=short
```

---

## Install Script (`scripts/install.sh`)

One-command installer — identical style to GhostWire's `install-server.sh`:
- Color functions: `p_step`, `p_ok`, `p_warn`, `p_err`, `p_info`, `p_ask`, `p_sep`
- Boxed key display for admin key (same `╔══╗` style)
- x86_64 + Linux check
- Configures systemd service identical to GhostWire's

```bash
wget https://raw.githubusercontent.com/Parham125/ghostpayments/main/scripts/install.sh -O install.sh
chmod +x install.sh
sudo ./install.sh
```

**Install flow (mirrors GhostWire install-server.sh exactly):**

```
1. Root + x86_64 + Linux check
2. Download ghostpayments binary from latest GitHub release + .sha256
3. sha256sum -c verification
4. install -m 755 /tmp/ghostpayments /usr/local/bin/ghostpayments
5. mkdir -p /etc/ghostpayments  (config dir, same as /etc/ghostwire)
6. If /etc/ghostpayments/.env does not exist:
     Interactive prompts:
       ? Main wallet mnemonic (12/24 words):
       ? Fee wallet mnemonic (12/24 words):
       ? Main wallet address (0x...):
       ? BSC RPC URL [https://bsc-dataseed.binance.org]:
       ? Polygon RPC URL [https://polygon-rpc.com]:
       ? Port [5000]:
       ? Enable auto-update? [Y/n]:
       ? HTTP proxy for updates (leave blank if none):
       ? HTTPS proxy for updates (leave blank if none):
       ? Enable nginx setup? [y/N]:
     Auto-generate ADMIN_PATH via `ghostpayments --generate-token`
     Auto-generate PAYMENT_PATH via `ghostpayments --generate-token`
     Write /etc/ghostpayments/.env
     Show admin dashboard URL in yellow box: https://host/{ADMIN_PATH}/
     Show payment prefix in cyan box: https://host/{PAYMENT_PATH}/pay/<invoice_id>
7. Install systemd unit to /etc/systemd/system/ghostpayments.service
   (EnvironmentFile=/etc/ghostpayments/.env, ExecStart=ghostpayments)
8. systemctl daemon-reload && systemctl enable --now ghostpayments
9. Optional nginx + certbot setup (identical flow to GhostWire)
10. Print summary: config path, dashboard URL, useful systemd commands
```

**Systemd unit (`systemd/ghostpayments.service`):**
```ini
[Unit]
Description=GhostPayments Crypto Payment Processor
After=network.target

[Service]
Type=simple
EnvironmentFile=/etc/ghostpayments/.env
ExecStart=/usr/local/bin/ghostpayments
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

---

Execute in this exact order to avoid circular imports and test incrementally:

```
Step 1: Project scaffolding
  - Create directory structure
  - requirements.txt, .env.example, docker-compose.yml, Dockerfile
  - updater.py (full GhostWire-identical Updater class, async aiohttp, SHA-256, os.execv)
  - build/build.sh (PyInstaller, python3.11, ubuntu-22.04)
  - .github/workflows/ci.yml, release.yml, benchmark.yml
  - scripts/install.sh (GhostWire style, downloads binary from release)
  - systemd/ghostpayments.service

Step 2: Config + Database
  - app/config.py (load from dotenv)
  - app/extensions.py (scheduler singleton)
  - app/db.py (sqlite3 WAL, PRAGMA foreign_keys, user_version migrations, initial schema)
  - init_db.py (calls app.db.init_db(), usable standalone)

Step 3: Wallet + Chain services
  - app/services/wallet.py (HD derivation, test with known mnemonic)
  - app/services/chains.py (Web3 clients, token ABI, helper functions)

Step 4: Core business logic
  - app/services/env_writer.py (read/write .env preserving comments + ordering)
  - app/services/sweeper.py (gas pump + sweep, test on testnet first)
  - app/services/monitor.py (APScheduler polling job)

Step 5: Flask routes + CLI entrypoint
  - run.py (CLI: `update` subcommand, `--version`, `--generate-token`, `--help`; starts Waitress + update thread)
  - app/routes/api.py (invoice CRUD + webhook + API-key auth middleware)
  - app/routes/payment.py (public pay page route)
  - app/routes/admin.py (dashboard + API keys + invoice detail + settings: paths/wallets/tuning + test-rpc AJAX)
  - app/__init__.py (app factory, register blueprints, start scheduler)

Step 6: Frontend
  - READ /mnt/skills/public/frontend-design/SKILL.md before writing any HTML/CSS
  - app/templates/base.html (CSS vars, fonts, shared layout)
  - app/templates/pay.html (main payment UI — dark terminal luxury aesthetic)
  - app/templates/success.html + expired.html
  - app/static/css/main.css
  - app/static/js/pay.js (QR, countdown, status polling)
  - app/templates/admin/dashboard.html + keys.html + detail.html
  - app/templates/admin/settings.html (3-tab: URI Paths / Wallets & RPC / Tuning)

Step 7: Entrypoint + testing
  - run.py (Waitress)
  - Smoke test: create invoice via API, verify address derivation, check monitoring loop
```

---

## Security Notes

- Mnemonics are **never stored** — only read from env at runtime
- Private keys are **derived in-memory** per sweep operation, never persisted
- Deposit address private keys exist only during the sweep function's stack frame
- Admin routes protected by secret key (consider rate limiting in production)
- Use a reverse proxy (Nginx/Caddy) with HTTPS in production
- Consider running with `--cap-drop=ALL` in Docker for defense-in-depth

---

## Known Limitations & Future Work

- No USDC support (easy to add: same flow, different contract address)
- No partial payment handling (amount must match exactly; configurable tolerance is a v2 feature)
- No automatic price conversion (merchant sets `amount_native` directly; fiat pricing via their app)
- Webhook delivery has no retry queue (v2: add Celery or simple retry table)
- Admin dashboard is read-only (v2: allow config changes via UI)
- Single main wallet destination (v2: per-invoice custom destination)
