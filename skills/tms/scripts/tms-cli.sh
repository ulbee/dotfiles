#!/usr/bin/env bash
set -euo pipefail

# TMS CLI — чтение тест-кейсов Yandex TMS (a.yandex-team.ru/tms) через REST API.
# Стиль и структура — как у соседних скиллов (arcanum-cli.sh / tracker-cli.sh).
#
# API:  https://api.tms.yandex-team.ru/v1
# Auth: TMS OAuth-токен, резолвится scripts/token.sh (env → cmd → file → keychain).
#       arc-токен Arcanum к TMS API НЕ подходит.

BASE_URL="${TMS_API_BASE:-https://api.tms.yandex-team.ru/v1}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
JSON_OUTPUT="false"

# --- Auth ---
TMS_TOKEN=""
load_token() {
  [[ -n "$TMS_TOKEN" ]] && return 0
  # token.sh экспортирует TMS_TOKEN либо печатает подсказку и возвращает 1.
  # shellcheck source=./token.sh
  . "${SCRIPT_DIR}/token.sh" || true
  # Если токен так и не получен — останавливаемся детерминированно (без лишних ошибок ниже).
  [[ -z "$TMS_TOKEN" ]] && exit 1
  return 0
}

# --- HTTP ---
# TMS отдаёт полезную нагрузку напрямую (без обёртки {"data":...}).
api_get() {
  local path="$1"
  load_token
  local body http
  body=$(curl -sS -o - -w $'\n%{http_code}' \
    -H "Authorization: OAuth $TMS_TOKEN" -H "Accept: application/json" \
    "${BASE_URL}${path}")
  http="${body##*$'\n'}"
  body="${body%$'\n'*}"
  if [[ "$http" == "401" ]]; then
    echo "ERROR: TMS-токен истёк или недействителен. Обнови его:" >&2
    echo "  https://oauth.yandex-team.ru/authorize?response_type=token&client_id=a5337eb7fd4c4fa1ad85900a0487f0a3" >&2
    return 1
  fi
  if [[ "$http" == "429" ]]; then
    echo "ERROR: TMS API rate limit (429, 50 rps/IP). Повтори позже или используй preproduction." >&2
    return 1
  fi
  if [[ "$http" != "200" ]]; then
    echo "ERROR: TMS API вернул HTTP $http для ${path}" >&2
    echo "$body" >&2
    return 1
  fi
  printf '%s' "$body"
}

api_post() {
  local path="$1" data="$2"
  load_token
  local body http
  body=$(curl -sS -o - -w $'\n%{http_code}' -X POST \
    -H "Authorization: OAuth $TMS_TOKEN" -H "Accept: application/json" \
    -H "Content-Type: application/json" --data "$data" \
    "${BASE_URL}${path}")
  http="${body##*$'\n'}"
  body="${body%$'\n'*}"
  if [[ "$http" != "200" ]]; then
    echo "ERROR: TMS API вернул HTTP $http для ${path}" >&2
    echo "$body" >&2
    return 1
  fi
  printf '%s' "$body"
}

# --- Парсинг URL/id ---
# Принимает:
#   https://a.yandex-team.ru/tms/projects/lm/testcases/876
#   https://tms.yandex-team.ru/projects/lm/testcases/876
#   876  (тогда нужен --project или TMS_PROJECT)
# Устанавливает глобальные PROJECT и CASE_ID.
PROJECT=""
CASE_ID=""
parse_ref() {
  local input="$1" project_opt="${2:-}"
  if [[ "$input" =~ /projects/([^/]+)/testcases/([0-9]+) ]]; then
    PROJECT="${BASH_REMATCH[1]}"
    CASE_ID="${BASH_REMATCH[2]}"
  elif [[ "$input" =~ ^[0-9]+$ ]]; then
    CASE_ID="$input"
    PROJECT="${project_opt:-${TMS_PROJECT:-}}"
  else
    echo "ERROR: не удалось разобрать TMS url/id из '$input'" >&2
    echo "  ожидается: https://a.yandex-team.ru/tms/projects/<project>/testcases/<id> или числовой id" >&2
    return 1
  fi
  if [[ -z "$PROJECT" ]]; then
    echo "ERROR: не указан проект. Передай полный URL, флаг --project <P> или env TMS_PROJECT." >&2
    return 1
  fi
}

# jq-функции: снять html-теги и раскодировать частые сущности → чистый текст.
JQ_HELPERS='
def clean:
  if . == null then "" else
    ( . | tostring
        | gsub("<br\\s*/?>";"\n")
        | gsub("</p>";"\n") | gsub("<[^>]*>";"")
        | gsub("&nbsp;";" ") | gsub("&amp;";"&")
        | gsub("&lt;";"<") | gsub("&gt;";">")
        | gsub("&quot;";"\"") | gsub("&#39;";"\u0027")
        | gsub("[ \\t]+\n";"\n") | gsub("^\\s+|\\s+$";"") )
  end;
'

# --- Команды ---

cmd_get() {
  local ref="" project_opt=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --project) project_opt="$2"; shift 2 ;;
      --json)    JSON_OUTPUT="true"; shift ;;
      *)         ref="$1"; shift ;;
    esac
  done
  [[ -z "$ref" ]] && { echo "ERROR: укажи URL или id тест-кейса" >&2; return 1; }

  parse_ref "$ref" "$project_opt"

  local data
  data=$(api_get "/projects/${PROJECT}/test-cases/${CASE_ID}")

  if [[ "$JSON_OUTPUT" == "true" ]]; then
    echo "$data" | jq '.'
    return
  fi

  # Человекочитаемый вид: название, статус/приоритет, предусловия, шаги (action → expectation).
  echo "$data" | jq -r "$JQ_HELPERS"'
    "# \(.title // "(без названия)")   [#\(.id)]",
    "Статус: \(.status.key // .status // "—")   |   Приоритет: \(.priority.key // .priority // "—")",
    "URL: https://a.yandex-team.ru/tms/projects/'"${PROJECT}"'/testcases/'"${CASE_ID}"'",
    ( (.description // "") | clean | if . != "" then "\n## Описание\n" + . else "" end ),

    "\n## Предусловия",
    ( ( .preconditions // [] )
      | if length == 0 then "  (нет)"
        else to_entries[] | "\(.key + 1). " +
          ( if (.value.type // "local") == "pointer"
            then "[shared-условие #\(.value.sharedConditionId // .value.id)]"
            else (.value.condition // .value.text // "") | clean
            end )
        end ),

    "\n## Шаги",
    ( ( .steps // [] )
      | if length == 0 then "  (нет)"
        else to_entries[] |
          "\n### Шаг \(.key + 1)" +
          ( if (.value.type // "local") == "pointer"
            then "\nStep: [shared-группа шагов #\(.value.sharedStepsGroupId // .value.id)]"
            else
              "\nAction:   " + ((.value.action // "") | clean | gsub("\n";"\n          ")) +
              "\nExpected: " + ((.value.expectation // .value.expected // "") | clean | gsub("\n";"\n          "))
            end )
        end ),

    ( ( .tasks // [] )
      | if length > 0 then "\n## Связанные задачи\n" + ( [ .[] | (.key // .id // tostring) ] | join(", ") ) else "" end )
  '
}

cmd_search() {
  local project_opt="" limit="20" filter="" term=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --project) project_opt="$2"; shift 2 ;;
      --limit)   limit="$2"; shift 2 ;;
      --filter)  filter="$2"; shift 2 ;;
      --json)    JSON_OUTPUT="true"; shift ;;
      *)         term="$1"; shift ;;
    esac
  done

  local project="${project_opt:-${TMS_PROJECT:-}}"
  [[ -z "$project" ]] && { echo "ERROR: нужен проект: --project <P> или env TMS_PROJECT" >&2; return 1; }

  # filter в синтаксисе TMS. Если не задан — ищем по подстроке в названии.
  [[ -z "$filter" && -n "$term" ]] && filter="title: \"${term}\""
  local data
  data=$(api_post "/projects/${project}/test-cases/search?limit=${limit}" \
    "$(jq -n --arg f "$filter" '{filter:$f}')")

  if [[ "$JSON_OUTPUT" == "true" ]]; then
    echo "$data" | jq '.'
    return
  fi
  echo "$data" | jq -r --arg p "$project" '
    "Найдено: \(.total // (.items|length))",
    ( .items[]? | "  #\(.id)  [\(.status.key // "—")/\(.priority.key // "—")]  \(.title)\n      https://a.yandex-team.ru/tms/projects/\($p)/testcases/\(.id)" )'
}

cmd_project() {
  local ref="" project_opt=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --json) JSON_OUTPUT="true"; shift ;;
      *)      ref="$1"; shift ;;
    esac
  done
  [[ -z "$ref" ]] && { echo "ERROR: укажи id проекта или URL" >&2; return 1; }
  # Достаём id проекта из URL, если передан URL.
  if [[ "$ref" =~ /projects/([^/]+) ]]; then project_opt="${BASH_REMATCH[1]}"; else project_opt="$ref"; fi

  local data
  data=$(api_get "/projects/${project_opt}")
  if [[ "$JSON_OUTPUT" == "true" ]]; then
    echo "$data" | jq '.'
  else
    echo "$data" | jq -r '"\(.title // .id)  [id=\(.id)]\n  archived: \(.isArchived // false)\n  workspace: \(.workspace.id // "—")"'
  fi
}

usage() {
  cat <<'EOF'
tms-cli.sh — чтение тест-кейсов Yandex TMS

Использование: tms-cli.sh <command> [args]

Команды:
  get <url|id> [--project P] [--json]
        Прочитать тест-кейс. По умолчанию — читаемый вид:
        название, статус/приоритет, предусловия, шаги (Action → Expected).
        Примеры:
          tms-cli.sh get https://a.yandex-team.ru/tms/projects/lm/testcases/876
          tms-cli.sh get 876 --project lm
          tms-cli.sh get 876 --project lm --json     # сырой JSON от API

  search <term> [--project P] [--filter F] [--limit N] [--json]
        Поиск кейсов. Без --filter ищет по подстроке в названии.
        --filter принимает синтаксис TMS, напр.:
          --filter 'status: "actual" AND tasks: "TMSLM-883"'

  project <id|url> [--json]
        Метаданные проекта.

Опции:
  --json    Сырой JSON вместо форматированного вывода.

Авторизация (нужен TMS OAuth-токен, не arc-токен):
  env TMS_OAUTH_TOKEN | TMS_TOKEN | YA_TMS_TOKEN,
  команда TMS_TOKEN_CMD, файлы ~/.arc/tms_token · ~/.yandex/tms_token · ~/.config/tms/token,
  либо macOS Keychain (service: tms-oauth-token). Подробности — при отсутствии токена.
  Получить токен: https://oauth.yandex-team.ru/authorize?response_type=token&client_id=a5337eb7fd4c4fa1ad85900a0487f0a3

Окружение:
  TMS_PROJECT    Проект по умолчанию для команд с числовым id.
  TMS_API_BASE   Базовый URL API (по умолчанию https://api.tms.yandex-team.ru/v1;
                 для экспериментов — https://api.tms-preproduction.yandex-team.ru/v1).
EOF
}

[[ $# -eq 0 ]] && { usage; exit 1; }
command="$1"; shift || true
case "$command" in
  get)             cmd_get "$@" ;;
  search)          cmd_search "$@" ;;
  project)         cmd_project "$@" ;;
  help|--help|-h)  usage ;;
  *) echo "Неизвестная команда: $command" >&2; usage; exit 1 ;;
esac
