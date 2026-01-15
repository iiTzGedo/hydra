# Phase 0-2 Review and Suggestions (Code + Plan)

This file summarizes what aligns with the intended updates, what is off or incomplete, and a concrete follow-up plan for Phase 0-2 code improvements. It also proposes plan updates for Phases 3+ without modifying the original plan document.

## What Matches the Plan / Core Idea

- Phase 0: Central validation module exists and includes new patterns and helper functions in `hydra-api/hydra/api/v1/core/validators.py`.
- Phase 0: Soft node ID validation (new + legacy) implemented for node registration in `hydra-api/hydra/api/v1/models/auth.py`.
- Phase 1: Storage abstraction added with S3 bundle and local bundle support in `hydra-api/hydra/api/v1/services/storage.py`.
- Phase 1: `/agent/download` and `/agent/versions` endpoints support `source=local|obs|binary` in `hydra-api/hydra/api/v1/routers/install.py`.
- Phase 2: Sub-account models and helpers implemented in `hydra-api/hydra/api/v1/models/auth.py`.
- Phase 2: Sub-account linking endpoints and service logic are implemented in `hydra-api/hydra/api/v1/routers/auth.py` and `hydra-api/hydra/api/v1/services/users.py`.
- Phase 2: Agent account registration endpoint exists with auto-linking and 90-day API key creation in `hydra-api/hydra/api/v1/services/auth.py`.

## Misalignments / Gaps (Phase 0-2)

### Phase 0 (Schema & Validation)
- Network ID, CIDR, IPv4 validations are not applied in request models. `hydra-api/hydra/api/v1/models/networks.py` still uses the old network ID regex and lacks CIDR/IP validators.
- Tag pattern is only enforced on node registration and node updates; network and topology tags only check length.
- `validate_profile_version`, `validate_service_id`, and `validate_agent_username` are defined but not used in any request models.
- `ProfileSubmission` has no validation for version format and the API generates `version` internally; this conflicts with the update note that the profile version is "sent from agent".
- No tests added for the shared validators module.

### Phase 1 (Agent Distribution API)
- `/agent/install` does not accept `source` and does not pass `version` into the embedded script; the endpoint ignores the query version and always embeds `source=binary` in the script.
- The install script doc comment still references `/api/v1/install` instead of `/api/v1/agent/install`.
- Local bundle storage path likely double-prefixes `bundles/`:
  - `HYDRA_LOCAL_STORAGE_PATH` defaults to `/var/lib/hydra/bundles` in `hydra-api/hydra/core/config.py`.
  - `LocalBundleStorageService` expects `bundles/{version}/...` under that base path, leading to `/var/lib/hydra/bundles/bundles/{version}`.
- `--dev-mode` option mentioned in the plan does not exist in the install script.
- Backward-compat endpoints or deprecation handling for old `/install` paths are not visible in this router.

### Phase 2 (Sub-Accounts + Agent Auth Flow)
- Sub-account list endpoint deviates from the plan:
  - Implemented: `GET /auth/subs` (current user only).
  - Planned: `GET /users/{userId}/subs` (admin/self access).
- Login does not allow a parent password to authenticate into a sub-account as required by updates.
- `CreateUserRequest` allows role=agent, which can create agent accounts without `isSystemAccount` or parent linking.
- Agent permissions are too narrow (`profiles:write`, `commands:poll`) and do not include node read/update or token create/revoke/read as required.
- API key endpoints only operate on the current user; there is no parent management for sub-account keys.
- Installer still registers nodes via `/node/register` and stores a node API key; the plan expects agent system account creation + sub-account linkage to be the primary auth flow.

## Suggested Code Update Plan (Phase 0-2)

### Phase 0: Validation and Schema Hardening
1. Apply the shared validators in all relevant models:
   - Network IDs, CIDR, IPv4 in `hydra-api/hydra/api/v1/models/networks.py`.
   - Tags in network/topology models to match `TAG_PATTERN`.
   - `serviceId` validation in `hydra-api/hydra/api/v1/models/services.py`, `hydra-api/hydra/api/v1/models/commands.py`, `hydra-api/hydra/api/v1/models/timemachine.py`.
   - `agent` username validation in `AgentRegistrationRequest` when a username is provided.
2. Clarify the profile version source:
   - If agent sends version, add a field and validate with `PROFILE_VERSION_PATTERN` in `ProfileSubmission`.
   - If API generates version, update model/docs to remove mention of agent-sent version.
3. Add unit tests for validators in `hydra-api/hydra/api/v1/core/validators.py` (node ID, tag, network ID, IPv4, CIDR, profile version, service ID).

### Phase 1: Distribution Endpoints and Storage
1. Add `source` and `version` query params to `/agent/install` and pass them into `get_installation_script` in `hydra-api/hydra/api/v1/routers/install.py`.
2. Fix the local bundle base path:
   - Option A: Change default `HYDRA_LOCAL_STORAGE_PATH` to `/var/lib/hydra`.
   - Option B: Treat `local_storage_path` as the bundles directory (remove the extra `bundles/` prefix in `LocalBundleStorageService`).
3. Add `--dev-mode` (or equivalent) to the install script to skip API calls and registration.
4. Update install script documentation to reference `/api/v1/agent/install` and new query parameters.
5. Decide whether to provide a deprecated `/install` path or explicitly document its removal.

### Phase 2: Sub-Accounts and Agent Auth
1. Enforce agent account creation via `/auth/register/agent` only:
   - Block `role=agent` in `CreateUserRequest` or auto-enforce `isSystemAccount` + parent linking.
2. Add parent-password login for sub-accounts in `authenticate_user` (verify parent password when `parentUserId` exists).
3. Expand agent permissions to include nodes read/update and token management in `hydra-api/hydra/api/v1/services/auth.py`.
4. Add sub-account key management for parent users (list/revoke/create scoped to sub-accounts).
5. Align install flow with the new agent account model:
   - Use `/auth/register/agent` + `/auth/register/sub/{userId}` as needed.
   - Store the agent API key in the credential vault instead of a node API key.
6. Add indexes or query optimizations for `parentUserId` and `subAccounts.userId` if needed for scale.

## Plan Update Suggestions for Phases 3+

These are plan changes only (no code edits yet) to align the remaining phases with what Phase 0-2 now implies.

1. Phase 3 (Agent CLI Overhaul)
   - Explicitly incorporate the agent system account registration flow (register agent -> store API key -> node registration).
   - Add a decision point: continue supporting node API keys or migrate fully to agent user API keys.
   - Ensure CLI supports parent-password sub-account login if required.

2. Phase 4 (Install Script & Bundling)
   - Add a required step for agent account creation and API key storage.
   - Add `/agent/install?source=...&version=...` query support as the default usage in docs.
   - Clarify the bundle storage directory layout for local mode (base path vs bundles path).

3. Phase 5 (Docs & Testing)
   - Update docs to reflect new auth flow and endpoint paths (`/agent/*`, `/auth/subs` vs `/users/{userId}/subs`).
   - Add tests for storage backends (local + S3 bundle), validator patterns, and sub-account login behavior.
   - Add migration notes for users currently using node API keys if the plan shifts to agent API keys.

