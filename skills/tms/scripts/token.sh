#!/usr/bin/env bash
# Source this: `. "$(dirname "$0")/token.sh"` — экспортирует TMS_TOKEN, при неудаче
# завершает с кодом 1 и печатает подсказку. Токен НИКОГДА не печатается, `set -x` не включается.
#
# Порядок поиска: env → команда (TMS_TOKEN_CMD) → файлы → macOS Keychain.
# Нужен именно TMS OAuth-токен (client_id a5337eb7fd4c4fa1ad85900a0487f0a3),
# arc-токен от Arcanum к api.tms.yandex-team.ru НЕ подходит.

_tms_oauth_url="https://oauth.yandex-team.ru/authorize?response_type=token&client_id=a5337eb7fd4c4fa1ad85900a0487f0a3"

_tms_load_raw() {
  # Читает файл; поддерживает сырой токен ИЛИ {"access_token":"..."} JSON.
  local path="$1"
  [ -f "$path" ] || return 1
  local content
  content=$(tr -d '\r' < "$path")
  if [[ "$content" == *access_token* ]]; then
    python3 -c "import json,sys; print(json.load(sys.stdin)['access_token'])" <<<"$content" 2>/dev/null
  else
    printf '%s' "$content" | tr -d '\n\t '
  fi
}

TMS_TOKEN=""

# 1. Прямые env-переменные (TMS_OAUTH_TOKEN — конвенция CI a.yaml, Yav-ключ 'tms-token').
for var in TMS_OAUTH_TOKEN TMS_TOKEN YA_TMS_TOKEN; do
  val="${!var:-}"
  if [ -n "$val" ]; then TMS_TOKEN="$val"; break; fi
done

# 2. TMS_TOKEN_CMD — пользовательская команда, печатающая токен в stdout.
if [ -z "$TMS_TOKEN" ] && [ -n "${TMS_TOKEN_CMD:-}" ]; then
  TMS_TOKEN=$(eval "$TMS_TOKEN_CMD" 2>/dev/null | tr -d '\n\r\t ')
fi

# 3. Файлы (сырой токен или OAuth JSON).
[ -z "$TMS_TOKEN" ] && TMS_TOKEN=$(_tms_load_raw "$HOME/.arc/tms_token" || true)
[ -z "$TMS_TOKEN" ] && TMS_TOKEN=$(_tms_load_raw "$HOME/.yandex/tms_token" || true)
[ -z "$TMS_TOKEN" ] && TMS_TOKEN=$(_tms_load_raw "$HOME/.config/tms/token" || true)

# 4. macOS Keychain — стандартные имена сервиса.
if [ -z "$TMS_TOKEN" ] && command -v security >/dev/null 2>&1; then
  for svc in tms-oauth-token yandex-tms tms-token; do
    TMS_TOKEN=$(security find-generic-password -s "$svc" -w 2>/dev/null | tr -d '\n\r\t ' || true)
    [ -n "$TMS_TOKEN" ] && break
  done
fi

if [ -z "$TMS_TOKEN" ]; then
  cat >&2 <<EOF
Не найден TMS OAuth-токен. Получи его по ссылке (открой в браузере):
  $_tms_oauth_url

И предоставь любым ОДНИМ способом (в порядке поиска):
  - env:       TMS_OAUTH_TOKEN (конвенция CI), TMS_TOKEN или YA_TMS_TOKEN
  - команда:   export TMS_TOKEN_CMD='<shell, печатающий токен>'
                 напр. 'security find-generic-password -s tms-oauth-token -w'
  - файл:      ~/.arc/tms_token, ~/.yandex/tms_token или ~/.config/tms/token
                 (сырой токен или OAuth JSON-блоб)
  - keychain:  добавь в macOS Keychain под именем сервиса
                 'tms-oauth-token', 'yandex-tms' или 'tms-token'
                 напр.: security add-generic-password -s tms-oauth-token -a "\$USER" -w '<TOKEN>'
EOF
  return 1 2>/dev/null || exit 1
fi

export TMS_TOKEN
