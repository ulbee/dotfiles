#!/usr/bin/env python3
"""Final setup: fix extracted dirs and verify everything works."""

import os
import sys
import shutil

DEPS = "/workspace/skills/telegram-user-client/deps"

# Fix tarball-extracted dirs (versioned → unversioned)
fixes = {
    "pyaes-1.6.1": "pyaes",
}
for old, new in fixes.items():
    old_path = os.path.join(DEPS, old)
    new_path = os.path.join(DEPS, new)
    if os.path.exists(old_path) and not os.path.exists(new_path):
        shutil.move(old_path, new_path)
        print(f"Moved {old} → {new}")

# Also fix telethon if needed
for item in os.listdir(DEPS):
    if item.startswith("telethon-") and "." in item[9:]:
        old = os.path.join(DEPS, item)
        new = os.path.join(DEPS, "telethon")
        if not os.path.exists(new):
            shutil.move(old, new)
            print(f"Fixed telethon dir")

# Add to path
sys.path.insert(0, DEPS)

# Test imports
print("\n--- Testing imports ---")
try:
    import pyaes
    print(f"✅ pyaes {pyaes.VERSION}")
except ImportError as e:
    print(f"❌ pyaes: {e}")

try:
    import dotenv
    print(f"✅ python-dotenv OK")
except ImportError as e:
    print(f"❌ dotenv: {e}")

try:
    import telethon
    print(f"✅ telethon {telethon.__version__}")
except ImportError as e:
    print(f"❌ telethon: {e}")

print("\nAll done!")
