#!/usr/bin/env python3
"""Download and verify the dedicated Kokoro v1.1 Mandarin runtime files."""

import argparse
import hashlib
import os
import sys
import urllib.request
from pathlib import Path


DEFAULT_MODEL_DIR = Path.home() / ".cache" / "paper-ear" / "kokoro-zh-v1.1"
FILES = {
    "kokoro-v1.1-zh.onnx": {
        "url": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/kokoro-v1.1-zh.onnx",
        "sha256": "859f9ded9f53be16c24857cdab3254a45da53c3afd5ba6ef134c7de3f822e326",
        "size": 325_506_167,
    },
    "voices-v1.1-zh.bin": {
        "url": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/voices-v1.1-zh.bin",
        "sha256": "14cb6186c99e4f6016871405f62046c5df863ae27465cbdc4ee08be7dd703acd",
        "size": 53_815_880,
    },
    "config.json": {
        "url": "https://huggingface.co/hexgrad/Kokoro-82M-v1.1-zh/raw/main/config.json",
        "sha256": "bc333efa5ce4ceff433c8c8e5d027a1eca0166001e4e4a62bea2d26ff7a46890",
        "size": 3_228,
    },
}


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_file(path, metadata):
    if not path.is_file():
        return False, "missing"
    if path.stat().st_size != metadata["size"]:
        return False, f"size mismatch ({path.stat().st_size} bytes)"
    actual_hash = sha256_file(path)
    if actual_hash.lower() != metadata["sha256"].lower():
        return False, f"SHA-256 mismatch ({actual_hash})"
    return True, "verified"


def download_file(target, metadata):
    temporary = target.with_name(target.name + ".download")
    request = urllib.request.Request(
        metadata["url"],
        headers={"User-Agent": "paper-ear-mandarin-setup/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response, temporary.open("wb") as output:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                output.write(chunk)
        ok, detail = verify_file(temporary, metadata)
        if not ok:
            raise RuntimeError(f"Downloaded {target.name} failed verification: {detail}")
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()


def main():
    parser = argparse.ArgumentParser(
        description="Install the dedicated Kokoro v1.1-zh model in the local Paper-Ear cache."
    )
    parser.add_argument("--model-dir", default=str(DEFAULT_MODEL_DIR), help="Local model cache directory")
    parser.add_argument("--check-only", action="store_true", help="Verify existing files without downloading")
    parser.add_argument("--force", action="store_true", help="Redownload even when a file already verifies")
    args = parser.parse_args()

    model_dir = Path(args.model_dir).expanduser().resolve()
    model_dir.mkdir(parents=True, exist_ok=True)
    failures = []
    for filename, metadata in FILES.items():
        target = model_dir / filename
        ok, detail = verify_file(target, metadata)
        if ok and not args.force:
            print(f"OK       {filename} ({metadata['size']:,} bytes)")
            continue
        if args.check_only:
            print(f"MISSING  {filename}: {detail}")
            failures.append(filename)
            continue
        print(f"DOWNLOAD {filename} from the official upstream release")
        download_file(target, metadata)
        print(f"OK       {filename} ({metadata['size']:,} bytes, SHA-256 verified)")

    if failures:
        print(f"FAIL: {len(failures)} required file(s) are missing or invalid.")
        return 1
    print(f"Ready: dedicated Mandarin model verified in {model_dir}")
    print("Privacy: model files stay in this local cache and are not added to the repository.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
