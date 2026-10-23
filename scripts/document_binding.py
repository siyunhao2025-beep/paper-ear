#!/usr/bin/env python3
"""Bind a dialogue script to the exact PDF used for a Paper-Ear run."""

import hashlib
import os
import re
from pathlib import Path


SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
HASH_ALGORITHM = "sha256"
RAW_BYTES_HASH_MODE = "raw-bytes-v1"
UTF8_LF_HASH_MODE = "utf8-lf-v1"
INPUT_HASH_CONTRACT = {
    "algorithm": HASH_ALGORITHM,
    "pdf_mode": RAW_BYTES_HASH_MODE,
    "script_raw_mode": RAW_BYTES_HASH_MODE,
    "script_content_mode": UTF8_LF_HASH_MODE,
}


class DocumentBindingError(ValueError):
    """Raised when a dialogue script does not match the supplied PDF."""

    def __init__(self, issues):
        self.issues = list(issues)
        message = "; ".join(issue["message"] for issue in self.issues)
        super().__init__(message)


def sha256_file(path, chunk_size=1024 * 1024):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_utf8_lf_file(path):
    """Hash UTF-8 text after normalizing CRLF and lone CR to LF."""
    payload = Path(path).read_bytes()
    text = payload.decode("utf-8")
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()


def canonical_existing_path(path):
    return Path(path).expanduser().resolve(strict=True)


def collect_input_identity(pdf_path, script_path, pdf_page_count):
    """Return immutable identifiers recorded in every successful render report."""
    pdf = canonical_existing_path(pdf_path)
    script = canonical_existing_path(script_path)
    return {
        "source_document": str(pdf),
        "pdf_sha256": sha256_file(pdf),
        "pdf_pages": int(pdf_page_count),
        "dialogue_script": str(script),
        "script_sha256": sha256_file(script),
        "script_content_sha256": sha256_utf8_lf_file(script),
        "input_hash_contract": dict(INPUT_HASH_CONTRACT),
    }


def _issue(issues, code, message):
    issues.append({"code": code, "message": message})


def _resolve_declared_path(value, script_path):
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = Path(script_path).parent / candidate
    return candidate.resolve(strict=False)


def validate_document_binding(
    data,
    identity,
    script_path,
    require_source_document=False,
    artifact_label="dialogue",
):
    """Validate a dialogue or web-brief root against the current input identity.

    Preferred schema::

        "source_document": {
          "filename": "paper.pdf",
          "sha256": "...",
          "page_count": 12
        }

    The legacy pair ``source_document: <path>`` + ``pdf_sha256`` remains
    readable for non-branded scripts.  Any declared binding is enforced.
    Branded production uses ``require_source_document=True`` and requires the
    preferred object with both SHA-256 and page count.
    """
    issues = []
    source = data.get("source_document")
    top_sha = data.get("pdf_sha256")
    top_pages = data.get("pdf_page_count")
    declared = source is not None or top_sha is not None or top_pages is not None

    expected_sha = top_sha
    expected_pages = top_pages
    expected_filename = None
    expected_path = None

    if isinstance(source, dict):
        object_sha = source.get("sha256")
        object_pages = source.get("page_count")
        expected_filename = source.get("filename")
        expected_path = source.get("path") or source.get("canonical_path")
        if object_sha is not None:
            if top_sha is not None and str(object_sha).lower() != str(top_sha).lower():
                _issue(
                    issues,
                    "conflicting_pdf_sha256",
                    "source_document.sha256 and root pdf_sha256 disagree.",
                )
            expected_sha = object_sha
        if object_pages is not None:
            if top_pages is not None and object_pages != top_pages:
                _issue(
                    issues,
                    "conflicting_pdf_page_count",
                    "source_document.page_count and root pdf_page_count disagree.",
                )
            expected_pages = object_pages
    elif isinstance(source, str):
        expected_path = source
    elif source is not None:
        _issue(
            issues,
            "invalid_source_document",
            "source_document must be an object (preferred) or a path string.",
        )

    if require_source_document and not isinstance(source, dict):
        _issue(
            issues,
            "missing_source_document",
            "brand_profile 'bubu-yier-v1' requires a source_document object with sha256 and page_count.",
        )

    if require_source_document or declared:
        if not isinstance(expected_sha, str) or not expected_sha.strip():
            _issue(
                issues,
                "missing_pdf_sha256",
                f"The {artifact_label} must declare source_document.sha256 for the current PDF.",
            )
        elif not SHA256_RE.fullmatch(expected_sha.strip()):
            _issue(issues, "invalid_pdf_sha256", "The declared PDF SHA-256 must contain exactly 64 hexadecimal characters.")
        elif expected_sha.strip().lower() != identity["pdf_sha256"]:
            _issue(
                issues,
                "pdf_sha256_mismatch",
                f"The {artifact_label} belongs to a different PDF: declared SHA-256 "
                f"{expected_sha.strip().lower()} but --pdf is {identity['pdf_sha256']}.",
            )

    if require_source_document:
        if isinstance(expected_pages, bool) or not isinstance(expected_pages, int):
            _issue(
                issues,
                "missing_pdf_page_count",
                "brand_profile 'bubu-yier-v1' requires source_document.page_count as an integer.",
            )
        elif expected_pages != identity["pdf_pages"]:
            _issue(
                issues,
                "pdf_page_count_mismatch",
                f"The {artifact_label} declares {expected_pages} PDF pages but --pdf has {identity['pdf_pages']}.",
            )
    elif expected_pages is not None:
        if isinstance(expected_pages, bool) or not isinstance(expected_pages, int) or expected_pages < 1:
            _issue(issues, "invalid_pdf_page_count", "The declared PDF page count must be a positive integer.")
        elif expected_pages != identity["pdf_pages"]:
            _issue(
                issues,
                "pdf_page_count_mismatch",
                f"The {artifact_label} declares {expected_pages} PDF pages but --pdf has {identity['pdf_pages']}.",
            )

    if expected_filename is not None:
        if not isinstance(expected_filename, str) or not expected_filename.strip():
            _issue(issues, "invalid_source_filename", "source_document.filename must be non-empty text.")
        elif expected_filename.strip() != Path(identity["source_document"]).name:
            _issue(
                issues,
                "source_filename_mismatch",
                f"The dialogue names '{expected_filename.strip()}' but --pdf is '{Path(identity['source_document']).name}'.",
            )

    if expected_path is not None:
        if not isinstance(expected_path, str) or not expected_path.strip():
            _issue(issues, "invalid_source_path", "The declared source document path must be non-empty text.")
        else:
            declared_path = _resolve_declared_path(expected_path.strip(), script_path)
            actual_path = Path(identity["source_document"])
            if os.path.normcase(str(declared_path)) != os.path.normcase(str(actual_path)):
                _issue(
                    issues,
                    "source_path_mismatch",
                    f"The dialogue is bound to '{declared_path}' but --pdf resolves to '{actual_path}'.",
                )

    return {
        "declared": bool(declared),
        "required": bool(require_source_document),
        "verified": not issues and (declared or require_source_document),
        "issues": issues,
    }


def enforce_document_binding(
    data,
    identity,
    script_path,
    require_source_document=False,
    artifact_label="dialogue",
):
    result = validate_document_binding(
        data,
        identity,
        script_path,
        require_source_document=require_source_document,
        artifact_label=artifact_label,
    )
    if result["issues"]:
        raise DocumentBindingError(result["issues"])
    return result
