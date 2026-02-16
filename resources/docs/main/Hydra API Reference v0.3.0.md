# Hydra API Reference

> **Version:** 0.3.0
> **Base URL:** `https://hydra.local/api/v1`
> **Last Updated:** 2026-01-15
> **Total Endpoints:** 128

---

## Table of Contents

1. [Introduction](#introduction)
   - [Base URL](#base-url)
   - [Authentication](#authentication)
   - [Request Format](#request-format)
   - [Response Format](#response-format)
   - [Pagination](#pagination)
   - [Rate Limits](#rate-limits)
   - [Error Handling](#error-handling)
2. [Health & System](#health--system)
3. [Authentication](#authentication-endpoints)
4. [Users](#users)
5. [Nodes](#nodes)
6. [Profiles](#profiles)
7. [Services](#services)
8. [Groups](#groups)
9. [Networks](#networks)
10. [Topologies](#topologies)
11. [Time Machine](#time-machine)
12. [Commands](#commands)
13. [Home Assistant](#home-assistant)
14. [AI Models](#ai-models)
15. [Chat](#chat)
16. [MCP Servers](#mcp-servers)
17. [Documentation](#documentation)
18. [Query & Analytics](#query--analytics)
19. [Search](#search)
20. [Settings](#settings)
21. [Agent Installation](#agent-installation)
22. [Appendices](#appendices)

---

## Introduction

### Base URL

All API endpoints are prefixed with `/api/v1`:

| Environment | Base URL |
|-------------|----------|
| Local Development | `http://localhost:8080/api/v1` |
| Production | `https://hydra.yourdomain.com/api/v1` |

### Authentication

All endpoints except `/health`, `/info`, and `/auth/register` (first user bootstrap) require authentication.

#### Methods

**Bearer Token (JWT)**
```http
Authorization: Bearer <access_token>
```

**API Key**
```http
X-API-Key: <api_key>
```

**Registration Token** (for node registration)
```http
X-Registration-Token: <registration_token>
```

#### Roles & Permissions

| Role | Level | Max Accounts | Permissions |
|------|-------|--------------|-------------|
| `admin` | 100 | 2 | `*:*` (full access) |
| `operator` | 50 | 10 | `nodes:*`, `profiles:*`, `services:*`, `groups:*`, `networks:*`, `topologies:read`, `docs:*`, `commands:execute`, `ha:*` |
| `viewer` | 25 | Unlimited | `nodes:read`, `profiles:read`, `services:read`, `groups:read`, `networks:read`, `topologies:read`, `docs:read`, `ha:read` |
| `family` | 10 | Unlimited | `iot:read`, `iot:control`, `ha:read`, `ha:control` |
| `agent` | 0 | Unlimited | `profiles:write` (own node), `commands:poll` (own node), `apikeys:refresh` (own key) |

### Request Format

- Content-Type: `application/json`
- Character encoding: UTF-8
- Dates: ISO 8601 format (`2025-12-16T10:00:00Z`)

### Response Format

**Success Response**
```json
{
  "data": { ... },
  "meta": {
    "total": 100,
    "limit": 50,
    "offset": 0
  }
}
```

**Error Response**
```json
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

List endpoints support pagination:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | 50 | Maximum results (1-200) |
| `offset` | integer | 0 | Number of results to skip |
| `sort` | string | varies | Sort field (prefix `-` for descending) |

### Rate Limits

| Category | Limit | Window |
|----------|-------|--------|
| Authentication | 10 req | 1 min |
| Profile submission | 100 req | 1 min |
| Read operations | 300 req | 1 min |
| Write operations | 30 req | 1 min |
| Query endpoints | 30 req | 1 min |
| Topology generation | 5 req | 1 min |
| Command execution | 20 req | 1 min |
| HA control | 60 req | 1 min |

**Rate Limit Headers**
```http
X-RateLimit-Limit: 300
X-RateLimit-Remaining: 287
X-RateLimit-Reset: 1703851200
```

### Error Handling

| HTTP | Code | Description |
|------|------|-------------|
| 400 | `INVALID_REQUEST` | Malformed request body |
| 400 | `VALIDATION_ERROR` | Schema validation failed |
| 401 | `AUTH_INVALID_TOKEN` | JWT token invalid or expired |
| 401 | `AUTH_MISSING_TOKEN` | No authorization header |
| 401 | `AUTH_INVALID_CREDENTIALS` | Wrong username/password |
| 403 | `AUTH_INSUFFICIENT_PERMISSIONS` | Lacks required permissions |
| 404 | `*_NOT_FOUND` | Resource does not exist |
| 409 | `*_ALREADY_EXISTS` | Duplicate resource |
| 422 | `ROLE_LIMIT_EXCEEDED` | Maximum accounts for role reached |
| 429 | `RATE_LIMIT_EXCEEDED` | Too many requests |
| 500 | `INTERNAL_ERROR` | Server error |
| 503 | `SERVICE_UNAVAILABLE` | Service temporarily unavailable |

---

## Health & System

### GET /health

Health check endpoint. No authentication required.

**Response:** `200 OK`
```json
{
  "status": "healthy",
  "version": "0.3.0",
  "timestamp": "2025-12-16T10:00:00Z"
}
```

---

### GET /info

System information. No authentication required.

**Response:** `200 OK`
```json
{
  "name": "hydra-api",
  "version": "0.3.0",
  "environment": "production",
  "features": {
    "ha_integration": true,
    "smtp_enabled": true,
    "object_storage": true
  }
}
```

---

## Authentication Endpoints

### POST /auth/register

Register a new user account. No authentication required for first user (bootstrap).

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

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `username` | string | Yes | Unique username (3-32 chars, lowercase alphanumeric, hyphens, underscores) |
| `email` | string | Yes | Valid email address |
| `password` | string | Yes | Password (min 8 chars) |
| `role` | enum | Yes | `admin`, `operator`, `viewer`, or `family` |
| `registrationToken` | string | No | Token for instant activation |

**Response (With Token):** `201 Created`
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

**Response (Without Token):** `202 Accepted`
```json
{
  "userId": "user_pending_xyz789",
  "username": "newuser",
  "status": "pending_approval",
  "message": "Registration submitted. Awaiting admin approval."
}
```

**Errors:**
- `400 BOOTSTRAP_REQUIRES_ADMIN` - First user must be admin
- `409 USERNAME_ALREADY_EXISTS` - Username taken
- `422 ROLE_LIMIT_EXCEEDED` - Max accounts for role reached

---

### POST /auth/login

Authenticate and obtain tokens.

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

### POST /auth/refresh

Refresh an expired access token.

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
  "expiresIn": 3600
}
```

---

### POST /auth/password/forgot

Request password reset email.

**Request Body:**
```json
{
  "email": "user@example.com"
}
```

**Response:** `200 OK`
```json
{
  "message": "If account exists, reset email sent"
}
```

---

### POST /auth/password/reset

Reset password with token.

**Request Body:**
```json
{
  "token": "reset_token_abc123",
  "newPassword": "newSecurePassword123"
}
```

**Response:** `200 OK`
```json
{
  "message": "Password reset successfully"
}
```

---

### POST /auth/password/change

Change password for authenticated user.

**Request Body:**
```json
{
  "currentPassword": "oldPassword123",
  "newPassword": "newSecurePassword123"
}
```

**Response:** `200 OK`
```json
{
  "message": "Password changed successfully"
}
```

**Required Permission:** Authenticated user

---

### GET /auth/me

Get current authenticated user.

**Response:** `200 OK`
```json
{
  "userId": "user_abc123",
  "username": "admin",
  "email": "admin@example.com",
  "role": "admin",
  "temporaryRoles": [],
  "createdAt": "2025-12-01T10:00:00Z",
  "lastLoginAt": "2025-12-16T08:00:00Z"
}
```

---

### GET /auth/approvals

List pending user registrations.

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `role` | enum | Filter by requested role |
| `limit` | integer | Max results (default: 50) |
| `offset` | integer | Pagination offset |

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
    }
  ],
  "total": 1
}
```

**Required Permission:** `admin` role

---

### POST /auth/approvals

Approve a pending user registration.

**Request Body:**
```json
{
  "userId": "user_pending_xyz789"
}
```

**Response:** `200 OK`
```json
{
  "userId": "user_abc123",
  "username": "newoperator",
  "status": "active",
  "approvedBy": "admin",
  "approvedAt": "2025-12-16T10:00:00Z"
}
```

**Required Permission:** `admin` role

---

### DELETE /auth/approvals/{userId}

Reject a pending user registration.

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `userId` | string | Pending user ID |

**Response:** `200 OK`
```json
{
  "message": "Registration rejected",
  "userId": "user_pending_xyz789"
}
```

**Required Permission:** `admin` role

---

### POST /auth/tokens

Create a registration token.

**Request Body:**
```json
{
  "scope": "user",
  "allowedRoles": ["operator", "viewer"],
  "maxUses": 5,
  "expiresIn": 604800,
  "description": "Operator onboarding"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `scope` | enum | Yes | `user` or `node` |
| `allowedRoles` | array | No | Roles that can be assigned (user scope only) |
| `maxUses` | integer | No | Maximum uses (default: 1) |
| `expiresIn` | integer | No | Seconds until expiry (default: 604800 = 7 days) |
| `description` | string | No | Token description |

**Response:** `201 Created`
```json
{
  "token": "reg_a1b2c3d4e5f6g7h8i9j0...",
  "tokenId": "token_abc123",
  "scope": "user",
  "allowedRoles": ["operator", "viewer"],
  "maxUses": 5,
  "usedCount": 0,
  "expiresAt": "2025-12-23T10:00:00Z",
  "createdBy": "admin"
}
```

**Required Permission:** `tokens:create` or higher role level

---

### GET /auth/tokens

List registration tokens.

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `scope` | enum | Filter by scope (`user`, `node`) |
| `active` | boolean | Only active (not expired/exhausted) |
| `limit` | integer | Max results |
| `offset` | integer | Pagination offset |

**Response:** `200 OK`
```json
{
  "tokens": [
    {
      "tokenId": "token_abc123",
      "scope": "user",
      "allowedRoles": ["operator", "viewer"],
      "maxUses": 5,
      "usedCount": 2,
      "expiresAt": "2025-12-23T10:00:00Z",
      "createdBy": "admin",
      "createdAt": "2025-12-16T10:00:00Z"
    }
  ],
  "total": 1
}
```

**Required Permission:** `tokens:read`

---

### POST /auth/apikeys

Create an API key.

**Request Body:**
```json
{
  "name": "CI/CD Pipeline",
  "expiresIn": 7776000,
  "permissions": ["nodes:read", "profiles:read"]
}
```

**Response:** `201 Created`
```json
{
  "apiKey": "hk_live_a1b2c3d4e5f6...",
  "keyId": "key_abc123",
  "name": "CI/CD Pipeline",
  "permissions": ["nodes:read", "profiles:read"],
  "expiresAt": "2026-03-16T10:00:00Z"
}
```

**Note:** The full API key is only shown once at creation.

**Required Permission:** Authenticated user

---

### GET /auth/apikeys

List API keys for current user.

**Response:** `200 OK`
```json
{
  "apiKeys": [
    {
      "keyId": "key_abc123",
      "name": "CI/CD Pipeline",
      "prefix": "hk_live_a1b2",
      "permissions": ["nodes:read", "profiles:read"],
      "lastUsedAt": "2025-12-16T09:00:00Z",
      "expiresAt": "2026-03-16T10:00:00Z"
    }
  ],
  "total": 1
}
```

---

### DELETE /auth/apikeys/{keyId}

Revoke an API key.

**Response:** `200 OK`
```json
{
  "message": "API key revoked",
  "keyId": "key_abc123"
}
```

---

### POST /auth/users

Create a user directly (admin only).

**Request Body:**
```json
{
  "username": "newuser",
  "email": "newuser@example.com",
  "password": "securepassword123",
  "role": "operator"
}
```

**Response:** `201 Created`
```json
{
  "userId": "user_abc123",
  "username": "newuser",
  "email": "newuser@example.com",
  "role": "operator",
  "status": "active"
}
```

**Required Permission:** `admin` role

---

### POST /auth/register/sub/{userId}

Link a sub-account to current user.

**Response:** `200 OK`
```json
{
  "message": "Sub-account linked",
  "subAccountId": "user_agent123",
  "parentUserId": "user_abc123"
}
```

**Required Permission:** Authenticated user with sufficient role level

---

### DELETE /auth/sub/{userId}

Unlink a sub-account.

**Response:** `200 OK`
```json
{
  "message": "Sub-account unlinked"
}
```

---

## Users

### GET /users

List all users.

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `role` | enum | Filter by role |
| `status` | enum | Filter by status (`active`, `inactive`) |
| `limit` | integer | Max results |
| `offset` | integer | Pagination offset |

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
      "createdAt": "2025-12-01T10:00:00Z",
      "lastLoginAt": "2025-12-16T08:00:00Z"
    }
  ],
  "total": 5
}
```

**Required Permission:** `users:read`

---

### GET /users/{userId}/subs

List sub-accounts of a user.

**Response:** `200 OK`
```json
{
  "subAccounts": [
    {
      "userId": "user_agent123",
      "username": "agent-proxmox01",
      "role": "agent",
      "linkedAt": "2025-12-10T10:00:00Z",
      "nodeId": "proxmox-01"
    }
  ],
  "total": 1
}
```

**Required Permission:** `users:read` or own user

---

### DELETE /users/{userId}

Archive a user account.

**Response:** `200 OK`
```json
{
  "message": "User archived",
  "userId": "user_abc123"
}
```

**Required Permission:** `admin` role

---

### POST /users/{userId}/roles/elevate

Permanently elevate user role.

**Request Body:**
```json
{
  "newRole": "operator"
}
```

**Response:** `200 OK`
```json
{
  "userId": "user_abc123",
  "previousRole": "viewer",
  "newRole": "operator"
}
```

**Required Permission:** `admin` role

---

### POST /users/{userId}/roles/grant-temporary

Grant temporary role.

**Request Body:**
```json
{
  "role": "operator",
  "duration": 86400,
  "reason": "Emergency maintenance"
}
```

**Response:** `200 OK`
```json
{
  "userId": "user_abc123",
  "temporaryRole": "operator",
  "expiresAt": "2025-12-17T10:00:00Z",
  "reason": "Emergency maintenance"
}
```

**Required Permission:** `admin` role

---

### DELETE /users/{userId}/roles/temporary/{role}

Revoke temporary role.

**Response:** `200 OK`
```json
{
  "message": "Temporary role revoked",
  "role": "operator"
}
```

**Required Permission:** `admin` role

---

## Nodes

### POST /nodes/register

Register a new node.

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
  "parentNodeId": null
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `nodeId` | string | Yes | Unique node ID (pattern: `^[a-z0-9][a-z0-9.-]{2,63}$`) |
| `class` | enum | Yes | `compute`, `networking`, or `iot` |
| `type` | enum | Yes | `physical` or `logical` |
| `kind` | string | No | Node kind (varies by class) |
| `displayName` | string | No | Human-readable name |
| `description` | string | No | Node description |
| `tags` | array | No | String tags for grouping |
| `parentNodeId` | string | No | Parent node for logical nodes |

**Node Kinds by Class:**
- `compute`: `bare-metal`, `vm`, `lxc`, `docker`, `kubernetes-pod`
- `networking`: `router`, `switch`, `access-point`, `firewall`, `load-balancer`
- `iot`: `sensor`, `actuator`, `controller`, `hub`, `bridge`, `appliance`

**Response:** `201 Created`
```json
{
  "nodeId": "proxmox-01",
  "class": "compute",
  "type": "physical",
  "kind": "bare-metal",
  "displayName": "Proxmox Host 01",
  "status": "active",
  "registeredBy": "user_abc123",
  "registeredAt": "2025-12-16T10:00:00Z"
}
```

**Required Permission:** `nodes:create` or valid registration token

---

### POST /nodes/{node_id}/apikey/refresh

Refresh API key for a node.

**Response:** `200 OK`
```json
{
  "apiKey": "hk_agent_newkey...",
  "expiresAt": "2026-03-16T10:00:00Z"
}
```

**Required Permission:** `agent` role (own node) or `admin`

---

### GET /nodes

List all nodes.

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `class` | enum | Filter by class (`compute`, `networking`, `iot`) |
| `type` | enum | Filter by type (`physical`, `logical`) |
| `kind` | string | Filter by kind |
| `status` | enum | Filter by status (`active`, `inactive`, `archived`, `pending`) |
| `tags` | string | Comma-separated tags (AND logic) |
| `networkId` | string | Filter by network membership |
| `parentNodeId` | string | Filter by parent node |
| `search` | string | Text search on displayName/description |
| `limit` | integer | Max results (default: 50, max: 200) |
| `offset` | integer | Pagination offset |
| `sort` | string | Sort field (prefix `-` for desc) |

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
      "registeredBy": "user_admin001",
      "networkIds": ["homenet-lan"],
      "lastProfileAt": "2025-12-16T06:00:00Z"
    }
  ],
  "total": 15
}
```

**Required Permission:** `nodes:read`

---

### GET /nodes/agents

List nodes with active agents.

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `status` | enum | Filter by status |
| `healthyOnly` | boolean | Only healthy agents (profile within 24h) |
| `limit` | integer | Max results |
| `offset` | integer | Pagination offset |

**Response:** `200 OK`
```json
{
  "agents": [
    {
      "nodeId": "proxmox-01",
      "displayName": "Proxmox Host 01",
      "status": "active",
      "lastProfileAt": "2025-12-16T06:00:00Z",
      "profileCount": 1452,
      "lastProfileVersion": "E0-0.1.2.45",
      "isHealthy": true
    }
  ],
  "total": 12,
  "active": 10
}
```

**Required Permission:** `nodes:read`

---

### GET /nodes/{nodeId}

Get node details.

**Response:** `200 OK`
```json
{
  "nodeId": "proxmox-01",
  "class": "compute",
  "type": "physical",
  "kind": "bare-metal",
  "displayName": "Proxmox Host 01",
  "description": "Primary hypervisor",
  "status": "active",
  "tags": ["production", "hypervisor"],
  "registeredBy": "user_admin001",
  "registeredAt": "2025-12-01T10:00:00Z",
  "networkIds": ["homenet-lan"],
  "parentNodeId": null,
  "childCount": 5,
  "serviceCount": 12,
  "lastProfileAt": "2025-12-16T06:00:00Z",
  "lastProfileVersion": "E0-0.1.2.45"
}
```

**Required Permission:** `nodes:read`

---

### GET /nodes/{nodeId}/children

Get child nodes.

**Response:** `200 OK`
```json
{
  "children": [
    {
      "nodeId": "vm-webserver",
      "class": "compute",
      "type": "logical",
      "kind": "vm",
      "displayName": "Web Server VM",
      "status": "active"
    }
  ],
  "total": 5
}
```

**Required Permission:** `nodes:read`

---

### PATCH /nodes/{nodeId}

Update node properties.

**Request Body:**
```json
{
  "displayName": "Updated Display Name",
  "description": "Updated description",
  "tags": ["production", "web"],
  "status": "inactive"
}
```

**Response:** `200 OK`
```json
{
  "nodeId": "proxmox-01",
  "displayName": "Updated Display Name",
  "updatedAt": "2025-12-16T10:00:00Z"
}
```

**Required Permission:** `nodes:update`

---

### DELETE /nodes/{nodeId}

Archive a node (soft delete).

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `cascade` | boolean | Also archive child nodes (default: false) |

**Response:** `200 OK`
```json
{
  "message": "Node archived",
  "nodeId": "proxmox-01"
}
```

**Required Permission:** `nodes:delete`

---

## Profiles

### POST /profiles

Submit a profile for a node.

**Request Body:**
```json
{
  "nodeId": "proxmox-01",
  "collectedAt": "2025-12-16T06:00:00Z",
  "collector": {
    "name": "hydra-agent",
    "version": "0.3.0"
  },
  "hardware": {
    "cpu": { ... },
    "memory": { ... },
    "gpu": [ ... ]
  },
  "network": {
    "interfaces": [ ... ],
    "routes": [ ... ]
  },
  "storage": {
    "disks": [ ... ],
    "filesystems": [ ... ]
  },
  "software": {
    "os": { ... },
    "packages": [ ... ],
    "users": [ ... ]
  },
  "services": [ ... ]
}
```

**Response:** `201 Created`
```json
{
  "profileId": "prof_abc123",
  "nodeId": "proxmox-01",
  "version": "E0-0.1.2.46",
  "submittedAt": "2025-12-16T06:00:00Z",
  "servicesExtracted": 12,
  "networksUpdated": 1
}
```

**Required Permission:** `profiles:write` (agent, own node)

---

### GET /profiles/{profileId}

Get profile by ID.

**Response:** `200 OK`
```json
{
  "profileId": "prof_abc123",
  "nodeId": "proxmox-01",
  "version": "E0-0.1.2.46",
  "collectedAt": "2025-12-16T06:00:00Z",
  "submittedAt": "2025-12-16T06:00:05Z",
  "hardware": { ... },
  "network": { ... },
  "storage": { ... },
  "software": { ... },
  "services": [ ... ]
}
```

**Required Permission:** `profiles:read`

---

### GET /nodes/{nodeId}/profiles

List profiles for a node.

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `limit` | integer | Max results (default: 50) |
| `offset` | integer | Pagination offset |
| `from` | datetime | Start date filter |
| `to` | datetime | End date filter |

**Response:** `200 OK`
```json
{
  "profiles": [
    {
      "profileId": "prof_abc123",
      "version": "E0-0.1.2.46",
      "collectedAt": "2025-12-16T06:00:00Z"
    }
  ],
  "total": 1452
}
```

**Required Permission:** `profiles:read`

---

### GET /nodes/{nodeId}/profiles/latest

Get latest profile for a node.

**Response:** `200 OK`
```json
{
  "profileId": "prof_abc123",
  "nodeId": "proxmox-01",
  "version": "E0-0.1.2.46",
  "collectedAt": "2025-12-16T06:00:00Z",
  "hardware": { ... },
  "network": { ... },
  "storage": { ... },
  "software": { ... }
}
```

**Required Permission:** `profiles:read`

---

### GET /nodes/{nodeId}/profiles/diff

Compare two profiles.

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `from` | string | No | Profile ID or version (default: previous) |
| `to` | string | No | Profile ID or version (default: latest) |

**Response:** `200 OK`
```json
{
  "nodeId": "proxmox-01",
  "fromProfile": {
    "profileId": "prof_abc122",
    "version": "E0-0.1.2.45"
  },
  "toProfile": {
    "profileId": "prof_abc123",
    "version": "E0-0.1.2.46"
  },
  "changes": {
    "hardware": {
      "memory": {
        "total": { "from": "32GB", "to": "64GB" }
      }
    },
    "services": {
      "added": ["svc-newservice-a1b2"],
      "removed": [],
      "modified": ["svc-nginx-c3d4"]
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

| Parameter | Type | Description |
|-----------|------|-------------|
| `nodeId` | string | Filter by node |
| `runtime` | string | Filter by runtime (`systemd`, `docker`, etc.) |
| `status` | enum | Filter by status (`running`, `stopped`, `unknown`) |
| `search` | string | Search by name |
| `limit` | integer | Max results |
| `offset` | integer | Pagination offset |

**Response:** `200 OK`
```json
{
  "services": [
    {
      "serviceId": "svc-nginx-c3d4",
      "nodeId": "proxmox-01",
      "runtime": "systemd",
      "name": "nginx",
      "displayName": "NGINX Web Server",
      "status": "running",
      "enabled": true,
      "ports": [80, 443],
      "lastSeenAt": "2025-12-16T06:00:00Z"
    }
  ],
  "total": 156
}
```

**Required Permission:** `services:read`

---

### GET /services/{serviceId}

Get service details.

**Response:** `200 OK`
```json
{
  "serviceId": "svc-nginx-c3d4",
  "nodeId": "proxmox-01",
  "runtime": "systemd",
  "name": "nginx",
  "displayName": "NGINX Web Server",
  "description": "HTTP and reverse proxy server",
  "status": "running",
  "enabled": true,
  "ports": [80, 443],
  "configFiles": ["/etc/nginx/nginx.conf"],
  "dependencies": ["network.target"],
  "firstSeenAt": "2025-12-01T10:00:00Z",
  "lastSeenAt": "2025-12-16T06:00:00Z"
}
```

**Required Permission:** `services:read`

---

### PATCH /services/{serviceId}

Update service metadata.

**Request Body:**
```json
{
  "displayName": "Updated Name",
  "description": "Updated description",
  "tags": ["web", "production"]
}
```

**Response:** `200 OK`
```json
{
  "serviceId": "svc-nginx-c3d4",
  "displayName": "Updated Name",
  "updatedAt": "2025-12-16T10:00:00Z"
}
```

**Required Permission:** `services:update`

---

### DELETE /services/{serviceId}

Archive a service.

**Response:** `200 OK`
```json
{
  "message": "Service archived",
  "serviceId": "svc-nginx-c3d4"
}
```

**Required Permission:** `services:delete`

---

### GET /nodes/{nodeId}/services

Get services for a specific node.

**Response:** `200 OK`
```json
{
  "services": [
    {
      "serviceId": "svc-nginx-c3d4",
      "runtime": "systemd",
      "name": "nginx",
      "status": "running"
    }
  ],
  "total": 12
}
```

**Required Permission:** `services:read`

---

## Groups

### GET /groups

List all groups.

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `type` | string | Filter by group type |
| `tags` | string | Filter by tags |
| `limit` | integer | Max results |
| `offset` | integer | Pagination offset |

**Response:** `200 OK`
```json
{
  "groups": [
    {
      "groupId": "production-servers",
      "displayName": "Production Servers",
      "type": "environment",
      "memberCount": 8,
      "createdAt": "2025-12-01T10:00:00Z"
    }
  ],
  "total": 5
}
```

**Required Permission:** `groups:read`

---

### POST /groups

Create a group.

**Request Body:**
```json
{
  "groupId": "production-servers",
  "displayName": "Production Servers",
  "description": "All production infrastructure",
  "type": "environment",
  "selector": {
    "type": "tag",
    "tags": ["production"]
  },
  "tags": ["critical"]
}
```

**Selector Types:**
- `tag`: Match nodes by tags
- `class`: Match nodes by class
- `network`: Match nodes by network
- `manual`: Explicit node list

**Response:** `201 Created`
```json
{
  "groupId": "production-servers",
  "displayName": "Production Servers",
  "memberCount": 8,
  "createdAt": "2025-12-16T10:00:00Z"
}
```

**Required Permission:** `groups:create`

---

### GET /groups/{groupId}

Get group details.

**Response:** `200 OK`
```json
{
  "groupId": "production-servers",
  "displayName": "Production Servers",
  "description": "All production infrastructure",
  "type": "environment",
  "selector": {
    "type": "tag",
    "tags": ["production"]
  },
  "memberCount": 8,
  "tags": ["critical"],
  "createdBy": "admin",
  "createdAt": "2025-12-01T10:00:00Z"
}
```

**Required Permission:** `groups:read`

---

### PUT /groups/{groupId}

Update a group.

**Request Body:**
```json
{
  "displayName": "Updated Name",
  "selector": {
    "type": "tag",
    "tags": ["production", "tier1"]
  }
}
```

**Response:** `200 OK`
```json
{
  "groupId": "production-servers",
  "displayName": "Updated Name",
  "memberCount": 6,
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
  "message": "Group deleted",
  "groupId": "production-servers"
}
```

**Required Permission:** `groups:delete`

---

### GET /groups/{groupId}/members

Get group members.

**Response:** `200 OK`
```json
{
  "members": [
    {
      "nodeId": "proxmox-01",
      "displayName": "Proxmox Host 01",
      "class": "compute",
      "status": "active"
    }
  ],
  "total": 8
}
```

**Required Permission:** `groups:read`

---

### POST /groups/{groupId}/resolve

Resolve group selector to get current members.

**Response:** `200 OK`
```json
{
  "groupId": "production-servers",
  "resolvedAt": "2025-12-16T10:00:00Z",
  "members": [
    {
      "nodeId": "proxmox-01",
      "matchedBy": "tag:production"
    }
  ],
  "total": 8
}
```

**Required Permission:** `groups:read`

---

## Networks

### GET /networks

List all networks.

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `type` | enum | Filter by type (`lan`, `vlan`, `wan`, `vpn`) |
| `limit` | integer | Max results |
| `offset` | integer | Pagination offset |

**Response:** `200 OK`
```json
{
  "networks": [
    {
      "networkId": "homenet-lan",
      "displayName": "Home Network LAN",
      "type": "lan",
      "cidr": "192.168.1.0/24",
      "gateway": "192.168.1.1",
      "nodeCount": 15,
      "isAutoDiscovered": true
    }
  ],
  "total": 3
}
```

**Required Permission:** `networks:read`

---

### POST /networks

Create a network.

**Request Body:**
```json
{
  "networkId": "iot-vlan",
  "displayName": "IoT VLAN",
  "type": "vlan",
  "cidr": "192.168.100.0/24",
  "gateway": "192.168.100.1",
  "vlanId": 100,
  "description": "Isolated IoT network"
}
```

**Response:** `201 Created`
```json
{
  "networkId": "iot-vlan",
  "displayName": "IoT VLAN",
  "type": "vlan",
  "cidr": "192.168.100.0/24",
  "createdAt": "2025-12-16T10:00:00Z"
}
```

**Required Permission:** `networks:create`

---

### GET /networks/{networkId}

Get network details.

**Response:** `200 OK`
```json
{
  "networkId": "homenet-lan",
  "displayName": "Home Network LAN",
  "type": "lan",
  "cidr": "192.168.1.0/24",
  "gateway": "192.168.1.1",
  "dns": ["192.168.1.1", "8.8.8.8"],
  "nodeCount": 15,
  "isAutoDiscovered": true,
  "discoveredAt": "2025-12-01T10:00:00Z"
}
```

**Required Permission:** `networks:read`

---

### PUT /networks/{networkId}

Update a network.

**Request Body:**
```json
{
  "displayName": "Updated Name",
  "description": "Updated description"
}
```

**Response:** `200 OK`
```json
{
  "networkId": "homenet-lan",
  "displayName": "Updated Name",
  "updatedAt": "2025-12-16T10:00:00Z"
}
```

**Required Permission:** `networks:update`

---

### DELETE /networks/{networkId}

Delete a network.

**Response:** `200 OK`
```json
{
  "message": "Network deleted",
  "networkId": "iot-vlan"
}
```

**Error:** `422 NETWORK_HAS_NODES` if network has associated nodes.

**Required Permission:** `networks:delete`

---

### GET /networks/{networkId}/nodes

Get nodes in a network.

**Response:** `200 OK`
```json
{
  "nodes": [
    {
      "nodeId": "proxmox-01",
      "displayName": "Proxmox Host 01",
      "ipAddresses": ["192.168.1.10"]
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

| Parameter | Type | Description |
|-----------|------|-------------|
| `mode` | enum | Filter by mode (`network`, `infrastructure`) |
| `limit` | integer | Max results |
| `offset` | integer | Pagination offset |

**Response:** `200 OK`
```json
{
  "topologies": [
    {
      "topologyId": "topo::infrastructure::20251216T120000Z",
      "mode": "infrastructure",
      "validFrom": "2025-12-16T12:00:00Z",
      "validUntil": null,
      "nodeCount": 15,
      "edgeCount": 24
    }
  ],
  "total": 50
}
```

**Required Permission:** `topologies:read`

---

### GET /topologies/latest

Get latest topology.

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `mode` | enum | Topology mode (`network`, `infrastructure`) |

**Response:** `200 OK`
```json
{
  "topologyId": "topo::infrastructure::20251216T120000Z",
  "mode": "infrastructure",
  "validFrom": "2025-12-16T12:00:00Z",
  "nodes": [
    {
      "id": "proxmox-01",
      "label": "Proxmox Host 01",
      "class": "compute",
      "status": "active",
      "x": 100,
      "y": 200
    }
  ],
  "edges": [
    {
      "source": "proxmox-01",
      "target": "vm-webserver",
      "type": "parent-child"
    }
  ]
}
```

**Required Permission:** `topologies:read`

---

### GET /topologies/{topologyId}

Get specific topology.

**Response:** `200 OK`

Same format as `/topologies/latest`.

**Required Permission:** `topologies:read`

---

### POST /topologies/generate

Trigger topology regeneration.

**Request Body:**
```json
{
  "mode": "infrastructure"
}
```

**Response:** `202 Accepted`
```json
{
  "message": "Topology generation started",
  "topologyId": "topo::infrastructure::20251216T130000Z"
}
```

**Required Permission:** `topologies:write`

---

### GET /topologies/diff

Compare two topologies.

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `from` | string | From topology ID |
| `to` | string | To topology ID |

**Response:** `200 OK`
```json
{
  "from": "topo::infrastructure::20251215T120000Z",
  "to": "topo::infrastructure::20251216T120000Z",
  "changes": {
    "nodesAdded": ["new-node"],
    "nodesRemoved": [],
    "edgesAdded": 2,
    "edgesRemoved": 0
  }
}
```

**Required Permission:** `topologies:read`

---

### GET /topologies/subgraph

Get subgraph centered on a node.

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `nodeId` | string | Yes | Center node |
| `depth` | integer | No | Traversal depth (default: 2) |
| `mode` | enum | No | Topology mode |

**Response:** `200 OK`

Returns a filtered topology containing only nodes within the specified depth.

**Required Permission:** `topologies:read`

---

## Time Machine

### GET /timemachine/node/{nodeId}

Get node state at a specific point in time.

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `at` | datetime | Yes | Target timestamp |

**Response:** `200 OK`
```json
{
  "nodeId": "proxmox-01",
  "timestamp": "2025-12-15T10:00:00Z",
  "state": {
    "status": "active",
    "profile": {
      "profileId": "prof_abc120",
      "version": "E0-0.1.2.42"
    },
    "services": [
      {
        "serviceId": "svc-nginx-c3d4",
        "status": "running"
      }
    ]
  }
}
```

**Required Permission:** `profiles:read`

---

### GET /timemachine/topology

Get topology at a specific point in time.

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `at` | datetime | Yes | Target timestamp |
| `mode` | enum | No | Topology mode |

**Response:** `200 OK`

Returns the topology that was valid at the specified timestamp.

**Required Permission:** `topologies:read`

---

### GET /timemachine/timeline

Get timeline of changes for a node or the system.

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `nodeId` | string | Filter by node |
| `from` | datetime | Start date |
| `to` | datetime | End date |
| `limit` | integer | Max results |

**Response:** `200 OK`
```json
{
  "events": [
    {
      "timestamp": "2025-12-16T06:00:00Z",
      "type": "profile_submitted",
      "nodeId": "proxmox-01",
      "details": {
        "version": "E0-0.1.2.46",
        "changes": ["hardware.memory"]
      }
    }
  ],
  "total": 100
}
```

**Required Permission:** `profiles:read`

---

## Commands

### POST /commands

Queue a command for execution.

**Request Body:**
```json
{
  "nodeId": "proxmox-01",
  "command": "systemctl restart nginx",
  "timeout": 30,
  "priority": "normal"
}
```

**Response:** `201 Created`
```json
{
  "commandId": "cmd_abc123",
  "nodeId": "proxmox-01",
  "command": "systemctl restart nginx",
  "status": "queued",
  "queuedAt": "2025-12-16T10:00:00Z",
  "queuedBy": "admin"
}
```

**Required Permission:** `commands:execute`

---

### GET /commands

List commands.

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `nodeId` | string | Filter by node |
| `status` | enum | Filter by status (`queued`, `executing`, `completed`, `failed`, `cancelled`) |
| `limit` | integer | Max results |
| `offset` | integer | Pagination offset |

**Response:** `200 OK`
```json
{
  "commands": [
    {
      "commandId": "cmd_abc123",
      "nodeId": "proxmox-01",
      "command": "systemctl restart nginx",
      "status": "completed",
      "queuedAt": "2025-12-16T10:00:00Z",
      "completedAt": "2025-12-16T10:00:05Z",
      "exitCode": 0
    }
  ],
  "total": 50
}
```

**Required Permission:** `commands:read`

---

### GET /commands/{commandId}

Get command details.

**Response:** `200 OK`
```json
{
  "commandId": "cmd_abc123",
  "nodeId": "proxmox-01",
  "command": "systemctl restart nginx",
  "status": "completed",
  "queuedAt": "2025-12-16T10:00:00Z",
  "startedAt": "2025-12-16T10:00:02Z",
  "completedAt": "2025-12-16T10:00:05Z",
  "exitCode": 0,
  "stdout": "Service restarted successfully",
  "stderr": ""
}
```

**Required Permission:** `commands:read`

---

### POST /commands/{commandId}/cancel

Cancel a queued command.

**Response:** `200 OK`
```json
{
  "commandId": "cmd_abc123",
  "status": "cancelled"
}
```

**Error:** `422 COMMAND_NOT_CANCELLABLE` if already executing/completed.

**Required Permission:** `commands:execute`

---

### GET /nodes/{nodeId}/commands/poll

Poll for pending commands (agent endpoint).

**Response:** `200 OK`
```json
{
  "commands": [
    {
      "commandId": "cmd_abc123",
      "command": "systemctl restart nginx",
      "timeout": 30
    }
  ]
}
```

**Required Permission:** `commands:poll` (agent)

---

### POST /nodes/{nodeId}/commands/{commandId}/result

Submit command result (agent endpoint).

**Request Body:**
```json
{
  "exitCode": 0,
  "stdout": "Service restarted successfully",
  "stderr": "",
  "executionTime": 3000
}
```

**Response:** `200 OK`
```json
{
  "message": "Result recorded"
}
```

**Required Permission:** `commands:poll` (agent)

---

## Home Assistant

### GET /ha/status

Get Home Assistant connection status.

**Response:** `200 OK`
```json
{
  "connected": true,
  "version": "2024.12.0",
  "url": "http://homeassistant.local:8123",
  "lastSyncAt": "2025-12-16T09:00:00Z",
  "deviceCount": 45,
  "areaCount": 8
}
```

**Required Permission:** `ha:read`

---

### GET /ha/devices

List Home Assistant devices.

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `area` | string | Filter by area |
| `domain` | string | Filter by domain (`light`, `switch`, `sensor`, etc.) |
| `search` | string | Search by name |
| `limit` | integer | Max results |
| `offset` | integer | Pagination offset |

**Response:** `200 OK`
```json
{
  "devices": [
    {
      "entityId": "light.living_room",
      "name": "Living Room Light",
      "domain": "light",
      "area": "Living Room",
      "state": "on",
      "attributes": {
        "brightness": 255,
        "color_temp": 370
      }
    }
  ],
  "total": 45
}
```

**Required Permission:** `ha:read`

---

### POST /ha/sync

Sync devices from Home Assistant.

**Response:** `200 OK`
```json
{
  "message": "Sync completed",
  "devicesAdded": 2,
  "devicesUpdated": 10,
  "devicesRemoved": 0,
  "syncedAt": "2025-12-16T10:00:00Z"
}
```

**Required Permission:** `ha:sync`

---

### POST /ha/control

Control a Home Assistant device.

**Request Body:**
```json
{
  "entityId": "light.living_room",
  "action": "turn_on",
  "parameters": {
    "brightness": 200,
    "color_temp": 400
  }
}
```

**Response:** `200 OK`
```json
{
  "entityId": "light.living_room",
  "action": "turn_on",
  "success": true,
  "newState": "on"
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
      "deviceCount": 8
    }
  ],
  "total": 8
}
```

**Required Permission:** `ha:read`

---

## AI Models

### GET /ai/models

List configured LLM providers.

**Response:** `200 OK`
```json
{
  "providers": [
    {
      "providerId": "anthropic-main",
      "name": "Anthropic Claude",
      "type": "anthropic",
      "model": "claude-3-5-sonnet-20241022",
      "isDefault": true,
      "isValid": true
    }
  ],
  "total": 2
}
```

**Required Permission:** Authenticated user

---

### POST /ai/models

Create LLM provider configuration.

**Request Body:**
```json
{
  "name": "Anthropic Claude",
  "type": "anthropic",
  "model": "claude-3-5-sonnet-20241022",
  "apiKey": "sk-ant-...",
  "isDefault": false
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Display name |
| `type` | enum | Yes | `anthropic`, `openai`, `ollama` |
| `model` | string | Yes | Model identifier |
| `apiKey` | string | Conditional | Required for anthropic/openai |
| `baseUrl` | string | No | Custom endpoint (for ollama) |
| `isDefault` | boolean | No | Set as default provider |

**Response:** `201 Created`
```json
{
  "providerId": "provider_abc123",
  "name": "Anthropic Claude",
  "type": "anthropic",
  "model": "claude-3-5-sonnet-20241022",
  "isDefault": false
}
```

**Required Permission:** Authenticated user

---

### GET /ai/models/{providerId}

Get LLM provider details.

**Response:** `200 OK`

Same as list item format.

---

### PUT /ai/models/{providerId}

Update LLM provider.

**Request Body:** Same as POST (all fields optional).

**Response:** `200 OK`

---

### DELETE /ai/models/{providerId}

Delete LLM provider.

**Response:** `200 OK`
```json
{
  "message": "Provider deleted"
}
```

---

### POST /ai/models/{providerId}/validate

Validate LLM provider configuration.

**Response:** `200 OK`
```json
{
  "valid": true,
  "message": "Connection successful",
  "responseTime": 450
}
```

---

## Chat

### GET /chat/projects

List chat projects.

**Response:** `200 OK`
```json
{
  "projects": [
    {
      "projectId": "proj_abc123",
      "name": "Infrastructure Analysis",
      "sessionCount": 5,
      "createdAt": "2025-12-01T10:00:00Z"
    }
  ],
  "total": 3
}
```

---

### POST /chat/projects

Create chat project.

**Request Body:**
```json
{
  "name": "New Project",
  "description": "Project description"
}
```

**Response:** `201 Created`

---

### GET /chat/projects/{projectId}

Get chat project.

---

### PUT /chat/projects/{projectId}

Update chat project.

---

### DELETE /chat/projects/{projectId}

Delete chat project.

---

### GET /chat/sessions

List chat sessions.

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `projectId` | string | Filter by project |
| `limit` | integer | Max results |
| `offset` | integer | Pagination offset |

**Response:** `200 OK`
```json
{
  "sessions": [
    {
      "sessionId": "sess_abc123",
      "projectId": "proj_abc123",
      "title": "Network troubleshooting",
      "messageCount": 12,
      "createdAt": "2025-12-16T09:00:00Z",
      "lastMessageAt": "2025-12-16T10:00:00Z"
    }
  ],
  "total": 5
}
```

---

### POST /chat/sessions

Create chat session.

**Request Body:**
```json
{
  "projectId": "proj_abc123",
  "title": "New Session",
  "providerId": "anthropic-main",
  "mcpServers": ["hydra-mcp"]
}
```

**Response:** `201 Created`

---

### GET /chat/sessions/{sessionId}

Get chat session.

---

### PUT /chat/sessions/{sessionId}

Update chat session.

---

### DELETE /chat/sessions/{sessionId}

Delete chat session.

---

### GET /chat/sessions/{sessionId}/messages

List messages in a session.

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `limit` | integer | Max results |
| `offset` | integer | Pagination offset |
| `order` | enum | `asc` or `desc` (default: asc) |

**Response:** `200 OK`
```json
{
  "messages": [
    {
      "messageId": "msg_abc123",
      "role": "user",
      "content": "List all production servers",
      "createdAt": "2025-12-16T10:00:00Z"
    },
    {
      "messageId": "msg_abc124",
      "role": "assistant",
      "content": "I found 8 production servers...",
      "toolCalls": [
        {
          "tool": "list_nodes",
          "arguments": {"tags": ["production"]}
        }
      ],
      "createdAt": "2025-12-16T10:00:05Z"
    }
  ],
  "total": 12
}
```

---

### POST /chat/sessions/{sessionId}/messages

Create a message (triggers AI response).

**Request Body:**
```json
{
  "content": "How many nodes are running?"
}
```

**Response:** `200 OK`
```json
{
  "userMessage": {
    "messageId": "msg_abc125",
    "role": "user",
    "content": "How many nodes are running?"
  },
  "assistantMessage": {
    "messageId": "msg_abc126",
    "role": "assistant",
    "content": "There are 15 active nodes..."
  }
}
```

---

### POST /chat/sessions/{sessionId}/messages/bulk

Bulk upsert messages (for syncing).

**Request Body:**
```json
{
  "messages": [
    {
      "messageId": "msg_abc123",
      "role": "user",
      "content": "Message content"
    }
  ]
}
```

**Response:** `200 OK`

---

### WebSocket /chat/ws

Real-time chat WebSocket connection.

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `sessionId` | string | Yes | Chat session ID |

**Message Format:**
```json
{
  "type": "message",
  "content": "User message"
}
```

**Response Events:**
- `message_start`: AI response started
- `content_delta`: Streaming content chunk
- `tool_call`: Tool invocation
- `message_end`: AI response complete

---

## MCP Servers

### GET /mcp/servers

List configured MCP servers.

**Response:** `200 OK`
```json
{
  "servers": [
    {
      "serverId": "hydra-mcp",
      "name": "Hydra MCP",
      "type": "builtin",
      "url": "http://localhost:8081",
      "status": "connected",
      "toolCount": 19
    }
  ],
  "total": 2
}
```

---

### POST /mcp/servers

Add MCP server.

**Request Body:**
```json
{
  "name": "Custom MCP",
  "url": "http://custom-mcp:8080",
  "apiKey": "optional-key"
}
```

**Response:** `201 Created`

---

### GET /mcp/servers/{serverId}

Get MCP server details.

---

### PUT /mcp/servers/{serverId}

Update MCP server.

---

### DELETE /mcp/servers/{serverId}

Remove MCP server.

---

### GET /mcp/servers/{serverId}/health

Check MCP server health.

**Response:** `200 OK`
```json
{
  "serverId": "hydra-mcp",
  "status": "healthy",
  "responseTime": 45,
  "checkedAt": "2025-12-16T10:00:00Z"
}
```

---

### GET /mcp/servers/{serverId}/tools

List tools available on MCP server.

**Response:** `200 OK`
```json
{
  "tools": [
    {
      "name": "list_nodes",
      "description": "List infrastructure nodes",
      "parameters": {
        "class": "Filter by node class",
        "status": "Filter by status"
      }
    }
  ],
  "total": 19
}
```

---

## Documentation

### GET /docs

List documentation.

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `category` | string | Filter by category |
| `search` | string | Search by title/content |
| `limit` | integer | Max results |
| `offset` | integer | Pagination offset |

**Response:** `200 OK`
```json
{
  "docs": [
    {
      "docId": "doc_abc123",
      "title": "Getting Started",
      "category": "guides",
      "createdAt": "2025-12-01T10:00:00Z",
      "updatedAt": "2025-12-15T10:00:00Z"
    }
  ],
  "total": 10
}
```

**Required Permission:** `docs:read`

---

### POST /docs

Create documentation.

**Request Body:**
```json
{
  "title": "New Document",
  "category": "guides",
  "content": "# Document Content\n\nMarkdown content here..."
}
```

**Response:** `201 Created`

**Required Permission:** `docs:create`

---

### GET /docs/{docId}

Get documentation by ID.

**Response:** `200 OK`
```json
{
  "docId": "doc_abc123",
  "title": "Getting Started",
  "category": "guides",
  "content": "# Getting Started\n\n...",
  "createdBy": "admin",
  "createdAt": "2025-12-01T10:00:00Z",
  "updatedAt": "2025-12-15T10:00:00Z"
}
```

**Required Permission:** `docs:read`

---

### PUT /docs/{docId}

Update documentation.

**Request Body:**
```json
{
  "title": "Updated Title",
  "content": "Updated content..."
}
```

**Response:** `200 OK`

**Required Permission:** `docs:update`

---

### DELETE /docs/{docId}

Delete documentation.

**Response:** `200 OK`

**Required Permission:** `docs:delete`

---

## Query & Analytics

### POST /query

Execute a raw query (admin only).

**Request Body:**
```json
{
  "collection": "nodes",
  "filter": {"status": "active"},
  "projection": {"nodeId": 1, "displayName": 1},
  "limit": 100
}
```

**Response:** `200 OK`
```json
{
  "results": [...],
  "count": 15,
  "executionTime": 45
}
```

**Required Permission:** `admin` role

---

### GET /capacity

Get infrastructure capacity summary.

**Response:** `200 OK`
```json
{
  "summary": {
    "totalNodes": 15,
    "activeNodes": 14,
    "totalServices": 156,
    "runningServices": 148
  },
  "byClass": {
    "compute": {"total": 10, "active": 9},
    "networking": {"total": 3, "active": 3},
    "iot": {"total": 2, "active": 2}
  },
  "resources": {
    "totalCpuCores": 64,
    "totalMemoryGb": 256,
    "totalStorageTb": 24
  }
}
```

**Required Permission:** `nodes:read`

---

### GET /audit

Get audit log.

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `userId` | string | Filter by user |
| `action` | string | Filter by action |
| `resource` | string | Filter by resource type |
| `from` | datetime | Start date |
| `to` | datetime | End date |
| `limit` | integer | Max results |
| `offset` | integer | Pagination offset |

**Response:** `200 OK`
```json
{
  "entries": [
    {
      "entryId": "audit_abc123",
      "timestamp": "2025-12-16T10:00:00Z",
      "userId": "user_abc123",
      "username": "admin",
      "action": "create",
      "resource": "node",
      "resourceId": "proxmox-01",
      "details": {...},
      "ipAddress": "192.168.1.100"
    }
  ],
  "total": 500
}
```

**Required Permission:** `audit:read`

---

## Search

### GET /search

Global infrastructure search.

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `q` | string | Yes | Search query |
| `types` | string | No | Comma-separated: `nodes`, `services`, `groups`, `networks` |
| `limit` | integer | No | Max results per type |

**Response:** `200 OK`
```json
{
  "query": "nginx",
  "results": {
    "nodes": [
      {"nodeId": "nginx-server", "displayName": "NGINX Server", "score": 0.95}
    ],
    "services": [
      {"serviceId": "svc-nginx-c3d4", "name": "nginx", "nodeId": "proxmox-01", "score": 1.0}
    ],
    "groups": [],
    "networks": []
  },
  "totalResults": 2
}
```

**Required Permission:** `nodes:read`

---

## Settings

### GET /settings

Get user settings.

**Response:** `200 OK`
```json
{
  "theme": "dark",
  "timezone": "America/New_York",
  "notifications": {
    "email": true,
    "desktop": true
  },
  "dashboard": {
    "defaultView": "topology",
    "refreshInterval": 30
  }
}
```

---

### PUT /settings

Update user settings.

**Request Body:**
```json
{
  "theme": "light",
  "timezone": "UTC"
}
```

**Response:** `200 OK`

---

### GET /settings/system

Get system settings (admin only).

**Response:** `200 OK`
```json
{
  "smtp": {
    "enabled": true,
    "host": "smtp.example.com",
    "port": 587
  },
  "objectStorage": {
    "enabled": true,
    "endpoint": "https://s3.example.com"
  },
  "registration": {
    "requireApproval": true,
    "allowedDomains": ["example.com"]
  }
}
```

**Required Permission:** `admin` role

---

### PUT /settings/system

Update system settings (admin only).

**Request Body:** Partial update of system settings.

**Response:** `200 OK`

**Required Permission:** `admin` role

---

## Agent Installation

### GET /agent/install

Get installation script.

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `version` | string | Agent version (default: latest) |
| `os` | string | Target OS (`linux`, `darwin`, `windows`) |

**Response:** `200 OK`

Returns shell script (bash or PowerShell).

---

### GET /agent/download

Download agent binary or source bundle.

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `version` | string | Version to download |
| `target` | string | Target platform (`linux-amd64`, `darwin-arm64`, etc.) |
| `source` | string | `obs` for source bundle |

**Response:** Binary file or redirect to object storage.

---

### GET /agent/versions

List available agent versions.

**Response:** `200 OK`
```json
{
  "versions": [
    {
      "version": "0.3.1",
      "releaseDate": "2025-12-15",
      "targets": ["linux-amd64", "linux-arm64", "darwin-amd64", "darwin-arm64", "windows-amd64"],
      "changelog": "Bug fixes and performance improvements"
    }
  ],
  "latest": "0.3.1"
}
```

---

## Appendices

### Node ID Format

Pattern: `^[a-z0-9][a-z0-9.-]{2,63}$`

Examples:
- `proxmox-01`
- `opnsense.gw`
- `ha-core`

---

### Service ID Format

Pattern: `svc-<name>-<hash>`

- `name`: Sanitized service name (lowercase, max 40 chars)
- `hash`: 4-character hash from `nodeId + runtime + name`

Examples:
- `svc-nginx-c3d4`
- `svc-mongodb-a1b2`
- `svc-api-gateway-e5f6`

---

### Profile Version Format

Pattern: `Ex-W.X.Y.Z` (hexadecimal)

- `E`: Epoch (breaking changes)
- `W`: Massive change (>75% sections)
- `X`: Major change (>50% sections)
- `Y`: Moderate change (>25% sections)
- `Z`: Minor change (any section)

Examples:
- `E0-0.0.0.1` — First profile
- `E0-0.0.1.0` — After 16 minor changes
- `E0-0.1.0.0` — Major change
- `E1-0.0.0.1` — New epoch

---

### Topology ID Format

Pattern: `topo::<mode>::<timestamp>`

- `mode`: `network` or `infrastructure`
- `timestamp`: ISO 8601 compact (`YYYYMMDDTHHmmssZ`)

Examples:
- `topo::network::20251216T120000Z`
- `topo::infrastructure::20251216T120000Z`

---

### Permission Format

Pattern: `resource:action`

**Resources:**
`nodes`, `profiles`, `services`, `groups`, `networks`, `topologies`, `docs`, `users`, `tokens`, `commands`, `iot`, `ha`, `audit`

**Actions:**
`read`, `write`, `create`, `update`, `delete`, `execute`, `control`, `poll`, `sync`, `*`

Examples:
- `nodes:read` — Read nodes
- `services:*` — All service operations
- `commands:execute` — Execute commands
- `*:*` — Full access (admin)

---

### Built-in Roles

| Role | Level | Max | Key Permissions |
|------|-------|-----|-----------------|
| `admin` | 100 | 2 | `*:*` |
| `operator` | 50 | 10 | `nodes:*`, `services:*`, `groups:*`, `networks:*`, `commands:execute` |
| `viewer` | 25 | ∞ | `*:read` (all read operations) |
| `family` | 10 | ∞ | `iot:*`, `ha:*` |
| `agent` | 0 | ∞ | `profiles:write` (own), `commands:poll` (own) |

---

### Supported Service Runtimes

| Runtime | Description |
|---------|-------------|
| `systemd` | Linux systemd services |
| `docker` | Docker containers |
| `podman` | Podman containers |
| `kubernetes` | Kubernetes pods |
| `rc` | BSD rc.d services |
| `openrc` | OpenRC services |
| `launchd` | macOS launchd services |
| `windows-service` | Windows services |

---

_For complete technical details, see the [Technical Documentation](Hydra%20Technical%20Documentation%20v0.3.0.md)._
