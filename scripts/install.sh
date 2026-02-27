#!/bin/bash
set -e

REPO="FrenchToblerone54/ghostpayments"
BINARY_URL="https://github.com/${REPO}/releases/latest/download/ghostpayments"
CONFIG_DIR="/etc/ghostpayments"
SERVICE_FILE="/etc/systemd/system/ghostpayments.service"
BIN_PATH="/usr/local/bin/ghostpayments"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

p_step()  { echo -e "\n${BOLD}${CYAN}▸ $*${NC}"; }
p_ok()    { echo -e "${GREEN}✓ $*${NC}"; }
p_warn()  { echo -e "${YELLOW}⚠ $*${NC}"; }
p_err()   { echo -e "${RED}✗ $*${NC}" >&2; }
p_info()  { echo -e "  $*"; }
p_ask()   { echo -en "${BOLD}? $*${NC} "; }
p_sep()   { echo -e "${CYAN}────────────────────────────────────────${NC}"; }

if [ "$(id -u)" != "0" ]; then p_err "Run as root: sudo ./install.sh"; exit 1; fi
if [ "$(uname -m)" != "x86_64" ]; then p_err "x86_64 only."; exit 1; fi
if [ "$(uname -s)" != "Linux" ]; then p_err "Linux only."; exit 1; fi

p_sep
echo -e "${BOLD}  GhostPayments Installer${NC}"
p_sep

p_step "Downloading binary..."
TMP=$(mktemp -d)
curl -fsSL "${BINARY_URL}" -o "${TMP}/ghostpayments"
curl -fsSL "${BINARY_URL}.sha256" -o "${TMP}/ghostpayments.sha256"
cd "${TMP}"
sha256sum -c ghostpayments.sha256 --status || { p_err "Checksum mismatch!"; exit 1; }
p_ok "Checksum verified"
install -m 755 ghostpayments "${BIN_PATH}"
p_ok "Installed to ${BIN_PATH}"
cd /

p_step "Configuring..."
mkdir -p "${CONFIG_DIR}"

if [ ! -f "${CONFIG_DIR}/.env" ]; then
    p_sep
    echo -e "${BOLD}  Configuration${NC}"
    p_sep

    p_ask "Main wallet mnemonic (12/24 words):"; read -r MAIN_MNEMONIC
    echo
    p_info "Fee wallet — choose an option:"
    p_info "  1) BIP-39 mnemonic phrase"
    p_info "  2) Direct private key (0x...)"
    p_ask "Option [1/2]:"; read -r FEE_OPT
    FEE_MNEMONIC=""
    FEE_PRIVATE_KEY=""
    if [ "${FEE_OPT}" = "2" ]; then
        p_ask "Fee wallet private key (0x...):"; read -r FEE_PRIVATE_KEY
    else
        p_ask "Fee wallet mnemonic (12/24 words):"; read -r FEE_MNEMONIC
    fi
    echo
    p_ask "Main wallet address (0x...):"; read -r MAIN_WALLET_ADDRESS
    p_ask "BSC RPC URL [https://bsc-dataseed.binance.org]:"; read -r BSC_RPC
    BSC_RPC="${BSC_RPC:-https://bsc-dataseed.binance.org}"
    p_ask "Polygon RPC URL [https://polygon-rpc.com]:"; read -r POL_RPC
    POL_RPC="${POL_RPC:-https://polygon-rpc.com}"
    p_ask "Port [5000]:"; read -r PORT
    PORT="${PORT:-5000}"
    p_ask "Enable auto-update? [Y/n]:"; read -r AUTO_UPDATE
    AUTO_UPDATE="true"; [[ "${AUTO_UPDATE,,}" == "n" ]] && AUTO_UPDATE="false"
    p_ask "HTTP proxy for updates (blank = none):"; read -r HTTP_PROXY
    p_ask "HTTPS proxy for updates (blank = none):"; read -r HTTPS_PROXY

    ADMIN_PATH="$(ghostpayments --generate-token)"
    PAYMENT_PATH="$(ghostpayments --generate-token)"

    cat > "${CONFIG_DIR}/.env" <<EOF
MAIN_MNEMONIC="${MAIN_MNEMONIC}"
FEE_MNEMONIC="${FEE_MNEMONIC}"
FEE_PRIVATE_KEY=${FEE_PRIVATE_KEY}
MAIN_WALLET_ADDRESS=${MAIN_WALLET_ADDRESS}
BSC_RPC_URL=${BSC_RPC}
POLYGON_RPC_URL=${POL_RPC}
ADMIN_PATH=${ADMIN_PATH}
PAYMENT_PATH=${PAYMENT_PATH}
AUTO_UPDATE=${AUTO_UPDATE}
UPDATE_CHECK_INTERVAL=300
UPDATE_CHECK_ON_STARTUP=true
UPDATE_HTTP_PROXY=${HTTP_PROXY}
UPDATE_HTTPS_PROXY=${HTTPS_PROXY}
INVOICE_TTL_MINUTES=30
BSC_CONFIRMATIONS=3
POLYGON_CONFIRMATIONS=1
GAS_BUFFER_PERCENT=20
POLL_INTERVAL_SECONDS=20
PORT=${PORT}
DB_PATH=/var/lib/ghostpayments/ghost.db
ENV_PATH=${CONFIG_DIR}/.env
EOF
    chmod 600 "${CONFIG_DIR}/.env"
    p_ok "Config written to ${CONFIG_DIR}/.env"

    p_sep
    echo -e "${YELLOW}╔══════════════════════════════════════════╗${NC}"
    echo -e "${YELLOW}║  Admin Dashboard URL:                    ║${NC}"
    echo -e "${YELLOW}║  http://YOUR_HOST:${PORT}/${ADMIN_PATH}/  ║${NC}"
    echo -e "${YELLOW}╚══════════════════════════════════════════╝${NC}"
    echo
    echo -e "${CYAN}╔══════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║  Payment page prefix:                    ║${NC}"
    echo -e "${CYAN}║  http://YOUR_HOST:${PORT}/${PAYMENT_PATH}/pay/<id>  ║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════╝${NC}"
    p_sep
fi

p_step "Installing systemd service..."
mkdir -p /var/lib/ghostpayments
cat > "${SERVICE_FILE}" <<'EOF'
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
EOF

systemctl daemon-reload
systemctl enable --now ghostpayments
p_ok "Service started"

p_sep
p_ok "GhostPayments installed successfully!"
p_info "Config: ${CONFIG_DIR}/.env"
p_info "Logs:   journalctl -fu ghostpayments"
p_info "Stop:   systemctl stop ghostpayments"
p_sep
