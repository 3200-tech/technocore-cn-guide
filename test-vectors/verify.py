#!/usr/bin/env python3
"""Verify Technocore signature test vectors using only the public key.

Run:

    python3 verify.py [--vectors vectors.json]

Requires: cryptography (pip install cryptography)

Exit code 0 means every vector verified; 1 means at least one failed.
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import sys
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

BASE58BTC_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
BASE58BTC_INDEX = {c: i for i, c in enumerate(BASE58BTC_ALPHABET)}
SIGNATURE_PATTERN = re.compile(r"[A-Za-z0-9_-]{86}")


def base58btc_decode(value: str) -> bytes:
    number = 0
    for character in value:
        number = number * 58 + BASE58BTC_INDEX[character]
    decoded = number.to_bytes((number.bit_length() + 7) // 8, "big") if number else b""
    zeroes = len(value) - len(value.lstrip("1"))
    return b"\x00" * zeroes + decoded


def public_key_from_did(did: str) -> Ed25519PublicKey:
    prefix = "did:key:"
    if not did.startswith(prefix):
        raise ValueError("DID must start with 'did:key:'")
    multibase = did[len(prefix):]
    if len(multibase) != 48 or not multibase.startswith("z6Mk"):
        raise ValueError("DID must be the canonical 48-character Ed25519 multibase form")
    decoded = base58btc_decode(multibase[1:])
    if len(decoded) != 34 or decoded[:2] != b"\xed\x01":
        raise ValueError("DID must contain an ed25519-pub multicodec")
    return Ed25519PublicKey.from_public_bytes(decoded[2:])


def check(signature: str, payload: bytes, public_key: Ed25519PublicKey) -> None:
    if not SIGNATURE_PATTERN.fullmatch(signature):
        raise ValueError("signature must contain 86 unpadded base64url characters")
    raw = base64.urlsafe_b64decode(signature + "==")
    public_key.verify(raw, payload)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vectors", type=Path, default=Path("vectors.json"))
    args = parser.parse_args()

    try:
        data: dict[str, Any] = json.loads(args.vectors.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"cannot read vectors: {error}", file=sys.stderr)
        return 1

    identity = data["identity"]
    try:
        public_key = public_key_from_did(identity["did"])
    except ValueError as error:
        print(f"invalid identity DID: {error}", file=sys.stderr)
        return 1

    raw = public_key.public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    if raw.hex() != identity["public_key_hex"]:
        print("DID public key does not match public_key_hex", file=sys.stderr)
        return 1

    failures = 0
    for vector in data["messages"]:
        name = vector.get("name", "?")
        payload = f"{vector['room']}|{vector['nonce']}|{vector['text_normalized']}".encode("utf-8")
        if payload != vector["signed_payload"].encode("utf-8"):
            print(f"FAIL {name}: signed_payload field mismatch")
            failures += 1
            continue
        try:
            check(vector["signature"], payload, public_key)
            print(f"OK   {name}: {vector['room']} seq-nonce {vector['nonce']}")
        except (InvalidSignature, ValueError) as error:
            print(f"FAIL {name}: {error}")
            failures += 1

    for vector in data["proofs"]:
        payload = vector["signed_payload"].encode("utf-8")
        try:
            check(vector["signature"], payload, public_key)
            print(f"OK   proof: {vector['commit'][:12]}… for {vector['artifact_url']}")
        except (InvalidSignature, ValueError) as error:
            print(f"FAIL proof: {error}")
            failures += 1

    total = len(data["messages"]) + len(data["proofs"])
    print(f"{total - failures}/{total} vectors valid for {identity['did']}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
