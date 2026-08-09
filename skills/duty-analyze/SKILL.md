---
name: duty-analyze
description: "Analyze on-call duty tickets — look up user logs via YQL queries, find appmetrica_device_id, inspect mobile app events. Use when investigating duty/on-call issues."
allowed-tools: Bash(yql-cli.sh:*), Bash(tracker-cli.sh:*), Bash(duty-analyze-cli.sh:*), Bash(monium-cli.sh:*)
user-invocable: true
---

# Duty Ticket Analysis

Analyze on-call (duty) tickets by looking up user data and mobile app logs via YQL.

**CLI:** `duty-analyze-cli.sh <command> [options]`

## Workflow

The typical investigation flow:

1. **Open ticket** — read the duty ticket to understand the problem
2. **Get appmetrica_device_id** — by executorId and date
3. **Get mobile logs** — by appmetrica_device_id and date
4. **Analyze** — find the root cause in the logs

## Commands

### `get-device-id` — Get appmetrica_device_id by executorId and date
```bash
duty-analyze-cli.sh get-device-id --executor-id UUID --date 2026-03-15
```
Runs YQL query to find the user's appmetrica_device_id from executor UUID.

### `get-mobile-logs` — Get mobile app event logs
```bash
duty-analyze-cli.sh get-mobile-logs --device-id DEVICE_ID_HASH --date 2026-03-15
duty-analyze-cli.sh get-mobile-logs --device-id DEVICE_ID_HASH --date 2026-03-15 --datetime "2026-03-15 14:00:00"
```
Runs YQL query to get AppMetrica events for the device. Optional `--datetime` to narrow the time window.

### `analyze-ticket` — Full analysis flow
```bash
duty-analyze-cli.sh analyze-ticket --ticket TICKET_KEY --executor-id UUID --date 2026-03-15
```
Combined workflow: reads the ticket, gets device ID, fetches logs, outputs everything for analysis.

## How to use as an agent

When a user asks to investigate a duty ticket:

1. Use `tracker-cli.sh show TICKET` to read the ticket description
2. Extract executorId (UUID) and date from the ticket or ask the user
3. Run `get-device-id` to find appmetrica_device_id
4. Run `get-mobile-logs` with the device ID to get event logs
5. Analyze the logs to identify the issue
6. If backend logs are needed, craft additional YQL queries using `yql-cli.sh run`

## Query Templates

The YQL queries are stored in `~/.claude/skills/duty-analyze/queries/`:
- `get_device_id.sql` — lookup appmetrica_device_id by executorId
- `get_mobile_logs.sql` — lookup mobile events by device_id_hash

These templates use `{{PLACEHOLDER}}` syntax for parameter substitution.

## Auth

Requires YQL token: `YQL_TOKEN` env var or `~/.yql-token` file.
Requires Tracker token for ticket lookup: `TRACKER_OAUTH_TOKEN` or `~/.tracker-token`.
