---
name: update-bank-sdk-ios
description: "Update iOS YandexBankSDK (YBSDK) version in flutter/pro project. Use when bumping BankSDK version for iOS."
user-invocable: true
---

# Update iOS BankSDK Version

Updates the YBSDK dependency version in the iOS Flutter project and regenerates Podfiles.

## Arguments

Required:
- `VERSION` — target YBSDK version (e.g. `214.2`, `215.0`). Will be prefixed with `0.` automatically if not already.

## Steps

### Step 1: Parse version

Extract VERSION from arguments. Normalize to `0.X.Y` format (e.g. `214.2` → `0.214.2`).

### Step 2: Determine worktree root

Use the current working directory to find the arcadia root (look for `.arcignore` or `.arc` directory up the tree). If in a worktree, use it. Otherwise use `~/arcadia`.

Set `ROOT` to the detected arcadia root.

### Step 3: Update podspec

Edit `$ROOT/flutter/pro/yxpro/pcidss/yx_bank/ios/yx_bank.podspec`:
- Find the line with `s.dependency 'YBSDK/Static'` and update the version to `'~> VERSION'`

### Step 4: Update Package.swift

Edit `$ROOT/flutter/pro/yxpro/pcidss/yx_bank/ios/yx_bank/Package.swift`:
- Find the line with `.package(id: "yandex.YBSDK"` and update the version to `exact: "VERSION"`

### Step 5: Flutter pub get

Run `flutter pub get` in both Flutter project roots (can run in parallel):

1. `$ROOT/flutter/pro/yxpro/professions/scooters/example`
2. `$ROOT/flutter/pro/yxpro/yxpro`

This generates `Generated.xcconfig` required by Podfile. Wait for both to complete.

### Step 6: Pod update

Run `bundle exec pod update YBSDK/Static` in both iOS directories (can run in parallel):

1. `$ROOT/flutter/pro/yxpro/professions/scooters/example/ios`
2. `$ROOT/flutter/pro/yxpro/yxpro/ios`

**Important:** Use `pod update YBSDK/Static` (not `pod install`) — the lock file has the old version pinned.

If yxpro fails with cascading dependency errors (YBPushNotificationProcessing, YXAccountManager/Static, etc.), add those pods to the update command:
```bash
bundle exec pod update YBSDK/Static YBPushNotificationProcessing YXAccountManager/Static YBAccountManagerImpl
```

Do NOT run a full `pod update` without arguments — it may pull incompatible versions of unrelated pods (e.g. YandexGoFoundation 404).

Wait for both to complete. Report any errors.

### Step 7: Summary

Show what was changed:
- Previous versions (from both files)
- New version
- Pod install results (success/failure for each directory)
