import os
from datetime import datetime, timezone
from app.services.wallet import derive_address, get_fee_address
from app.services.chains import (get_native_balance, get_token_balance, get_gas_price,
    estimate_token_transfer_gas, send_native, send_token, wait_for_receipt, parse_token_amount)
from app.db import open_db
import requests

def _fire_webhook(invoice):
    if not invoice["webhook_url"]:
        return
    try:
        requests.post(invoice["webhook_url"], json={"invoice_id": invoice["id"], "status": invoice["status"]}, timeout=10)
    except Exception:
        pass

def _now():
    return datetime.now(timezone.utc).isoformat()

def _resolve_main_wallet():
    addr = os.getenv("MAIN_WALLET_ADDRESS", "")
    if addr:
        return addr
    mnemonic = os.getenv("MAIN_MNEMONIC", "")
    if mnemonic:
        derived, _ = derive_address(mnemonic, 0)
        return derived
    raise ValueError("No main wallet configured: set MAIN_WALLET_ADDRESS or MAIN_MNEMONIC")

def sweep_token(invoice):
    chain = invoice["chain"]
    main_mnemonic = os.getenv("MAIN_MNEMONIC", "")
    fee_mnemonic = os.getenv("FEE_MNEMONIC", "")
    main_wallet = _resolve_main_wallet()
    gas_buffer = int(os.getenv("GAS_BUFFER_PERCENT", 20))
    deposit_address, deposit_privkey = derive_address(main_mnemonic, invoice["hd_index"])
    _, fee_privkey = get_fee_address(fee_mnemonic or None, chain)
    gas_units = estimate_token_transfer_gas(chain, invoice["token"])
    gas_price = get_gas_price(chain)
    gas_cost_wei = int(gas_units * gas_price * (1 + gas_buffer / 100))
    native_balance = get_native_balance(chain, deposit_address)
    gas_tx_hash = None
    if native_balance < gas_cost_wei:
        deficit = gas_cost_wei - native_balance
        gas_tx_hash = send_native(chain, fee_privkey, deposit_address, deficit)
        wait_for_receipt(chain, gas_tx_hash)
    token_balance = get_token_balance(chain, deposit_address, invoice["token"])
    tx_out_hash = send_token(chain, deposit_privkey, invoice["token"], main_wallet, token_balance)
    db = open_db()
    db.execute("UPDATE invoices SET status='completed', tx_out_hash=?, gas_tx_hash=?, completed_at=? WHERE id=?",
        (tx_out_hash, gas_tx_hash, _now(), invoice["id"]))
    db.commit()
    invoice_row = db.execute("SELECT * FROM invoices WHERE id=?", (invoice["id"],)).fetchone()
    db.close()
    _fire_webhook(invoice_row)

def sweep_native(invoice):
    chain = invoice["chain"]
    main_mnemonic = os.getenv("MAIN_MNEMONIC", "")
    main_wallet = _resolve_main_wallet()
    gas_buffer = int(os.getenv("GAS_BUFFER_PERCENT", 20))
    _, deposit_privkey = derive_address(main_mnemonic, invoice["hd_index"])
    deposit_address = invoice["deposit_address"]
    gas_price = get_gas_price(chain)
    gas_cost = int(21000 * gas_price * (1 + gas_buffer / 100))
    balance = get_native_balance(chain, deposit_address)
    sweep_amount = balance - gas_cost
    if sweep_amount <= 0:
        return
    tx_out_hash = send_native(chain, deposit_privkey, main_wallet, sweep_amount)
    db = open_db()
    db.execute("UPDATE invoices SET status='completed', tx_out_hash=?, completed_at=? WHERE id=?",
        (tx_out_hash, _now(), invoice["id"]))
    db.commit()
    invoice_row = db.execute("SELECT * FROM invoices WHERE id=?", (invoice["id"],)).fetchone()
    db.close()
    _fire_webhook(invoice_row)
