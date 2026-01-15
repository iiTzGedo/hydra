# Phase 3 Review & Suggestions (Plan vs Code)

This review checks the Phase 3 CLI overhaul against `Plan-Agent-Distribution-Update.md` and the current codebase. It highlights what matches, what deviates, and the remaining improvements or plan adjustments.

## What Matches the Plan / Core Idea

- CLI is modularized with `login`, `register`, `config`, `node`, and `service` subcommands in `hydra-agent/src/cli/`.
- Global CLI options exist (`--config`, `--mode`, `--aliased`, `--verbose`) with a live/dev mode split.
- Session-based login is implemented and stored in the vault for privileged actions.
- Node management commands exist (register/status/info/update/unregister).
- Vault exists at `/var/cv/hydra` and stores agent credentials, API keys, and sessions.

## Misalignments / Gaps (Phase 3)

1. **Agent auto-login after registration**
   - The plan expects the CLI to auto-login as the newly created agent after registration. Current flow stores credentials and API key but does not transition session or validate access as agent.

2. **Config updates do not auto-push node changes**
   - The plan specifies `node.*` config updates should immediately post to the API in live mode. Current `config` command edits TOML only.

3. **Service command missing docker/cron options**
   - The plan includes `--docker` and `--cron` for `service activate` / scheduling. Current `service` subcommand only supports systemd with no cron/docker options.

4. **Node registration idempotency feedback**
   - The plan calls out idempotency/duplicate handling on register; CLI currently errors if already registered unless `--force` is used but does not reconcile with API status.

## Improvements Implemented (Phase 0-3)

The following improvements from the plan’s “Identified Gaps & Improvements” section were implemented as part of this update:

- **API key renewal in agent**: when the key is near expiry (7 days), the agent auto-renews via `/auth/apikeys` and updates the vault.
- **Dev mode output**: dev mode now writes profiles to `~/hydra/profiles/` instead of a single `/tmp` file.
- **Config CRUD hardening**: config updates now validate allowed keys, parse types (bool/int/list), append list values, and create a `.toml.bak` backup before writes.
- **CLI ↔ API alignment fixes**: agent registration uses `/auth/register/agent` and node registration uses `/node/register` with correct field names.

## Suggested Plan Updates (Phase 3+)

1. **Clarify agent auto-login behavior**
   - Define whether auto-login is required or optional when API keys are already provided by `/auth/register/agent`.

2. **Add a “config apply” step**
   - If node config changes should update the API immediately, specify whether `hydra config set` should call the API directly or trigger `hydra node update` under the hood.

3. **Service command scope**
   - If docker/cron modes are required, add explicit acceptance criteria (supported platforms, cron format validation, docker image strategy).

4. **Diagnose and preview commands**
   - Consider adding `hydra diagnose` and `hydra profile preview` as Phase 3+ tasks if they’re required by operators for troubleshooting.

