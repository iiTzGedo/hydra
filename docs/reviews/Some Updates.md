### Schema check updates: 

- all tags items should match regex pattern: `"^[a-z]+[_:]?[a-z]+$"` 
- networkIds must match: `"^[a-z]{1,}[0-9a-z]*([\\-]?net$"`
- ipv4 must match: `"^(25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])(\\.(25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])){3}$"`
- cidr must match: `"^(25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])(\\.(25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])){3}\\/(3[0-2]|[12]?[0-9])$"`
- nodeId must match: `"^[a-z]+([._-][a-z0-9]+){0,2}$"`
- profile.version must match (Sent from agent): `"^E([0-9]|[1-9][0-9]+)-([0-9A-F]\\.){3}[0-9A-F]$"`
- serviceId match: `"^svc::[a-z0-9-_]+::[a-zA-Z0-9]{4}$"`


### Sub Accounts

Introducing the concept of sub accounts for users - To keep it simple. Only Admin and Operators can have sub accounts of (family, viewer or agent role) and sub accounting can only be done at Max 1 Level, i.e. a sub account cannot have a sub account.
- Creating a Family/Viewer sub account can be done by `auth/register/sub/{userId}` - userId has to be of an existing Family or Viewer user. Only Admins and Operators can call this endpoint. Password for account will be the json payload in request like.
- Both Parent Password and Sub account password can be used to login to sub account
  ``` json
    // POST `auth/register/sub/{userId}`
    {
      "password": "string", // REQUIRED| password of userId to be linked as sub account.
      "reset_password": "bool" // OPTIONAL| whether to reset password of this 'to-be' sub account - this makes the passowrd to be same as parent password if set to 'true' defaults to 'false'
    }
  ```
- Agent User must always be a sub account - Given on Admin and Operator can install agents, this fits for agent users, as on installation, logged in account will either be operator or admin, then `auth/register/sub/{userId}` will be called for newly created agent-user.
- During Agent-User creation, default password for agent user will be auto-generated and saved in config but on linking to main account param 
- Agent User Account being is a System account, thus cannot be used to log into the Web.

### Agent Distribution

Questions?
- Q: Why cant I just clone the repo locally and build hydra agent for my machine target?.
- A: You can, but fundamentally, hydra-agent is to have many heads in many machines, it could be suboptimal to clone the repo on multiple machines then build - however it is up to the individual.

- Q: Do I have to use an S3 compatible storage for my distribution - if I want use the install endpoint?
- A: No you do not, you can set the bundle storage to be local directory for the install endpoint - But ensure hydra agent code is reachable on the same machine (or different machine via network share) from the active API service.


## Hydra Agent Installation Review (Distribution Update)

Shifting away from Utilizing S3 as Upload for compiled binary, instead for zipped/bundled hydra-agent code (still with current versioning system), API & Agent need be updated to reflect this.

Using S3 is now optional for agent distribution when using API download endpoint, Local Storage Path must be set on the API end , Just Like S3 URL and details, then config will be used accordingly. This requires updates to download, install & version-list endpoints for Agent distributions.
source param for the endpoint is an Enum `obs` for S3 storage or `local` for local storage.

`/api/v1/agent/download/{binary}` -> `api/v1/agent/download?source=local|obs`
`/api/v1/agent/install` -> `api/v1/agent/install?source=local|obs`
`api/v1/agent/versions` -> `api/v1/agent/versions?source=local|obs`

### Linux/Unix(MacOS)/FreeBSD
##### Option 1  (Manual, via `/download` )

1. Download Hydra Agent from API `api/v1/agent/download?source=local|obs`, downloads a bundled version of hydra-agent and zipped.
2. Unzip/Extract downloaded code bundle as `{cwd}/hydra-agent/`
3. Run `./hydra-agent/scripts/install.sh` script locally

##### Option 2 (Easy, via `/install` endpoint)

 1. Run `api/v1/agemt/install?source=local|obs` remote script which does - This must be designed to be Async
	a. Downloads the hydra-agent bundled code (from specified source) to cwd, then extracts it to cwd
	b. Runs the install section of script interactively
	c. Cleans up extracted hydra-agent code files

##### Option 3 (Development, via Repository)

 1. Clone the hydra repository and cd into hydra-agent code directory
 2. Run the `./hydra-agent/scripts/install.sh` locally 


> [!NOTE]  Install Script consistency
> Install section of script ran by API and install script in hydra-agent Repo must be consistent with each other.
#### Install Script

Hydra Agent Install script does the following
1. Detects the details of the current machine for which the install takes place
2. Checks & Downloads(if absent) rustup, toolchains and necessary dependencies for current target build.
3. Builds Release binary into cwd
4. Installs hydra-agent build into relevant `install_dir` path. (Optional arg  `--install-dir`  can be specified to install in different location, setting `--install-dir "cwd"` installs the binary in current working directory; default install_dir is  `/usr/local/bin`)
5. Sets HOME PATH to hydra-agent for user so user can call `hydra-agent` cli directly from shell session. (Optional `--global` must be passed for this step, else documentation note will be displayed post installation on how to set to HOME path)
6. Optional Aliasing setup for the hydra-agent cli to just hydra for cleaner interactions i.e. instead of using `hydra-agent node -r` to register a node, use `hydra node -r` (where `-r | --register` to register node which agent is installed on)
7. Config files and Secret Directories are created if not existing at defaults: `/etc/hydra/agent.toml` and `/var/cv/hydra/` (cv means credential-vault where secrets like agent password, api-key details will be stored and any other sensitive info used by hydra-agent. e.g. `/var/cv/hydra/.creds` ) 

##### Registering an Agent

Before a Node Can be profiled, the hydra system needs to know what is being profiled and who is profiling it, thus we need to complete prerequisites (only in `live` mode). - These steps can be skipped in `dev` mode

Post Installation of hydra-agent, then user is to 
1. login via `hydra-agent login` or e.g. `hydra login --username <username> --pasword <pasword>` if aliased, user must be admin or operator.
2. On successful login, An hydra-agent system user account need be created and linked to the primary admin/operator user. `hydra register` registers system user account via provided `api/v1/auth/register`
	- If a user is logged in, i.e. `hydra login -u <uname> -p <pwd>` successful, to register an agent run `hydra register` e.g. `hydra register --id <agent_id> [OPTIONAL] --pwd <agent_password> [OPTIONAL]`, else
	- If no user logged in, a registration token (admin/operator) can also be used like `hydra register -t <registration token> [REQUIRED IF NO JWT CLAIM FOR LOGGED IN ADMIN OR OPERATOR FOUND PRIOR]`
	```json
	// POST /api/v1/auth/register for agent user.
	{
	  "username": "string",  // either custom provided or generated to match `^agent-[0-9A-Z]{8}$`
	  "password": "stringst",  // Auto generated by system
	  "role": "agent", //fixed role=agent cannot be changed
	  "registrationToken": "string" // Set if provided by user
	}
	```
3. On successful agent system user account creation, the system auto links the system logged in user or user of registration token (admin/operator) as a sub-account via `auth/register/sub/{userId}` (where userId is agent id/username of agent account).
4. After Successful account linkage, the agent user will auto-login (logs out admin/operator user).
5. On System account log in via API, the JWT session will be used to create and API-KEY (with expiration of 90 days) via the API for this system account. (NOTE: Need to ensure Agent user can create api-keys, revoke api-keys, list api keys (owned by agent user), all profile & node & node registration endpoints are default permissions for an agent user.)
6. The API-KEY details as well as Agent Credentials will be stored in the credential-vault for hydra secrets.
7. Subsequent operations requiring API interaction like `node` updates, `profile` updates will utilize the system user api-key (where required)
8. When API key is expired, hydra-agent (if running as a service will auto create another key by logging into agent account creating api-key & updating relevant creds files)


Alternatively, instead of running `hydra login` and/or `hydra register`, `--register <reg_token>` option can be passed to installer.

**PS: See below API endpoint updates due to this new plan.**

##### Registering a Node

Post Registering the agent (who profiles), we need to register the "what is profiled" which is the machine where the agent is installed. This is done via API endpoint `POST /node/register`. !! Node registration can only be done after agent registration !!

Using hydra-agent node registration is done via `hydra node register` command - this uses the config file defined during installation.
#### Supported Options, Flags & Commands

##### `install.sh` & `/agent/install


> [!WARNING]  API Versioning
> When using the API endpoint for installation, the set version number must be a valid version that exists in OBS or Local Storage.
> Available versions can be retrieved via `api/v1/agent/versions?source=local|obs`

| Arg             | Shorthand | Action                                                                                                                                                                                         | Default                 | Requirement | Type   | Example Usage                                        |
| --------------- | --------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------- | ----------- | ------ | ---------------------------------------------------- |
| `--version`     | `-v`      | Specified version number to apply to binary manifest for build and install                                                                                                                     |                         | Required    | Option | `install.sh -v 0.1.1` , `install.sh --version 0.0.1` |
| `--help`        | `-h`      | Help Documentation for installation                                                                                                                                                            |                         | Optional    | Flag   | `install.sh --help`                                  |
| `--aliased`     | `-a`      | To Create an alias bin `hydra` for alternate call to `hydra-agent`                                                                                                                             |                         | Optional    | Flag   | `install.sh -a`                                      |
| `--global`      | `-g`      | If hydra-agent binary should be set to $HOME PATH on current machine for global access                                                                                                         |                         | Optional    | Flag   | `install.sh -g`                                      |
| `--install-dir` | `-d`      | Decides where the hydra-agent binary is built and installed to. `cwd` is a valid param to pass to `-d`, this makes the installation in current working directory instead                       | `/usr/local/bin`        | Optional    | Option | `install.sh -d cwd`                                  |
| `--config`      | `-c`      | Specifies the config file path for hydra to use for subsequent actions, creates if non-existent in path with default values, if service running, service restart required.                     | `/etc/hydra/agent.toml` | Optional    | Option | `install.sh -c agent.toml`                           |
| `--register`    | `-r`      | If provided, the Agent Registration step is auto completed during installation process. Token provided must have appropriate permissions for registering an agent e.g. admin or operator roles |                         | Optional    | Option | `install.sh -r dhdhgyy27266819jsjsyy1121s1223ddd09`  |

##### `hydra` | `hydra-agent`

|     Arg     | Shorthand | Action                                                                                                                                                                                                                                                           | Default                 | Requirement | Type    | Example Usage                    |
| :---------: | --------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------- | ----------- | ------- | -------------------------------- |
|  `--help`   | `-h`      | Help Documentation for hydra-agent and applicable parent command                                                                                                                                                                                                 |                         | Optional    | Flag    | `hydra -h` , `hydra node --help` |
| `--aliased` | `-a`      | Creates an alias bin `hydra` for alternate call to `hydra-agent`                                                                                                                                                                                                 |                         | Optional    | Flag    | `hydra --aliased`                |
| `--config`  | `-c`      | Specifies the config path for hydra to use for subsequent actions, creates if non-existent in path with default values                                                                                                                                           | `/etc/hydra/agent.toml` | Optional    | Option  | `hydra --config agent.toml`      |
|  `--mode`   | `-m`      | Sets hydra-agent mode, `live` (Default API full mode) or `dev` prevents profiling runs from posting to API, and just publishes the Profiles to specified path <br>(default: `/home/<user>/hydra/profiles/`) - basically runs everything absent API connectivity. | `live`                  | Optional    | Option  | `hydra --mode dev`               |
|   `login`   | `--l`     | In other to login as a real user on a potential node.                                                                                                                                                                                                            |                         | Optional    | Command | `hydra login {*args}`            |
| `register`  | `--r`     | Management and controls to register the hydra agent responsible for profiling the give Node.                                                                                                                                                                     |                         | Optional    | Command | `hydra register {*arg}`          |
|  `config`   | `--c`     | Manging and Updating hydra-agent configs                                                                                                                                                                                                                         |                         | Optional    | Command | `hydra config {*args}`           |
|   `node`    | `--n`     | Managing & Controlling Current Node machine                                                                                                                                                                                                                      |                         | Optional    | Command | `hydra node {*args}`             |
|  `service`  | `--s`     | Controlling and updating hydra-agent service (systemd or docker with `cross` dependency), schedules & logs                                                                                                                                                       |                         | Optional    | Command | `hydra service {*args}`          |

##### `hydra login` 

| Arg          | Shorthand | Action                                                         | Default | Requirement | Type   | Example Usage                     |
| ------------ | --------- | -------------------------------------------------------------- | ------- | ----------- | ------ | --------------------------------- |
| `--help`     | `-h`      | Help documentation for Login procedure                         |         | Optional    | Flag   | `hydra login --help`              |
| `--refresh`  | `-r`      | Refresh login session via JWT refresh token from initial login |         | Optional    | Flag   | `hydra login --refresh`           |
| `--username` | `-u`      | Existing Admin or Operator username                            |         | Required    | Option | `hydra login -u a1b2c3 -p xx12xy` |
| `--password` | `-p`      | User password for user login                                   |         | Required    | Option | `hydra login -u a1b2c3 -p xx12xy` |

#####  `hydra register`

| Arg          | Shorthand | Action                                                                        | Default                                       | Requirement                     | Type   | Example Usage                                     |
| ------------ | --------- | ----------------------------------------------------------------------------- | --------------------------------------------- | ------------------------------- | ------ | ------------------------------------------------- |
| `--help`     | `-h`      | Help documentation for agent registration controls                            |                                               | OPTIONAL                        | Flag   | `hydra register --help`                           |
| `--token`    | `-t`      | Apply registration token provided by admin or operator user to register agent |                                               | REQUIRED (IF NO USER LOGGED IN) | Option | `hydra register --token <reg_token>`              |
| `--username` | `-id`     | Custom Agent Id provisioned by user.                                          | Auto generated to match `^agent-[0-9A-Z]{8}$` | OPTIONAL                        | Option | `hydra register --username agent-01 --pwd a1b2c4` |
| `--password` | `-pwd`    | Custom Password for agent provisioned by user                                 | Auto generated by `hydra register` command    | OPTIONAL                        | Option | `hydra register --id agent-01 --pwd a1b2c4`       |

##### `hydra config`

Given updated `agent.toml` schema with sections for each config target/section `api`, `node`, `collection`, `schedule` 

```toml
# Hydra Agent Configuration
# File is copied to /etc/hydra/agent.toml and adjust for your environment

[api]

url = "http://localhost:8080/api/v1"                 # Base URL of the Hydra API
credentials_file = "/etc/hydra/credentials.json"     # Path to credentials file (created during registration)
timeout_seconds = 30                                 # Request timeout in seconds
retries = 3                                          # Number of retries for failed requests

  
[node]
# Unique node identifier (required)
node_id = "my-server-01"                            # Pattern: ^[a-z]+([._-][a-z0-9]+){0,2}$
class = "compute"                                   # Node class: compute, networking, or iot
node_type = "physical"                              # Node type: physical or logical

# Node kind (optional)
# Compute: bare-metal, vm, lxc, docker, kubernetes-pod
# Networking: router, switch, access-point, firewall, load-balancer
# IoT: sensor, actuator, controller, hub, bridge, appliance
kind = "bare-metal"
display_name = "My Server 01"                      # Display name for the node (defaults to node_id)
description = "Primary compute node"               # Description (optional)
tags = ["production", "web-server"]                # Tags for grouping
parent_node_id = ""                                # Parent node ID for VMs/containers (optional)

  
[collection]
level = "neutral"                                  # Collection level: shallow, neutral, or deep
collectors = ["hardware", "network", "storage", "software", "services"]   # Enabled collectors
include_packages = true                            # Include package list (can be slow on systems with many packages)
include_users = true                               # Include user list
config_files = [ "/etc/nginx/nginx.conf",
				"/etc/ssh/sshd_config", 
			]                                      # Config files to track (paths to hash)

  
[schedule]
enabled = true                                     # Enable scheduled collection
interval_seconds = 86400                           # Collection interval in seconds (default: 24 hours)
on_startup = true                                  # Collect on startup
```

Managing the config can be done through CRUD operation options `--set`, `--get`, `--unset`. All options take in key of config to update. The query format must be `<section_name>.<key_name>=<value>` 
- `<section_name>`  must be one of existing sections `api`, `node` , `collection`, `schedule`
- `<key_name>` must be name of a key in the target section.

> [!INFO] Config on Service
> 1. Config Updates require Service restart if hydra running as a service
> 2. `node` config updates will be immediately posted to the API node update endpoints.

| Arg       | Shorthand | Action                                                                                                                                                          | Default | Requirement | Type   | Example Usage                                                                              |
| --------- | --------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------- | ----------- | ------ | ------------------------------------------------------------------------------------------ |
| `--help`  | `-h`      | Help Documentation of config management usage                                                                                                                   |         | OPTIONAL    | Flag   | `hydra config -h`                                                                          |
| `--set`   | `-s`      | Sets or Updates a Config entry key with value, if Array type, it adds value to the array, else sets the value to specified key                                  |         | OPTIONAL    | Option | `hydra config --set node.node_id="p0.server_01"` , `hydra config -s collection.level=deep` |
| `--unset` | `-r`      | Removes a value a list type config, and sets the value of string config entry to `""` or `null` & boolean to false- this would be the indicator of unset config |         | OPTIONAL    | Option | `hydra config --unset schedule.enabled`, `hydra config --r node.tags="server"`             |
| `--get`   | `-g`      | Gets the current value of a config key                                                                                                                          |         | OPTIONAL    | Option | `hydra config --get api.url`                                                               |

##### `hydra node`

On Node registration, caveats to look out for are:
1. Idempotency & consistency of registration requests (no duplicate registrations)
2. No two nodes can have the same `nodeId`

| Arg        | Shorthand | Action                                                                                                     | Default | Requirement | Type    | Example Usage                           |     |
| ---------- | --------- | ---------------------------------------------------------------------------------------------------------- | ------- | ----------- | ------- | --------------------------------------- | --- |
| `--help`   | `-h`      | Help Documentation on node command usage                                                                   |         | OPTIONAL    | Flag    | `hydra node -h`                         |     |
| `--update` | `-u`      | Update Node details using config update strategy (same as calling `hydra config --set node.<key>=<value>`) |         | OPTIONAL    | Option  | `hydra node --update kind="bare-metal"` |     |
| `register` | `-r`      | Registering the Machine as a Node to hydra server (no duplicate registration)                              |         | OPTIONAL    | Command | `hydra node register`                   |     |

##### `hydra service`

| Arg        | Shorthand | Action                                                                                                                                                          | Default | Requirement | Type    | Example Usage                                         |
| ---------- | --------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------- | ----------- | ------- | ----------------------------------------------------- |
| `activate` | `-a`      | Setup systemd (default) service for running hydra agent on default cron config, takes an optional flag `-d` which switches the mode to setup as docker service. |         | Command     | Command | `hydra service activate`, `hydra service activate -d` |
| `start`    | `-s`      | Start already "activated" hydra-agent service                                                                                                                   |         | OPTIONAL    | Command | `hydra service star`                                  |
| `run`      | `-d`      | One time Service run with pre-defined configs, this is agnostic of service "start"                                                                              |         | OPTIONAL    | Command | `hydra service run`                                   |
| `stop`     | `-s`      | Stop Hydra Agent systemd/docker service if running                                                                                                              |         | OPTIONAL    | Command | `hydra service stop`                                  |
| `--cron`   | `-c`      | Define and Register a system cron job that will auto-run hydra agent on a schedule e.g. `"0 */6 * * *"`                                                         |         | Command     | Option  | `hydra service --cron "0 */1 * * *"`                  |

### Agent Docs

- Add more details to documentation in readme on cross compilation prerequisites - rustup install, toolchains setup, target build, deployment(to s3 - including prerequisites) and installation docs for various supported platforms with individual use case example for each platform. also add support for raspberry-pi Linux agents.  
- Update the hydra-agent command line usage in docs (add examples for each)

## API Updates

1. Need to update user docs & schema to reflect subaccounts 
   ```json
   //example addition to user doc
    {
      "subaccounts": [
	      {
		      "userId": "string",
		      "role" "enum" // agent/viewer/family
	      }
      ]
    ```

2. New Endpoint `GET /api/v1/{userId}/subs` to fetch all sub accounts of a user.
3. Ensure Agent user has right permissions to fulfil all requests.
4. Ensure Admin or Operator Users with sub accounts can manage sub accounts from primary accounts, Relevant Endpoints like list, create or get API Key can be called on behalf of a sub account using primary account session. e.g. When Listing API keys, user will be able to view/filter by api keys from sub-accounts.

### Other Updates
1. Update deployment script in hydra agent to focus on deploying the code as bundle version to Object storage or local storage.
2. Ensure install scripts, hydra API & agent are all consistent in behaviour, functionality and data contracts
3. For the Storing of secrets in `var/cv/hydra/` the password and api keys can be cached in environment variables for quick access.