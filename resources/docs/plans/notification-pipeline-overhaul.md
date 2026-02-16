# Fix Notification System — Full Pipeline Overhaul

## Context

The notification system has logical flaws across the entire pipeline — state transitions don't cascade properly, the bell dropdown shows stale notifications, there's no deletion capability, and the permission model prevents family/viewer users from managing their own notifications. This plan addresses the full pipeline holistically.

**Core principles:**
- Resolving = fully dismissing (auto-acknowledge + auto-read)
- The dropdown shows only what needs YOUR attention right now
- Every user can manage (delete) their own notifications
- The dashboard tells a clear story: what needs attention vs what's being handled

---

## Issues (13 total)

### A. State Transitions

| # | Issue | Severity | File |
|---|-------|----------|------|
| 1 | `resolve()` doesn't auto-acknowledge or auto-read | CRITICAL | actions.py:226-256 |
| 2 | Tier 3 (Warning) has no resolution path (`RESOLVE_MIN_TIER=4`) | HIGH | preferences.py |
| 3 | "Acknowledged" badge shows on resolved notifications | HIGH | notification-item.tsx:250, details-modal.tsx:104 |

### B. Bell Dropdown

| # | Issue | Severity | File |
|---|-------|----------|------|
| 4 | Dropdown shows ALL active notifications indefinitely | CRITICAL | notification-panel.tsx:55-58 |

### C. Dashboard

| # | Issue | Severity | File |
|---|-------|----------|------|
| 5 | No distinction between "needs attention" vs "in progress" | MEDIUM | stats-cards.tsx:279 |

### D. Deletion/Cleanup (Missing)

| # | Issue | Severity | File |
|---|-------|----------|------|
| 6 | No bulk delete API endpoint | HIGH | — |
| 7 | No delete button in UI (hook exists but unused) | HIGH | notifications.ts:171 |
| 8 | Delete is admin-only (`notifications:manage`) | HIGH | router.py:358 |
| 9 | No date range filter for cleanup | MEDIUM | — |

### E. Permission/Targeting

| # | Issue | Severity | File |
|---|-------|----------|------|
| 10 | Login notification missing `target_user_id` — family users miss it | HIGH | login.py:289-298 |
| 11 | Family not in tier 1 `DEFAULT_TARGET_ROLES` (safety net) | MEDIUM | models/notifications.py:224 |
| 12 | UI doesn't check user permissions for action buttons | MEDIUM | notification-item.tsx |

### F. Page UI

| # | Issue | Severity | File |
|---|-------|----------|------|
| 13 | "Acknowledge all" button shows on wrong tabs | LOW | index.tsx:187 |

---

## Implementation Checklist

### Part A: API Backend

- [ ] **A1.** Fix `resolve()` to cascade state — auto-acknowledge + auto-read (actions.py)
- [ ] **A2.** Lower `RESOLVE_MIN_TIER` to 3 (preferences.py)
- [ ] **A3.** Add `needsAttention` + `acknowledgedPending` to stats (query.py + models)
- [ ] **A4.** Add bulk delete endpoint + relax delete permissions (actions.py + router + models)
- [ ] **A5.** Fix login notification targeting — add `target_user_id` (login.py)
- [ ] **A6.** Add "family" to tier 1 default target roles (models/notifications.py)

### Part B: Web Frontend

- [ ] **B1.** Fix bell dropdown to show only unattended notifications (notification-panel.tsx)
- [ ] **B2.** Fix "Acknowledged" badge visibility (notification-item.tsx + details-modal.tsx)
- [ ] **B3.** Redesign dashboard notification card (stats-cards.tsx)
- [ ] **B4.** Add delete capabilities to notifications page (index.tsx)
- [ ] **B5.** Add delete button to notification items + modal (notification-item.tsx + details-modal.tsx)
- [ ] **B6.** Add role-aware action buttons (notification-item.tsx + details-modal.tsx + panel)
- [ ] **B7.** Add bulk delete hook (notifications.ts)
- [ ] **B8.** Update notification types (notification.ts)

### Part C: Verification

- [ ] Run API tests
- [ ] Playwright verification
