#!/usr/bin/env python3
"""Cross-platform hashing contract for Paper Ear branded web sites.

Git may rewrite text line endings between LF and CRLF on checkout. Site
identity therefore hashes recognized UTF-8 text after normalizing line endings
to LF, while images, PDFs, and every other binary file remain byte-exact.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Mapping


SITE_IDENTITY_SCHEMA_VERSION = 2
SITE_HASH_ALGORITHM = "sha256"
SITE_TEXT_HASH_MODE = "utf8-lf-v1"
SITE_BINARY_HASH_MODE = "raw-bytes-v1"
SITE_MANIFEST_HASH_MODE = "canonical-json-v1"
SITE_HASH_CONTRACT = {
    "algorithm": SITE_HASH_ALGORITHM,
    "text_mode": SITE_TEXT_HASH_MODE,
    "binary_mode": SITE_BINARY_HASH_MODE,
    "manifest_mode": SITE_MANIFEST_HASH_MODE,
}

UTF8_TEXT_SUFFIXES = frozenset(
    {
        ".css",
        ".csv",
        ".html",
        ".htm",
        ".js",
        ".json",
        ".md",
        ".svg",
        ".txt",
        ".xml",
    }
)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def normalize_utf8_text(payload: bytes) -> bytes:
    """Return UTF-8 bytes with CRLF and lone CR converted to LF."""
    text = payload.decode("utf-8")
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def site_file_record(path: Path) -> dict[str, str]:
    """Hash one site file using its explicit cross-platform content mode."""
    path = Path(path)
    payload = path.read_bytes()
    if path.suffix.lower() in UTF8_TEXT_SUFFIXES:
        try:
            payload = normalize_utf8_text(payload)
        except UnicodeDecodeError:
            mode = SITE_BINARY_HASH_MODE
        else:
            mode = SITE_TEXT_HASH_MODE
    else:
        mode = SITE_BINARY_HASH_MODE
    return {"sha256": _sha256_bytes(payload), "mode": mode}


def site_manifest_sha256(files: Mapping[str, object]) -> str:
    """Hash the canonical JSON representation of the per-file records."""
    canonical = json.dumps(files, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return _sha256_bytes(canonical.encode("utf-8"))


def valid_site_file_record(record: object) -> bool:
    if not isinstance(record, dict):
        return False
    digest = str(record.get("sha256") or "").lower()
    mode = record.get("mode")
    return bool(
        SHA256_RE.fullmatch(digest)
        and mode in {SITE_TEXT_HASH_MODE, SITE_BINARY_HASH_MODE}
    )
