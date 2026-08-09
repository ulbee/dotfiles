# update-bank-sdk-ios

Обновление версии iOS YandexBankSDK (YBSDK) в проекте flutter/pro.

## Использование

Вызывается как скилл `/update-bank-sdk-ios VERSION`.

## Что делает

1. Обновляет версию в podspec и Package.swift
2. Запускает `flutter pub get`
3. Запускает `pod update` в ios директории
