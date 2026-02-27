import pytest
from app.services.wallet import derive_address, get_fee_address

TEST_MNEMONIC = "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about"

def test_derive_address_returns_checksum_address():
    addr, privkey = derive_address(TEST_MNEMONIC, 0)
    assert addr.startswith("0x")
    assert len(addr) == 42
    assert privkey.startswith("0x")
    assert len(privkey) == 66

def test_derive_address_different_indices():
    addr0, _ = derive_address(TEST_MNEMONIC, 0)
    addr1, _ = derive_address(TEST_MNEMONIC, 1)
    assert addr0 != addr1

def test_derive_address_deterministic():
    addr1, key1 = derive_address(TEST_MNEMONIC, 5)
    addr2, key2 = derive_address(TEST_MNEMONIC, 5)
    assert addr1 == addr2
    assert key1 == key2

def test_get_fee_address_from_mnemonic():
    addr, privkey = get_fee_address(mnemonic=TEST_MNEMONIC)
    addr0, _ = derive_address(TEST_MNEMONIC, 0)
    assert addr == addr0

def test_get_fee_address_from_privkey(monkeypatch):
    _, privkey = derive_address(TEST_MNEMONIC, 3)
    monkeypatch.setenv("FEE_PRIVATE_KEY", privkey)
    addr, returned_key = get_fee_address()
    assert addr.startswith("0x")
    assert returned_key == privkey

def test_get_fee_address_privkey_takes_precedence(monkeypatch):
    _, privkey = derive_address(TEST_MNEMONIC, 3)
    addr_from_index3, _ = derive_address(TEST_MNEMONIC, 3)
    addr_from_index0, _ = derive_address(TEST_MNEMONIC, 0)
    monkeypatch.setenv("FEE_PRIVATE_KEY", privkey)
    addr, _ = get_fee_address(mnemonic=TEST_MNEMONIC)
    assert addr == addr_from_index3
    assert addr != addr_from_index0

def test_get_fee_address_no_config_raises(monkeypatch):
    monkeypatch.delenv("FEE_PRIVATE_KEY", raising=False)
    with pytest.raises(ValueError):
        get_fee_address()
