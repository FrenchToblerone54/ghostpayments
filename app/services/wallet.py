from bip_utils import Bip39SeedGenerator, Bip44, Bip44Coins, Bip44Changes
from eth_account import Account

def derive_address(mnemonic, index):
    seed = Bip39SeedGenerator(mnemonic).Generate()
    bip44 = Bip44.FromSeed(seed, Bip44Coins.ETHEREUM)
    child = bip44.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(index)
    privkey = "0x" + child.PrivateKey().Raw().ToHex()
    account = Account.from_key(privkey)
    return account.address, privkey

def get_fee_address(mnemonic=None, chain=None):
    import os
    privkey = os.getenv("FEE_PRIVATE_KEY", "")
    if privkey:
        if not privkey.startswith("0x"):
            privkey = "0x" + privkey
        account = Account.from_key(privkey)
        return account.address, privkey
    if mnemonic:
        return derive_address(mnemonic, 0)
    raise ValueError("No fee wallet configured: set FEE_PRIVATE_KEY or FEE_MNEMONIC")
