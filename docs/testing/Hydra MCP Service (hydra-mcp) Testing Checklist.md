
> **Version:** 0.3.0  
> **Component:** hydra-mcp (Python/MCP SDK)  
> **Last Updated:** 2026-01-02

---

## Table of Contents

1. [Service Setup & Configuration](https://claude.ai/chat/eb95da67-6ec0-436a-b5b8-0e3f9a851048#1-service-setup--configuration)
2. [MCP Protocol Compliance](https://claude.ai/chat/eb95da67-6ec0-436a-b5b8-0e3f9a851048#2-mcp-protocol-compliance)
3. [TOON Response Formatting](https://claude.ai/chat/eb95da67-6ec0-436a-b5b8-0e3f9a851048#3-toon-response-formatting)
4. [Node Tools](https://claude.ai/chat/eb95da67-6ec0-436a-b5b8-0e3f9a851048#4-node-tools)
5. [Service Tools](https://claude.ai/chat/eb95da67-6ec0-436a-b5b8-0e3f9a851048#5-service-tools)
6. [Organization Tools (Groups & Networks)](https://claude.ai/chat/eb95da67-6ec0-436a-b5b8-0e3f9a851048#6-organization-tools-groups--networks)
7. [Topology Tools](https://claude.ai/chat/eb95da67-6ec0-436a-b5b8-0e3f9a851048#7-topology-tools)
8. [Time Machine Tools](https://claude.ai/chat/eb95da67-6ec0-436a-b5b8-0e3f9a851048#8-time-machine-tools)
9. [Query Tools](https://claude.ai/chat/eb95da67-6ec0-436a-b5b8-0e3f9a851048#9-query-tools)
10. [Control Tools (Write Operations)](https://claude.ai/chat/eb95da67-6ec0-436a-b5b8-0e3f9a851048#10-control-tools-write-operations)
11. [MCP Resources](https://claude.ai/chat/eb95da67-6ec0-436a-b5b8-0e3f9a851048#11-mcp-resources)
12. [MCP Prompts](https://claude.ai/chat/eb95da67-6ec0-436a-b5b8-0e3f9a851048#12-mcp-prompts)
13. [API Client Integration](https://claude.ai/chat/eb95da67-6ec0-436a-b5b8-0e3f9a851048#13-api-client-integration)
14. [Error Handling](https://claude.ai/chat/eb95da67-6ec0-436a-b5b8-0e3f9a851048#14-error-handling)
15. [Performance & Caching](https://claude.ai/chat/eb95da67-6ec0-436a-b5b8-0e3f9a851048#15-performance--caching)
16. [Security](https://claude.ai/chat/eb95da67-6ec0-436a-b5b8-0e3f9a851048#16-security)

---

## 1. Service Setup & Configuration

### 1.1 Service Startup

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|1.1.1|Service starts with valid config|MCP server running|☐|
|1.1.2|Environment variables loaded|HYDRA_API_URL, etc.|☐|
|1.1.3|API connection validated|Health check on startup|☐|
|1.1.4|Transport mode configurable|stdio or SSE|☐|
|1.1.5|Logging initialized|JSON structured logs|☐|
|1.1.6|Graceful shutdown|Clean disconnect|☐|

### 1.2 Configuration

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|1.2.1|HYDRA_API_URL required|Clear error if missing|☐|
|1.2.2|HYDRA_API_KEY for auth|API key loaded|☐|
|1.2.3|MCP_TRANSPORT setting|stdio or sse|☐|
|1.2.4|LOG_LEVEL setting|info, debug, warn|☐|
|1.2.5|CACHE_TTL_SECONDS|Resource cache lifetime|☐|

### 1.3 Docker Deployment

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|1.3.1|Docker image builds|No build errors|☐|
|1.3.2|Container runs MCP server|Port 3000 exposed|☐|
|1.3.3|Environment injection|Docker env vars work|☐|
|1.3.4|Health endpoint|Docker health check|☐|

---

## 2. MCP Protocol Compliance

### 2.1 Protocol Handshake

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|2.1.1|Initialize request handled|Server capabilities returned|☐|
|2.1.2|Protocol version negotiated|Compatible version|☐|
|2.1.3|Server info returned|Name, version|☐|
|2.1.4|Capabilities declared|tools, resources, prompts|☐|

### 2.2 Tool Discovery

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|2.2.1|tools/list returns all tools|Complete tool list|☐|
|2.2.2|Tool schemas included|JSON schema for params|☐|
|2.2.3|Tool descriptions accurate|Clear descriptions|☐|

### 2.3 Resource Discovery

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|2.3.1|resources/list returns all|Complete resource list|☐|
|2.3.2|Resource URIs valid|infrastructure:// scheme|☐|
|2.3.3|Resource templates included|Dynamic URIs|☐|

### 2.4 Prompt Discovery

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|2.4.1|prompts/list returns all|Complete prompt list|☐|
|2.4.2|Prompt arguments defined|Input parameters|☐|
|2.4.3|Prompt descriptions useful|Guide LLM usage|☐|

### 2.5 Transport Modes

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|2.5.1|stdio transport works|Process communication|☐|
|2.5.2|SSE transport works|HTTP streaming|☐|
|2.5.3|WebSocket (if supported)|Real-time connection|☐|

---

## 3. TOON Response Formatting

### 3.1 Hierarchy Formatting

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|3.1.1|Tree structure rendered|├── and └── chars|☐|
|3.1.2|Proper indentation|Nested levels clear|☐|
|3.1.3|Section headers|ALL CAPS with ===|☐|
|3.1.4|Subsection headers|Title Case with ---|☐|

### 3.2 List Formatting

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|3.2.1|Numbered lists|1. 2. 3. format|☐|
|3.2.2|Bulleted lists|• or - format|☐|
|3.2.3|Key-value pairs|Key: Value format|☐|
|3.2.4|Tables (where appropriate)|Aligned columns|☐|

### 3.3 Infrastructure Overview Format

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|3.3.1|Node counts by class|Compute, Networking, IoT|☐|
|3.3.2|Service counts by runtime|systemd, docker|☐|
|3.3.3|Network summary|Networks with node counts|☐|
|3.3.4|Last profile timestamp|Recent activity|☐|

### 3.4 Entity Detail Format

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|3.4.1|Node details|Hardware, network, services|☐|
|3.4.2|Service details|Status, ports, runtime|☐|
|3.4.3|Network details|CIDR, gateway, nodes|☐|
|3.4.4|Profile sections|Structured data display|☐|

---

## 4. Node Tools

### 4.1 `list_nodes` Tool

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|4.1.1|No parameters lists all|All active nodes|☐|
|4.1.2|class filter|compute/networking/iot|☐|
|4.1.3|type filter|physical/logical|☐|
|4.1.4|status filter|active/inactive/archived|☐|
|4.1.5|tags filter|Tag-based filtering|☐|
|4.1.6|limit parameter|Pagination|☐|
|4.1.7|Empty result handling|"No nodes found" message|☐|
|4.1.8|TOON formatted output|Readable list|☐|

### 4.2 `get_node` Tool

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|4.2.1|Returns node by nodeId|Node details|☐|
|4.2.2|includeChildren option|Shows child nodes|☐|
|4.2.3|includeServices option|Shows services|☐|
|4.2.4|Invalid nodeId|Clear error message|☐|
|4.2.5|TOON formatted output|Readable details|☐|

### 4.3 `get_node_profile` Tool

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|4.3.1|Returns latest profile|Most recent snapshot|☐|
|4.3.2|sections[] parameter|Filter to specific sections|☐|
|4.3.3|hardware section|CPU, RAM, system info|☐|
|4.3.4|network section|Interfaces, IPs|☐|
|4.3.5|storage section|Disks, filesystems|☐|
|4.3.6|software section|OS, packages|☐|
|4.3.7|services section|Service list|☐|
|4.3.8|Node has no profile|Clear message|☐|
|4.3.9|TOON formatted output|Structured profile|☐|

---

## 5. Service Tools

### 5.1 `list_services` Tool

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|5.1.1|No parameters lists all|All services|☐|
|5.1.2|nodeId filter|Services on specific node|☐|
|5.1.3|runtime filter|systemd/docker/kubernetes|☐|
|5.1.4|status filter|running/stopped|☐|
|5.1.5|limit parameter|Pagination|☐|
|5.1.6|Empty result handling|"No services found"|☐|
|5.1.7|TOON formatted output|Service list|☐|

### 5.2 `get_service` Tool

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|5.2.1|Returns service by serviceId|Service details|☐|
|5.2.2|Shows port exposure|Exposed ports|☐|
|5.2.3|Shows resource allocation|CPU, memory limits|☐|
|5.2.4|Shows node association|Host node|☐|
|5.2.5|Invalid serviceId|Clear error|☐|
|5.2.6|TOON formatted output|Readable details|☐|

---

## 6. Organization Tools (Groups & Networks)

### 6.1 `list_groups` Tool

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|6.1.1|Lists all groups|Group list|☐|
|6.1.2|types[] filter|nodes/services/both|☐|
|6.1.3|tags filter|Group tags|☐|
|6.1.4|Shows member counts|Cached counts|☐|
|6.1.5|TOON formatted output|Group hierarchy|☐|

### 6.2 `get_group` Tool

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|6.2.1|Returns group by groupId|Group details|☐|
|6.2.2|resolveMembers option|Actual members listed|☐|
|6.2.3|Shows selectors|Group criteria|☐|
|6.2.4|Shows parent/children|Hierarchy|☐|
|6.2.5|Invalid groupId|Clear error|☐|
|6.2.6|TOON formatted output|Readable details|☐|

### 6.3 `list_networks` Tool

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|6.3.1|Lists all networks|Network list|☐|
|6.3.2|type filter|physical/virtual/vlan|☐|
|6.3.3|Shows CIDR|Network range|☐|
|6.3.4|Shows node counts|Nodes per network|☐|
|6.3.5|TOON formatted output|Network summary|☐|

### 6.4 `get_network` Tool

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|6.4.1|Returns network by networkId|Network details|☐|
|6.4.2|includeNodes option|Nodes in network|☐|
|6.4.3|Shows gateway|Gateway IP|☐|
|6.4.4|Shows DHCP config|DHCP settings|☐|
|6.4.5|Shows DNS config|DNS servers|☐|
|6.4.6|Invalid networkId|Clear error|☐|
|6.4.7|TOON formatted output|Readable details|☐|

---

## 7. Topology Tools

### 7.1 `get_topology` Tool

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|7.1.1|mode=network|Network topology|☐|
|7.1.2|mode=infrastructure|Infrastructure hierarchy|☐|
|7.1.3|scope parameter|Filtered topology|☐|
|7.1.4|Returns nodes array|Topology nodes|☐|
|7.1.5|Returns edges array|Connections|☐|
|7.1.6|Node types described|compute-physical, etc.|☐|
|7.1.7|Edge types described|network-connection, etc.|☐|
|7.1.8|TOON formatted output|Readable topology|☐|

### 7.2 `compare_profiles` Tool

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|7.2.1|Compare two versions|Diff output|☐|
|7.2.2|fromVersion parameter|Starting version|☐|
|7.2.3|toVersion parameter|Ending version (or latest)|☐|
|7.2.4|Shows sections changed|Which sections|☐|
|7.2.5|Shows change details|What changed|☐|
|7.2.6|TOON formatted diff|Readable comparison|☐|

---

## 8. Time Machine Tools

### 8.1 `time_machine_node` Tool

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|8.1.1|nodeId parameter|Target node|☐|
|8.1.2|timestamp parameter|Historical point|☐|
|8.1.3|Returns node state at time|Reconstructed state|☐|
|8.1.4|Shows profile version at time|Which profile was active|☐|
|8.1.5|Shows services at time|Historical services|☐|
|8.1.6|Timestamp parsing|ISO 8601 format|☐|
|8.1.7|Relative time support|"yesterday", "last week"|☐|
|8.1.8|TOON formatted output|Readable state|☐|

### 8.2 `time_machine_topology` Tool

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|8.2.1|mode parameter|network/infrastructure|☐|
|8.2.2|timestamp parameter|Historical point|☐|
|8.2.3|Returns topology at time|Historical topology|☐|
|8.2.4|Shows changes from current|Diff indicator|☐|
|8.2.5|TOON formatted output|Readable topology|☐|

---

## 9. Query Tools

### 9.1 `search_infrastructure` Tool

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|9.1.1|query parameter|Search term|☐|
|9.1.2|types[] parameter|nodes/services/networks|☐|
|9.1.3|limit parameter|Max results|☐|
|9.1.4|Searches displayName|Name matches|☐|
|9.1.5|Searches description|Description matches|☐|
|9.1.6|Searches tags|Tag matches|☐|
|9.1.7|Cross-entity results|Mixed types|☐|
|9.1.8|TOON formatted output|Search results|☐|

### 9.2 `get_capacity` Tool

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|9.2.1|No parameters|Full capacity summary|☐|
|9.2.2|groupBy=node|Per-node breakdown|☐|
|9.2.3|groupBy=class|Per-class breakdown|☐|
|9.2.4|groupBy=location|Per-location breakdown|☐|
|9.2.5|groupBy=network|Per-network breakdown|☐|
|9.2.6|includeLogical option|Include VMs|☐|
|9.2.7|Shows total CPU cores|Aggregate|☐|
|9.2.8|Shows total RAM|Aggregate|☐|
|9.2.9|Shows total storage|Aggregate|☐|
|9.2.10|TOON formatted output|Capacity report|☐|

### 9.3 `query_infrastructure` Tool

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|9.3.1|collection parameter|Target collection|☐|
|9.3.2|filter parameter|MongoDB-style filter|☐|
|9.3.3|projection parameter|Field selection|☐|
|9.3.4|Complex queries work|Nested filters|☐|
|9.3.5|Dangerous queries blocked|Injection prevention|☐|
|9.3.6|TOON formatted output|Query results|☐|

---

## 10. Control Tools (Write Operations)

### 10.1 `control_service` Tool

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|10.1.1|serviceId parameter|Target service|☐|
|10.1.2|action=start|Start service|☐|
|10.1.3|action=stop|Stop service|☐|
|10.1.4|action=restart|Restart service|☐|
|10.1.5|action=reload|Reload config|☐|
|10.1.6|Returns command status|Queued confirmation|☐|
|10.1.7|Permission check|Requires commands:execute|☐|
|10.1.8|TOON formatted output|Action confirmation|☐|

### 10.2 `control_device` Tool (Home Assistant)

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|10.2.1|nodeId parameter|Target IoT device|☐|
|10.2.2|command parameter|HA service call|☐|
|10.2.3|parameters object|Command parameters|☐|
|10.2.4|Light on/off|Light control|☐|
|10.2.5|Thermostat set temp|Climate control|☐|
|10.2.6|Switch toggle|Switch control|☐|
|10.2.7|Permission check|Requires ha:control|☐|
|10.2.8|Returns new state|Device state after|☐|
|10.2.9|TOON formatted output|Action confirmation|☐|

---

## 11. MCP Resources

### 11.1 Static Resources

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|11.1.1|infrastructure://overview|High-level summary|☐|
|11.1.2|infrastructure://nodes|All nodes list|☐|
|11.1.3|infrastructure://services|All services list|☐|
|11.1.4|infrastructure://networks|All networks list|☐|
|11.1.5|infrastructure://topology/network|Network topology|☐|
|11.1.6|infrastructure://topology/infrastructure|Infra topology|☐|

### 11.2 Dynamic Resources

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|11.2.1|infrastructure://node/{nodeId}|Specific node|☐|
|11.2.2|infrastructure://service/{serviceId}|Specific service|☐|
|11.2.3|infrastructure://network/{networkId}|Specific network|☐|
|11.2.4|infrastructure://group/{groupId}|Specific group|☐|
|11.2.5|Invalid URI handled|Clear error|☐|

### 11.3 Resource Content

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|11.3.1|MIME type text/plain|For TOON output|☐|
|11.3.2|Optional JSON format|application/json|☐|
|11.3.3|Resource URI in response|Identifies resource|☐|
|11.3.4|Resource name in response|Human-readable|☐|

### 11.4 Resource Caching

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|11.4.1|Cache populated on first access|Cached data|☐|
|11.4.2|Cache TTL honored|Expiration works|☐|
|11.4.3|Cache invalidation on changes|Fresh data|☐|
|11.4.4|Cache miss handled|Fetch from API|☐|

---

## 12. MCP Prompts

### 12.1 `capacity_planning` Prompt

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|12.1.1|workload_description argument|Required input|☐|
|12.1.2|Includes current capacity|Base context|☐|
|12.1.3|Suggests placement|Where to deploy|☐|
|12.1.4|Identifies constraints|Resource limits|☐|
|12.1.5|TOON formatted output|Analysis report|☐|

### 12.2 `troubleshoot_network` Prompt

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|12.2.1|symptom argument|Problem description|☐|
|12.2.2|target_node argument|Optional focus node|☐|
|12.2.3|Includes network topology|Context|☐|
|12.2.4|Suggests diagnostics|What to check|☐|
|12.2.5|TOON formatted output|Troubleshooting guide|☐|

### 12.3 `infrastructure_audit` Prompt

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|12.3.1|audit_type argument|security/config/all|☐|
|12.3.2|scope argument|Optional scope|☐|
|12.3.3|Reviews configurations|Config analysis|☐|
|12.3.4|Identifies issues|Problems found|☐|
|12.3.5|Provides recommendations|Fix suggestions|☐|
|12.3.6|TOON formatted output|Audit report|☐|

### 12.4 `service_dependency_map` Prompt

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|12.4.1|service argument|Target service|☐|
|12.4.2|Maps dependencies|What service needs|☐|
|12.4.3|Maps dependents|What depends on service|☐|
|12.4.4|Impact analysis|Failure impact|☐|
|12.4.5|TOON formatted output|Dependency tree|☐|

### 12.5 `migration_planning` Prompt

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|12.5.1|source argument|Source node/service|☐|
|12.5.2|destination argument|Target location|☐|
|12.5.3|Analyzes requirements|What's needed|☐|
|12.5.4|Creates checklist|Migration steps|☐|
|12.5.5|Identifies risks|Potential issues|☐|
|12.5.6|TOON formatted output|Migration plan|☐|

### 12.6 `documentation_generator` Prompt

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|12.6.1|entity_type argument|node/service/network|☐|
|12.6.2|entity_id argument|Target entity|☐|
|12.6.3|Generates markdown|Documentation content|☐|
|12.6.4|Includes configuration|Settings documented|☐|
|12.6.5|Includes relationships|Dependencies|☐|
|12.6.6|TOON formatted output|Doc template|☐|

---

## 13. API Client Integration

### 13.1 HTTP Client

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|13.1.1|API key authentication|X-API-Key header|☐|
|13.1.2|Base URL configuration|Correct endpoint|☐|
|13.1.3|Request timeout|Configurable timeout|☐|
|13.1.4|Connection pooling|Efficient connections|☐|

### 13.2 Error Handling

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|13.2.1|API 401 handled|Auth error message|☐|
|13.2.2|API 403 handled|Permission error|☐|
|13.2.3|API 404 handled|Not found error|☐|
|13.2.4|API 500 handled|Server error message|☐|
|13.2.5|API timeout handled|Timeout message|☐|
|13.2.6|Connection refused|Clear error|☐|

### 13.3 Response Parsing

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|13.3.1|JSON response parsed|Data extracted|☐|
|13.3.2|Pagination handled|All pages fetched|☐|
|13.3.3|Empty response handled|Empty result|☐|
|13.3.4|Malformed JSON handled|Parse error|☐|

---

## 14. Error Handling

### 14.1 Tool Errors

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|14.1.1|Missing required parameter|Clear error message|☐|
|14.1.2|Invalid parameter value|Validation error|☐|
|14.1.3|Entity not found|404 translated to message|☐|
|14.1.4|Permission denied|403 translated to message|☐|
|14.1.5|API unreachable|Connection error|☐|

### 14.2 Resource Errors

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|14.2.1|Invalid URI|URI parse error|☐|
|14.2.2|Resource not found|Clear message|☐|
|14.2.3|Cache miss + API error|Fallback handling|☐|

### 14.3 Prompt Errors

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|14.3.1|Missing arguments|Argument required|☐|
|14.3.2|Invalid argument values|Validation error|☐|
|14.3.3|Context fetch failure|Graceful degradation|☐|

### 14.4 Error Response Format

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|14.4.1|MCP error format|isError: true|☐|
|14.4.2|Human-readable message|Clear description|☐|
|14.4.3|No stack traces to client|Security|☐|
|14.4.4|Error logged server-side|Debug info available|☐|

---

## 15. Performance & Caching

### 15.1 Response Time

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|15.1.1|Tool response < 2 seconds|P0 target|☐|
|15.1.2|Resource response < 2 seconds|P0 target|☐|
|15.1.3|Prompt response < 3 seconds|Reasonable|☐|
|15.1.4|Cached responses faster|Sub-second|☐|

### 15.2 Caching Strategy

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|15.2.1|Resource caching enabled|TTL-based cache|☐|
|15.2.2|Cache key generation|Unique per resource|☐|
|15.2.3|Cache invalidation|On data changes|☐|
|15.2.4|Cache size limits|Memory bounded|☐|

### 15.3 Concurrency

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|15.3.1|Multiple concurrent tools|All complete|☐|
|15.3.2|Async API calls|Non-blocking|☐|
|15.3.3|Rate limiting (if needed)|Prevents API overload|☐|

---

## 16. Security

### 16.1 Authentication

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|16.1.1|API key required|Cannot start without|☐|
|16.1.2|API key validated|Invalid key rejected|☐|
|16.1.3|Expired key handling|Clear error|☐|

### 16.2 Authorization

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|16.2.1|Tool permissions enforced|API enforces RBAC|☐|
|16.2.2|Control tools restricted|commands:execute needed|☐|
|16.2.3|HA control restricted|ha:control needed|☐|
|16.2.4|Error messages don't leak|No internal details|☐|

### 16.3 Input Validation

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|16.3.1|Parameter sanitization|Injection prevented|☐|
|16.3.2|Query filter validation|Safe queries only|☐|
|16.3.3|URI validation|Valid URIs only|☐|

---

## Progress Summary

|Section|Total Tests|Passed|Failed|Blocked|Not Started|
|---|---|---|---|---|---|
|1. Service Setup|10|0|0|0|10|
|2. MCP Protocol|14|0|0|0|14|
|3. TOON Formatting|16|0|0|0|16|
|4. Node Tools|21|0|0|0|21|
|5. Service Tools|13|0|0|0|13|
|6. Organization Tools|22|0|0|0|22|
|7. Topology Tools|14|0|0|0|14|
|8. Time Machine Tools|13|0|0|0|13|
|9. Query Tools|18|0|0|0|18|
|10. Control Tools|17|0|0|0|17|
|11. MCP Resources|18|0|0|0|18|
|12. MCP Prompts|31|0|0|0|31|
|13. API Client|14|0|0|0|14|
|14. Error Handling|16|0|0|0|16|
|15. Performance|11|0|0|0|11|
|16. Security|11|0|0|0|11|
|**TOTAL**|**259**|**0**|**0**|**0**|**259**|

---

_Last Updated: 2026-01-02_