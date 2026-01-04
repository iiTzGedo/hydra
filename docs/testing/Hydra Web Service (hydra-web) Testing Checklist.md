
> **Version:** 0.3.0  
> **Component:** hydra-web (React/TypeScript)  
> **Last Updated:** 2026-01-02

---

## Table of Contents

1. [Build & Deployment](https://claude.ai/chat/eb95da67-6ec0-436a-b5b8-0e3f9a851048#1-build--deployment)
2. [Authentication UI](https://claude.ai/chat/eb95da67-6ec0-436a-b5b8-0e3f9a851048#2-authentication-ui)
3. [Layout & Navigation](https://claude.ai/chat/eb95da67-6ec0-436a-b5b8-0e3f9a851048#3-layout--navigation)
4. [Dashboard](https://claude.ai/chat/eb95da67-6ec0-436a-b5b8-0e3f9a851048#4-dashboard)
5. [Node Explorer](https://claude.ai/chat/eb95da67-6ec0-436a-b5b8-0e3f9a851048#5-node-explorer)
6. [Service Explorer](https://claude.ai/chat/eb95da67-6ec0-436a-b5b8-0e3f9a851048#6-service-explorer)
7. [Network Explorer](https://claude.ai/chat/eb95da67-6ec0-436a-b5b8-0e3f9a851048#7-network-explorer)
8. [Group Management](https://claude.ai/chat/eb95da67-6ec0-436a-b5b8-0e3f9a851048#8-group-management)
9. [Topology Viewer](https://claude.ai/chat/eb95da67-6ec0-436a-b5b8-0e3f9a851048#9-topology-viewer)
10. [Time Machine](https://claude.ai/chat/eb95da67-6ec0-436a-b5b8-0e3f9a851048#10-time-machine)
11. [MCP Chat Interface](https://claude.ai/chat/eb95da67-6ec0-436a-b5b8-0e3f9a851048#11-mcp-chat-interface)
12. [Admin Dashboard](https://claude.ai/chat/eb95da67-6ec0-436a-b5b8-0e3f9a851048#12-admin-dashboard)
13. [Home Dashboard (Family View)](https://claude.ai/chat/eb95da67-6ec0-436a-b5b8-0e3f9a851048#13-home-dashboard-family-view)
14. [Documentation Viewer](https://claude.ai/chat/eb95da67-6ec0-436a-b5b8-0e3f9a851048#14-documentation-viewer)
15. [Responsive Design & UX](https://claude.ai/chat/eb95da67-6ec0-436a-b5b8-0e3f9a851048#15-responsive-design--ux)
16. [State Management](https://claude.ai/chat/eb95da67-6ec0-436a-b5b8-0e3f9a851048#16-state-management)
17. [API Integration](https://claude.ai/chat/eb95da67-6ec0-436a-b5b8-0e3f9a851048#17-api-integration)
18. [Performance](https://claude.ai/chat/eb95da67-6ec0-436a-b5b8-0e3f9a851048#18-performance)
19. [Accessibility](https://claude.ai/chat/eb95da67-6ec0-436a-b5b8-0e3f9a851048#19-accessibility)
20. [Browser Compatibility](https://claude.ai/chat/eb95da67-6ec0-436a-b5b8-0e3f9a851048#20-browser-compatibility)

---

## 1. Build & Deployment

### 1.1 Development Build

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|1.1.1|`npm install` completes|All dependencies installed|☐|
|1.1.2|`npm run dev` starts|Vite dev server on port 5173|☐|
|1.1.3|Hot module replacement works|Changes reflect instantly|☐|
|1.1.4|TypeScript compilation|No type errors|☐|
|1.1.5|ESLint passes|No linting errors|☐|

### 1.2 Production Build

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|1.2.1|`npm run build` completes|dist/ folder created|☐|
|1.2.2|Bundle size reasonable|< 500KB gzipped|☐|
|1.2.3|Source maps generated|For debugging|☐|
|1.2.4|Assets optimized|Images compressed|☐|
|1.2.5|Tree shaking works|Unused code removed|☐|

### 1.3 Docker Deployment

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|1.3.1|Docker image builds|No build errors|☐|
|1.3.2|Nginx serves static files|Port 80/443|☐|
|1.3.3|Environment variables injected|API_URL, MCP_URL|☐|
|1.3.4|SPA routing works|nginx.conf correct|☐|
|1.3.5|Gzip compression enabled|Reduced transfer|☐|

### 1.4 Initial Load Performance

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|1.4.1|Initial load < 3 seconds|P1 target|☐|
|1.4.2|First contentful paint < 1.5s|Fast rendering|☐|
|1.4.3|Time to interactive < 3s|Usable quickly|☐|
|1.4.4|Code splitting works|Lazy-loaded routes|☐|

---

## 2. Authentication UI

### 2.1 Login Page

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|2.1.1|Login page renders|Form displayed|☐|
|2.1.2|Username field works|Input accepted|☐|
|2.1.3|Password field works|Input masked|☐|
|2.1.4|Submit button enabled|When fields filled|☐|
|2.1.5|Successful login redirects|To dashboard|☐|
|2.1.6|Invalid credentials error|Clear error message|☐|
|2.1.7|Loading state shown|During API call|☐|
|2.1.8|Enter key submits form|Keyboard support|☐|
|2.1.9|Link to registration|"Create account" link|☐|

### 2.2 Registration Page

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|2.2.1|Registration page renders|Form displayed|☐|
|2.2.2|Username validation|Pattern checked|☐|
|2.2.3|Email validation|Format checked|☐|
|2.2.4|Password validation|Min length checked|☐|
|2.2.5|Password confirmation|Match checked|☐|
|2.2.6|Role selection|Dropdown works|☐|
|2.2.7|Registration token field|Optional input|☐|
|2.2.8|Success without token|"Pending approval" message|☐|
|2.2.9|Success with token|Direct to login|☐|
|2.2.10|Error messages displayed|Validation feedback|☐|

### 2.3 Token Management

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|2.3.1|Access token stored|localStorage or secure|☐|
|2.3.2|Refresh token stored|Separate from access|☐|
|2.3.3|Token auto-refresh|Before expiry|☐|
|2.3.4|Expired token logout|Redirect to login|☐|
|2.3.5|Logout clears tokens|Clean logout|☐|
|2.3.6|Protected routes redirect|If not authenticated|☐|

### 2.4 Session Management

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|2.4.1|Session persists refresh|Still logged in|☐|
|2.4.2|Multiple tabs supported|Shared session|☐|
|2.4.3|Session timeout warning|Before auto-logout|☐|
|2.4.4|Manual logout works|Clear and redirect|☐|

---

## 3. Layout & Navigation

### 3.1 Main Layout

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|3.1.1|Sidebar renders|Navigation menu|☐|
|3.1.2|Header renders|User info, logout|☐|
|3.1.3|Main content area|Route content|☐|
|3.1.4|Footer (if any)|Version, links|☐|
|3.1.5|Sidebar collapsible|Toggle button|☐|
|3.1.6|Responsive layout|Mobile adaptation|☐|

### 3.2 Navigation Menu

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|3.2.1|Dashboard link|Routes to /|☐|
|3.2.2|Nodes link|Routes to /nodes|☐|
|3.2.3|Services link|Routes to /services|☐|
|3.2.4|Networks link|Routes to /networks|☐|
|3.2.5|Groups link|Routes to /groups|☐|
|3.2.6|Topology link|Routes to /topology|☐|
|3.2.7|Time Machine link|Routes to /timemachine|☐|
|3.2.8|Chat link|Routes to /chat|☐|
|3.2.9|Admin link (if admin)|Routes to /admin|☐|
|3.2.10|Active route highlighted|Visual indicator|☐|
|3.2.11|Role-based menu items|Hidden if no permission|☐|

### 3.3 Breadcrumbs

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|3.3.1|Breadcrumb trail shown|Path visible|☐|
|3.3.2|Links clickable|Navigate back|☐|
|3.3.3|Current page not linked|Last item plain|☐|
|3.3.4|Dynamic breadcrumbs|Entity names shown|☐|

### 3.4 Theme Support

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|3.4.1|Light theme works|Light colors|☐|
|3.4.2|Dark theme works|Dark colors|☐|
|3.4.3|System theme detection|Auto-switch|☐|
|3.4.4|Theme toggle in UI|User can switch|☐|
|3.4.5|Theme persisted|Saved preference|☐|
|3.4.6|All components themed|Consistent look|☐|

---

## 4. Dashboard

### 4.1 Infrastructure Overview

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|4.1.1|Total node count|Accurate number|☐|
|4.1.2|Active node count|Currently active|☐|
|4.1.3|Nodes by class|Compute/Networking/IoT|☐|
|4.1.4|Node health indicator|Visual status|☐|
|4.1.5|Click navigates to nodes|Drilldown|☐|

### 4.2 Capacity Overview

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|4.2.1|Total CPU cores|Aggregate|☐|
|4.2.2|Total RAM|Aggregate GB|☐|
|4.2.3|Total Storage|Aggregate TB|☐|
|4.2.4|Visual gauge/chart|Progress bars|☐|
|4.2.5|Physical vs logical breakdown|Clear distinction|☐|

### 4.3 Service Summary

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|4.3.1|Total service count|Accurate|☐|
|4.3.2|Running services|Green indicator|☐|
|4.3.3|Stopped services|Red indicator|☐|
|4.3.4|Services by runtime|systemd/docker breakdown|☐|
|4.3.5|Click navigates to services|Drilldown|☐|

### 4.4 Recent Activity

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|4.4.1|Recent profile submissions|List with times|☐|
|4.4.2|Recent service changes|Status changes|☐|
|4.4.3|Recent node additions|New registrations|☐|
|4.4.4|Timestamp formatting|Relative time|☐|
|4.4.5|Click navigates to entity|Drilldown|☐|

### 4.5 Alert Summary

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|4.5.1|Stale profiles alert|Nodes not reporting|☐|
|4.5.2|Service failures alert|Stopped services|☐|
|4.5.3|Network issues alert|Connectivity problems|☐|
|4.5.4|Alert severity indicators|Color coding|☐|
|4.5.5|Click navigates to issue|Drilldown|☐|

### 4.6 Mini Topology

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|4.6.1|Simplified topology shown|Network overview|☐|
|4.6.2|Node count indicators|Per network|☐|
|4.6.3|Click navigates to full topology|Expand|☐|
|4.6.4|Responsive sizing|Fits dashboard|☐|

---

## 5. Node Explorer

### 5.1 Node List View

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|5.1.1|All nodes displayed|Table or cards|☐|
|5.1.2|Node name shown|displayName|☐|
|5.1.3|Node class shown|Badge/icon|☐|
|5.1.4|Node type shown|Physical/logical|☐|
|5.1.5|Node status shown|Active/inactive|☐|
|5.1.6|Last profile time|Relative time|☐|
|5.1.7|Pagination works|Next/prev pages|☐|
|5.1.8|Loading state|Skeleton/spinner|☐|
|5.1.9|Empty state|"No nodes" message|☐|

### 5.2 Node Filtering

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|5.2.1|Search by name|Real-time filter|☐|
|5.2.2|Filter by class|Dropdown/chips|☐|
|5.2.3|Filter by type|Physical/logical|☐|
|5.2.4|Filter by status|Active/inactive|☐|
|5.2.5|Filter by tags|Tag chips|☐|
|5.2.6|Filter by network|Network dropdown|☐|
|5.2.7|Clear filters button|Reset all|☐|
|5.2.8|Filter state in URL|Shareable links|☐|

### 5.3 Node Detail View

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|5.3.1|Node header|Name, status badge|☐|
|5.3.2|Node metadata|Class, type, kind|☐|
|5.3.3|Tags displayed|Editable chips|☐|
|5.3.4|Location info|Site, room, rack|☐|
|5.3.5|Parent node link|If logical|☐|
|5.3.6|Child nodes list|If parent|☐|
|5.3.7|Network memberships|Linked networks|☐|
|5.3.8|Services on node|Service list|☐|
|5.3.9|Latest profile summary|Key metrics|☐|
|5.3.10|Edit button (if permitted)|Opens edit form|☐|
|5.3.11|Archive button (if permitted)|Confirmation dialog|☐|

### 5.4 Profile History View

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|5.4.1|Profile history timeline|Version list|☐|
|5.4.2|Version numbers shown|Ex-W.X.Y.Z format|☐|
|5.4.3|Submission timestamps|When submitted|☐|
|5.4.4|Click to view profile|Profile detail|☐|
|5.4.5|Compare two profiles|Diff view|☐|
|5.4.6|Profile sections collapsible|Expand/collapse|☐|

### 5.5 Profile Detail View

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|5.5.1|Hardware section|CPU, RAM, system|☐|
|5.5.2|Network section|Interfaces, IPs|☐|
|5.5.3|Storage section|Disks, filesystems|☐|
|5.5.4|Software section|OS, packages|☐|
|5.5.5|Services section|Discovered services|☐|
|5.5.6|Users section|If collected|☐|
|5.5.7|Configs section|If collected|☐|
|5.5.8|JSON raw view toggle|Technical view|☐|
|5.5.9|Copy JSON button|Clipboard|☐|

---

## 6. Service Explorer

### 6.1 Service List View

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|6.1.1|All services displayed|Table or cards|☐|
|6.1.2|Service name shown|Service ID|☐|
|6.1.3|Runtime shown|systemd/docker badge|☐|
|6.1.4|Status shown|Running/stopped|☐|
|6.1.5|Host node shown|Link to node|☐|
|6.1.6|Exposed ports shown|Port list|☐|
|6.1.7|Pagination works|Pages|☐|
|6.1.8|Loading/empty states|Proper feedback|☐|

### 6.2 Service Filtering

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|6.2.1|Search by name|Real-time filter|☐|
|6.2.2|Filter by runtime|systemd/docker/k8s|☐|
|6.2.3|Filter by status|Running/stopped|☐|
|6.2.4|Filter by node|Specific host|☐|
|6.2.5|Filter by tags|Tag chips|☐|
|6.2.6|Clear filters|Reset|☐|

### 6.3 Service Detail View

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|6.3.1|Service header|Name, status|☐|
|6.3.2|Runtime info|Type, version|☐|
|6.3.3|Host node link|Navigate to node|☐|
|6.3.4|Port exposure|Internal/external|☐|
|6.3.5|Resource allocation|CPU, memory limits|☐|
|6.3.6|Environment variables|If available|☐|
|6.3.7|Container image|For Docker|☐|
|6.3.8|Service controls|Start/stop/restart|☐|
|6.3.9|Command history|Recent commands|☐|

### 6.4 Service Controls

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|6.4.1|Start button|If stopped|☐|
|6.4.2|Stop button|If running|☐|
|6.4.3|Restart button|Always available|☐|
|6.4.4|Reload button|Config reload|☐|
|6.4.5|Confirmation dialog|Before action|☐|
|6.4.6|Loading state|During command|☐|
|6.4.7|Success feedback|Toast notification|☐|
|6.4.8|Error feedback|Error toast|☐|
|6.4.9|Permission check|Hidden if no permission|☐|

---

## 7. Network Explorer

### 7.1 Network List View

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|7.1.1|All networks displayed|Table or cards|☐|
|7.1.2|Network name shown|Display name|☐|
|7.1.3|Network type shown|Physical/VLAN/virtual|☐|
|7.1.4|CIDR shown|IP range|☐|
|7.1.5|Node count shown|Devices in network|☐|
|7.1.6|Gateway shown|Gateway IP|☐|
|7.1.7|VLAN ID shown|If VLAN|☐|
|7.1.8|Pagination/loading|Proper states|☐|

### 7.2 Network Filtering

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|7.2.1|Search by name|Real-time filter|☐|
|7.2.2|Filter by type|Network type|☐|
|7.2.3|Filter by VLAN|Has VLAN ID|☐|
|7.2.4|Clear filters|Reset|☐|

### 7.3 Network Detail View

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|7.3.1|Network header|Name, type badge|☐|
|7.3.2|CIDR display|Full range|☐|
|7.3.3|Gateway display|Gateway IP|☐|
|7.3.4|VLAN ID display|If applicable|☐|
|7.3.5|DHCP configuration|Range, server|☐|
|7.3.6|DNS configuration|Servers, domain|☐|
|7.3.7|Router node link|Gateway device|☐|
|7.3.8|Parent network|If subnet|☐|
|7.3.9|Child subnets|Nested networks|☐|
|7.3.10|Nodes in network|Device list|☐|
|7.3.11|Edit button|If permitted|☐|

---

## 8. Group Management

### 8.1 Group List View

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|8.1.1|All groups displayed|Table or tree|☐|
|8.1.2|Group name shown|Display name|☐|
|8.1.3|Group type shown|nodes/services/both|☐|
|8.1.4|Member count shown|Number of members|☐|
|8.1.5|Parent group shown|Hierarchy|☐|
|8.1.6|Create group button|Opens form|☐|

### 8.2 Group Detail View

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|8.2.1|Group header|Name, type|☐|
|8.2.2|Selectors displayed|Membership criteria|☐|
|8.2.3|Members list|Resolved members|☐|
|8.2.4|Parent/child groups|Hierarchy links|☐|
|8.2.5|Edit selectors|Modify criteria|☐|
|8.2.6|Re-resolve button|Force recalculation|☐|
|8.2.7|Delete button|With confirmation|☐|

### 8.3 Group Creation/Edit

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|8.3.1|Name input|Required|☐|
|8.3.2|Type selection|nodes/services/both|☐|
|8.3.3|Selector builder|Visual selector UI|☐|
|8.3.4|ID selector|Select specific IDs|☐|
|8.3.5|Network selector|Select by network|☐|
|8.3.6|Tag selector|isAny/isAll modes|☐|
|8.3.7|Status selector|Active/inactive|☐|
|8.3.8|Preview members|Before saving|☐|
|8.3.9|Save button|Creates/updates group|☐|
|8.3.10|Cancel button|Discards changes|☐|

---

## 9. Topology Viewer

### 9.1 Network Topology View

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|9.1.1|Network topology renders|ReactFlow canvas|☐|
|9.1.2|Networks as nodes|Network boxes|☐|
|9.1.3|Devices as nodes|Device nodes|☐|
|9.1.4|Connections as edges|Link lines|☐|
|9.1.5|Gateway indicators|Router icons|☐|
|9.1.6|VLAN relationships|Trunk lines|☐|
|9.1.7|L2/L3 visualization|Layer distinction|☐|

### 9.2 Infrastructure Topology View

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|9.2.1|Infrastructure topology renders|Hierarchy view|☐|
|9.2.2|Physical nodes at top|Bare metal|☐|
|9.2.3|Logical nodes nested|VMs, containers|☐|
|9.2.4|Parent-child edges|Hierarchy lines|☐|
|9.2.5|Service nodes (optional)|Service layer|☐|

### 9.3 Topology Interactions

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|9.3.1|Zoom in/out|Mouse wheel|☐|
|9.3.2|Pan/drag|Move canvas|☐|
|9.3.3|Fit to screen|Auto-zoom|☐|
|9.3.4|Node click|Select node|☐|
|9.3.5|Detail panel on select|Sidebar info|☐|
|9.3.6|Double-click navigation|Go to entity|☐|
|9.3.7|Drag to reposition|Move nodes|☐|
|9.3.8|Multi-select|Shift+click|☐|

### 9.4 Topology Filtering

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|9.4.1|Filter by class|Show/hide classes|☐|
|9.4.2|Filter by status|Active only|☐|
|9.4.3|Filter by network|Specific network|☐|
|9.4.4|Search highlight|Find node|☐|
|9.4.5|Reset filters|Show all|☐|

### 9.5 Topology Export

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|9.5.1|Export as SVG|Vector image|☐|
|9.5.2|Export as PNG|Raster image|☐|
|9.5.3|File download|Browser download|☐|
|9.5.4|Quality options|Resolution|☐|

### 9.6 Topology Performance

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|9.6.1|50 nodes renders|Smooth performance|☐|
|9.6.2|100 nodes renders|Acceptable lag|☐|
|9.6.3|Layout algorithm|Auto-arrangement|☐|
|9.6.4|Incremental updates|Efficient re-render|☐|

---

## 10. Time Machine

### 10.1 Timeline Interface

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|10.1.1|Timeline scrubber|Slider component|☐|
|10.1.2|Date range selection|Start/end dates|☐|
|10.1.3|Event markers|Profile, topology events|☐|
|10.1.4|Marker tooltips|Event details|☐|
|10.1.5|Click marker to jump|Navigate to time|☐|
|10.1.6|Zoom timeline|Day/week/month|☐|
|10.1.7|Current time indicator|"Now" marker|☐|

### 10.2 Historical Topology View

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|10.2.1|Topology at selected time|Historical state|☐|
|10.2.2|"Historical" indicator|Clear label|☐|
|10.2.3|Changes highlighted|Diff visualization|☐|
|10.2.4|Missing nodes shown|Grayed out|☐|
|10.2.5|Added nodes shown|Highlighted|☐|
|10.2.6|Transition animation|Smooth change|☐|

### 10.3 Node History View

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|10.3.1|Select node + time|Historical state|☐|
|10.3.2|Profile at time shown|Historical profile|☐|
|10.3.3|Services at time|Historical services|☐|
|10.3.4|Compare with current|Diff view|☐|
|10.3.5|Navigate timeline|See evolution|☐|

### 10.4 Comparison Mode

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|10.4.1|Select two time points|Point A and B|☐|
|10.4.2|Side-by-side view|Both states|☐|
|10.4.3|Diff highlighting|Changes marked|☐|
|10.4.4|Summary of changes|Change count|☐|
|10.4.5|Drill into specifics|Click to expand|☐|

### 10.5 Playback Controls

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|10.5.1|Play button|Auto-advance|☐|
|10.5.2|Pause button|Stop playback|☐|
|10.5.3|Speed control|Faster/slower|☐|
|10.5.4|Step forward|Next event|☐|
|10.5.5|Step backward|Previous event|☐|

---

## 11. MCP Chat Interface

### 11.1 Chat UI

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|11.1.1|Chat panel renders|Message area|☐|
|11.1.2|Input field|Text input|☐|
|11.1.3|Send button|Sends message|☐|
|11.1.4|Enter key sends|Keyboard shortcut|☐|
|11.1.5|Message history|Scrollable list|☐|
|11.1.6|User messages styled|Right-aligned|☐|
|11.1.7|AI responses styled|Left-aligned|☐|
|11.1.8|Timestamps shown|Message time|☐|

### 11.2 MCP Integration

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|11.2.1|WebSocket connection|Real-time comms|☐|
|11.2.2|Connection status|Indicator shown|☐|
|11.2.3|Reconnection logic|Auto-reconnect|☐|
|11.2.4|Message sent to MCP|Request dispatched|☐|
|11.2.5|Response received|Displayed in chat|☐|

### 11.3 Tool Call Visualization

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|11.3.1|Tool calls shown|During processing|☐|
|11.3.2|Tool name displayed|Which tool called|☐|
|11.3.3|Parameters shown|Collapsible|☐|
|11.3.4|Tool result shown|Output data|☐|
|11.3.5|Loading indicator|While executing|☐|
|11.3.6|Error display|If tool fails|☐|

### 11.4 Context Awareness

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|11.4.1|Current view context|Page context sent|☐|
|11.4.2|Selected entity context|Entity in context|☐|
|11.4.3|Suggested queries|Context-based|☐|
|11.4.4|Query templates|Common queries|☐|
|11.4.5|Click to insert|Template insertion|☐|

### 11.5 Query History

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|11.5.1|Recent queries list|History panel|☐|
|11.5.2|Click to repeat|Re-run query|☐|
|11.5.3|Clear history|Delete option|☐|
|11.5.4|Save favorite queries|Bookmark feature|☐|
|11.5.5|History persisted|Across sessions|☐|

### 11.6 Response Formatting

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|11.6.1|TOON format rendered|Proper styling|☐|
|11.6.2|Code blocks|Syntax highlighting|☐|
|11.6.3|Tables rendered|Formatted tables|☐|
|11.6.4|Lists rendered|Bulleted/numbered|☐|
|11.6.5|Links clickable|Navigate to entities|☐|
|11.6.6|Copy response button|Clipboard|☐|

---

## 12. Admin Dashboard

### 12.1 User Management

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|12.1.1|User list displayed|All users|☐|
|12.1.2|User roles shown|Role badges|☐|
|12.1.3|User status shown|Active/inactive|☐|
|12.1.4|Create user button|Opens form|☐|
|12.1.5|Edit user|Modify details|☐|
|12.1.6|Delete user|With confirmation|☐|
|12.1.7|Role elevation|Permanent upgrade|☐|
|12.1.8|Temporary role grant|Time-limited|☐|
|12.1.9|Search/filter users|Find user|☐|

### 12.2 Pending Approvals

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|12.2.1|Pending users list|Awaiting approval|☐|
|12.2.2|Requested role shown|What they want|☐|
|12.2.3|Request date shown|When requested|☐|
|12.2.4|Approve button|Activates user|☐|
|12.2.5|Reject button|Deletes request|☐|
|12.2.6|Badge/notification|Pending count|☐|

### 12.3 Token Management

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|12.3.1|Registration tokens list|All tokens|☐|
|12.3.2|Token usage shown|Used/max uses|☐|
|12.3.3|Token expiry shown|Expiration date|☐|
|12.3.4|Create token button|Generate new|☐|
|12.3.5|Token form|Description, expiry, roles|☐|
|12.3.6|Copy token button|Clipboard|☐|
|12.3.7|Revoke token|Delete token|☐|

### 12.4 API Keys Management

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|12.4.1|API keys list|All keys|☐|
|12.4.2|Key permissions shown|Scopes|☐|
|12.4.3|Last used shown|Activity|☐|
|12.4.4|Create key button|Generate new|☐|
|12.4.5|Key shown once|Copy warning|☐|
|12.4.6|Revoke key|Delete key|☐|

### 12.5 Audit Log Viewer

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|12.5.1|Audit entries list|Log table|☐|
|12.5.2|Action shown|CREATE/UPDATE/DELETE|☐|
|12.5.3|Resource shown|What changed|☐|
|12.5.4|Actor shown|Who did it|☐|
|12.5.5|Timestamp shown|When|☐|
|12.5.6|Details expandable|Full details|☐|
|12.5.7|Filter by action|Action type|☐|
|12.5.8|Filter by resource|Resource type|☐|
|12.5.9|Filter by date|Date range|☐|
|12.5.10|Export option|Download CSV|☐|

### 12.6 System Settings

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|12.6.1|Settings page|Configuration UI|☐|
|12.6.2|Feature toggles|Enable/disable|☐|
|12.6.3|Integration settings|HA config|☐|
|12.6.4|Save settings|Persist changes|☐|
|12.6.5|Reset defaults|Restore|☐|

---

## 13. Home Dashboard (Family View)

### 13.1 Simplified Home View

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|13.1.1|Home dashboard renders|Simplified UI|☐|
|13.1.2|Room-by-room layout|Area-based|☐|
|13.1.3|No technical jargon|Family-friendly|☐|
|13.1.4|Large touch targets|Mobile-friendly|☐|

### 13.2 Device Cards

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|13.2.1|Device cards displayed|Per device|☐|
|13.2.2|Device name shown|Friendly name|☐|
|13.2.3|Device icon|Type-specific|☐|
|13.2.4|Current state shown|On/off, temp|☐|
|13.2.5|Tap for controls|Open control panel|☐|

### 13.3 Device Controls

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|13.3.1|Light on/off|Toggle switch|☐|
|13.3.2|Light brightness|Slider|☐|
|13.3.3|Thermostat target temp|+/- buttons|☐|
|13.3.4|Thermostat mode|Heat/cool/auto/off|☐|
|13.3.5|Switch toggle|On/off|☐|
|13.3.6|Lock control|Lock/unlock|☐|
|13.3.7|Instant feedback|UI updates|☐|
|13.3.8|Error feedback|If control fails|☐|

### 13.4 Scene Support

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|13.4.1|Scene list|Available scenes|☐|
|13.4.2|Scene icons|Custom icons|☐|
|13.4.3|Activate scene|One-tap|☐|
|13.4.4|Scene status|Active indicator|☐|
|13.4.5|Quick scenes|Favorites|☐|

### 13.5 Environmental Overview

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|13.5.1|Temperature by room|Current temps|☐|
|13.5.2|Humidity levels|If sensors|☐|
|13.5.3|Energy usage|If available|☐|
|13.5.4|Security status|Locks, sensors|☐|
|13.5.5|Weather widget|Current conditions|☐|

---

## 14. Documentation Viewer

### 14.1 Documentation List

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|14.1.1|Docs list displayed|All documentation|☐|
|14.1.2|Title shown|Doc title|☐|
|14.1.3|Type shown|Guide/architecture/etc.|☐|
|14.1.4|Category shown|Category tag|☐|
|14.1.5|Last updated shown|Timestamp|☐|
|14.1.6|Search docs|Full-text|☐|
|14.1.7|Filter by type|Type dropdown|☐|
|14.1.8|Filter by category|Category dropdown|☐|

### 14.2 Documentation Viewer

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|14.2.1|Markdown rendered|Formatted content|☐|
|14.2.2|Code blocks styled|Syntax highlight|☐|
|14.2.3|Table of contents|Sidebar TOC|☐|
|14.2.4|Anchor links|Jump to section|☐|
|14.2.5|Linked entities|Links to nodes/services|☐|
|14.2.6|Version selector|View old versions|☐|
|14.2.7|Edit button|If permitted|☐|

### 14.3 Documentation Editor

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|14.3.1|Markdown editor|Text area|☐|
|14.3.2|Preview mode|Rendered preview|☐|
|14.3.3|Split view|Edit + preview|☐|
|14.3.4|Entity linking|Insert entity links|☐|
|14.3.5|Save as new version|Version incremented|☐|
|14.3.6|Discard changes|Cancel edit|☐|

---

## 15. Responsive Design & UX

### 15.1 Desktop Experience

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|15.1.1|1920x1080 displays well|Proper layout|☐|
|15.1.2|1440x900 displays well|Adapts|☐|
|15.1.3|Sidebar always visible|Full navigation|☐|
|15.1.4|Multi-column layouts|Where appropriate|☐|

### 15.2 Tablet Experience

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|15.2.1|iPad displays well|Responsive|☐|
|15.2.2|Sidebar collapsible|Hamburger menu|☐|
|15.2.3|Touch interactions|Tap targets sized|☐|
|15.2.4|Landscape mode|Proper layout|☐|
|15.2.5|Portrait mode|Proper layout|☐|

### 15.3 Mobile Experience

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|15.3.1|iPhone displays well|Responsive|☐|
|15.3.2|Android displays well|Responsive|☐|
|15.3.3|Navigation drawer|Mobile nav|☐|
|15.3.4|Single column layouts|Mobile first|☐|
|15.3.5|Swipe gestures|Where appropriate|☐|
|15.3.6|No horizontal scroll|Proper sizing|☐|

### 15.4 Loading States

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|15.4.1|Skeleton loaders|Content placeholders|☐|
|15.4.2|Spinners|Processing indicator|☐|
|15.4.3|Progress bars|Long operations|☐|
|15.4.4|Shimmer effects|Visual feedback|☐|

### 15.5 Error States

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|15.5.1|Error boundaries|Catch React errors|☐|
|15.5.2|Error pages|404, 500 pages|☐|
|15.5.3|Inline errors|Form validation|☐|
|15.5.4|Toast notifications|Error toasts|☐|
|15.5.5|Retry options|Where applicable|☐|

### 15.6 Empty States

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|15.6.1|Empty lists|Helpful message|☐|
|15.6.2|Empty search|"No results"|☐|
|15.6.3|Call to action|What to do next|☐|
|15.6.4|Illustrations|Visual appeal|☐|

---

## 16. State Management

### 16.1 Zustand Store

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|16.1.1|Auth state managed|User, tokens|☐|
|16.1.2|UI state managed|Theme, sidebar|☐|
|16.1.3|Persist middleware|localStorage|☐|
|16.1.4|Store devtools|Debug support|☐|

### 16.2 TanStack Query

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|16.2.1|Query caching|Cached responses|☐|
|16.2.2|Stale time configuration|Appropriate TTL|☐|
|16.2.3|Background refetch|Auto-refresh|☐|
|16.2.4|Mutation handling|Optimistic updates|☐|
|16.2.5|Error retry|Automatic retries|☐|
|16.2.6|Query invalidation|On mutations|☐|

### 16.3 URL State

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|16.3.1|Filters in URL|Query params|☐|
|16.3.2|Pagination in URL|Page number|☐|
|16.3.3|Tab state in URL|Active tab|☐|
|16.3.4|Back button works|State restored|☐|
|16.3.5|Shareable URLs|Link preserves state|☐|

---

## 17. API Integration

### 17.1 API Client Setup

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|17.1.1|Base URL configured|From environment|☐|
|17.1.2|Auth interceptor|Adds Bearer token|☐|
|17.1.3|Error interceptor|Global error handling|☐|
|17.1.4|Request timeout|Configured|☐|

### 17.2 API Response Handling

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|17.2.1|Success responses|Data extracted|☐|
|17.2.2|Pagination handled|Meta extracted|☐|
|17.2.3|401 triggers logout|Redirect to login|☐|
|17.2.4|403 shows error|Permission denied|☐|
|17.2.5|404 shows error|Not found|☐|
|17.2.6|500 shows error|Server error|☐|
|17.2.7|Network error shown|Connection failed|☐|

### 17.3 Real-time Updates

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|17.3.1|WebSocket connection|For live updates|☐|
|17.3.2|Event subscription|Subscribe to changes|☐|
|17.3.3|UI updates on events|Live refresh|☐|
|17.3.4|Reconnection handling|Auto-reconnect|☐|

---

## 18. Performance

### 18.1 Bundle Optimization

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|18.1.1|Code splitting|Route-based chunks|☐|
|18.1.2|Lazy loading|Components on demand|☐|
|18.1.3|Tree shaking|Dead code removed|☐|
|18.1.4|Minification|Production build|☐|
|18.1.5|Compression|Gzip/Brotli|☐|

### 18.2 Rendering Performance

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|18.2.1|Virtual scrolling|Large lists|☐|
|18.2.2|Memoization|Prevent re-renders|☐|
|18.2.3|Debounced search|Input throttling|☐|
|18.2.4|Image optimization|Lazy load images|☐|

### 18.3 Lighthouse Scores

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|18.3.1|Performance > 80|Good score|☐|
|18.3.2|Accessibility > 90|A11y compliance|☐|
|18.3.3|Best Practices > 90|Modern standards|☐|
|18.3.4|SEO > 80|If applicable|☐|

---

## 19. Accessibility

### 19.1 Keyboard Navigation

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|19.1.1|Tab navigation|Focusable elements|☐|
|19.1.2|Focus visible|Focus ring|☐|
|19.1.3|Enter/Space activation|Buttons, links|☐|
|19.1.4|Escape closes modals|Dialog dismissal|☐|
|19.1.5|Arrow key navigation|Lists, menus|☐|

### 19.2 Screen Reader Support

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|19.2.1|Semantic HTML|Proper elements|☐|
|19.2.2|ARIA labels|Interactive elements|☐|
|19.2.3|ARIA live regions|Dynamic content|☐|
|19.2.4|Alt text for images|Descriptive|☐|
|19.2.5|Form labels|Input association|☐|

### 19.3 Visual Accessibility

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|19.3.1|Color contrast|WCAG AA|☐|
|19.3.2|Don't rely on color alone|Icons + color|☐|
|19.3.3|Text resizable|200% zoom|☐|
|19.3.4|Motion reduced|prefers-reduced-motion|☐|

---

## 20. Browser Compatibility

### 20.1 Supported Browsers

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|20.1.1|Chrome (latest)|Full support|☐|
|20.1.2|Firefox (latest)|Full support|☐|
|20.1.3|Safari (latest)|Full support|☐|
|20.1.4|Edge (latest)|Full support|☐|
|20.1.5|Chrome (N-1)|Compatible|☐|
|20.1.6|Firefox (N-1)|Compatible|☐|

### 20.2 Mobile Browsers

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|20.2.1|Safari iOS|Full support|☐|
|20.2.2|Chrome Android|Full support|☐|
|20.2.3|Samsung Internet|Compatible|☐|

### 20.3 Feature Detection

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|20.3.1|Polyfills loaded|If needed|☐|
|20.3.2|Fallbacks work|Graceful degradation|☐|
|20.3.3|No console errors|Clean execution|☐|

---

## Progress Summary

|Section|Total Tests|Passed|Failed|Blocked|Not Started|
|---|---|---|---|---|---|
|1. Build & Deployment|18|0|0|0|18|
|2. Authentication UI|23|0|0|0|23|
|3. Layout & Navigation|26|0|0|0|26|
|4. Dashboard|27|0|0|0|27|
|5. Node Explorer|35|0|0|0|35|
|6. Service Explorer|28|0|0|0|28|
|7. Network Explorer|22|0|0|0|22|
|8. Group Management|22|0|0|0|22|
|9. Topology Viewer|26|0|0|0|26|
|10. Time Machine|22|0|0|0|22|
|11. MCP Chat|28|0|0|0|28|
|12. Admin Dashboard|30|0|0|0|30|
|13. Home Dashboard|23|0|0|0|23|
|14. Documentation|17|0|0|0|17|
|15. Responsive Design|27|0|0|0|27|
|16. State Management|14|0|0|0|14|
|17. API Integration|14|0|0|0|14|
|18. Performance|13|0|0|0|13|
|19. Accessibility|14|0|0|0|14|
|20. Browser Compatibility|11|0|0|0|11|
|**TOTAL**|**460**|**0**|**0**|**0**|**460**|

---

_Last Updated: 2026-01-02_