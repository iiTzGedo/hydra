
> **Version:** 0.3.0  
> **Component:** hydra-api (Python/FastAPI)  
> **Last Updated:** 2026-01-02

---

## Table of Contents

1. [Infrastructure & Deployment](https://claude.ai/chat/eb95da67-6ec0-436a-b5b8-0e3f9a851048#1-infrastructure--deployment)
2. [Health & System Endpoints](https://claude.ai/chat/eb95da67-6ec0-436a-b5b8-0e3f9a851048#2-health--system-endpoints)
3. [Authentication & Authorization](https://claude.ai/chat/eb95da67-6ec0-436a-b5b8-0e3f9a851048#3-authentication--authorization)
4. [User Management](https://claude.ai/chat/eb95da67-6ec0-436a-b5b8-0e3f9a851048#4-user-management)
5. [Node Management](https://claude.ai/chat/eb95da67-6ec0-436a-b5b8-0e3f9a851048#5-node-management)
6. [Profile Management](https://claude.ai/chat/eb95da67-6ec0-436a-b5b8-0e3f9a851048#6-profile-management)
7. [Service Management](https://claude.ai/chat/eb95da67-6ec0-436a-b5b8-0e3f9a851048#7-service-management)
8. [Group Management](https://claude.ai/chat/eb95da67-6ec0-436a-b5b8-0e3f9a851048#8-group-management)
9. [Network Management](https://claude.ai/chat/eb95da67-6ec0-436a-b5b8-0e3f9a851048#9-network-management)
10. [Topology Generation](https://claude.ai/chat/eb95da67-6ec0-436a-b5b8-0e3f9a851048#10-topology-generation)
11. [Time Machine](https://claude.ai/chat/eb95da67-6ec0-436a-b5b8-0e3f9a851048#11-time-machine)
12. [Command Execution](https://claude.ai/chat/eb95da67-6ec0-436a-b5b8-0e3f9a851048#12-command-execution)
13. [Documentation System](https://claude.ai/chat/eb95da67-6ec0-436a-b5b8-0e3f9a851048#13-documentation-system)
14. [Home Assistant Integration](https://claude.ai/chat/eb95da67-6ec0-436a-b5b8-0e3f9a851048#14-home-assistant-integration)
15. [Query & Analytics](https://claude.ai/chat/eb95da67-6ec0-436a-b5b8-0e3f9a851048#15-query--analytics)
16. [Performance & Scalability](https://claude.ai/chat/eb95da67-6ec0-436a-b5b8-0e3f9a851048#16-performance--scalability)
17. [Security](https://claude.ai/chat/eb95da67-6ec0-436a-b5b8-0e3f9a851048#17-security)
18. [Error Handling](https://claude.ai/chat/eb95da67-6ec0-436a-b5b8-0e3f9a851048#18-error-handling)

---

## 1. Infrastructure & Deployment

### 1.1 Service Startup

| #     | Test Case                                     | Expected Result                                    | Status |
| ----- | --------------------------------------------- | -------------------------------------------------- | ------ |
| 1.1.1 | Service starts with valid configuration       | Service binds to configured port (default: 8080)   | ☐      |
| 1.1.2 | Service fails gracefully with missing MongoDB | Returns 503 with clear error message               | ☐      |
| 1.1.3 | Service fails gracefully with missing Redis   | Returns 503 with clear error message               | ☐      |
| 1.1.4 | Service reads environment variables           | Correctly reads MONGODB_URI, REDIS_URL, JWT_SECRET | ☐      |
| 1.1.5 | Service reads YAML configuration              | Config file values applied correctly               | ☐      |
| 1.1.6 | Environment variables override config file    | ENV vars take precedence over YAML                 | ☐      |

### 1.2 Docker Deployment

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|1.2.1|Docker image builds successfully|No build errors, image tagged correctly|☐|
|1.2.2|Docker Compose stack starts|All services healthy within 60 seconds|☐|
|1.2.3|Service survives container restart|State preserved via volume mounts|☐|
|1.2.4|Health checks function in Docker|Docker reports container as healthy|☐|
|1.2.5|Resource limits respected|Container stays within memory/CPU limits|☐|

### 1.3 Database Connectivity

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|1.3.1|MongoDB connection established|Connection pool initialized|☐|
|1.3.2|MongoDB indexes created on startup|All required indexes exist|☐|
|1.3.3|Redis connection established|Redis ping returns PONG|☐|
|1.3.4|Handles MongoDB connection loss|Graceful degradation, retry logic|☐|
|1.3.5|Handles Redis connection loss|Queued operations preserved|☐|

---

## 2. Health & System Endpoints

### 2.1 GET /health

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|2.1.1|Returns 200 when all dependencies healthy|`{"status": "healthy"}` with all checks "ok"|☐|
|2.1.2|Returns 200 with degraded status|Shows failing checks but service available|☐|
|2.1.3|Returns 503 when unhealthy|Critical dependency failure|☐|
|2.1.4|No authentication required|Accessible without Bearer token|☐|
|2.1.5|Includes version information|Version matches deployment|☐|
|2.1.6|Includes uptime_seconds|Accurate uptime reported|☐|

### 2.2 GET /info

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|2.2.1|Returns service statistics|Node, service, network counts accurate|☐|
|2.2.2|Includes feature flags|Shows enabled/disabled features|☐|
|2.2.3|Includes API version|Returns "v1"|☐|
|2.2.4|Stats refresh on data changes|Counts update after CRUD operations|☐|

---

## 3. Authentication & Authorization

### 3.1 Bootstrap Flow (First User)

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|3.1.1|First user must be admin|Non-admin registration rejected with BOOTSTRAP_REQUIRES_ADMIN|☐|
|3.1.2|First admin created without token|201 Created with isBootstrap: true|☐|
|3.1.3|Second registration requires token/approval|Cannot bypass after bootstrap|☐|

### 3.2 POST /auth/register

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|3.2.1|Register with valid token|201 Created, user immediately active|☐|
|3.2.2|Register without token|202 Accepted, user in pending state|☐|
|3.2.3|Duplicate username rejected|409 USERNAME_ALREADY_EXISTS|☐|
|3.2.4|Duplicate email rejected|409 EMAIL_ALREADY_EXISTS|☐|
|3.2.5|Invalid email format rejected|400 VALIDATION_ERROR|☐|
|3.2.6|Password too short rejected|400 (min 8 chars)|☐|
|3.2.7|Username format validated|Pattern: ^[a-z0-9_-]{3,32}$|☐|
|3.2.8|Expired token rejected|401 AUTH_REGISTRATION_TOKEN_EXPIRED|☐|
|3.2.9|Used token rejected|401 AUTH_REGISTRATION_TOKEN_USED|☐|
|3.2.10|Role limit enforced|422 ROLE_LIMIT_EXCEEDED (2 admins, 10 operators)|☐|

### 3.3 POST /auth/login

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|3.3.1|Valid credentials return tokens|accessToken, refreshToken, expiresIn|☐|
|3.3.2|Invalid password rejected|401 AUTH_INVALID_CREDENTIALS|☐|
|3.3.3|Unknown username rejected|401 AUTH_INVALID_CREDENTIALS|☐|
|3.3.4|Locked account rejected|401 with account locked message|☐|
|3.3.5|lastLogin timestamp updated|User record shows login time|☐|
|3.3.6|Access token expires in 1 hour|expiresIn: 3600|☐|

### 3.4 POST /auth/refresh

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|3.4.1|Valid refresh token returns new access token|200 with new accessToken|☐|
|3.4.2|Expired refresh token rejected|401 AUTH_INVALID_TOKEN|☐|
|3.4.3|Invalid refresh token rejected|401 AUTH_INVALID_TOKEN|☐|
|3.4.4|Revoked refresh token rejected|401 AUTH_INVALID_TOKEN|☐|

### 3.5 GET /auth/me

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|3.5.1|Returns current user info|userId, username, role, permissions|☐|
|3.5.2|Includes temporary roles|Active temporaryRoles shown|☐|
|3.5.3|Agent token returns node context|type: "agent", nodeId present|☐|

### 3.6 User Approvals (Admin Only)

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|3.6.1|GET /auth/approvals lists pending|Returns pending users|☐|
|3.6.2|POST /auth/approvals approves user|User moved to active, can login|☐|
|3.6.3|DELETE /auth/approvals/{userId} rejects|User removed from pending|☐|
|3.6.4|Non-admin cannot access approvals|403 AUTH_INSUFFICIENT_PERMISSIONS|☐|
|3.6.5|Pending users auto-expire (7 days)|TTL index removes old pending|☐|

### 3.7 Registration Tokens

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|3.7.1|POST /auth/tokens creates token|Token with expiry returned|☐|
|3.7.2|maxUses enforced|Token invalidated after max uses|☐|
|3.7.3|allowedRoles enforced|Registration rejected if role not allowed|☐|
|3.7.4|Only admin can create tokens|403 for non-admin|☐|

### 3.8 API Keys

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|3.8.1|POST /auth/apikeys creates key|Key value returned only once|☐|
|3.8.2|API key authenticates requests|X-API-Key header accepted|☐|
|3.8.3|API key permissions enforced|Cannot exceed user's permissions|☐|
|3.8.4|DELETE /auth/apikeys/{keyId} revokes|Subsequent requests rejected|☐|
|3.8.5|Expired API key rejected|401 AUTH_INVALID_TOKEN|☐|
|3.8.6|lastUsedAt updated on use|Timestamp reflects last API call|☐|

### 3.9 JWT Validation

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|3.9.1|Valid JWT accepted|Request proceeds|☐|
|3.9.2|Expired JWT rejected|401 AUTH_INVALID_TOKEN|☐|
|3.9.3|Malformed JWT rejected|401 AUTH_INVALID_TOKEN|☐|
|3.9.4|Wrong signature rejected|401 AUTH_INVALID_TOKEN|☐|
|3.9.5|Missing Authorization header|401 AUTH_MISSING_TOKEN|☐|

---

## 4. User Management

### 4.1 GET /users

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|4.1.1|Lists all users (admin)|Returns paginated user list|☐|
|4.1.2|Filter by role|Returns only matching role|☐|
|4.1.3|Filter by status|Returns only matching status|☐|
|4.1.4|Search by username/email|Partial match search works|☐|
|4.1.5|Pagination works|limit, offset, total correct|☐|
|4.1.6|Requires users:read permission|403 for unauthorized|☐|

### 4.2 POST /users

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|4.2.1|Admin can create user|201 Created|☐|
|4.2.2|Password hashed with bcrypt|Not stored in plaintext|☐|
|4.2.3|Role limits enforced|Cannot exceed max per role|☐|
|4.2.4|Requires users:create permission|403 for unauthorized|☐|

### 4.3 GET /users/{userId}

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|4.3.1|Returns user details|Full user object|☐|
|4.3.2|User can view own profile|Own userId accessible|☐|
|4.3.3|Non-existent user|404 USER_NOT_FOUND|☐|

### 4.4 PATCH /users/{userId}

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|4.4.1|Update email|Email changed|☐|
|4.4.2|Update preferences|Theme, dashboard type saved|☐|
|4.4.3|User can update own limited fields|Email, preferences allowed|☐|
|4.4.4|User cannot change own role|403 for role change|☐|
|4.4.5|Admin can change user role|Role updated|☐|
|4.4.6|updatedAt timestamp set|Reflects modification time|☐|

### 4.5 DELETE /users/{userId}

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|4.5.1|Admin can delete user|User removed|☐|
|4.5.2|Cannot delete self|422 OPERATION_NOT_ALLOWED|☐|
|4.5.3|Cannot delete last admin|422 OPERATION_NOT_ALLOWED|☐|
|4.5.4|Requires users:delete permission|403 for unauthorized|☐|

### 4.6 Role Elevation

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|4.6.1|POST /users/{userId}/roles/elevate|Permanent role change|☐|
|4.6.2|Cannot elevate to admin if 2 exist|422 ROLE_LIMIT_EXCEEDED|☐|
|4.6.3|POST /users/{userId}/roles/grant-temporary|Temporary role added|☐|
|4.6.4|Temporary role expires|Role removed after expiresAt|☐|
|4.6.5|DELETE temporary role early|Role revoked immediately|☐|

---

## 5. Node Management

### 5.1 POST /node/register

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|5.1.1|Register new node with valid data|201 Created with nodeId|☐|
|5.1.2|API key generated for node|Node can authenticate|☐|
|5.1.3|Duplicate nodeId rejected|409 RESOURCE_ALREADY_EXISTS|☐|
|5.1.4|Invalid nodeId format rejected|400 INVALID_NODE_ID|☐|
|5.1.5|Required fields enforced|class, type, displayName required|☐|
|5.1.6|Requires admin/operator auth|Agent cannot register nodes|☐|
|5.1.7|registeredBy tracks user|Audit trail maintained|☐|

### 5.2 GET /nodes

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|5.2.1|Lists all active nodes|Paginated list returned|☐|
|5.2.2|Filter by class|compute, networking, iot|☐|
|5.2.3|Filter by type|physical, logical|☐|
|5.2.4|Filter by status|active, inactive, archived, pending|☐|
|5.2.5|Filter by tags|Nodes with matching tags|☐|
|5.2.6|Filter by networkId|Nodes in specific network|☐|
|5.2.7|Filter by parentNodeId|Child nodes of parent|☐|
|5.2.8|Text search on displayName/description|Partial match works|☐|
|5.2.9|Sort by lastProfileAt|Newest/oldest first|☐|
|5.2.10|Pagination correct|limit, offset, total accurate|☐|

### 5.3 GET /nodes/{nodeId}

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|5.3.1|Returns node details|Full node object|☐|
|5.3.2|includeChildren option|Shows child nodes|☐|
|5.3.3|includeServices option|Shows node's services|☐|
|5.3.4|includeLatestProfile option|Includes latest profile|☐|
|5.3.5|Non-existent node|404 NODE_NOT_FOUND|☐|

### 5.4 PATCH /nodes/{nodeId}

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|5.4.1|Update displayName|Name changed|☐|
|5.4.2|Update tags|Tags array updated|☐|
|5.4.3|Update location|Location object updated|☐|
|5.4.4|Update description|Description changed|☐|
|5.4.5|Cannot change nodeId|400 error|☐|
|5.4.6|Cannot change class/type|400 error|☐|
|5.4.7|lastUpdated timestamp set|Reflects modification time|☐|

### 5.5 DELETE /nodes/{nodeId}

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|5.5.1|Archives node (default)|Status set to archived|☐|
|5.5.2|Permanent delete with force=true|Node removed from DB|☐|
|5.5.3|Child nodes handled|Orphaned or cascaded|☐|
|5.5.4|Services archived|Node's services marked inactive|☐|
|5.5.5|Profile history preserved|Historical profiles remain|☐|

### 5.6 Node Validation

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|5.6.1|nodeId pattern enforced|^[a-z0-9][a-z0-9.-]{2,63}$|☐|
|5.6.2|class enum validated|compute, networking, iot only|☐|
|5.6.3|type enum validated|physical, logical only|☐|
|5.6.4|kind enum validated|Valid kinds per class|☐|
|5.6.5|tag format validated|^[a-z0-9]+[_:-]?[a-z0-9]*$|☐|

---

## 6. Profile Management

### 6.1 POST /profiles

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|6.1.1|Submit valid compute profile|201 Created with profileId|☐|
|6.1.2|Submit valid networking profile|201 Created|☐|
|6.1.3|Submit valid IoT profile|201 Created|☐|
|6.1.4|Schema validation per node class|Invalid schema rejected|☐|
|6.1.5|Version calculated automatically|Ex-W.X.Y.Z format|☐|
|6.1.6|First profile gets E0-0.0.0.1|Initial version correct|☐|
|6.1.7|Profile hash computed|Stored in profile_meta|☐|
|6.1.8|Section fingerprints computed|For diff optimization|☐|
|6.1.9|Services extracted and upserted|Services collection updated|☐|
|6.1.10|Networks auto-created|Network definitions created|☐|
|6.1.11|Topology regeneration triggered|Background job queued|☐|
|6.1.12|node.lastProfileAt updated|Timestamp reflects submission|☐|
|6.1.13|collectionLevel validated|shallow, neutral, deep|☐|
|6.1.14|Agent can only submit own node|403 for other nodes|☐|

### 6.2 Version Calculation

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|6.2.1|Identical profile = no version change|Same profileHash detected|☐|
|6.2.2|Minor change (<25%) increments Z|E0-0.0.0.1 → E0-0.0.0.2|☐|
|6.2.3|Moderate change (25-50%) increments Y|E0-0.0.0.F → E0-0.0.1.0|☐|
|6.2.4|Major change (50-75%) increments X|Appropriate version bump|☐|
|6.2.5|Massive change (>75%) increments W|Appropriate version bump|☐|
|6.2.6|Overflow behavior correct|Z > F → Y++, Z=0|☐|
|6.2.7|Section weights applied|hardware:30%, configs:25%, etc.|☐|

### 6.3 GET /profiles

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|6.3.1|Query profiles by nodeId|Returns node's profiles|☐|
|6.3.2|Query by date range|since, until parameters work|☐|
|6.3.3|Query by version|Specific version returned|☐|
|6.3.4|Pagination correct|limit, offset work|☐|
|6.3.5|Sort by submittedAt|Chronological order|☐|

### 6.4 GET /profiles/{profileId}

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|6.4.1|Returns full profile|All sections included|☐|
|6.4.2|sections parameter filters|Only requested sections|☐|
|6.4.3|Non-existent profile|404 PROFILE_NOT_FOUND|☐|

### 6.5 GET /nodes/{nodeId}/profiles/latest

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|6.5.1|Returns most recent profile|Latest submittedAt|☐|
|6.5.2|sections parameter works|Filters sections|☐|
|6.5.3|Node with no profiles|404 or empty response|☐|

### 6.6 GET /nodes/{nodeId}/profiles/diff

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|6.6.1|Diff between two versions|Changes highlighted|☐|
|6.6.2|Diff from specific version to latest|Current vs. historical|☐|
|6.6.3|Section-level changes identified|Which sections changed|☐|
|6.6.4|Uses hash fingerprints|O(1) comparison|☐|
|6.6.5|Change summary generated|Added, removed, modified counts|☐|

---

## 7. Service Management

### 7.1 Service Extraction

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|7.1.1|Services extracted from profile|serviceIds array populated|☐|
|7.1.2|Service ID format correct|svc::runtime::name|☐|
|7.1.3|Systemd services discovered|Runtime: systemd|☐|
|7.1.4|Docker containers discovered|Runtime: docker|☐|
|7.1.5|Kubernetes pods discovered|Runtime: kubernetes|☐|
|7.1.6|Service status captured|running, stopped, etc.|☐|
|7.1.7|Exposure info captured|Ports, endpoints|☐|

### 7.2 GET /services

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|7.2.1|Lists all services|Paginated list|☐|
|7.2.2|Filter by nodeId|Services on specific node|☐|
|7.2.3|Filter by runtime|systemd, docker, kubernetes|☐|
|7.2.4|Filter by status|running, stopped|☐|
|7.2.5|Filter by tags|Matching tags|☐|
|7.2.6|Search by name|Partial match|☐|

### 7.3 GET /services/{serviceId}

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|7.3.1|Returns service details|Full service object|☐|
|7.3.2|Includes exposure info|Ports, URLs|☐|
|7.3.3|Includes resource allocation|CPU, memory limits|☐|
|7.3.4|Non-existent service|404 SERVICE_NOT_FOUND|☐|

### 7.4 PATCH /services/{serviceId}

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|7.4.1|Update tags|Tags modified|☐|
|7.4.2|Update description|Description changed|☐|
|7.4.3|Cannot change serviceId|400 error|☐|
|7.4.4|Cannot change runtime|400 error|☐|

### 7.5 DELETE /services/{serviceId}

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|7.5.1|Archives service|Status set to archived|☐|
|7.5.2|Permanent delete option|Service removed|☐|

### 7.6 POST /services/{serviceId}/control

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|7.6.1|Start service|Command queued|☐|
|7.6.2|Stop service|Command queued|☐|
|7.6.3|Restart service|Command queued|☐|
|7.6.4|Reload service|Command queued|☐|
|7.6.5|Requires commands:execute permission|403 for unauthorized|☐|

---

## 8. Group Management

### 8.1 POST /groups

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|8.1.1|Create group with ID selector|Group created|☐|
|8.1.2|Create group with network selector|Network-based membership|☐|
|8.1.3|Create group with tag selector (isAny)|Any tag matches|☐|
|8.1.4|Create group with tag selector (isAll)|All tags required|☐|
|8.1.5|Create group with status selector|Status-based membership|☐|
|8.1.6|Create group with kind selector|Kind-based membership|☐|
|8.1.7|Create hierarchical group (parentGroupId)|Parent-child relationship|☐|
|8.1.8|Duplicate groupId rejected|409 error|☐|
|8.1.9|Invalid selector rejected|400 SELECTOR_VALIDATION_ERROR|☐|

### 8.2 GET /groups

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|8.2.1|Lists all groups|Paginated list|☐|
|8.2.2|Filter by types|nodes, services, both|☐|
|8.2.3|Filter by tags|Group tags|☐|
|8.2.4|Includes member counts|Cached counts accurate|☐|

### 8.3 GET /groups/{groupId}

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|8.3.1|Returns group details|Full group object|☐|
|8.3.2|resolveMembers option|Actual members returned|☐|
|8.3.3|Non-existent group|404 GROUP_NOT_FOUND|☐|

### 8.4 GET /groups/{groupId}/members

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|8.4.1|Returns resolved members|List of nodes/services|☐|
|8.4.2|Members match selectors|Correct entities included|☐|
|8.4.3|Member type filtering|nodes only, services only|☐|

### 8.5 POST /groups/{groupId}/resolve

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|8.5.1|Forces membership recalculation|Member counts updated|☐|
|8.5.2|Updates cachedMemberCount|Accurate count stored|☐|

### 8.6 PUT /groups/{groupId}

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|8.6.1|Update selectors|New selectors applied|☐|
|8.6.2|Update name/description|Metadata changed|☐|
|8.6.3|Triggers re-resolution|Members recalculated|☐|

### 8.7 DELETE /groups/{groupId}

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|8.7.1|Deletes group|Group removed|☐|
|8.7.2|Child groups handled|Orphaned or cascaded|☐|

---

## 9. Network Management

### 9.1 Auto-creation from Profiles

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|9.1.1|Network created from profile data|CIDR extracted and stored|☐|
|9.1.2|Duplicate network not created|Existing network matched|☐|
|9.1.3|Node added to network|networkIds updated|☐|
|9.1.4|origin.sourceNodeId tracked|First node that created it|☐|

### 9.2 POST /networks

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|9.2.1|Create manual network|201 Created|☐|
|9.2.2|VLAN network with vlanId|VLAN ID stored|☐|
|9.2.3|Parent network relationship|parentNetworkId works|☐|
|9.2.4|Router node association|routerNodeId linked|☐|
|9.2.5|DHCP configuration|Range stored|☐|
|9.2.6|DNS configuration|Servers stored|☐|
|9.2.7|Duplicate networkId rejected|409 error|☐|

### 9.3 GET /networks

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|9.3.1|Lists all networks|Paginated list|☐|
|9.3.2|Filter by type|physical, virtual, vlan|☐|
|9.3.3|Includes node counts|nodeCount accurate|☐|

### 9.4 GET /networks/{networkId}

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|9.4.1|Returns network details|Full network object|☐|
|9.4.2|includeNodes option|Nodes in network listed|☐|
|9.4.3|includeSubnets option|Child networks listed|☐|
|9.4.4|Non-existent network|404 NETWORK_NOT_FOUND|☐|

### 9.5 GET /networks/{networkId}/nodes

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|9.5.1|Returns nodes in network|List with IP addresses|☐|
|9.5.2|Pagination works|limit, offset correct|☐|

### 9.6 PUT /networks/{networkId}

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|9.6.1|Update network details|Changes saved|☐|
|9.6.2|Cannot change CIDR|400 error|☐|

### 9.7 DELETE /networks/{networkId}

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|9.7.1|Delete network without nodes|Network removed|☐|
|9.7.2|force=true with nodes|Network removed anyway|☐|
|9.7.3|Cannot delete with nodes (default)|422 error|☐|

---

## 10. Topology Generation

### 10.1 Automatic Generation

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|10.1.1|Triggered on profile change|New topology generated|☐|
|10.1.2|Periodic generation (configurable)|Interval respected|☐|
|10.1.3|Background job processing|Non-blocking operation|☐|

### 10.2 GET /topologies

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|10.2.1|Lists topology snapshots|Paginated list|☐|
|10.2.2|Filter by mode|network, infrastructure|☐|
|10.2.3|Sort by generatedAt|Chronological order|☐|

### 10.3 GET /topologies/latest

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|10.3.1|Returns most recent topology|Latest generatedAt|☐|
|10.3.2|mode parameter required|network or infrastructure|☐|
|10.3.3|Graph structure correct|Nodes and edges arrays|☐|

### 10.4 GET /topologies/{topologyId}

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|10.4.1|Returns specific topology|Full topology object|☐|
|10.4.2|Includes stats|nodeCount, edgeCount|☐|
|10.4.3|Includes diff from previous|Changes highlighted|☐|
|10.4.4|Non-existent topology|404 TOPOLOGY_NOT_FOUND|☐|

### 10.5 POST /topologies/generate

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|10.5.1|Trigger network topology generation|Job started|☐|
|10.5.2|Trigger infrastructure topology|Job started|☐|
|10.5.3|Scoped generation (networkIds)|Only specified networks|☐|
|10.5.4|Scoped generation (groupIds)|Only group members|☐|
|10.5.5|Returns jobId for tracking|202 Accepted|☐|

### 10.6 GET /topologies/diff

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|10.6.1|Compare two topologies|Diff returned|☐|
|10.6.2|nodesAdded identified|New nodes listed|☐|
|10.6.3|nodesRemoved identified|Removed nodes listed|☐|
|10.6.4|nodesModified identified|Changed nodes listed|☐|
|10.6.5|edgesAdded identified|New connections|☐|
|10.6.6|edgesRemoved identified|Removed connections|☐|

### 10.7 Graph Structure

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|10.7.1|Node types correct|compute-physical, network-router, etc.|☐|
|10.7.2|Edge types correct|network-connection, parent-child, etc.|☐|
|10.7.3|Network topology shows L2/L3|Proper network hierarchy|☐|
|10.7.4|Infrastructure topology shows hierarchy|Parent-child relationships|☐|
|10.7.5|Generation time < 5 seconds (100 nodes)|Performance target met|☐|

---

## 11. Time Machine

### 11.1 GET /timemachine/node/{nodeId}

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|11.1.1|Returns node state at timestamp|Reconstructed state|☐|
|11.1.2|Profile valid at time found|submittedAt <= timestamp|☐|
|11.1.3|Services at time included|Historical service state|☐|
|11.1.4|sections parameter filters|Only requested sections|☐|
|11.1.5|closestSnapshot info provided|Shows delta from actual|☐|
|11.1.6|Timestamp before first profile|Returns earliest available|☐|
|11.1.7|Response time < 1 second|Performance target met|☐|

### 11.2 GET /timemachine/topology

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|11.2.1|Returns topology at timestamp|Historical topology|☐|
|11.2.2|mode parameter required|network or infrastructure|☐|
|11.2.3|validFrom <= timestamp < validUntil|Correct topology found|☐|
|11.2.4|Timestamp before first topology|Returns earliest|☐|

### 11.3 GET /timemachine/timeline

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|11.3.1|Returns timeline events|Event stream|☐|
|11.3.2|since/until parameters work|Date range filtering|☐|
|11.3.3|nodeId filter works|Events for specific node|☐|
|11.3.4|types filter works|Specific event types|☐|
|11.3.5|Event types: profile, service, topology|All types present|☐|
|11.3.6|Events sorted chronologically|Correct order|☐|

---

## 12. Command Execution

### 12.1 POST /commands

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|12.1.1|Queue service command|202 Accepted with commandId|☐|
|12.1.2|Queue package command (admin only)|Command queued|☐|
|12.1.3|Queue config command (admin only)|Command queued|☐|
|12.1.4|Queue system command (admin only)|Command queued|☐|
|12.1.5|Permission check enforced|403 for unauthorized|☐|
|12.1.6|Target node validation|Node must exist|☐|
|12.1.7|Target service validation|Service must exist|☐|
|12.1.8|Timeout parameter respected|Default 60 seconds|☐|
|12.1.9|Command stored in Redis queue|For agent polling|☐|
|12.1.10|Audit log entry created|Command logged|☐|

### 12.2 GET /commands/{commandId}

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|12.2.1|Returns command status|queued, pending, running, completed, failed|☐|
|12.2.2|Includes result when completed|output, exitCode|☐|
|12.2.3|Includes error when failed|error message|☐|
|12.2.4|Non-existent command|404 COMMAND_NOT_FOUND|☐|

### 12.3 GET /commands

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|12.3.1|Lists command history|Paginated list|☐|
|12.3.2|Filter by nodeId|Commands for node|☐|
|12.3.3|Filter by status|Specific status|☐|
|12.3.4|Filter by type|Command type|☐|

### 12.4 POST /commands/{commandId}/cancel

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|12.4.1|Cancel queued command|Status set to cancelled|☐|
|12.4.2|Cannot cancel completed command|422 error|☐|
|12.4.3|Removed from Redis queue|Agent won't receive|☐|

### 12.5 Agent Polling

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|12.5.1|GET /nodes/{nodeId}/commands/poll|Returns pending commands|☐|
|12.5.2|Agent can only poll own node|403 for other nodes|☐|
|12.5.3|Commands marked as pending|Status updated|☐|
|12.5.4|POST .../result submits result|Command completed|☐|
|12.5.5|Requires commands:poll permission|Agent role|☐|

---

## 13. Documentation System

### 13.1 POST /docs

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|13.1.1|Create documentation|201 Created|☐|
|13.1.2|docId format validated|doc::slug-format|☐|
|13.1.3|linkedEntities stored|Entity references|☐|
|13.1.4|Version starts at 1|Initial version|☐|
|13.1.5|type validated|guide, architecture, runbook, etc.|☐|
|13.1.6|format validated|markdown, html|☐|

### 13.2 GET /docs

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|13.2.1|Lists documentation|Paginated list|☐|
|13.2.2|Filter by type|Specific doc type|☐|
|13.2.3|Filter by status|published, draft|☐|
|13.2.4|Filter by category|Category match|☐|
|13.2.5|Filter by linkedEntity|Docs for entity|☐|
|13.2.6|Full-text search|Content search|☐|

### 13.3 GET /docs/{docId}

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|13.3.1|Returns documentation|Full content|☐|
|13.3.2|version parameter|Specific version|☐|
|13.3.3|Non-existent doc|404 error|☐|

### 13.4 PUT /docs/{docId}

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|13.4.1|Update content|New version created|☐|
|13.4.2|Version incremented|Version + 1|☐|
|13.4.3|History preserved|Old versions available|☐|

### 13.5 DELETE /docs/{docId}

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|13.5.1|Archive (default)|Status set to archived|☐|
|13.5.2|permanent=true|Doc removed|☐|

---

## 14. Home Assistant Integration

### 14.1 GET /ha/status

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|14.1.1|Returns integration status|enabled, connected, lastSync|☐|
|14.1.2|Shows entity count|Number of HA entities|☐|
|14.1.3|Shows mapped node count|Hydra nodes from HA|☐|

### 14.2 GET /ha/devices

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|14.2.1|Lists HA devices|Entity list|☐|
|14.2.2|Filter by domain|climate, light, switch|☐|
|14.2.3|Filter by area|HA areas|☐|
|14.2.4|Shows Hydra node mapping|nodeId reference|☐|
|14.2.5|Includes current state|State and attributes|☐|

### 14.3 POST /ha/sync

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|14.3.1|Triggers HA sync|Job started|☐|
|14.3.2|domains filter works|Specific domains only|☐|
|14.3.3|createNodes option|Auto-create Hydra nodes|☐|
|14.3.4|Returns jobId|For tracking|☐|

### 14.4 POST /ha/control

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|14.4.1|Control HA device|Service called|☐|
|14.4.2|Returns new state|Updated device state|☐|
|14.4.3|Requires ha:control permission|403 for unauthorized|☐|
|14.4.4|Invalid entity rejected|404 error|☐|

### 14.5 GET /ha/areas

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|14.5.1|Lists HA areas|Area list|☐|
|14.5.2|Includes device/entity counts|Per area counts|☐|

---

## 15. Query & Analytics

### 15.1 POST /query

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|15.1.1|Query nodes collection|Results returned|☐|
|15.1.2|Query profiles collection|Results returned|☐|
|15.1.3|Query services collection|Results returned|☐|
|15.1.4|MongoDB filter syntax works|Complex filters|☐|
|15.1.5|Projection limits fields|Only requested fields|☐|
|15.1.6|Sort works|Correct order|☐|
|15.1.7|limit enforced (max 200)|Cannot exceed 200|☐|
|15.1.8|Permission check|Collection read permission|☐|

### 15.2 GET /capacity

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|15.2.1|Returns capacity summary|Total cores, RAM, storage|☐|
|15.2.2|groupBy=node|Per-node breakdown|☐|
|15.2.3|groupBy=class|Per-class breakdown|☐|
|15.2.4|groupBy=location|Per-location breakdown|☐|
|15.2.5|groupBy=network|Per-network breakdown|☐|
|15.2.6|includeLogical option|VMs/containers included|☐|
|15.2.7|groupId filter|Group members only|☐|
|15.2.8|Physical vs logical separation|No double-counting (default)|☐|

### 15.3 GET /audit

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|15.3.1|Lists audit entries|Paginated log|☐|
|15.3.2|Filter by action|CREATE, UPDATE, DELETE|☐|
|15.3.3|Filter by resource|nodes, services, etc.|☐|
|15.3.4|Filter by actor|User who performed action|☐|
|15.3.5|Date range filter|since, until|☐|
|15.3.6|Requires audit:read permission|Admin only|☐|

---

## 16. Performance & Scalability

### 16.1 Response Time Targets

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|16.1.1|Profile submission < 500ms|P0 target met|☐|
|16.1.2|Topology generation < 5s (100 nodes)|P0 target met|☐|
|16.1.3|Time Machine retrieval < 1s|P0 target met|☐|
|16.1.4|Command acknowledgment < 1s|P1 target met|☐|
|16.1.5|Node list (1000 nodes) < 2s|Scalability check|☐|

### 16.2 Rate Limiting

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|16.2.1|Auth endpoints: 10/minute|Rate limit enforced|☐|
|16.2.2|Profile submit: 100/minute|Rate limit enforced|☐|
|16.2.3|Read endpoints: 300/minute|Rate limit enforced|☐|
|16.2.4|Write endpoints: 30/minute|Rate limit enforced|☐|
|16.2.5|429 returned when exceeded|RATE_LIMIT_EXCEEDED|☐|
|16.2.6|Rate limit headers present|X-RateLimit-* headers|☐|

### 16.3 Database Performance

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|16.3.1|Indexes used for common queries|Explain plan shows index use|☐|
|16.3.2|Text search performs well|Full-text indexes work|☐|
|16.3.3|Profile history queries efficient|Compound index on nodeId, submittedAt|☐|
|16.3.4|Connection pooling works|Pool reused|☐|

---

## 17. Security

### 17.1 Authentication Security

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|17.1.1|Passwords hashed with bcrypt|Not stored plaintext|☐|
|17.1.2|JWT secret rotation supported|New secret works|☐|
|17.1.3|Token refresh doesn't leak info|Minimal response|☐|
|17.1.4|Brute force protection|Account lockout|☐|

### 17.2 Authorization Security

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|17.2.1|RBAC enforced on all endpoints|Permission checks|☐|
|17.2.2|Resource-level permissions work|Fine-grained access|☐|
|17.2.3|Agent scoped to own node|Cannot access other nodes|☐|
|17.2.4|Temporary roles expire correctly|Access revoked|☐|

### 17.3 Data Security

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|17.3.1|No secrets in profiles|Sensitive data filtered|☐|
|17.3.2|Config files hashed only|No plaintext configs|☐|
|17.3.3|TLS for external traffic|HTTPS enforced|☐|
|17.3.4|Audit logging enabled|All writes logged|☐|

### 17.4 Input Validation

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|17.4.1|SQL injection prevented|Parameterized queries|☐|
|17.4.2|NoSQL injection prevented|Input sanitization|☐|
|17.4.3|XSS in stored data prevented|Output encoding|☐|
|17.4.4|Request size limits enforced|Large payloads rejected|☐|

---

## 18. Error Handling

### 18.1 Error Response Format

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|18.1.1|Consistent error structure|error.code, error.message, requestId|☐|
|18.1.2|400 for validation errors|VALIDATION_ERROR with details|☐|
|18.1.3|401 for auth failures|AUTH_* error codes|☐|
|18.1.4|403 for permission denied|AUTH_INSUFFICIENT_PERMISSIONS|☐|
|18.1.5|404 for not found|*_NOT_FOUND error codes|☐|
|18.1.6|409 for conflicts|*_ALREADY_EXISTS|☐|
|18.1.7|422 for business logic|OPERATION_NOT_ALLOWED|☐|
|18.1.8|429 for rate limits|RATE_LIMIT_EXCEEDED|☐|
|18.1.9|500 for server errors|INTERNAL_ERROR|☐|
|18.1.10|503 for dependencies|SERVICE_UNAVAILABLE|☐|

### 18.2 Error Logging

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|18.2.1|Errors logged with requestId|Correlation possible|☐|
|18.2.2|Stack traces in logs (not response)|Debug info available|☐|
|18.2.3|Structured JSON logs|Parseable format|☐|

---

## Progress Summary

|Section|Total Tests|Passed|Failed|Blocked|Not Started|
|---|---|---|---|---|---|
|1. Infrastructure|16|0|0|0|16|
|2. Health & System|10|0|0|0|10|
|3. Authentication|50|0|0|0|50|
|4. User Management|25|0|0|0|25|
|5. Node Management|30|0|0|0|30|
|6. Profile Management|30|0|0|0|30|
|7. Service Management|22|0|0|0|22|
|8. Group Management|20|0|0|0|20|
|9. Network Management|22|0|0|0|22|
|10. Topology|23|0|0|0|23|
|11. Time Machine|13|0|0|0|13|
|12. Commands|18|0|0|0|18|
|13. Documentation|13|0|0|0|13|
|14. Home Assistant|14|0|0|0|14|
|15. Query & Analytics|17|0|0|0|17|
|16. Performance|14|0|0|0|14|
|17. Security|14|0|0|0|14|
|18. Error Handling|13|0|0|0|13|
|**TOTAL**|**364**|**0**|**0**|**0**|**364**|

---

_Last Updated: 2026-01-02_