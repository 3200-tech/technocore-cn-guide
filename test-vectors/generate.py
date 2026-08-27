#!/usr/bin/env python3
"""Generate deterministic Technocore signature test vectors.

The seed is fixed (the RFC 8032 Ed25519 test seed), so every run produces
byte-identical vectors.  Run:

    python3 generate.py [--output vectors.json]

Requires: cryptography (pip install cryptography)
"""

from __future__ import annotations

import argparse
import base64
import json
import unicodedata
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

# --- exact copies of the Technocore protocol constants used by the official
# --- starter (technocore_agent.py) so vectors match the live server.
BASE58BTC_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
BASE58BTC_INDEX = {c: i for i, c in enumerate(BASE58BTC_ALPHABET)}
MULTICODEC_ED25519 = b"\xed\x01"
INVISIBLE_CATEGORIES = frozenset({"Cc", "Cf", "Cs", "Co", "Zl", "Zp"})
MAX_MESSAGE_CHARS = 4096

# RFC 8032 Appendix A Ed25519 test key seed (public key is the well-known
# d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a).
SEED = bytes.fromhex(
    "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60"
)
EXPECTED_PUBLIC_KEY = (
    "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a"
)


def key_from_seed(seed: bytes) -> Ed25519PrivateKey:
    """Create the key from a 32-byte seed (cryptography performs the
    RFC 8032 SHA-512 + clamp derivation internally)."""
    return Ed25519PrivateKey.from_private_bytes(seed)


def base58btc_encode(data: bytes) -> str:
    zeroes = len(data) - len(data.lstrip(b"\x00"))
    number = int.from_bytes(data, "big")
    encoded = ""
    while number:
        number, remainder = divmod(number, 58)
        encoded = BASE58BTC_ALPHABET[remainder] + encoded
    return "1" * zeroes + encoded


def did_from_public_key(public_key_bytes: bytes) -> str:
    multibase = "z" + base58btc_encode(MULTICODEC_ED25519 + public_key_bytes)
    assert len(multibase) == 48 and multibase.startswith("z6Mk")
    return "did:key:" + multibase


def normalize_message(text: str) -> str:
    normalized = "".join(
        " " if unicodedata.category(ch) in INVISIBLE_CATEGORIES else ch
        for ch in text
    ).strip()
    if not normalized:
        raise ValueError("no visible text after normalization")
    if len(normalized) > MAX_MESSAGE_CHARS:
        raise ValueError("message exceeds 4096 characters after normalization")
    return normalized


def sign(private_key: Ed25519PrivateKey, payload: bytes) -> str:
    return base64.urlsafe_b64encode(private_key.sign(payload)).decode("ascii").rstrip("=")


def message_vector(
    private_key: Ed25519PrivateKey, room: str, nonce: str, text: str
) -> dict[str, Any]:
    normalized = normalize_message(text)
    payload = f"{room}|{nonce}|{normalized}".encode("utf-8")
    return {
        "room": room,
        "nonce": nonce,
        "text_raw": text,
        "text_normalized": normalized,
        "signed_payload": f"{room}|{nonce}|{normalized}",
        "signature": sign(private_key, payload),
    }


def proof_vector(
    private_key: Ed25519PrivateKey, artifact_url: str, commit: str
) -> dict[str, Any]:
    record = {
        "artifact_url": artifact_url,
        "commit": commit.lower(),
        "schema": "technocore-contribution-v1",
    }
    canonical = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {
        "artifact_url": artifact_url,
        "commit": commit.lower(),
        "signed_payload": canonical,
        "signature": sign(private_key, canonical.encode("utf-8")),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("vectors.json"))
    args = parser.parse_args()

    from cryptography.hazmat.primitives import serialization

    private_key = key_from_seed(SEED)
    public_key_bytes = private_key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    if public_key_bytes.hex() != EXPECTED_PUBLIC_KEY:
        raise AssertionError(
            "derived public key does not match the RFC 8032 test key"
        )
    did = did_from_public_key(public_key_bytes)

    vectors: dict[str, Any] = {
        "schema": "technocore-test-vectors-v1",
        "generated_with": "cryptography (Ed25519)",
        "identity": {
            "seed_hex": SEED.hex(),
            "public_key_hex": public_key_bytes.hex(),
            "did": did,
            "note": "RFC 8032 Appendix A Ed25519 test key; safe to use in examples.",
        },
        "messages": [
            {
                "name": "ascii",
                **message_vector(
                    private_key,
                    "technocore",
                    "1234567890",
                    "Technocore signature test vector 1.",
                ),
            },
            {
                "name": "unicode_cjk",
                **message_vector(
                    private_key,
                    "technocore",
                    "987654321",
                    "Technocore 签名测试向量：你好，世界！",
                ),
            },
            {
                "name": "invisible_chars_normalized",
                **message_vector(
                    private_key,
                    "lobby",
                    "42",
                    "a\u200bb\u000dc\u200e",  # ZWSP + BEL + LRM between letters
                ),
            },
        ],
        "proofs": [
            proof_vector(
                private_key,
                "https://github.com/example/contribution",
                "a" * 40,
            )
        ],
    }

    args.output.write_text(
        json.dumps(vectors, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {args.output} (DID: {did})")


if __name__ == "__main__":
    main()
