# GhostPayments — Self-Hosted Crypto Payment Processor

**[📖 فارسی / Persian](README_FA.md)**

GhostPayments is a self-hosted, non-custodial crypto payment processor for BSC and Polygon chains. It generates unique deposit addresses from your wallet mnemonic, monitors incoming payments via public RPC nodes, and automatically sweeps funds to your main wallet — using a separate fee wallet to cover gas without manual intervention.

Part of the Ghost ecosystem: [GhostWire](https://github.com/FrenchToblerone54/ghostwire) · [GhostGate](https://github.com/FrenchToblerone54/ghostgate) · [GhostPass](https://github.com/FrenchToblerone54/ghostpass) · **GhostPayments**

## Features

* **No full node required** — uses public RPC endpoints (BSC, Polygon)
* **Non-custodial** — funds flow directly to your wallet; the server never holds them
* **HD wallet derivation** — BIP-44 child addresses from your mnemonic; one unique address per invoice
* **Auto gas pump** — fee wallet (BNB/POL) automatically covers gas before sweeping tokens
* **Multi-chain, multi-token** — USDT BEP-20, USDT Polygon, BNB, POL
* **Webhook callbacks** — POST to your app on payment confirmation
* **Secret URI paths** — admin panel and payment pages live on secret paths; all other URLs return 404 with an empty body
* **Admin settings panel** — configure URI paths, wallets, RPC endpoints, and API keys from the browser — no manual `.env` editing required after setup
* **Beautiful payment UI** — QR code, live countdown, animated status transitions
* **Auto-update** — checks GitHub releases on startup and in the background; same model as GhostWire
* **Easy installation** — one-command setup script with interactive configuration
* **Docker support** — single `docker-compose up` deployment

## Quick Start

### Step 1: Install GhostPayments

```bash
wget https://raw.githubusercontent.com/FrenchToblerone54/ghostpayments/main/scripts/install.sh -O install.sh
chmod +x install.sh
sudo ./install.sh
```

The installer will:
- Download the pre-built binary from the latest GitHub release and verify its SHA-256 checksum
- Ask for your main wallet mnemonic, fee wallet mnemonic, and main wallet address
- Ask for your desired RPC URLs (or use public defaults)
- Ask for optional HTTP/HTTPS proxy for auto-updates
- Auto-generate secret `ADMIN_PATH` and `PAYMENT_PATH` via `ghostpayments --generate-token`
- Write config to `/etc/ghostpayments/.env`
- Install and start a systemd service (`ghostpayments`)
- Show your admin dashboard URL in a highlighted box — save it, it will not be shown again
- Optionally configure nginx with Let's Encrypt TLS

### Step 2: Access the Admin Dashboard

The installer displays your admin URL at the end. It looks like:

```
https://your-server/{ADMIN_PATH}/
```

From the admin panel you can:
- View all invoices and their status
- Monitor fee wallet and main wallet balances
- **Create and revoke API keys** for your integrations
- **Configure URI paths, wallets, and RPC endpoints** from the Settings page — no need to edit `.env` manually

### Step 3: Create an Invoice via API

```bash
curl -X POST https://your-server/{PAYMENT_PATH}/api/invoice \
  -H "X-GhostPay-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "chain": "BSC",
    "token": "USDT",
    "amount_native": "10.00",
    "webhook_url": "https://yourapp.com/webhook/crypto",
    "metadata": {"order_id": "abc123"}
  }'
```

Send the returned `payment_url` to your customer. GhostPayments handles the rest.

## Documentation

* **[Installation Guide](docs/installation.md)** — Detailed setup for server and Docker
* **[Configuration Reference](docs/configuration.md)** — All `.env` options explained
* **[API Reference](#api-reference)** — Full REST API documentation (below)
* **[Webhook Guide](docs/webhooks.md)** — Payload format and retry behavior
* **[Security](docs/security.md)** — Key handling and operational security notes
* **[Troubleshooting](docs/troubleshooting.md)** — Common issues and RPC tips

## Architecture

```
[Customer Browser]
       │
       │  GET /{PAYMENT_PATH}/pay/<invoice_id>
       ▼
[GhostPayments Server]
       │
       ├── Derives unique deposit address from MAIN_MNEMONIC (BIP-44)
       │
       ├── APScheduler polls public RPC every 20s
       │        BSC: https://bsc-dataseed.binance.org
       │        POL: https://polygon-rpc.com
       │
       │  Payment detected ──────────────────────────────────────────┐
       │                                                              │
       │  [Fee Wallet (FEE_MNEMONIC)]  ──── gas pump tx ──────►  [Deposit Address]
       │                                                              │
       │                                                    sweep tx │
       │                                                              ▼
       │                                                    [Main Wallet]
       │
       └── POST webhook → your app
```

**Payment Flow:**

1. Your app calls `POST /{PAYMENT_PATH}/api/invoice` with chain, token, amount
2. GhostPayments derives a unique HD child address (index stored in DB)
3. Customer sends crypto to the deposit address
4. Monitor detects incoming transaction on-chain
5. For token payments (USDT): fee wallet sends gas to deposit address first
6. Deposit address sweeps full balance to your main wallet
7. Invoice marked `completed`, webhook fired to your app

**Private keys are derived in-memory only during the sweep and never stored.**

## Configuration

### `.env` File

```env
# ── Wallets ────────────────────────────────────────────────────────────────
MAIN_MNEMONIC="word1 word2 word3 word4 word5 word6 word7 word8 word9 word10 word11 word12"
FEE_MNEMONIC="word1 word2 word3 word4 word5 word6 word7 word8 word9 word10 word11 word12"
MAIN_WALLET_ADDRESS=0xYourMainWalletAddress

# ── RPC Endpoints ──────────────────────────────────────────────────────────
BSC_RPC_URL=https://bsc-dataseed.binance.org
POLYGON_RPC_URL=https://polygon-rpc.com

# ── URI Paths (generated at install — treat like passwords) ────────────────
# Admin panel:    https://yourhost/{ADMIN_PATH}/
# Payment pages:  https://yourhost/{PAYMENT_PATH}/pay/<invoice_id>
# All other paths return 404 with empty body
ADMIN_PATH=aBcDeFgHiJkLmNoPqRsT        # ghostpayments --generate-token
PAYMENT_PATH=pQrStUvWxYzAbCdEfGhIj     # ghostpayments --generate-token

# ── Auto-update ────────────────────────────────────────────────────────────
AUTO_UPDATE=true
UPDATE_CHECK_INTERVAL=300        # Seconds between background checks
UPDATE_CHECK_ON_STARTUP=true     # Check immediately on launch
UPDATE_HTTP_PROXY=               # Optional proxy for update downloads only
UPDATE_HTTPS_PROXY=              # e.g. http://127.0.0.1:8080

# ── Tuning (optional) ──────────────────────────────────────────────────────
INVOICE_TTL_MINUTES=30
BSC_CONFIRMATIONS=3
POLYGON_CONFIRMATIONS=1
GAS_BUFFER_PERCENT=20
POLL_INTERVAL_SECONDS=20
PORT=5000
DB_PATH=data/ghost.db
```

**HTTP/HTTPS Proxy for Updates:** If your server needs a proxy to reach GitHub, set `UPDATE_HTTP_PROXY` / `UPDATE_HTTPS_PROXY`. These settings only affect auto-update downloads — they do not affect payment processing or RPC calls. The `ghostpayments update` CLI command also reads `HTTP_PROXY` / `HTTPS_PROXY` environment variables as a fallback.

### CLI Commands

```bash
# Start server (reads .env)
ghostpayments

# Manual update — checks GitHub, downloads, verifies SHA-256, restarts service
ghostpayments update

# Print current version
ghostpayments --version

# Print a bare nanoid(20) to stdout — use for ADMIN_PATH, PAYMENT_PATH, etc.
ghostpayments --generate-token

# Help
ghostpayments --help
```

**Auto-update (background):** When running as a service, GhostPayments checks for new releases every `UPDATE_CHECK_INTERVAL` seconds (default: 300). On finding a new version it downloads the binary, verifies the SHA-256 checksum, and replaces itself in-place — systemd restarts the service automatically. Set `AUTO_UPDATE=false` in `.env` to disable.

## Supported Tokens & Contracts

| Token | Chain | Contract |
|---|---|---|
| USDT | BSC (BEP-20) | `0x55d398326f99059fF775485246999027B3197955` |
| USDT | Polygon | `0xc2132D05D31c914a87C6611C10748AEb04B58e8F` |
| BNB | BSC | native |
| POL | Polygon | native |

## Admin Panel

The admin panel lives at `https://yourhost/{ADMIN_PATH}/`. All other paths return **404 with an empty body** — no HTML, no hints that GhostPayments is running. The secret path is the only access control; treat the admin URL like a password.

The sidebar has four sections:

### Dashboard

Invoice stats (total, completed, pending, expired, volume), fee wallet balances, and an invoice table with color-coded status badges.

### API Keys — `/{ADMIN_PATH}/keys`

Create and revoke API keys used to authenticate invoice API calls.

**Creating a key:**
1. Enter a label (e.g., `GhostGate Production`) and click **"Create Key"**
2. Copy the full key immediately — it is shown **only once**; only the SHA-256 hash is stored

**Revoking a key:** click **"Revoke"** — takes effect immediately.

### Invoices — `/{ADMIN_PATH}/invoices`

Filterable table by status, chain, and token. Click any invoice to see the full timeline: deposit address, tx hashes, gas pump tx, sweep tx, and block explorer links.

### Settings — `/{ADMIN_PATH}/settings`

Three-tab settings page — change configuration from the browser without manually editing `.env`.

**URI Paths tab**
- Current `ADMIN_PATH` and `PAYMENT_PATH` shown masked with a reveal toggle
- **Regenerate** button: calls `ghostpayments --generate-token` equivalent inline, writes new value to `.env`
- ⚠ Requires service restart: `sudo systemctl restart ghostpayments`

**Wallets & RPC tab**
- Mnemonic fields are **write-only** — never pre-filled in HTML; leave blank to keep current value
- Main wallet address: pre-filled and editable
- BSC and Polygon RPC URLs with a **[Test]** button — fires a live `eth_blockNumber` call and shows the result inline
- ⚠ Requires service restart after saving

**Tuning tab**
- Invoice TTL, confirmation counts, gas buffer %, poll interval
- Auto-update toggle and check interval
- Most changes take effect on the next poll cycle — no restart needed

## API Reference

All API endpoints live under the `/{PAYMENT_PATH}/api/` prefix. Requests to any path outside the two valid prefixes return **404 with an empty body**.

Invoice write operations require an `X-GhostPay-Key` header. The status endpoint (`GET /api/invoice/<id>`) is public — used by the payment page for live polling.

---

### `POST /{PAYMENT_PATH}/api/invoice` — Create Invoice

**Request**

```
POST /{PAYMENT_PATH}/api/invoice
X-GhostPay-Key: your_api_key
Content-Type: application/json
```

```json
{
  "chain": "BSC",
  "token": "USDT",
  "amount_native": "10.00",
  "amount_usd": 10.00,
  "webhook_url": "https://yourapp.com/webhook/crypto",
  "metadata": {
    "order_id": "abc123",
    "user_id": "u_456"
  }
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `chain` | string | ✅ | `BSC` or `POLYGON` |
| `token` | string | ✅ | `USDT`, `BNB`, or `POL` |
| `amount_native` | string | ✅ | Exact amount customer must send (in token units) |
| `amount_usd` | number | ❌ | Display-only USD value (not used for validation) |
| `webhook_url` | string | ❌ | URL to POST on payment completion |
| `metadata` | object | ❌ | Arbitrary JSON stored with invoice |

**Response `201 Created`**

```json
{
  "invoice_id": "V3mKpXq2nLwRtY8uZe5A",
  "chain": "BSC",
  "token": "USDT",
  "amount_native": "10.00",
  "deposit_address": "0x1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b",
  "payment_url": "https://yourhost/{PAYMENT_PATH}/pay/V3mKpXq2nLwRtY8uZe5A",
  "expires_at": "2025-01-01T12:30:00Z",
  "status": "pending"
}
```

| Status | Reason |
|---|---|
| `400` | Missing required field or invalid chain/token combination |
| `401` | Missing or invalid API key |
| `422` | Invalid combination (e.g. `POL` token on `BSC` chain) |

---

### `GET /{PAYMENT_PATH}/api/invoice/<invoice_id>` — Get Invoice Status

No authentication required.

**Response `200 OK`**

```json
{
  "invoice_id": "V3mKpXq2nLwRtY8uZe5A",
  "chain": "BSC",
  "token": "USDT",
  "amount_native": "10.00",
  "deposit_address": "0x1a2b...",
  "status": "completed",
  "tx_in_hash": "0xabc...def",
  "tx_out_hash": "0x333...444",
  "metadata": {"order_id": "abc123"},
  "created_at": "2025-01-01T12:00:00Z",
  "expires_at": "2025-01-01T12:30:00Z",
  "confirmed_at": "2025-01-01T12:08:14Z",
  "completed_at": "2025-01-01T12:08:52Z"
}
```

**Invoice Statuses**

| Status | Description |
|---|---|
| `pending` | Waiting for customer payment |
| `underpaid` | Payment received but below required amount |
| `confirming` | Payment detected, waiting for block confirmations |
| `sweeping` | Gas pumped, sweeping funds to main wallet |
| `completed` | Funds swept to main wallet, webhook fired |
| `expired` | Invoice TTL elapsed with no payment |
| `failed` | Sweep failed (check admin dashboard for details) |

---

### `POST /{PAYMENT_PATH}/api/invoice/<invoice_id>/cancel` — Cancel Invoice

Marks a `pending` invoice as expired. Requires API key.

**Response `200 OK`**

```json
{"invoice_id": "V3mKpXq2nLwRtY8uZe5A", "status": "expired"}
```

---

### `GET /{PAYMENT_PATH}/api/invoices` — List Invoices

Requires API key.

```
GET /{PAYMENT_PATH}/api/invoices?status=completed&chain=BSC&page=1&per_page=20
X-GhostPay-Key: your_api_key
```

| Query Param | Type | Description |
|---|---|---|
| `status` | string | Filter by status |
| `chain` | string | Filter by `BSC` or `POLYGON` |
| `token` | string | Filter by token |
| `page` | int | Page number (default: 1) |
| `per_page` | int | Results per page (default: 20, max: 100) |

---

### `GET /{PAYMENT_PATH}/api/wallets` — Wallet Balances

Requires API key.

**Response `200 OK`**

```json
{
  "fee_wallet": {
    "address": "0xfee...",
    "bnb_balance": "0.021400",
    "pol_balance": "1.883000"
  },
  "main_wallet": {
    "address": "0xmain...",
    "usdt_bsc_balance": "482.340000",
    "usdt_pol_balance": "91.500000"
  }
}
```

---

### Webhook Payload

Sent as `POST` to `webhook_url` when a payment reaches `completed`:

```json
{
  "event": "payment.completed",
  "invoice_id": "V3mKpXq2nLwRtY8uZe5A",
  "chain": "BSC",
  "token": "USDT",
  "amount_native": "10.00",
  "deposit_address": "0x1a2b...",
  "tx_in_hash": "0xabc...def",
  "gas_tx_hash": "0x111...222",
  "tx_out_hash": "0x333...444",
  "metadata": {"order_id": "abc123"},
  "completed_at": "2025-01-01T12:08:52Z"
}
```

Your endpoint should return `200 OK`. GhostPayments retries up to 3 times with exponential backoff on non-200 responses.

---

## Nginx (Reverse Proxy)

```nginx
server {
    listen 443 ssl;
    server_name payments.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/payments.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/payments.yourdomain.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Docker

```bash
git clone https://github.com/FrenchToblerone54/ghostpayments
cd ghostpayments
cp .env.example .env
nano .env   # fill in your mnemonics and addresses
docker-compose up -d
```

## systemd Management

```bash
sudo systemctl start ghostpayments
sudo systemctl stop ghostpayments
sudo systemctl restart ghostpayments
sudo systemctl status ghostpayments
sudo journalctl -u ghostpayments -f
```

## Building from Source

```bash
git clone https://github.com/FrenchToblerone54/ghostpayments
cd ghostpayments
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env
python init_db.py
python run.py
```

**Build binary (Ubuntu 22.04+):**

```bash
pip install -r requirements.txt
bash build/build.sh
# Output: dist/ghostpayments + dist/ghostpayments.sha256
```

## Database

GhostPayments uses **SQLite** with WAL journal mode (`PRAGMA journal_mode=WAL`) and `PRAGMA foreign_keys=ON`. The database file is at `DB_PATH` (default: `data/ghost.db`).

Migrations are handled automatically via SQLite's `user_version` pragma — schema applied on first run, future versions add migrations without data loss.

## Security

1. **Mnemonics never stored** — read from `.env` at startup only; never written to DB or logs
2. **Private keys in-memory only** — derived per sweep, exist only within that function's stack frame
3. **HD derivation** — each invoice uses a unique child address; one compromised address does not affect others
4. **API key hashing** — keys stored as SHA-256 hashes; plaintext shown once on creation
5. **URI path security** — admin and payment URLs use secret `nanoid(20)` path prefixes (same model as GhostWire's panel). All other paths return `404` with an **empty body** — no HTML, no `Server` header, no indication GhostPayments is running. Error pages are only served within the two valid path prefixes
6. **Mnemonic fields write-only in settings UI** — never pre-filled in HTML responses
7. **Use HTTPS** — always run behind nginx with TLS; the secret path offers no protection over plain HTTP

## License

MIT License — See [LICENSE](LICENSE) for details

## Contributing

Contributions welcome. Please open an issue or pull request.

## Community

Join the Telegram channel for updates: [@GhostSoftDev](https://t.me/GhostSoftDev)
