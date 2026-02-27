import os

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", os.urandom(32).hex())
    DB_PATH = os.getenv("DB_PATH", "data/ghost.db")
    MAIN_MNEMONIC = os.getenv("MAIN_MNEMONIC", "")
    FEE_MNEMONIC = os.getenv("FEE_MNEMONIC", "")
    FEE_PRIVATE_KEY = os.getenv("FEE_PRIVATE_KEY", "")
    MAIN_WALLET_ADDRESS = os.getenv("MAIN_WALLET_ADDRESS", "")  # blank = auto-derive from MAIN_MNEMONIC index 0
    BSC_RPC_URL = os.getenv("BSC_RPC_URL", "https://bsc-dataseed.binance.org")
    POLYGON_RPC_URL = os.getenv("POLYGON_RPC_URL", "https://polygon-rpc.com")
    ADMIN_PATH = os.getenv("ADMIN_PATH", "admin")
    PAYMENT_PATH = os.getenv("PAYMENT_PATH", "pay")
    INVOICE_TTL_MINUTES = int(os.getenv("INVOICE_TTL_MINUTES", 30))
    BSC_CONFIRMATIONS = int(os.getenv("BSC_CONFIRMATIONS", 3))
    POLYGON_CONFIRMATIONS = int(os.getenv("POLYGON_CONFIRMATIONS", 1))
    GAS_BUFFER_PERCENT = int(os.getenv("GAS_BUFFER_PERCENT", 20))
    POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", 20))
    PORT = int(os.getenv("PORT", 5000))
    AUTO_UPDATE = os.getenv("AUTO_UPDATE", "true").lower() == "true"
    UPDATE_CHECK_INTERVAL = int(os.getenv("UPDATE_CHECK_INTERVAL", 300))
    UPDATE_CHECK_ON_STARTUP = os.getenv("UPDATE_CHECK_ON_STARTUP", "true").lower() == "true"
    UPDATE_HTTP_PROXY = os.getenv("UPDATE_HTTP_PROXY", "")
    UPDATE_HTTPS_PROXY = os.getenv("UPDATE_HTTPS_PROXY", "")
    ENV_PATH = os.getenv("ENV_PATH", "/etc/ghostpayments/.env")
