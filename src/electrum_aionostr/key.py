"""
forked from https://github.com/jeffthibault/python-nostr.git
"""
import secrets
import base64
from hashlib import sha256

import electrum_ecc as ecc

# TODO abstract-away crypto backend, as done in electrum/crypto.py
try:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import padding
except ImportError:
    raise ImportError("Missing dependency 'cryptography'. You could install it using the [crypto] extra.") from None

from .delegation import Delegation
from .event import Event
from . import bech32


class PublicKey:
    def __init__(self, raw_bytes: bytes) -> None:
        assert isinstance(raw_bytes, bytes), type(raw_bytes)
        assert len(raw_bytes) == 32, len(raw_bytes)
        self.raw_bytes = raw_bytes

    def bech32(self) -> str:
        converted_bits = bech32.convertbits(self.raw_bytes, 8, 5)
        return bech32.bech32_encode("npub", converted_bits, bech32.Encoding.BECH32)

    def hex(self) -> str:
        return self.raw_bytes.hex()

    def verify_signed_message_hash(self, hash: str, sig: str) -> bool:
        return ecc.ECPubkey(b'\x02' + self.raw_bytes).schnorr_verify(
            bytes.fromhex(sig), bytes.fromhex(hash)
        )

    @classmethod
    def from_npub(cls, npub: str):
        """Load a PublicKey from its bech32/npub form"""
        hrp, data, spec = bech32.bech32_decode(npub)
        raw_public_key = bech32.convertbits(data, 5, 8)[:-1]
        return cls(bytes(raw_public_key))


class PrivateKey:
    def __init__(self, raw_secret: bytes = None) -> None:
        if raw_secret is not None:
            self.raw_secret = raw_secret
        else:
            self.raw_secret = secrets.token_bytes(32)

        sk = ecc.ECPrivkey(self.raw_secret)
        self.public_key = PublicKey(sk.get_public_key_bytes()[1:])

    @classmethod
    def from_nsec(cls, nsec: str):
        """Load a PrivateKey from its bech32/nsec form"""
        hrp, data, spec = bech32.bech32_decode(nsec)
        raw_secret = bech32.convertbits(data, 5, 8)[:-1]
        return cls(bytes(raw_secret))

    def bech32(self) -> str:
        converted_bits = bech32.convertbits(self.raw_secret, 8, 5)
        return bech32.bech32_encode("nsec", converted_bits, bech32.Encoding.BECH32)

    def hex(self) -> str:
        return self.raw_secret.hex()

    def compute_shared_secret(self, public_key_hex: str) -> bytes:
        privkey = ecc.ECPrivkey(self.raw_secret)
        pubkey = ecc.ECPubkey(bytes.fromhex("02" + public_key_hex))
        pt = pubkey * privkey.secret_scalar
        return int.to_bytes(pt.x(), length=32, byteorder='big', signed=False)

    def encrypt_message(self, message: str, public_key_hex: str) -> str:
        padder = padding.PKCS7(128).padder()
        padded_data = padder.update(message.encode()) + padder.finalize()

        iv = secrets.token_bytes(16)
        cipher = Cipher(
            algorithms.AES(self.compute_shared_secret(public_key_hex)), modes.CBC(iv), default_backend()
        )

        encryptor = cipher.encryptor()
        encrypted_message = encryptor.update(padded_data) + encryptor.finalize()

        return f"{base64.b64encode(encrypted_message).decode()}?iv={base64.b64encode(iv).decode()}"

    def decrypt_message(self, encoded_message: str, public_key_hex: str) -> str:
        encoded_data = encoded_message.split("?iv=")
        encoded_content, encoded_iv = encoded_data[0], encoded_data[1]

        iv = base64.b64decode(encoded_iv)
        cipher = Cipher(
            algorithms.AES(self.compute_shared_secret(public_key_hex)), modes.CBC(iv), default_backend()
        )
        encrypted_content = base64.b64decode(encoded_content)

        decryptor = cipher.decryptor()
        decrypted_message = decryptor.update(encrypted_content) + decryptor.finalize()

        unpadder = padding.PKCS7(128).unpadder()
        unpadded_data = unpadder.update(decrypted_message) + unpadder.finalize()

        return unpadded_data.decode()

    def sign_message_hash(self, hash: bytes) -> str:
        sk = ecc.ECPrivkey(self.raw_secret)
        sig = sk.schnorr_sign(hash)
        return sig.hex()

    def sign_event(self, event: Event) -> None:
        event.sig = self.sign_message_hash(bytes.fromhex(event.id))

    def sign_delegation(self, delegation: Delegation) -> None:
        delegation.signature = self.sign_message_hash(
            sha256(delegation.delegation_token.encode()).digest()
        )

    def __eq__(self, other):
        return self.raw_secret == other.raw_secret


def mine_vanity_key(prefix: str = None, suffix: str = None) -> PrivateKey:
    if prefix is None and suffix is None:
        raise ValueError("Expected at least one of 'prefix' or 'suffix' arguments")

    while True:
        sk = PrivateKey()
        if (
            prefix is not None
            and not sk.public_key.bech32()[5 : 5 + len(prefix)] == prefix
        ):
            continue
        if suffix is not None and not sk.public_key.bech32()[-len(suffix) :] == suffix:
            continue
        break

    return sk
