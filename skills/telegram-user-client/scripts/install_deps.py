#!/usr/bin/env python3
"""Install Python packages without pip — download wheels and extract manually."""

import os
import sys
import zipfile
import tarfile
import urllib.request
import json
import argparse
import tempfile
import shutil

TARGET = os.path.dirname(os.path.abspath(__file__))
DEPS_DIR = os.path.join(TARGET, "deps")
os.makedirs(DEPS_DIR, exist_ok=True)

PYTHON_VERSION = f"py{sys.version_info.major}.{sys.version_info.minor}"
SYSTEM = f"{sys.platform}-x86_64"

def get_pypi_urls(package_name):
    """Get download URLs for a package via PyPI JSON API."""
    url = f"https://pypi.org/pypi/{package_name}/json"
    with urllib.request.urlopen(url, timeout=15) as resp:
        data = json.load(resp)

    latest = data["info"]["version"]
    files = data["releases"][latest]

    wheels = []
    sdist = None
    for f in files:
        fn = f["filename"]
        if fn.endswith(".whl"):
            # Prefer pure Python (none-any) or platform-specific cp311
            if "none-any" in fn or PYTHON_VERSION in fn:
                wheels.append((f["url"], fn, f["digests"]["sha256"]))
        elif fn.endswith(".tar.gz"):
            sdist = (f["url"], fn, f["digests"]["sha256"])

    return latest, wheels or [sdist] if sdist else [], wheels

def download_and_extract(url, filename, sha256_expected):
    """Download a wheel or tarball and extract into DEPS_DIR."""
    dest = os.path.join(DEPS_DIR, filename)

    # Already extracted?
    if os.path.exists(dest + ".extracted"):
        print(f"  Already extracted: {filename}")
        return

    # Download
    print(f"  Downloading {filename}...")
    with urllib.request.urlopen(url, timeout=60) as resp:
        data = resp.read()

    # Verify
    import hashlib
    actual = hashlib.sha256(data).hexdigest()
    if sha256_expected != actual:
        print(f"  SHA256 MISMATCH! {actual[:16]} != {sha256_expected[:16]}")
        return

    # Extract
    if filename.endswith(".whl"):
        print(f"  Extracting wheel...")
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            zf.extractall(DEPS_DIR)
    elif filename.endswith(".tar.gz"):
        print(f"  Extracting tarball...")
        with tarfile.open(fileobj=io.BytesIO(data)) as tf:
            tf.extractall(DEPS_DIR)
    else:
        print(f"  Unknown format, saving as-is")
        with open(dest, "wb") as f:
            f.write(data)

    # Mark
    open(dest + ".extracted", "w").close()
    print(f"  Done: {filename}")

import io

def main():
    parser = argparse.ArgumentParser(description="Install packages without pip")
    parser.add_argument("packages", nargs="+")
    args = parser.parse_args()

    for pkg in args.packages:
        print(f"\n=== {pkg} ===")
        try:
            version, all_urls, pure_wheels = get_pypi_urls(pkg)
            print(f"  Latest: {version}")
            print(f"  Pure wheels: {len(pure_wheels)}, all downloads: {len(all_urls)}")

            # Prefer none-any wheel first, then cp311
            url, filename, sha256 = None, None, None
            for u, fn, s in pure_wheels:
                if "none-any" in fn:
                    url, filename, sha256 = u, fn, s
                    break
            if not url:
                for u, fn, s in pure_wheels:
                    if PYTHON_VERSION in fn:
                        url, filename, sha256 = u, fn, s
                        break
            if not url and all_urls:
                url, filename, sha256 = all_urls[0]

            if not url:
                print(f"  No suitable wheel found for {PYTHON_VERSION}")
                continue

            download_and_extract(url, filename, sha256)
            print(f"  Installed {pkg} {version}")

        except Exception as e:
            print(f"  ERROR: {e}")

    print(f"\n✅ All done. Add this to PYTHONPATH:")
    print(f"   export PYTHONPATH={DEPS_DIR}:$PYTHONPATH")
    print(f"\nOr put in deps/__init__.py:")
    print(f"   import sys; sys.path.insert(0, '{DEPS_DIR}')")

if __name__ == "__main__":
    main()
