#!/bin/bash
set -e

GITHUB_REPO="FrenchToblerone54/ghostpayments"
VERSION="latest"
RED="\033[0;31m"
GREEN="\033[0;32m"
YELLOW="\033[1;33m"
BLUE="\033[0;34m"
CYAN="\033[0;36m"
MAGENTA="\033[0;35m"
BOLD="\033[1m"
DIM="\033[2m"
NC="\033[0m"
CONFIG_DIR="/etc/ghostpayments"
SERVICE_FILE="/etc/systemd/system/ghostpayments.service"
BIN_PATH="/usr/local/bin/ghostpayments"

p_step() { echo -e "\n${BLUE}${BOLD}▶  $1${NC}"; }
p_ok()   { echo -e "  ${GREEN}✓${NC}  $1"; }
p_warn() { echo -e "  ${YELLOW}⚠${NC}  $1"; }
p_err()  { echo -e "  ${RED}✗${NC}  $1" >&2; }
p_info() { echo -e "  ${CYAN}ℹ${NC}  $1"; }
p_ask()  { echo -ne "  ${MAGENTA}?${NC}  $1"; }
p_sep()  { echo -e "  ${DIM}------------------------------------------------------------${NC}"; }

p_admin_box() {
    local admin_url="$1"
    echo ""
    echo -e "  ${YELLOW}${BOLD}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "  ${YELLOW}${BOLD}║  🔑  Admin Dashboard URL                                 ║${NC}"
    echo -e "  ${YELLOW}${BOLD}║                                                          ║${NC}"
    echo -e "  ${YELLOW}${BOLD}║  ${NC}${BOLD}${admin_url}${NC}${YELLOW}${BOLD}  ║${NC}"
    echo -e "  ${YELLOW}${BOLD}║                                                          ║${NC}"
    echo -e "  ${YELLOW}${BOLD}║  ⚠  Save this URL! It's your admin panel.               ║${NC}"
    echo -e "  ${YELLOW}${BOLD}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

p_payment_box() {
    local pay_url="$1"
    echo ""
    echo -e "  ${CYAN}${BOLD}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "  ${CYAN}${BOLD}║  💳  Payment URL Format                                  ║${NC}"
    echo -e "  ${CYAN}${BOLD}║                                                          ║${NC}"
    echo -e "  ${CYAN}${BOLD}║  ${NC}${pay_url}${CYAN}${BOLD}  ║${NC}"
    echo -e "  ${CYAN}${BOLD}║                                                          ║${NC}"
    echo -e "  ${CYAN}${BOLD}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

clear
echo -e "${CYAN}${BOLD}"
echo "  ============================================================"
echo "    GhostPayments Installation                              "
echo "    Non-Custodial Crypto Payment Processor                  "
echo "  ============================================================"
echo -e "${NC}"
echo -e "  ${DIM}Source: github.com/${GITHUB_REPO}${NC}"
echo ""

p_step "Checking prerequisites..."
if [ "$EUID" -ne 0 ]; then
    p_err "Please run as root (use sudo)"
    exit 1
fi
p_ok "Root access: OK"

ARCH=$(uname -m)
if [ "$ARCH" != "x86_64" ]; then
    p_err "Only x86_64 (amd64) architecture is supported"
    exit 1
fi
p_ok "CPU: x86_64 — OK"

OS=$(uname -s)
if [ "$OS" != "Linux" ]; then
    p_err "Only Linux is supported"
    exit 1
fi
p_ok "OS: Linux — OK"

p_step "Downloading GhostPayments binary..."
TMP=$(mktemp -d)
wget -q --show-progress "https://github.com/${GITHUB_REPO}/releases/${VERSION}/download/ghostpayments" -O "${TMP}/ghostpayments"
wget -q "https://github.com/${GITHUB_REPO}/releases/${VERSION}/download/ghostpayments.sha256" -O "${TMP}/ghostpayments.sha256"

p_step "Verifying checksum..."
cd "${TMP}"
sha256sum -c ghostpayments.sha256
p_ok "Checksum verified"

p_step "Installing binary..."
install -m 755 "${TMP}/ghostpayments" "${BIN_PATH}"
p_ok "Binary installed to ${BIN_PATH}"
cd /

p_step "Creating configuration directory..."
mkdir -p "${CONFIG_DIR}"
p_ok "Directory ready: ${CONFIG_DIR}"

if [ ! -f "${CONFIG_DIR}/.env" ]; then
    p_step "Configuring GhostPayments..."
    p_sep
    p_info "HD Wallet — generates unique deposit addresses per invoice"
    p_ask "Main mnemonic phrase (12/24 words): "; read -r MAIN_MNEMONIC
    echo ""
    p_sep
    p_info "Destination Wallet — where swept funds are sent"
    p_info "  Leave blank to auto-derive from mnemonic (recommended)"
    p_ask "Main wallet address (0x...) [blank = auto-derive]: "; read -r MAIN_WALLET_ADDRESS
    echo ""
    p_sep
    p_info "Fee Wallet — funds gas costs for sweeping tokens"
    p_info "  1) BIP-39 mnemonic phrase"
    p_info "  2) Direct private key (0x...)"
    p_ask "Option [1/2]: "; read -r FEE_OPT
    FEE_MNEMONIC=""
    FEE_PRIVATE_KEY=""
    if [ "${FEE_OPT}" = "2" ]; then
        p_ask "Fee wallet private key (0x...): "; read -r FEE_PRIVATE_KEY
    else
        p_ask "Fee wallet mnemonic (12/24 words): "; read -r FEE_MNEMONIC
    fi
    echo ""
    p_sep
    p_info "Network Configuration"
    p_ask "BSC RPC URL [https://bsc-dataseed.binance.org]: "; read -r BSC_RPC
    BSC_RPC="${BSC_RPC:-https://bsc-dataseed.binance.org}"
    p_ask "Polygon RPC URL [https://polygon-rpc.com]: "; read -r POL_RPC
    POL_RPC="${POL_RPC:-https://polygon-rpc.com}"
    p_ask "Listen port [5000]: "; read -r PORT
    PORT="${PORT:-5000}"
    p_sep
    p_ask "Enable auto-update? [Y/n]: "; read -r AUTO_UPDATE
    AUTO_UPDATE="${AUTO_UPDATE:-y}"
    if [[ $AUTO_UPDATE =~ ^[Yy]$ ]]; then
        AUTO_UPDATE="true"
    else
        AUTO_UPDATE="false"
    fi
    p_ask "HTTP proxy for updates (blank = none): "; read -r HTTP_PROXY
    p_ask "HTTPS proxy for updates (blank = none): "; read -r HTTPS_PROXY
    ADMIN_PATH="$("${BIN_PATH}" --generate-token)"
    PAYMENT_PATH="$("${BIN_PATH}" --generate-token)"
    p_sep
    p_step "Configuration Summary:"
    p_info "HD wallet mnemonic: [provided]"
    if [ -n "${MAIN_WALLET_ADDRESS}" ]; then
        p_info "Destination wallet: ${MAIN_WALLET_ADDRESS}"
    else
        p_info "Destination wallet: auto-derive from mnemonic (index 0)"
    fi
    p_info "BSC RPC:            ${BSC_RPC}"
    p_info "Polygon RPC:        ${POL_RPC}"
    p_info "Port:               ${PORT}"
    p_info "Auto-update:        ${AUTO_UPDATE}"
    echo ""
    p_ask "Confirm and save configuration? [Y/n]: "; read -r CONFIRM
    CONFIRM="${CONFIRM:-y}"
    if [[ ! $CONFIRM =~ ^[Yy]$ ]]; then
        p_err "Installation cancelled"
        exit 1
    fi

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
WAITRESS_THREADS=8
INVOICE_TTL_MINUTES=30
BSC_CONFIRMATIONS=3
POLYGON_CONFIRMATIONS=1
GAS_BUFFER_PERCENT=60
POLL_INTERVAL_SECONDS=20
PORT=${PORT}
DB_PATH=/var/lib/ghostpayments/ghost.db
ENV_PATH=${CONFIG_DIR}/.env
EOF

    chmod 600 "${CONFIG_DIR}/.env"
    p_ok "Config written to ${CONFIG_DIR}/.env"
    p_admin_box "http://YOUR_HOST:${PORT}/${ADMIN_PATH}/"
    p_payment_box "http://YOUR_HOST:${PORT}/${PAYMENT_PATH}/pay/<invoice_id>"
    p_info "Replace YOUR_HOST with your server IP or domain."
    p_info "Tip: Use nginx + Cloudflare for better reliability and DDoS protection."
    echo ""
else
    p_warn "Configuration already exists at ${CONFIG_DIR}/.env"
    PORT=$(grep "^PORT=" "${CONFIG_DIR}/.env" | cut -d"=" -f2 | tr -d " ")
    PORT="${PORT:-5000}"
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
p_ok "Systemd service installed"

p_step "Enabling and starting GhostPayments..."
systemctl enable ghostpayments
if systemctl is-active --quiet ghostpayments; then
    p_warn "Restarting existing service..."
    systemctl restart ghostpayments
else
    systemctl start ghostpayments
fi
p_ok "GhostPayments is running"

p_sep
p_ask "Setup nginx now? [y/N] "; read -r -n 1 REPLY; echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    p_step "Installing nginx..."
    apt-get update && apt-get install -y nginx certbot python3-certbot-nginx
    if [ -f /etc/nginx/sites-available/ghostpayments ]; then
        p_warn "Removing existing ghostpayments nginx configuration..."
        rm -f /etc/nginx/sites-enabled/ghostpayments
        rm -f /etc/nginx/sites-available/ghostpayments
        if systemctl is-active --quiet nginx; then
            p_info "Restarting nginx..."
            systemctl restart nginx
        fi
    fi
    p_ask "Enter your domain name: "; read -r DOMAIN

    cat > /etc/nginx/sites-available/ghostpayments <<EOF
server {
    listen 80;
    server_name ${DOMAIN};

    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }
}
EOF

    ln -sf /etc/nginx/sites-available/ghostpayments /etc/nginx/sites-enabled/
    nginx -t && systemctl reload nginx

    p_ask "Generate TLS certificate with Let's Encrypt? [y/N] "; read -r -n 1 REPLY; echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        certbot --nginx -d ${DOMAIN}
    fi

    cat > /etc/nginx/sites-available/ghostpayments <<EOF
server {
    listen 80;
    server_name ${DOMAIN};

    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    location / {
        return 301 https://\$server_name\$request_uri;
    }
}

server {
    listen 443 ssl http2;
    server_name ${DOMAIN};

    ssl_certificate /etc/letsencrypt/live/${DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${DOMAIN}/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    location / {
        proxy_pass http://127.0.0.1:${PORT};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 86400;
        proxy_send_timeout 86400;
        proxy_buffering off;
        proxy_request_buffering off;
        tcp_nodelay on;
    }
}
EOF

    systemctl reload nginx
    p_ok "nginx configured for ${DOMAIN}"
    echo ""
    if [ -n "${ADMIN_PATH}" ]; then
        p_admin_box "https://${DOMAIN}/${ADMIN_PATH}/"
        p_payment_box "https://${DOMAIN}/${PAYMENT_PATH}/pay/<invoice_id>"
    fi
else
    p_info "Skipping nginx setup. Example configuration available at the GitHub repository README."
fi

p_sep
p_ok "Installation complete!"
p_sep
p_info "Configuration: ${CONFIG_DIR}/.env"
echo ""
p_info "Useful commands:"
echo -e "  ${DIM}sudo systemctl status ghostpayments${NC}"
echo -e "  ${DIM}sudo systemctl stop ghostpayments${NC}"
echo -e "  ${DIM}sudo systemctl restart ghostpayments${NC}"
echo -e "  ${DIM}sudo journalctl -u ghostpayments -f${NC}"
echo ""
