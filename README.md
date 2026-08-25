# htb-mcp

`htb-mcp` is a small FastMCP server for Hack The Box. It exposes the provider actions that are useful when running an MCP-driven workflow: list machines, inspect a machine, start a machine, check its status, submit a machine flag, list challenges, inspect a challenge, download challenge files, start a challenge instance, inspect challenge instance status, submit a challenge flag, and work with Sherlock scenarios and tasks.

The point of the project is to move HTB API interactions behind MCP tools so other local agents or clients can operate on Hack The Box targets without reimplementing the API logic each time.

## What It Does

- Lists HTB machines
- Looks up a machine by name or id
- Starts a machine and waits for the IP
- Checks machine status
- Submits a machine flag
- Lists HTB challenges
- Looks up a challenge by name or id
- Downloads challenge files
- Starts a remote challenge instance when the challenge supports it
- Checks challenge instance status
- Submits a challenge flag
- Lists Sherlocks
- Looks up a Sherlock by name or id
- Reads Sherlock play details
- Lists Sherlock tasks
- Submits a Sherlock task flag

## Requirements

- Python 3.10+
- An HTB account
- An HTB API token from `https://app.hackthebox.com/account-settings`

## Setup

Install dependencies:

```bash
pip install -r requirements.txt
```

Store your HTB token:

```bash
python main.py token set
```

You can also pass the token directly:

```bash
python main.py token set your_htb_token
```

The token is stored in `~/.config/htb-mcp/config.ini` by default. If `HTB_TOKEN` is set in the environment, that value takes precedence over the config file.

## Run The MCP Server

Start the server over stdio:

```bash
python main.py serve
```

Register it in Codex:

```bash
codex mcp add htb-mcp -- python /home/noma/htb-mcp/main.py serve
```

Then verify it:

```bash
codex mcp list
codex mcp get htb-mcp
```

Start it with another FastMCP transport:

```bash
python main.py serve --transport sse
python main.py serve --transport streamable-http
```

## Tool Surface

The server exposes these FastMCP tools:

- `list_htb_machines`
- `get_htb_machine`
- `start_htb_machine`
- `get_htb_machine_status`
- `get_active_htb_machine`
- `submit_htb_machine_flag`
- `list_htb_challenges`
- `get_htb_challenge`
- `download_htb_challenge`
- `start_htb_challenge`
- `get_htb_challenge_status`
- `setup_htb_challenge`
- `submit_htb_challenge_flag`
- `list_htb_sherlocks`
- `get_htb_sherlock`
- `get_htb_sherlock_play`
- `list_htb_sherlock_tasks`
- `submit_htb_sherlock_task_flag`

