
> **Version:** 0.3.0  
> **Base URL:** `https://hydra.local/api/v1`  
> **Last Updated:** 2025-12-31

---

## Table of Contents

1. [[#Overview|Overview]]
2. [[#Authentication|Authentication]]
3. [[#Health & System|Health & System]]
4. [[#Users|Users]]
5. [[#Nodes|Nodes]]
6. [[#Profiles|Profiles]]
7. [[#Services|Services]]
8. [[#Groups|Groups]]
9. [[#Networks|Networks]]
10. [[#Topologies|Topologies]]
11. [[#Time Machine|Time Machine]]
12. [[#Commands|Commands]]
13. [[#Documentations|Documentations]]
14. [[#Home Assistant|Home Assistant]]
15. [[#Query & Analytics|Query & Analytics]]
16. [[#Error Codes|Error Codes]]
17. [[#Rate Limits|Rate Limits]]
18. [[#Appendices|Appendices]]

---

## Overview

### Base URL

All API endpoints are prefixed with `/api/v1`. The base URL depends on your deployment:

- Local development: `http://localhost:8080/api/v1`
- Production: `https://hydra.yourdomain.com/api/v1`

### Request Format

- All request bodies must be JSON with `Content-Type: application/json`
- Query parameters use standard URL encoding
- Dates use ISO 8601 format: `2025-12-16T10:00:00Z`

### Response Format

All responses follow this structure:

```json
// Success response
{
  "data": { ... },
  "meta": {
    "total": 100,
    "limit": 50,
    "offset": 0
  }
}

// Error response
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable message",
    "details": { ... }
  },
  "requestId": "req-abc123"
}
```

### Pagination

List endpoints support pagination via query parameters:

|Parameter|Type|Default|Description|
|---|---|---|---|
|`limit`|integer|50|Max results (1-200)|
|`offset`|integer|0|Skip N results|
|`sort`|string|varies|Sort field (prefix `-` for desc)|

---

## Authentication

All endpoints except `/health` and `/auth/register` require authentication via JWT bearer token or API key.

### Account Limits

| Role       | Maximum Accounts | Notes                                            | Permissions                                                                              |
| ---------- | ---------------- | ------------------------------------------------ | ---------------------------------------------------------------------------------------- |
| `admin`    | 2                | Full system access                               | `*:*`                                                                                    |
| `operator` | 10               | Infrastructure management                        | `nodes:*`, `services:*`, `groups:*`, `networks:*`, `topologies:read`, `commands:execute` |
| `viewer`   | Unlimited        | Read-only access                                 | `nodes:read`, `services:read`, `groups:read`, `networks:read`, `topologies:read`         |
| `family`   | Unlimited        | IoT/smart home controls                          | `iot:read`, `iot:control`, `ha:control`                                                  |
| `agent`    | Unlimited        | Node-specific, auto-created on node registration | `profiles:write` (own node), `commands:poll`                                             |

### Registration Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         USER REGISTRATION FLOW                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  FIRST USER (Bootstrap)                                                      │
│  ═══════════════════════                                                     │
│  ┌──────────┐     ┌──────────────┐     ┌─────────────┐                      │
│  │ New User │────▶│ POST /auth/  │────▶│ Auto-Admin  │  (No approval needed) │
│  │          │     │   register   │     │  Created    │                      │
│  └──────────┘     └──────────────┘     └─────────────┘                      │
│                                                                              │
│  SUBSEQUENT USERS (Two paths)                                                │
│  ════════════════════════════                                                │
│                                                                              │
│  Path A: With Registration Token                                             │
│  ┌──────────┐     ┌──────────────┐     ┌─────────────┐                      │
│  │ New User │────▶│ POST /auth/  │────▶│   User      │  (Instant activation) │
│  │ + token  │     │   register   │     │  Created    │                      │
│  └──────────┘     └──────────────┘     └─────────────┘                      │
│                                                                              │
│  Path B: Without Token (Approval Required)                                   │
│  ┌──────────┐     ┌──────────────┐     ┌─────────────┐     ┌─────────────┐  │
│  │ New User │────▶│ POST /auth/  │────▶│ users_      │────▶│ Admin       │  │
│  │          │     │   register   │     │ pending     │     │ Approval    │  │
│  └──────────┘     └──────────────┘     └─────────────┘     └──────┬──────┘  │
│                                                                    │         │
│                                            ┌─────────────┐         │         │
│                                            │   User      │◀────────┘         │
│                                            │  Created    │                   │
│                                            └─────────────┘                   │
└─────────────────────────────────────────────────────────────────────────────┘
```


### System Rules

1. **First Registration Bootstrap:** If no users exist in the system, the first registration MUST be an `admin` account and requires no approval or token
2. **Username Uniqueness:** Usernames must be unique across both `users` and `users_pending` collections
3. **Role Limits Enforced:** Registration fails if role limits are exceeded


### Headers

```
Authorization: Bearer <access_token>
```

or

```
X-API-Key: <api_key>
```

---

### POST /auth/register

Register a new user account. Open endpoint - no authentication required.

**Request Body:**

```json
{
  "username": "newuser",
  "email": "newuser@example.com",
  "password": "securepassword123",
  "role": "operator",
  "registrationToken": "reg_a1b2c3d4e5f6..."
}
```

| Field               | Type   | Required | Description                                                                |
| ------------------- | ------ | -------- | -------------------------------------------------------------------------- |
| `username`          | string | Yes      | Unique username (3-32 chars, lowercase alphanumeric, hyphens, underscores) |
| `email`             | string | Yes      | Valid email address                                                        |
| `password`          | string | Yes      | Password (min 8 chars)                                                     |
| `role`              | enum   | Yes      | `admin`, `operator`, `viewer`, or `family`                                 |
| `registrationToken` | string | No       | Admin-provided token for instant activation                                |

**Response (With Valid Token):** `201 Created`

```json
{
  "userId": "user_abc123",
  "username": "newuser",
  "email": "newuser@example.com",
  "role": "operator",
  "status": "active",
  "createdAt": "2025-12-16T10:00:00Z"
}
```

**Response (Without Token - Pending Approval):** `202 Accepted`

```json
{
  "userId": "user_pending_xyz789",
  "username": "newuser",
  "email": "newuser@example.com",
  "role": "operator",
  "status": "pending_approval",
  "message": "Registration submitted. Awaiting admin approval.",
  "createdAt": "2025-12-16T10:00:00Z"
}
```

**Response (First User Bootstrap):** `201 Created`

```json
{
  "userId": "user_admin001",
  "username": "admin",
  "email": "admin@example.com",
  "role": "admin",
  "status": "active",
  "isBootstrap": true,
  "createdAt": "2025-12-16T10:00:00Z"
}
```

**Error Responses:**

|HTTP|Code|Condition|
|---|---|---|
|400|`BOOTSTRAP_REQUIRES_ADMIN`|First user must register as admin|
|409|`USERNAME_ALREADY_EXISTS`|Username taken (in users or pending)|
|409|`EMAIL_ALREADY_EXISTS`|Email already registered|
|422|`ROLE_LIMIT_EXCEEDED`|Max accounts for role reached|
|401|`AUTH_REGISTRATION_TOKEN_INVALID`|Token invalid|
|401|`AUTH_REGISTRATION_TOKEN_EXPIRED`|Token expired|

---

### POST /auth/login

Authenticate a user and obtain tokens.

**Request Body:**

```json
{
  "username": "admin",
  "password": "password123"
}
```

**Response:** `200 OK`

```json
{
  "accessToken": "eyJhbGciOiJIUzI1NiIs...",
  "refreshToken": "dGhpcyBpcyBhIHJlZnJlc2g...",
  "expiresIn": 3600,
  "tokenType": "Bearer",
  "user": {
    "userId": "user_abc123",
    "username": "admin",
    "email": "admin@example.com",
    "role": "admin",
    "temporaryRoles": []
  }
}
```

---


### GET /auth/approvals

List pending user registrations awaiting approval.

**Query Parameters:**

|Parameter|Type|Description|
|---|---|---|
|`role`|enum|Filter by requested role|
|`limit`|integer|Max results (default: 50)|
|`offset`|integer|Pagination offset|

**Response:** `200 OK`

```json
{
  "pendingUsers": [
    {
      "userId": "user_pending_xyz789",
      "username": "newoperator",
      "email": "newoperator@example.com",
      "role": "operator",
      "requestedAt": "2025-12-16T09:00:00Z"
    },
    {
      "userId": "user_pending_abc456",
      "username": "familymember",
      "email": "family@example.com",
      "role": "family",
      "requestedAt": "2025-12-16T08:30:00Z"
    }
  ],
  "total": 2,
  "limit": 50,
  "offset": 0
}
```

**Required Permission:** `admin` role only

---



### POST /auth/approvals

Approve a pending user registration.

**Request Body:**

```json
{
  "userId": "user_pending_xyz789"
}
```

or

```json
{
  "username": "newoperator"
}
```

|Field|Type|Required|Description|
|---|---|---|---|
|`userId`|string|One of|Pending user ID|
|`username`|string|One of|Pending username (alternative to ID)|

**Response:** `200 OK`

```json
{
  "userId": "user_xyz789",
  "username": "newoperator",
  "email": "newoperator@example.com",
  "role": "operator",
  "status": "active",
  "approvedBy": "user_admin001",
  "approvedAt": "2025-12-16T10:30:00Z"
}
```

**Required Permission:** `admin` role only

---



### DELETE /auth/approvals/{userId}

Reject and delete a pending user registration.

**Response:** `200 OK`

```json
{
  "userId": "user_pending_xyz789",
  "rejected": true,
  "rejectedBy": "user_admin001",
  "rejectedAt": "2025-12-16T10:30:00Z"
}
```

**Required Permission:** `admin` role only

---



### POST /auth/refresh

Refresh an access token.

**Request Body:**

```json
{
  "refreshToken": "dGhpcyBpcyBhIHJlZnJlc2g..."
}
```

**Response:** `200 OK`

```json
{
  "accessToken": "eyJhbGciOiJIUzI1NiIs...",
  "expiresIn": 3600,
  "tokenType": "Bearer"
}
```

---



### POST /auth/tokens

Create a new registration token (admin only).

**Request Body:**

```json
{
  "description": "Token for new team member",
  "expiresIn": 604800,
  "maxUses": 1,
  "allowedRoles": ["operator", "viewer"]
}
```

|Field|Type|Required|Description|
|---|---|---|---|
|`description`|string|No|Token description|
|`expiresIn`|integer|No|Expiry in seconds (default: 604800 = 7 days)|
|`maxUses`|integer|No|Max uses (null = unlimited)|
|`allowedRoles`|string[]|No|Restrict token to specific roles (null = any)|

**Response:** `201 Created`

```json
{
  "token": "reg_a1b2c3d4e5f6...",
  "expiresAt": "2025-12-23T00:00:00Z",
  "maxUses": 1,
  "usedCount": 0,
  "allowedRoles": ["operator", "viewer"],
  "createdBy": "user_admin001"
}
```

**Required Permission:** `admin` role only

---


### GET /auth/me

Get current authenticated user/agent info.

**Response:** `200 OK`

```json
{
  "type": "user",
  "userId": "user_abc123",
  "username": "admin",
  "email": "admin@example.com",
  "role": "admin",
  "permissions": ["*:*"]
}
```

---


### POST /auth/apikeys

Create an API key for automation. API Key access control is determined by roles and/or permissions. Roles defined must not include any role higher than current user role, same with permissions.

**Request Body:**

```json
{
  "name": "CI/CD Pipeline",
  "roles": ["agent"],
  "permissions": ["nodes:read", "profiles:read"],
  "expiresAt": "2026-12-31T23:59:59Z"
}
```

**Response:** `201 Created`

```json
{
  "keyId": "key_abc123",
  "key": "hyk_live_abc123...",
  "name": "CI/CD Pipeline",
  "roles": ["agent"],
  "permissions": ["nodes:read", "profiles:read"],
  "expiresAt": "2026-12-31T23:59:59Z",
  "createdBy": "user_abc123",
  "createdAt": "2025-12-16T10:00:00Z"
}
```

**Note:** The `key` value is only returned once at creation time. Only registered users can create API keys.

**Required Permission:** `tokens:create`

---


### GET /auth/apikeys

List API keys owned by the current user.

**Response:** `200 OK`

```json
{
  "apiKeys": [
    {
      "keyId": "key_abc123",
      "name": "CI/CD Pipeline",
      "permissions": ["nodes:read", "profiles:read"],
      "expiresAt": "2026-12-31T23:59:59Z",
      "lastUsedAt": "2025-12-16T09:00:00Z",
      "createdAt": "2025-12-16T10:00:00Z"
    }
  ],
  "total": 1
}
```

**Required Permission:** Authenticated user

---


### DELETE /auth/apikeys/{keyId}

Revoke an API key.

**Response:** `200 OK`

```json
{
  "keyId": "key_abc123",
  "revoked": true,
  "revokedAt": "2025-12-16T10:00:00Z"
}
```

**Required Permission:** Key owner or `admin`

---


## Health & System

### GET /health

Health check endpoint (no authentication required).

**Response:** `200 OK`

```json
{
  "status": "healthy",
  "version": "0.3.0",
  "timestamp": "2025-12-16T10:00:00Z",
  "checks": {
    "database": "ok",
    "redis": "ok",
    "disk": "ok"
  },
  "uptime_seconds": 86400
}
```

|Status|HTTP Code|
|---|---|
|Healthy|200|
|Degraded|200 (with failing checks)|
|Unhealthy|503|

---

### GET /info

Service information and statistics.

**Response:** `200 OK`

```json
{
  "name": "hydra-api",
  "version": "0.3.0",
  "apiVersion": "v1",
  "stats": {
    "nodes": { "total": 15, "active": 14, "byClass": { "compute": 10, "networking": 2, "iot": 3 } },
    "services": { "total": 47, "running": 42 },
    "networks": { "total": 3 },
    "groups": { "total": 5 },
    "profiles": { "total": 150 },
    "users": { "total": 5 }
  },
  "features": {
    "topologyGeneration": true,
    "timeMachine": true,
    "autoNetworkCreation": true,
    "rbac": true,
    "writeOperations": false,
    "homeAssistant": true
  }
}
```

---

## Users

### GET /users

List all users.

**Query Parameters:**

|Parameter|Type|Description|
|---|---|---|
|`role`|enum|Filter by role|
|`status`|enum|Filter by status|
|`search`|string|Search username/email|
|`limit`|integer|Max results|
|`offset`|integer|Pagination offset|

**Response:** `200 OK`

```json
{
  "users": [
    {
      "userId": "user_abc123",
      "username": "admin",
      "email": "admin@example.com",
      "role": "admin",
      "status": "active",
      "lastLogin": "2025-12-16T05:00:00Z",
      "createdAt": "2025-12-01T00:00:00Z"
    }
  ],
  "total": 5,
  "limit": 50,
  "offset": 0
}
```

**Required Permission:** `users:read`

---

### POST /users

Create a new user.

**Request Body:**

```json
{
  "username": "operator1",
  "email": "operator1@example.com",
  "password": "securepassword123",
  "role": "operator",
  "permissions": [],
  "preferences": {
    "dashboardType": "admin",
    "theme": "dark"
  }
}
```

**Response:** `201 Created`

```json
{
  "userId": "user_def456",
  "username": "operator1",
  "email": "operator1@example.com",
  "role": "operator",
  "status": "active",
  "createdAt": "2025-12-16T10:00:00Z"
}
```

**Required Permission:** `users:create`

---

### GET /users/{userId}

Get user details.

**Response:** `200 OK`

```json
{
  "userId": "user_abc123",
  "username": "admin",
  "email": "admin@example.com",
  "role": "admin",
  "permissions": [],
  "resourcePermissions": [],
  "preferences": {
    "dashboardType": "admin",
    "theme": "dark",
    "notifications": {
      "email": true,
      "push": true
    }
  },
  "status": "active",
  "lastLogin": "2025-12-16T05:00:00Z",
  "createdAt": "2025-12-01T00:00:00Z",
  "updatedAt": "2025-12-16T10:00:00Z"
}
```

**Required Permission:** `users:read` or own user

---

### PATCH /users/{userId}

Update user details.

**Request Body:**

```json
{
  "email": "newemail@example.com",
  "role": "viewer",
  "permissions": ["nodes:read"],
  "status": "active"
}
```

**Response:** `200 OK`

```json
{
  "userId": "user_abc123",
  "updatedAt": "2025-12-16T10:00:00Z"
}
```

**Required Permission:** `users:update` or own user (limited fields)

---

### DELETE /users/{userId}

Delete a user.

**Response:** `200 OK`

```json
{
  "userId": "user_abc123",
  "deleted": true
}
```

**Required Permission:** `users:delete`

---

### POST /users/{userId}/roles/elevate

Permanently elevate a user's role (admin only).

**Request Body:**

```json
{
  "newRole": "operator"
}
```

**Response:** `200 OK`

```json
{
  "userId": "user_xyz789",
  "previousRole": "viewer",
  "newRole": "operator",
  "elevatedBy": "user_admin001",
  "elevatedAt": "2025-12-16T10:00:00Z"
}
```

**Required Permission:** `admin` role only

**Notes:**

- Cannot elevate to `admin` if 2 admins already exist
- Cannot elevate to `operator` if 10 operators already exist
- `agent` role cannot be elevated (system-managed)

---

### POST /users/{userId}/roles/grant-temporary

Grant temporary additional role to a user.

**Request Body:**

```json
{
  "role": "operator",
  "expiresAt": "2025-12-17T10:00:00Z",
  "reason": "Emergency maintenance access"
}
```

|Field|Type|Required|Description|
|---|---|---|---|
|`role`|enum|Yes|Role to grant temporarily|
|`expiresAt`|datetime|Yes|When the temporary role expires|
|`reason`|string|No|Audit reason for the grant|

**Response:** `200 OK`

```json
{
  "userId": "user_xyz789",
  "baseRole": "viewer",
  "temporaryRoles": [
    {
      "role": "operator",
      "expiresAt": "2025-12-17T10:00:00Z",
      "grantedBy": "user_admin001",
      "grantedAt": "2025-12-16T10:00:00Z",
      "reason": "Emergency maintenance access"
    }
  ]
}
```

**Required Permission:** `admin` role only

---

### DELETE /users/{userId}/roles/temporary/{role}

Revoke a temporary role grant early.

**Response:** `200 OK`

```json
{
  "userId": "user_xyz789",
  "revokedRole": "operator",
  "revokedBy": "user_admin001",
  "revokedAt": "2025-12-16T11:00:00Z"
}
```

**Required Permission:** `admin` role only

---

## Nodes

### POST /node/register

Register a new node. Requires authentication as `admin` or `operator` user.

**Use Cases:**

- Agent installation script calls this endpoint with user credentials
- Manual registration for node types that don't run agents (IoT, networking)

**Headers:**

```
Authorization: Bearer <user_access_token>
Content-Type: application/json
```

**Request Body:**

```json
{
  "nodeId": "proxmox-01",
  "class": "compute",
  "type": "physical",
  "kind": "bare-metal",
  "displayName": "Proxmox Host 01",
  "description": "Primary hypervisor",
  "tags": ["production", "hypervisor"],
  "parentNodeId": null,
  "location": {
    "site": "home",
    "rack": "main",
    "position": 1
  }
}
```

|Field|Type|Required|Description|
|---|---|---|---|
|`nodeId`|string|Yes|Unique identifier (3-64 chars, lowercase alphanumeric, hyphens, dots)|
|`class`|enum|Yes|`compute`, `networking`, `iot`|
|`type`|enum|Yes|`physical`, `logical`|
|`kind`|enum|No|Node subtype (see schema)|
|`displayName`|string|Yes|Human-readable name (max 128 chars)|
|`description`|string|No|Description (max 1024 chars)|
|`tags`|string[]|No|Tags for categorization|
|`parentNodeId`|string|No|Parent node ID (for logical nodes)|
|`location`|object|No|Physical location metadata|

**Response:** `201 Created`

```json
{
  "nodeId": "proxmox-01",
  "apiKey": "hyk_node_abc123def456...",
  "apiKeyId": "key_node_abc123",
  "registeredBy": "user_abc123",
  "registeredAt": "2025-12-16T10:00:00Z",
  "status": "active"
}
```

**Node API Key Details:**

- The `apiKey` is only returned once at registration
- Node uses this API key for all subsequent API interactions via the agent
- API key has `agent` role permissions scoped to this node only
- API key can be refreshed via `POST /node/{nodeId}/apikey/refresh`

**Required Permission:** `admin` or `operator` role

---

### POST /node/{nodeId}/apikey/refresh

Refresh the API key for a registered node. Can be called by the node itself (using current API key) or by an admin/operator user.

**Response:** `200 OK`

```json
{
  "nodeId": "proxmox-01",
  "apiKeyId": "key_node_xyz789",
  "apiKey": "hyk_node_newkey789...",
  "previousKeyRevoked": true,
  "refreshedAt": "2025-12-16T10:00:00Z"
}
```

**Note:** The `apiKey` value is only returned once. Previous API key is immediately revoked.

**Required Permission:** Node's own API key, `admin`, or `operator`

---

### GET /nodes

List all registered nodes.

**Query Parameters:**

|Parameter|Type|Description|
|---|---|---|
|`class`|enum|Filter by class: `compute`, `networking`, `iot`|
|`type`|enum|Filter by type: `physical`, `logical`|
|`kind`|enum|Filter by kind|
|`status`|enum|Filter by status: `active`, `inactive`, `archived`, `pending`|
|`tags`|string|Comma-separated tags (AND logic)|
|`networkId`|string|Filter by network membership|
|`parentNodeId`|string|Filter by parent node|
|`search`|string|Text search on displayName/description|
|`limit`|integer|Max results (default: 50, max: 200)|
|`offset`|integer|Pagination offset|
|`sort`|string|Sort field (prefix `-` for desc)|

**Response:** `200 OK`

```json
{
  "nodes": [
    {
      "nodeId": "proxmox-01",
      "class": "compute",
      "type": "physical",
      "kind": "bare-metal",
      "displayName": "Proxmox Host 01",
      "status": "active",
      "tags": ["production", "hypervisor"],
      "networkIds": ["homenet-lan"],
      "lastProfileAt": "2025-12-16T06:00:00Z"
    }
  ],
  "total": 15,
  "limit": 50,
  "offset": 0
}
```

**Required Permission:** `nodes:read`

---

### GET /nodes/{nodeId}

Get detailed information for a specific node.

**Query Parameters:**

|Parameter|Type|Description|
|---|---|---|
|`includeChildren`|boolean|Include child nodes (default: true)|
|`includeServices`|boolean|Include services (default: true)|
|`includeLatestProfile`|boolean|Include latest profile summary (default: false)|

**Response:** `200 OK`

```json
{
  "nodeId": "proxmox-01",
  "class": "compute",
  "type": "physical",
  "kind": "bare-metal",
  "displayName": "Proxmox Host 01",
  "description": "Primary hypervisor running LXCs and VMs",
  "tags": ["production", "hypervisor"],
  "parentNodeId": null,
  "networkIds": ["homenet-lan"],
  "location": {
    "site": "home",
    "rack": "main",
    "position": 1
  },
  "registeredAt": "2025-12-01T10:30:00Z",
  "lastUpdated": "2025-12-16T08:15:00Z",
  "lastProfileAt": "2025-12-16T06:00:00Z",
  "status": "active",
  "children": [
    {
      "nodeId": "docker-host-01",
      "class": "compute",
      "type": "logical",
      "kind": "lxc",
      "displayName": "Docker Host LXC",
      "status": "active"
    }
  ],
  "services": [
    {
      "serviceId": "svc::systemd::pveproxy",
      "name": "pveproxy",
      "status": "running"
    }
  ]
}
```

**Required Permission:** `nodes:read`

---

### PATCH /nodes/{nodeId}

Update node metadata.

**Request Body:**

```json
{
  "displayName": "Proxmox Host 01 (Updated)",
  "description": "Primary hypervisor - 128GB RAM",
  "tags": ["production", "hypervisor", "upgraded"],
  "location": {
    "site": "home",
    "rack": "main",
    "position": 2
  },
  "status": "active"
}
```

**Response:** `200 OK`

```json
{
  "nodeId": "proxmox-01",
  "displayName": "Proxmox Host 01 (Updated)",
  "lastUpdated": "2025-12-16T10:00:00Z"
}
```

**Required Permission:** `nodes:update`

---

### DELETE /nodes/{nodeId}

Archive a node (soft delete).

**Query Parameters:**

|Parameter|Type|Description|
|---|---|---|
|`cascade`|boolean|Also archive child nodes (default: false)|

**Response:** `200 OK`

```json
{
  "nodeId": "proxmox-01",
  "status": "archived",
  "archivedAt": "2025-12-16T10:00:00Z",
  "childrenArchived": 0
}
```

**Required Permission:** `nodes:delete`

---

## Profiles

### POST /profiles

Submit a new profile for a node.

**Request Body:**

```json
{
  "nodeId": "proxmox-01",
  "collectedAt": "2025-12-16T06:00:00Z",
  "agentVersion": "0.1.0",
  "collectionLevel": "neutral",
  "hardware": { "..." },
  "network": { "..." },
  "storage": { "..." },
  "software": { "..." },
  "virtualization": { "..." },
  "users": { "..." },
  "configs": { "..." }
}
```

See Profile Schema sections in Technical Documentation for full field details.

**Response:** `201 Created`

```json
{
  "profileId": "prof-proxmox-01-1703145600",
  "nodeId": "proxmox-01",
  "version": "E0-0.0.1.4",
  "previousVersion": "E0-0.0.1.3",
  "submittedAt": "2025-12-16T06:00:02Z",
  "changes": {
    "sectionsChanged": ["software.services", "users.accounts"],
    "changeLevel": "minor",
    "diffPercentage": 2.5,
    "servicesDiscovered": 3,
    "networksCreated": 0
  }
}
```

**Required Permission:** `profiles:write` (agents only submit own node)

---

### GET /profiles

Query profiles across all nodes.

**Query Parameters:**

|Parameter|Type|Description|
|---|---|---|
|`nodeId`|string|Filter by node|
|`since`|datetime|Profiles after timestamp|
|`until`|datetime|Profiles before timestamp|
|`latest`|boolean|Only latest per node|
|`minVersion`|string|Minimum version|
|`limit`|integer|Max results (default: 50)|
|`offset`|integer|Pagination offset|

**Response:** `200 OK`

```json
{
  "profiles": [
    {
      "profileId": "prof-proxmox-01-1703145600",
      "nodeId": "proxmox-01",
      "version": "E0-0.0.1.4",
      "collectedAt": "2025-12-16T06:00:00Z",
      "submittedAt": "2025-12-16T06:00:02Z",
      "collectionLevel": "neutral"
    }
  ],
  "total": 150,
  "limit": 50,
  "offset": 0
}
```

**Required Permission:** `profiles:read`

---

### GET /profiles/{profileId}

Get a specific profile by ID.

**Query Parameters:**

|Parameter|Type|Description|
|---|---|---|
|`sections`|string|Comma-separated sections to include|

**Response:** `200 OK`

```json
{
  "profileId": "prof-proxmox-01-1703145600",
  "nodeId": "proxmox-01",
  "version": "E0-0.0.1.4",
  "collectedAt": "2025-12-16T06:00:00Z",
  "submittedAt": "2025-12-16T06:00:02Z",
  "agentVersion": "0.1.0",
  "collectionLevel": "neutral",
  "serviceIds": ["svc::systemd::pveproxy"],
  "hardware": { "..." },
  "network": { "..." },
  "storage": { "..." },
  "software": { "..." }
}
```

**Required Permission:** `profiles:read`

---

### GET /nodes/{nodeId}/profiles

Get all profiles for a node.

**Query Parameters:**

|Parameter|Type|Description|
|---|---|---|
|`since`|datetime|Profiles after timestamp|
|`until`|datetime|Profiles before timestamp|
|`limit`|integer|Max results (default: 20)|

**Response:** `200 OK`

```json
{
  "nodeId": "proxmox-01",
  "profiles": [
    {
      "profileId": "prof-proxmox-01-1703145600",
      "version": "E0-0.0.1.4",
      "submittedAt": "2025-12-16T06:00:02Z"
    },
    {
      "profileId": "prof-proxmox-01-1703059200",
      "version": "E0-0.0.1.3",
      "submittedAt": "2025-12-15T06:00:02Z"
    }
  ],
  "total": 45
}
```

**Required Permission:** `profiles:read`

---

### GET /nodes/{nodeId}/profiles/latest

Get the latest profile for a node.

**Query Parameters:**

|Parameter|Type|Description|
|---|---|---|
|`sections`|string|Comma-separated sections to include|

**Response:** `200 OK`

```json
{
  "profileId": "prof-proxmox-01-1703145600",
  "nodeId": "proxmox-01",
  "version": "E0-0.0.1.4",
  "collectedAt": "2025-12-16T06:00:00Z",
  "hardware": { "..." },
  "network": { "..." }
}
```

**Required Permission:** `profiles:read`

---

### GET /nodes/{nodeId}/profiles/diff

Compare two profiles for a node.

**Query Parameters:**

|Parameter|Type|Description|
|---|---|---|
|`from`|string|From version or profileId|
|`to`|string|To version or profileId (default: latest)|

**Response:** `200 OK`

```json
{
  "nodeId": "proxmox-01",
  "from": {
    "profileId": "prof-proxmox-01-1703059200",
    "version": "E0-0.0.1.3",
    "submittedAt": "2025-12-15T06:00:02Z"
  },
  "to": {
    "profileId": "prof-proxmox-01-1703145600",
    "version": "E0-0.0.1.4",
    "submittedAt": "2025-12-16T06:00:02Z"
  },
  "diffPercentage": 2.5,
  "changes": {
    "sectionsChanged": ["software.services", "users.accounts"],
    "changeLevel": "minor",
    "details": {
      "software.services": {
        "added": ["svc::systemd::nginx"],
        "removed": [],
        "modified": []
      },
      "users.accounts": {
        "added": [],
        "removed": [],
        "modified": ["admin"]
      }
    }
  }
}
```

**Required Permission:** `profiles:read`

---

## Services

### GET /services

List all services.

**Query Parameters:**

|Parameter|Type|Description|
|---|---|---|
|`nodeId`|string|Filter by node|
|`runtime`|enum|Filter by runtime|
|`status`|enum|Filter by status|
|`name`|string|Filter by service name (partial match)|
|`tags`|string|Comma-separated tags|
|`port`|integer|Filter by exposed port|
|`search`|string|Text search|
|`limit`|integer|Max results (default: 50)|
|`offset`|integer|Pagination offset|
|`sort`|string|Sort field|

**Response:** `200 OK`

```json
{
  "services": [
    {
      "serviceId": "svc::docker::mongodb",
      "name": "mongodb",
      "displayName": "MongoDB Database",
      "runtime": "docker",
      "status": "running",
      "version": "7.0.2",
      "nodeId": "docker-host-01",
      "exposure": {
        "ports": [{ "port": 27017, "protocol": "tcp" }]
      },
      "lastSeen": "2025-12-16T06:00:00Z"
    }
  ],
  "total": 47,
  "limit": 50,
  "offset": 0
}
```

**Required Permission:** `services:read`

---

### GET /services/{serviceId}

Get detailed information for a service.

**Response:** `200 OK`

```json
{
  "serviceId": "svc::docker::mongodb",
  "runtime": "docker",
  "name": "mongodb",
  "displayName": "MongoDB Database",
  "description": "Primary MongoDB instance",
  "status": "running",
  "version": "7.0.2",
  "image": "mongo:7.0.2",
  "profileId": "prof-docker-host-01-1703145600",
  "nodeId": "docker-host-01",
  "exposure": {
    "ports": [
      { "port": 27017, "protocol": "tcp", "hostPort": 27017 }
    ],
    "endpoints": [
      { "url": "mongodb://docker-host-01:27017", "type": "tcp", "internal": true }
    ]
  },
  "resources": {
    "memoryLimitBytes": 4294967296
  },
  "attachments": {
    "volumes": [
      { "name": "mongo-data", "source": "/data/mongodb", "destination": "/data/db", "mode": "rw" }
    ],
    "networks": ["backend"]
  },
  "origin": {
    "nativeId": "a1b2c3d4e5f6",
    "discoveredBy": "agent",
    "collectedAt": "2025-12-14T10:00:00Z"
  },
  "health": {
    "status": "healthy",
    "lastCheck": "2025-12-16T06:00:00Z"
  },
  "tags": ["database", "production"],
  "firstSeen": "2025-12-14T10:00:00Z",
  "lastSeen": "2025-12-16T06:00:00Z"
}
```

**Required Permission:** `services:read`

---

### PATCH /services/{serviceId}

Update service metadata (user-managed fields only).

**Request Body:**

```json
{
  "displayName": "MongoDB Database (Primary)",
  "description": "Primary MongoDB instance for production",
  "tags": ["database", "production", "critical"]
}
```

**Response:** `200 OK`

```json
{
  "serviceId": "svc::docker::mongodb",
  "displayName": "MongoDB Database (Primary)",
  "updatedAt": "2025-12-16T10:00:00Z"
}
```

**Required Permission:** `services:update`

---

### DELETE /services/{serviceId}

Archive a service (removes from active tracking).

**Response:** `200 OK`

```json
{
  "serviceId": "svc::docker::mongodb",
  "archived": true,
  "archivedAt": "2025-12-16T10:00:00Z"
}
```

**Required Permission:** `services:delete`

---

### POST /services/{serviceId}/control

Control a service (start, stop, restart).

**Request Body:**

```json
{
  "action": "restart",
  "force": false,
  "timeoutSeconds": 60
}
```

|Field|Type|Required|Description|
|---|---|---|---|
|`action`|enum|Yes|`start`, `stop`, `restart`, `reload`|
|`force`|boolean|No|Force action (default: false)|
|`timeoutSeconds`|integer|No|Timeout (default: 60)|

**Response:** `202 Accepted`

```json
{
  "commandId": "cmd-abc123",
  "serviceId": "svc::docker::mongodb",
  "action": "restart",
  "status": "queued",
  "queuedAt": "2025-12-16T10:00:00Z"
}
```

**Required Permission:** `services:control`

---

### GET /nodes/{nodeId}/services

Get all services for a specific node.

**Query Parameters:**

|Parameter|Type|Description|
|---|---|---|
|`runtime`|enum|Filter by runtime|
|`status`|enum|Filter by status|

**Response:** `200 OK`

```json
{
  "nodeId": "docker-host-01",
  "services": [
    {
      "serviceId": "svc::docker::mongodb",
      "name": "mongodb",
      "status": "running",
      "runtime": "docker"
    },
    {
      "serviceId": "svc::docker::redis",
      "name": "redis",
      "status": "running",
      "runtime": "docker"
    }
  ],
  "total": 8
}
```

**Required Permission:** `services:read`

---

## Groups

### GET /groups

List all groups.

**Query Parameters:**

|Parameter|Type|Description|
|---|---|---|
|`types`|string|Comma-separated types: `node`, `service`|
|`tags`|string|Comma-separated tags|
|`parentGroupId`|string|Filter by parent group|
|`search`|string|Text search|
|`limit`|integer|Max results (default: 50)|
|`offset`|integer|Pagination offset|

**Response:** `200 OK`

```json
{
  "groups": [
    {
      "groupId": "production-servers",
      "name": "Production Servers",
      "description": "All production infrastructure",
      "types": ["node", "service"],
      "memberCount": {
        "nodes": 8,
        "services": 42,
        "lastComputed": "2025-12-16T00:00:00Z"
      },
      "tags": ["production"]
    }
  ],
  "total": 5,
  "limit": 50,
  "offset": 0
}
```

**Required Permission:** `groups:read`

---

### POST /groups

Create a new group.

**Request Body:**

```json
{
  "groupId": "database-servers",
  "name": "Database Servers",
  "description": "All nodes and services related to databases",
  "types": ["node", "service"],
  "selectors": {
    "tags": {
      "isAny": ["database", "db"]
    },
    "runtime": {
      "isAny": ["docker", "systemd"]
    }
  },
  "parentGroupIds": [],
  "tags": ["databases"]
}
```

**Selector Options:**

|Selector|Type|Logic|
|---|---|---|
|`id.isAll`|string[]|Explicit entity IDs|
|`network.isAny`|string[]|In any listed network|
|`status.isAny`|string[]|Has any listed status|
|`kind.isAny`|string[]|Node class matches|
|`tags.isAny`|string[]|Has any listed tag|
|`tags.isAll`|string[]|Has all listed tags|
|`runtime.isAny`|string[]|Service runtime matches|
|`location.site`|string|At site|
|`location.rack`|string|In rack|

**Response:** `201 Created`

```json
{
  "groupId": "database-servers",
  "name": "Database Servers",
  "createdAt": "2025-12-16T10:00:00Z"
}
```

**Required Permission:** `groups:create`

---

### GET /groups/{groupId}

Get group details.

**Query Parameters:**

|Parameter|Type|Description|
|---|---|---|
|`resolveMembers`|boolean|Include resolved members (default: false)|
|`memberLimit`|integer|Max members to return (default: 20)|

**Response:** `200 OK`

```json
{
  "groupId": "production-servers",
  "name": "Production Servers",
  "description": "All production infrastructure",
  "types": ["node", "service"],
  "selectors": {
    "tags": { "isAny": ["production", "prod"] }
  },
  "memberCount": {
    "nodes": 8,
    "services": 42,
    "lastComputed": "2025-12-16T00:00:00Z"
  },
  "members": {
    "nodes": [
      { "nodeId": "proxmox-01", "displayName": "Proxmox Host 01" }
    ],
    "services": [
      { "serviceId": "svc::docker::mongodb", "name": "mongodb" }
    ]
  },
  "tags": ["production"],
  "createdAt": "2025-12-10T00:00:00Z",
  "updatedAt": "2025-12-16T00:00:00Z"
}
```

**Required Permission:** `groups:read`

---

### PUT /groups/{groupId}

Update a group.

**Request Body:**

```json
{
  "name": "Production Servers (Updated)",
  "selectors": {
    "tags": { "isAny": ["production", "prod", "live"] }
  }
}
```

**Response:** `200 OK`

```json
{
  "groupId": "production-servers",
  "updatedAt": "2025-12-16T10:00:00Z"
}
```

**Required Permission:** `groups:update`

---

### DELETE /groups/{groupId}

Delete a group.

**Response:** `200 OK`

```json
{
  "groupId": "production-servers",
  "deleted": true
}
```

**Required Permission:** `groups:delete`

---

### GET /groups/{groupId}/members

Get resolved group members.

**Query Parameters:**

|Parameter|Type|Description|
|---|---|---|
|`type`|enum|Filter by type: `node`, `service`|
|`limit`|integer|Max results|
|`offset`|integer|Pagination offset|

**Response:** `200 OK`

```json
{
  "groupId": "production-servers",
  "members": {
    "nodes": [
      {
        "nodeId": "proxmox-01",
        "displayName": "Proxmox Host 01",
        "matchedSelectors": ["tags.isAny"]
      }
    ],
    "services": [
      {
        "serviceId": "svc::docker::mongodb",
        "name": "mongodb",
        "nodeId": "docker-host-01",
        "matchedSelectors": ["tags.isAny"]
      }
    ]
  },
  "total": { "nodes": 8, "services": 42 }
}
```

**Required Permission:** `groups:read`

---

### POST /groups/{groupId}/resolve

Force re-resolution of group membership.

**Response:** `200 OK`

```json
{
  "groupId": "production-servers",
  "memberCount": {
    "nodes": 8,
    "services": 43,
    "lastComputed": "2025-12-16T10:00:00Z"
  },
  "changes": {
    "nodesAdded": [],
    "nodesRemoved": [],
    "servicesAdded": ["svc::docker::new-service"],
    "servicesRemoved": []
  }
}
```

**Required Permission:** `groups:update`

---

## Networks

### GET /networks

List all networks.

**Query Parameters:**

|Parameter|Type|Description|
|---|---|---|
|`type`|enum|Filter by type|
|`parentNetworkId`|string|Filter by parent network|
|`routerNodeId`|string|Filter by router node|
|`cidr`|string|Filter by CIDR (exact or contains)|
|`tags`|string|Comma-separated tags|
|`search`|string|Text search|
|`limit`|integer|Max results (default: 50)|
|`offset`|integer|Pagination offset|

**Response:** `200 OK`

```json
{
  "networks": [
    {
      "networkId": "homenet-lan",
      "type": "physical",
      "name": "HomeNET LAN",
      "cidr": "192.168.0.0/24",
      "gatewayV4": "192.168.0.1",
      "routerNodeId": "opnsense-gw",
      "nodeCount": 15,
      "tags": ["primary"]
    }
  ],
  "total": 3,
  "limit": 50,
  "offset": 0
}
```

**Required Permission:** `networks:read`

---

### POST /networks

Create a new network (manual).

**Request Body:**

```json
{
  "networkId": "guest-vlan",
  "type": "vlan",
  "name": "Guest VLAN",
  "description": "Isolated guest network",
  "cidr": "192.168.20.0/24",
  "gatewayV4": "192.168.20.1",
  "vlanId": 20,
  "parentNetworkId": "homenet-lan",
  "routerNodeId": "opnsense-gw",
  "dhcp": {
    "enabled": true,
    "rangeStart": "192.168.20.100",
    "rangeEnd": "192.168.20.250"
  },
  "tags": ["guest", "isolated"]
}
```

**Response:** `201 Created`

```json
{
  "networkId": "guest-vlan",
  "name": "Guest VLAN",
  "createdAt": "2025-12-16T10:00:00Z"
}
```

**Required Permission:** `networks:create`

---

### GET /networks/{networkId}

Get network details.

**Query Parameters:**

|Parameter|Type|Description|
|---|---|---|
|`includeNodes`|boolean|Include nodes in network (default: false)|
|`includeSubnets`|boolean|Include child subnets (default: true)|

**Response:** `200 OK`

```json
{
  "networkId": "homenet-lan",
  "type": "physical",
  "name": "HomeNET LAN",
  "description": "Primary home network LAN segment",
  "cidr": "192.168.0.0/24",
  "gatewayV4": "192.168.0.1",
  "vlanId": null,
  "subnetIds": ["iot-vlan", "guest-vlan"],
  "parentNetworkId": null,
  "routerNodeId": "opnsense-gw",
  "dhcp": {
    "enabled": true,
    "rangeStart": "192.168.0.100",
    "rangeEnd": "192.168.0.250",
    "serverNodeId": "opnsense-gw"
  },
  "dns": {
    "servers": ["192.168.0.1", "1.1.1.1"],
    "domain": "home.lan"
  },
  "nodeCount": 15,
  "origin": {
    "createdBy": "auto",
    "sourceNodeId": "proxmox-01"
  },
  "nodes": [
    { "nodeId": "proxmox-01", "displayName": "Proxmox Host 01", "ipAddresses": ["192.168.0.10"] }
  ],
  "subnets": [
    { "networkId": "iot-vlan", "name": "IoT VLAN", "cidr": "192.168.10.0/24" }
  ],
  "tags": ["primary"],
  "createdAt": "2025-12-01T00:00:00Z",
  "updatedAt": "2025-12-16T00:00:00Z"
}
```

**Required Permission:** `networks:read`

---

### PUT /networks/{networkId}

Update a network.

**Request Body:**

```json
{
  "name": "HomeNET LAN (Updated)",
  "description": "Primary home network - 50 device capacity",
  "dhcp": {
    "rangeEnd": "192.168.0.200"
  }
}
```

**Response:** `200 OK`

```json
{
  "networkId": "homenet-lan",
  "updatedAt": "2025-12-16T10:00:00Z"
}
```

**Required Permission:** `networks:update`

---

### DELETE /networks/{networkId}

Delete a network.

**Query Parameters:**

|Parameter|Type|Description|
|---|---|---|
|`force`|boolean|Delete even if nodes reference it (default: false)|

**Response:** `200 OK`

```json
{
  "networkId": "guest-vlan",
  "deleted": true
}
```

**Required Permission:** `networks:delete`

---

### GET /networks/{networkId}/nodes

Get all nodes in a network.

**Response:** `200 OK`

```json
{
  "networkId": "homenet-lan",
  "nodes": [
    {
      "nodeId": "proxmox-01",
      "displayName": "Proxmox Host 01",
      "class": "compute",
      "ipAddresses": ["192.168.0.10"]
    },
    {
      "nodeId": "opnsense-gw",
      "displayName": "OPNsense Gateway",
      "class": "networking",
      "ipAddresses": ["192.168.0.1"]
    }
  ],
  "total": 15
}
```

**Required Permission:** `networks:read`

---

## Topologies

### GET /topologies

List topology snapshots.

**Query Parameters:**

|Parameter|Type|Description|
|---|---|---|
|`mode`|enum|Filter by mode: `network`, `infrastructure`|
|`since`|datetime|Topologies after timestamp|
|`until`|datetime|Topologies before timestamp|
|`limit`|integer|Max results (default: 20)|
|`offset`|integer|Pagination offset|

**Response:** `200 OK`

```json
{
  "topologies": [
    {
      "topologyId": "topo::network::20251216T120000Z",
      "mode": "network",
      "version": 42,
      "generatedAt": "2025-12-16T12:00:00Z",
      "stats": {
        "nodeCount": 18,
        "edgeCount": 24,
        "networkCount": 3
      }
    }
  ],
  "total": 84,
  "limit": 20,
  "offset": 0
}
```

**Required Permission:** `topologies:read`

---

### GET /topologies/latest

Get the latest topology snapshot.

**Query Parameters:**

|Parameter|Type|Description|
|---|---|---|
|`mode`|enum|Required: `network` or `infrastructure`|
|`includeGraph`|boolean|Include full graph data (default: true)|

**Response:** `200 OK`

```json
{
  "topologyId": "topo::network::20251216T120000Z",
  "mode": "network",
  "version": 42,
  "generatedAt": "2025-12-16T12:00:00Z",
  "validFrom": "2025-12-16T12:00:00Z",
  "validUntil": null,
  "graph": {
    "nodes": [
      {
        "id": "net::homenet-lan",
        "type": "network",
        "label": "HomeNET LAN (192.168.0.0/24)",
        "data": { "entityId": "homenet-lan", "cidr": "192.168.0.0/24" },
        "position": { "x": 400, "y": 100 }
      },
      {
        "id": "node::proxmox-01",
        "type": "compute-physical",
        "label": "Proxmox Host 01",
        "data": { "entityId": "proxmox-01", "status": "active" },
        "position": { "x": 200, "y": 300 }
      }
    ],
    "edges": [
      {
        "id": "edge::proxmox-01::homenet-lan",
        "source": "node::proxmox-01",
        "target": "net::homenet-lan",
        "type": "network-connection"
      }
    ]
  },
  "stats": {
    "nodeCount": 18,
    "edgeCount": 24,
    "computeTime": 245
  }
}
```

**Required Permission:** `topologies:read`

---

### GET /topologies/{topologyId}

Get a specific topology snapshot.

**Response:** Same structure as `/topologies/latest`.

**Required Permission:** `topologies:read`

---

### POST /topologies/generate

Trigger topology generation.

**Request Body:**

```json
{
  "mode": "network",
  "scope": {
    "networkIds": ["homenet-lan"]
  }
}
```

|Field|Type|Required|Description|
|---|---|---|---|
|`mode`|enum|Yes|`network` or `infrastructure`|
|`scope`|object|No|Limit scope (null = all)|
|`scope.networkIds`|string[]|No|Filter to networks|
|`scope.groupIds`|string[]|No|Filter to groups|
|`scope.nodeIds`|string[]|No|Filter to nodes|

**Response:** `202 Accepted`

```json
{
  "message": "Topology generation started",
  "mode": "network",
  "jobId": "job-abc123"
}
```

**Required Permission:** `topologies:create`

---

### GET /topologies/diff

Compare two topology snapshots.

**Query Parameters:**

|Parameter|Type|Description|
|---|---|---|
|`from`|string|From topologyId or timestamp|
|`to`|string|To topologyId or timestamp (default: latest)|
|`mode`|enum|Required if using timestamps|

**Response:** `200 OK`

```json
{
  "from": {
    "topologyId": "topo::network::20251215T120000Z",
    "generatedAt": "2025-12-15T12:00:00Z"
  },
  "to": {
    "topologyId": "topo::network::20251216T120000Z",
    "generatedAt": "2025-12-16T12:00:00Z"
  },
  "diff": {
    "nodesAdded": [
      { "id": "node::new-server", "type": "compute-physical", "label": "New Server" }
    ],
    "nodesRemoved": [],
    "nodesModified": [
      { "id": "node::proxmox-01", "changes": ["data.serviceCount"] }
    ],
    "edgesAdded": [
      { "id": "edge::new-server::homenet-lan", "type": "network-connection" }
    ],
    "edgesRemoved": []
  },
  "summary": {
    "totalChanges": 3,
    "nodesAdded": 1,
    "nodesRemoved": 0,
    "nodesModified": 1,
    "edgesAdded": 1,
    "edgesRemoved": 0
  }
}
```

**Required Permission:** `topologies:read`

---

## Time Machine

### GET /timemachine/node/{nodeId}

Get node state at a specific point in time.

**Query Parameters:**

|Parameter|Type|Description|
|---|---|---|
|`timestamp`|datetime|Required: Point in time|
|`sections`|string|Comma-separated profile sections|

**Response:** `200 OK`

```json
{
  "nodeId": "proxmox-01",
  "timestamp": "2025-12-15T12:00:00Z",
  "state": {
    "node": {
      "nodeId": "proxmox-01",
      "displayName": "Proxmox Host 01",
      "status": "active"
    },
    "profile": {
      "profileId": "prof-proxmox-01-1703059200",
      "version": "E0-0.0.1.3",
      "submittedAt": "2025-12-15T06:00:02Z",
      "hardware": { "..." },
      "network": { "..." }
    },
    "services": [
      {
        "serviceId": "svc::systemd::pveproxy",
        "status": "running"
      }
    ]
  },
  "closestSnapshot": {
    "profileAt": "2025-12-15T06:00:02Z",
    "deltaMinutes": 360
  }
}
```

**Required Permission:** `nodes:read`, `profiles:read`

---

### GET /timemachine/topology

Get topology at a specific point in time.

**Query Parameters:**

|Parameter|Type|Description|
|---|---|---|
|`mode`|enum|Required: `network` or `infrastructure`|
|`timestamp`|datetime|Required: Point in time|

**Response:** Returns topology snapshot valid at the specified timestamp (same structure as `/topologies/{topologyId}`).

**Required Permission:** `topologies:read`

---

### GET /timemachine/timeline

Get timeline events for Time Machine visualization.

**Query Parameters:**

|Parameter|Type|Description|
|---|---|---|
|`since`|datetime|Start of timeline|
|`until`|datetime|End of timeline|
|`nodeId`|string|Filter to specific node|
|`types`|string|Comma-separated event types|
|`limit`|integer|Max events (default: 100)|

**Response:** `200 OK`

```json
{
  "timeline": {
    "since": "2025-12-10T00:00:00Z",
    "until": "2025-12-16T12:00:00Z"
  },
  "events": [
    {
      "timestamp": "2025-12-16T12:00:00Z",
      "type": "topology",
      "description": "Network topology updated",
      "metadata": { "topologyId": "topo::network::20251216T120000Z" }
    },
    {
      "timestamp": "2025-12-16T06:00:02Z",
      "type": "profile",
      "description": "proxmox-01 profile updated",
      "metadata": { "nodeId": "proxmox-01", "version": "E0-0.0.1.4" }
    },
    {
      "timestamp": "2025-12-15T10:30:00Z",
      "type": "service",
      "description": "nginx service started",
      "metadata": { "serviceId": "svc::systemd::nginx", "nodeId": "web-server-01" }
    }
  ],
  "total": 45
}
```

**Required Permission:** `nodes:read`

---

## Commands

### POST /commands

Queue a command for execution.

**Request Body:**

```json
{
  "type": "service",
  "target": {
    "nodeId": "docker-host-01",
    "serviceId": "svc::docker::nginx"
  },
  "action": "restart",
  "parameters": {},
  "timeoutSeconds": 60
}
```

|Field|Type|Required|Description|
|---|---|---|---|
|`type`|enum|Yes|`service`, `package`, `config`, `system`, `custom`|
|`target.nodeId`|string|Yes|Target node|
|`target.serviceId`|string|No|Target service (for service commands)|
|`action`|string|Yes|Action to execute|
|`parameters`|object|No|Action parameters|
|`timeoutSeconds`|integer|No|Timeout (default: 60)|

**Response:** `202 Accepted`

```json
{
  "commandId": "cmd-abc123",
  "type": "service",
  "target": {
    "nodeId": "docker-host-01",
    "serviceId": "svc::docker::nginx"
  },
  "action": "restart",
  "status": "queued",
  "queuedAt": "2025-12-16T10:00:00Z"
}
```

**Required Permission:** `commands:execute`

---

### GET /commands/{commandId}

Get command status and result.

**Response:** `200 OK`

```json
{
  "commandId": "cmd-abc123",
  "type": "service",
  "target": {
    "nodeId": "docker-host-01",
    "serviceId": "svc::docker::nginx"
  },
  "action": "restart",
  "parameters": {},
  "status": "completed",
  "result": {
    "success": true,
    "output": "Service nginx restarted successfully",
    "exitCode": 0,
    "error": null
  },
  "requestedBy": {
    "userId": "user_abc123",
    "source": "web"
  },
  "timeoutSeconds": 60,
  "createdAt": "2025-12-16T10:00:00Z",
  "queuedAt": "2025-12-16T10:00:01Z",
  "startedAt": "2025-12-16T10:00:02Z",
  "completedAt": "2025-12-16T10:00:05Z"
}
```

**Required Permission:** `commands:read`

---

### GET /commands

List commands (history).

**Query Parameters:**

|Parameter|Type|Description|
|---|---|---|
|`nodeId`|string|Filter by target node|
|`type`|enum|Filter by command type|
|`status`|enum|Filter by status|
|`since`|datetime|Commands after timestamp|
|`limit`|integer|Max results (default: 50)|
|`offset`|integer|Pagination offset|

**Response:** `200 OK`

```json
{
  "commands": [
    {
      "commandId": "cmd-abc123",
      "type": "service",
      "target": { "nodeId": "docker-host-01" },
      "action": "restart",
      "status": "completed",
      "createdAt": "2025-12-16T10:00:00Z"
    }
  ],
  "total": 25,
  "limit": 50,
  "offset": 0
}
```

**Required Permission:** `commands:read`

---

### POST /commands/{commandId}/cancel

Cancel a pending or queued command.

**Response:** `200 OK`

```json
{
  "commandId": "cmd-abc123",
  "status": "cancelled",
  "cancelledAt": "2025-12-16T10:00:10Z"
}
```

**Required Permission:** `commands:execute`

---

### GET /nodes/{nodeId}/commands/poll

Poll for pending commands (agent endpoint).

**Response:** `200 OK`

```json
{
  "commands": [
    {
      "commandId": "cmd-abc123",
      "type": "service",
      "action": "restart",
      "parameters": { "serviceId": "svc::docker::nginx" },
      "timeoutSeconds": 60
    }
  ]
}
```

**Required Permission:** `commands:poll` (agent only)

---

### POST /nodes/{nodeId}/commands/{commandId}/result

Submit command execution result (agent endpoint).

**Request Body:**

```json
{
  "success": true,
  "output": "Service nginx restarted successfully",
  "exitCode": 0,
  "error": null
}
```

**Response:** `200 OK`

```json
{
  "commandId": "cmd-abc123",
  "status": "completed",
  "completedAt": "2025-12-16T10:00:05Z"
}
```

**Required Permission:** `commands:poll` (agent only)

---

## Documentations

### GET /docs

List documentation.

**Query Parameters:**

|Parameter|Type|Description|
|---|---|---|
|`type`|enum|Filter by type|
|`status`|enum|Filter by status|
|`category`|string|Filter by category|
|`entityType`|enum|Filter by linked entity type|
|`entityId`|string|Filter by linked entity ID|
|`tags`|string|Comma-separated tags|
|`search`|string|Full-text search|
|`limit`|integer|Max results (default: 20)|
|`offset`|integer|Pagination offset|

**Response:** `200 OK`

```json
{
  "docs": [
    {
      "docId": "doc::proxmox-setup-guide",
      "title": "Proxmox Cluster Setup Guide",
      "type": "guide",
      "category": "infrastructure",
      "status": "published",
      "linkedEntities": [
        { "entityType": "node", "entityId": "proxmox-01" }
      ],
      "version": 3,
      "updatedAt": "2025-12-16T00:00:00Z"
    }
  ],
  "total": 12,
  "limit": 20,
  "offset": 0
}
```

**Required Permission:** `docs:read`

---

### POST /docs

Create new documentation.

**Request Body:**

```json
{
  "docId": "doc::network-architecture",
  "title": "Home Network Architecture",
  "description": "Overview of network segmentation and VLANs",
  "type": "architecture",
  "format": "markdown",
  "content": "# Home Network Architecture\n\n## Overview\n\n...",
  "linkedEntities": [
    { "entityType": "network", "entityId": "homenet-lan" }
  ],
  "category": "network",
  "tags": ["network", "architecture", "vlan"]
}
```

**Response:** `201 Created`

```json
{
  "docId": "doc::network-architecture",
  "title": "Home Network Architecture",
  "version": 1,
  "createdAt": "2025-12-16T10:00:00Z"
}
```

**Required Permission:** `docs:create`

---

### GET /docs/{docId}

Get documentation content.

**Query Parameters:**

|Parameter|Type|Description|
|---|---|---|
|`version`|integer|Specific version (default: latest)|

**Response:** `200 OK`

```json
{
  "docId": "doc::proxmox-setup-guide",
  "title": "Proxmox Cluster Setup Guide",
  "description": "Step-by-step guide for setting up the Proxmox cluster",
  "type": "guide",
  "format": "markdown",
  "content": "# Proxmox Cluster Setup\n\n## Overview\n\n...",
  "linkedEntities": [
    { "entityType": "node", "entityId": "proxmox-01" },
    { "entityType": "node", "entityId": "proxmox-02" }
  ],
  "category": "infrastructure",
  "tags": ["proxmox", "setup", "cluster"],
  "version": 3,
  "author": "admin",
  "status": "published",
  "createdAt": "2025-12-10T00:00:00Z",
  "updatedAt": "2025-12-16T00:00:00Z"
}
```

**Required Permission:** `docs:read`

---

### PUT /docs/{docId}

Update documentation.

**Request Body:**

```json
{
  "title": "Proxmox Cluster Setup Guide (v2)",
  "content": "# Proxmox Cluster Setup\n\n## Updated Overview\n\n..."
}
```

**Response:** `200 OK`

```json
{
  "docId": "doc::proxmox-setup-guide",
  "version": 4,
  "updatedAt": "2025-12-16T10:00:00Z"
}
```

**Required Permission:** `docs:update`

---

### DELETE /docs/{docId}

Delete documentation.

**Query Parameters:**

|Parameter|Type|Description|
|---|---|---|
|`permanent`|boolean|Permanently delete (default: false = archive)|

**Response:** `200 OK`

```json
{
  "docId": "doc::proxmox-setup-guide",
  "status": "archived"
}
```

**Required Permission:** `docs:delete`

---

## Home Assistant

### GET /ha/status

Get Home Assistant integration status.

**Response:** `200 OK`

```json
{
  "enabled": true,
  "connected": true,
  "url": "http://homeassistant.local:8123",
  "lastSync": "2025-12-16T09:45:00Z",
  "entityCount": 145,
  "mappedNodes": 23
}
```

**Required Permission:** `ha:read`

---

### GET /ha/devices

List Home Assistant devices mapped to Hydra nodes.

**Query Parameters:**

|Parameter|Type|Description|
|---|---|---|
|`domain`|string|Filter by HA domain (climate, light, etc.)|
|`area`|string|Filter by HA area|
|`mapped`|boolean|Filter by mapping status|
|`limit`|integer|Max results|
|`offset`|integer|Pagination offset|

**Response:** `200 OK`

```json
{
  "devices": [
    {
      "entityId": "climate.living_room_thermostat",
      "name": "Living Room Thermostat",
      "domain": "climate",
      "area": "Living Room",
      "state": "heat",
      "attributes": {
        "current_temperature": 21.5,
        "temperature": 22.0
      },
      "hydraNode": {
        "nodeId": "ha-climate-living-room-thermostat",
        "displayName": "Living Room Thermostat"
      },
      "lastUpdated": "2025-12-16T10:00:00Z"
    }
  ],
  "total": 23,
  "limit": 50,
  "offset": 0
}
```

**Required Permission:** `ha:read`

---

### POST /ha/sync

Trigger sync from Home Assistant.

**Request Body:**

```json
{
  "domains": ["climate", "light", "switch"],
  "createNodes": true
}
```

**Response:** `202 Accepted`

```json
{
  "jobId": "job-ha-sync-123",
  "status": "started",
  "startedAt": "2025-12-16T10:00:00Z"
}
```

**Required Permission:** `ha:sync`

---

### POST /ha/control

Control a Home Assistant device.

**Request Body:**

```json
{
  "entityId": "climate.living_room_thermostat",
  "service": "set_temperature",
  "data": {
    "temperature": 22
  }
}
```

**Response:** `200 OK`

```json
{
  "entityId": "climate.living_room_thermostat",
  "service": "set_temperature",
  "success": true,
  "newState": {
    "state": "heat",
    "attributes": {
      "temperature": 22
    }
  }
}
```

**Required Permission:** `ha:control`

---

### GET /ha/areas

List Home Assistant areas.

**Response:** `200 OK`

```json
{
  "areas": [
    {
      "areaId": "living_room",
      "name": "Living Room",
      "deviceCount": 5,
      "entityCount": 12
    },
    {
      "areaId": "bedroom",
      "name": "Bedroom",
      "deviceCount": 3,
      "entityCount": 8
    }
  ],
  "total": 8
}
```

**Required Permission:** `ha:read`

---

## Query & Analytics

### POST /query

Execute a structured query across collections.

**Request Body:**

```json
{
  "collection": "nodes",
  "filter": {
    "class": "compute",
    "status": "active"
  },
  "projection": {
    "nodeId": 1,
    "displayName": 1,
    "lastProfileAt": 1
  },
  "sort": { "lastProfileAt": -1 },
  "limit": 10
}
```

|Field|Type|Required|Description|
|---|---|---|---|
|`collection`|enum|Yes|`nodes`, `profiles`, `services`, `groups`, `networks`|
|`filter`|object|No|MongoDB-style filter|
|`projection`|object|No|Fields to include (1) or exclude (0)|
|`sort`|object|No|Sort specification|
|`limit`|integer|No|Max results (default: 50, max: 200)|
|`skip`|integer|No|Skip N results|

**Response:** `200 OK`

```json
{
  "collection": "nodes",
  "results": [
    {
      "nodeId": "proxmox-01",
      "displayName": "Proxmox Host 01",
      "lastProfileAt": "2025-12-16T06:00:00Z"
    }
  ],
  "total": 14,
  "returned": 10
}
```

**Required Permission:** Read permission for target collection

---

### GET /capacity

Get infrastructure capacity summary.

**Query Parameters:**

|Parameter|Type|Description|
|---|---|---|
|`groupBy`|enum|Group results: `node`, `class`, `location`, `network`, `group`|
|`includeLogical`|boolean|Include logical nodes (may double-count resources)|
|`groupId`|string|Filter to group members|
|`networkId`|string|Filter to network|

**Response:** `200 OK`

```json
{
  "summary": {
    "totalNodes": 15,
    "physicalNodes": 3,
    "logicalNodes": 12,
    "totalCores": 96,
    "totalMemoryGB": 384,
    "totalStorageTB": 12.5
  },
  "byClass": {
    "compute": {
      "nodes": 12,
      "cores": 88,
      "memoryGB": 352,
      "storageTB": 10.0
    },
    "networking": {
      "nodes": 2
    },
    "iot": {
      "nodes": 1
    }
  },
  "byLocation": {
    "home/main": {
      "nodes": 10,
      "cores": 72,
      "memoryGB": 288
    }
  }
}
```

**Required Permission:** `nodes:read`, `profiles:read`

---

### GET /audit

Get audit log entries.

**Query Parameters:**

|Parameter|Type|Description|
|---|---|---|
|`action`|enum|Filter by action|
|`resourceType`|string|Filter by resource type|
|`resourceId`|string|Filter by resource ID|
|`actorId`|string|Filter by actor ID|
|`since`|datetime|Entries after timestamp|
|`until`|datetime|Entries before timestamp|
|`limit`|integer|Max results (default: 100)|
|`offset`|integer|Pagination offset|

**Response:** `200 OK`

```json
{
  "entries": [
    {
      "entryId": "audit-abc123",
      "timestamp": "2025-12-16T10:00:00Z",
      "action": "update",
      "resource": {
        "type": "node",
        "id": "proxmox-01"
      },
      "actor": {
        "type": "user",
        "id": "user_abc123",
        "ip": "192.168.0.100"
      },
      "details": {
        "field": "displayName",
        "oldValue": "Proxmox Host 01",
        "newValue": "Proxmox Host 01 (Updated)"
      },
      "result": {
        "success": true
      }
    }
  ],
  "total": 500,
  "limit": 100,
  "offset": 0
}
```

**Required Permission:** `audit:read`

---

## Error Codes

| HTTP | Code                              | Description                           |
| ---- | --------------------------------- | ------------------------------------- |
| 400  | `INVALID_REQUEST`                 | Malformed request body                |
| 400  | `VALIDATION_ERROR`                | Schema validation failed              |
| 400  | `INVALID_NODE_ID`                 | Invalid node ID format                |
| 400  | `INVALID_SERVICE_ID`              | Invalid service ID format             |
| 400  | `INVALID_GROUP_ID`                | Invalid group ID format               |
| 400  | `INVALID_NETWORK_ID`              | Invalid network ID format             |
| 400  | `SELECTOR_VALIDATION_ERROR`       | Invalid group selector                |
| 401  | `AUTH_INVALID_TOKEN`              | JWT token invalid or expired          |
| 401  | `AUTH_MISSING_TOKEN`              | No authorization header               |
| 401  | `AUTH_REGISTRATION_TOKEN_INVALID` | Registration token invalid            |
| 401  | `AUTH_REGISTRATION_TOKEN_EXPIRED` | Registration token expired            |
| 401  | `AUTH_REGISTRATION_TOKEN_USED`    | Registration token already used       |
| 401  | `AUTH_INVALID_CREDENTIALS`        | Wrong username/password               |
| 403  | `AUTH_INSUFFICIENT_PERMISSIONS`   | Lacks required permissions            |
| 404  | `NODE_NOT_FOUND`                  | Node does not exist                   |
| 404  | `PROFILE_NOT_FOUND`               | Profile does not exist                |
| 404  | `SERVICE_NOT_FOUND`               | Service does not exist                |
| 404  | `GROUP_NOT_FOUND`                 | Group does not exist                  |
| 404  | `NETWORK_NOT_FOUND`               | Network does not exist                |
| 404  | `TOPOLOGY_NOT_FOUND`              | Topology does not exist               |
| 404  | `USER_NOT_FOUND`                  | User does not exist                   |
| 404  | `COMMAND_NOT_FOUND`               | Command does not exist                |
| 409  | `NODE_ALREADY_EXISTS`             | Duplicate nodeId                      |
| 409  | `GROUP_ALREADY_EXISTS`            | Duplicate groupId                     |
| 409  | `NETWORK_ALREADY_EXISTS`          | Duplicate networkId                   |
| 409  | `USER_ALREADY_EXISTS`             | Duplicate username/email              |
| 422  | `NETWORK_HAS_NODES`               | Cannot delete network with nodes      |
| 422  | `COMMAND_NOT_CANCELLABLE`         | Command already completed/executing   |
| 429  | `RATE_LIMIT_EXCEEDED`             | Too many requests                     |
| 500  | `INTERNAL_ERROR`                  | Server error                          |
| 503  | `SERVICE_UNAVAILABLE`             | Service temporarily unavailable       |
| 503  | `HA_UNAVAILABLE`                  | Home Assistant not reachable          |
| 400  | `BOOTSTRAP_REQUIRES_ADMIN`        | First registration must be admin role |
| 400  | `INVALID_ROLE_FOR_ELEVATION`      | Cannot elevate to requested role      |
| 401  | `AUTH_PENDING_APPROVAL`           | User registered but not yet approved  |
| 403  | `ADMIN_ONLY_OPERATION`            | Operation requires admin role         |
| 404  | `PENDING_USER_NOT_FOUND`          | Pending user not found in approvals   |
| 409  | `USERNAME_ALREADY_EXISTS`         | Username already taken                |
| 409  | `NODE_ALREADY_REGISTERED`         | Node ID already exists                |
| 422  | `ROLE_LIMIT_EXCEEDED`             | Maximum accounts for role reached     |
| 422  | `CANNOT_ELEVATE_AGENT`            | Agent role is system-managed          |
| 422  | `TEMP_ROLE_ALREADY_ACTIVE`        | User already has this temporary role  |

**Error Response Format:**

```json
{
  "error": {
    "code": "NODE_NOT_FOUND",
    "message": "Node 'invalid-node' not found",
    "details": {
      "nodeId": "invalid-node"
    }
  },
  "requestId": "req-abc123"
}
```

---

## Rate Limits

|Category|Limit|Window|
|---|---|---|
|Authentication|10 req|1 min|
|Profile submission|100 req|1 min|
|Read operations|300 req|1 min|
|Write operations|30 req|1 min|
|Query endpoints|30 req|1 min|
|Topology generation|5 req|1 min|
|Command execution|20 req|1 min|
|HA control|60 req|1 min|

**Rate Limit Headers:**

```
X-RateLimit-Limit: 300
X-RateLimit-Remaining: 287
X-RateLimit-Reset: 1703851200
```

---

## Appendices

### Version Format

```
Ex-W.X.Y.Z

E = Epoch (0+) — Manual increment for breaking changes
W = Massive (0-F) — >75% of sections changed
X = Major (0-F) — >50% of sections changed
Y = Moderate (0-F) — >25% of sections changed
Z = Minor (0-F) — Any section changed

All positions are hexadecimal (0-F with overflow carry)
```

**Examples:**

- `E0-0.0.0.1` — First profile
- `E0-0.0.0.F` → `E0-0.0.1.0` — Z overflow
- `E0-0.1.0.0` — Major change (>50% sections)
- `E1-0.0.0.1` — New epoch (breaking change)

---

### Service ID Format

```
svc::<runtime>::<name>

runtime = systemd | docker | podman | kubernetes | rc | openrc | etc.
name = service name (lowercase, alphanumeric, hyphens, underscores, dots)
```

**Examples:**

- `svc::systemd::nginx`
- `svc::docker::mongodb`
- `svc::kubernetes::api-gateway`

---

### Topology ID Format

```
topo::<mode>::<timestamp>

mode = network | infrastructure
timestamp = ISO 8601 compact (YYYYMMDDTHHmmssZ)
```

**Examples:**

- `topo::network::20251216T120000Z`
- `topo::infrastructure::20251216T120000Z`

---

### Permission Format

```
resource:action

Resources: nodes, profiles, services, groups, networks, topologies,
           docs, users, tokens, commands, iot, ha, audit

Actions: read, write, create, update, delete, execute, control, poll, sync, *
```

**Examples:**

- `nodes:read` — Read nodes
- `services:*` — All service operations
- `commands:execute` — Execute commands
- `*:*` — Full access (admin)

---

### Built-in Roles

| Role       | Permissions                                                                                                               | Notes                        |
| ---------- | ------------------------------------------------------------------------------------------------------------------------- | ---------------------------- |
| `admin`    | `*:*`                                                                                                                     | Max 2 accounts               |
| `operator` | `nodes:*`, `profiles:*`, `services:*`, `groups:*`, `networks:*`, `topologies:read`, `docs:*`, `commands:execute`, `ha:*`  | Max 10 accounts              |
| `viewer`   | `nodes:read`, `profiles:read`, `services:read`, `groups:read`, `networks:read`, `topologies:read`, `docs:read`, `ha:read` | Unlimited                    |
| `family`   | `iot:read`, `iot:control`, `ha:read`, `ha:control`                                                                        | Unlimited                    |
| `agent`    | `profiles:write` (own node), `commands:poll` (own node), `apikeys:refresh` (own key)                                      | System-managed, one per node |

---

_For complete schema definitions and technical details, see the Technical Documentation._