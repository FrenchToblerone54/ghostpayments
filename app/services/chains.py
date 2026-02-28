import os
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware

USDT_ABI = [
    {"inputs": [{"name": "account", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"},
    {"inputs": [{"name": "to", "type": "address"}, {"name": "value", "type": "uint256"}], "name": "transfer", "outputs": [{"name": "", "type": "bool"}], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [], "name": "decimals", "outputs": [{"name": "", "type": "uint8"}], "stateMutability": "view", "type": "function"},
]

USDT_CONTRACTS = {
    "BSC": "0x55d398326f99059fF775485246999027B3197955",
    "POLYGON": "0xc2132D05D31c914a87C6611C10748AEb04B58e8F",
}

def _make_w3(rpc_url, poa=False):
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if poa:
        w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    return w3

def get_w3(chain):
    if chain == "BSC":
        return _make_w3(os.getenv("BSC_RPC_URL", "https://bsc-dataseed.binance.org"), poa=True)
    return _make_w3(os.getenv("POLYGON_RPC_URL", "https://polygon-rpc.com"), poa=True)

def get_native_balance(chain, address):
    return get_w3(chain).eth.get_balance(address)

def get_token_balance(chain, address, token):
    w3 = get_w3(chain)
    contract = w3.eth.contract(address=Web3.to_checksum_address(USDT_CONTRACTS[chain]), abi=USDT_ABI)
    return contract.functions.balanceOf(Web3.to_checksum_address(address)).call()

def get_block_number(chain):
    return get_w3(chain).eth.block_number

def get_gas_price(chain):
    return get_w3(chain).eth.gas_price

def send_native(chain, from_privkey, to_address, value_wei, gas_price=None):
    w3 = get_w3(chain)
    account = w3.eth.account.from_key(from_privkey)
    nonce = w3.eth.get_transaction_count(account.address)
    if gas_price is None:
        gas_price = w3.eth.gas_price
    tx = {"to": Web3.to_checksum_address(to_address), "value": value_wei, "gas": 21000, "gasPrice": gas_price, "nonce": nonce, "chainId": w3.eth.chain_id}
    signed = w3.eth.account.sign_transaction(tx, from_privkey)
    return w3.eth.send_raw_transaction(signed.raw_transaction).hex()

def send_token(chain, from_privkey, token, to_address, amount):
    w3 = get_w3(chain)
    account = w3.eth.account.from_key(from_privkey)
    contract = w3.eth.contract(address=Web3.to_checksum_address(USDT_CONTRACTS[chain]), abi=USDT_ABI)
    nonce = w3.eth.get_transaction_count(account.address)
    gas_price = w3.eth.gas_price
    tx = contract.functions.transfer(Web3.to_checksum_address(to_address), amount).build_transaction({"from": account.address, "gas": 100000, "gasPrice": gas_price, "nonce": nonce, "chainId": w3.eth.chain_id})
    signed = w3.eth.account.sign_transaction(tx, from_privkey)
    return w3.eth.send_raw_transaction(signed.raw_transaction).hex()

def estimate_token_transfer_gas(chain, token):
    return 65000

def wait_for_receipt(chain, tx_hash, timeout=120):
    w3 = get_w3(chain)
    return w3.eth.wait_for_transaction_receipt(tx_hash, timeout=timeout)

def token_decimals(chain, token):
    w3 = get_w3(chain)
    contract = w3.eth.contract(address=Web3.to_checksum_address(USDT_CONTRACTS[chain]), abi=USDT_ABI)
    return contract.functions.decimals().call()

def parse_token_amount(chain, token, amount_str):
    decimals = token_decimals(chain, token)
    from decimal import Decimal
    return int(Decimal(amount_str) * Decimal(10 ** decimals))
