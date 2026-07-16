from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from .api import (
    HtbApiConfig,
    HtbApiError,
    get_challenge,
    get_machine,
    get_active_machine,
    get_sherlock,
    get_sherlock_play,
    list_challenges,
    list_machines,
    list_sherlock_tasks,
    list_sherlocks,
    prepare_challenge,
    submit_sherlock_task_flag,
    start_challenge_instance,
    start_machine,
    submit_challenge_flag,
    submit_machine_flag,
)
from .config import get_token


def _api_config() -> HtbApiConfig:
    token = get_token()
    if not token:
        raise HtbApiError(
            "No HTB token is configured. Run `python main.py token set <token>` or set HTB_TOKEN."
        )
    return HtbApiConfig(token=token)


def _machine_summary(machine: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": machine.get("id"),
        "name": machine.get("name"),
        "os": machine.get("os"),
        "difficulty": machine.get("difficultyText") or machine.get("difficulty"),
        "points": machine.get("points"),
        "rating": machine.get("star"),
        "active": machine.get("active"),
        "retired": machine.get("retired"),
        "free": machine.get("free"),
        "avatar": machine.get("avatar"),
        "ip": machine.get("ip"),
        "is_spawning": machine.get("isSpawning"),
    }


def _machine_status(machine: dict[str, Any], active: dict[str, Any] | None) -> dict[str, Any]:
    machine_id = machine.get("id")
    is_active = bool(active and active.get("id") == machine_id)
    return {
        **_machine_summary(machine),
        "status": "active" if is_active else "inactive",
        "active_machine": _machine_summary(active) if is_active and active else None,
    }


def _challenge_summary(challenge: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": challenge.get("id"),
        "name": challenge.get("name"),
        "category": challenge.get("category_name"),
        "difficulty": challenge.get("difficulty"),
        "points": challenge.get("points"),
        "solves": challenge.get("solves"),
        "download": challenge.get("download"),
        "docker": challenge.get("docker"),
        "docker_ip": challenge.get("docker_ip"),
        "docker_ports": challenge.get("docker_ports"),
    }


def _challenge_instance_summary(challenge: dict[str, Any]) -> dict[str, Any] | None:
    host = challenge.get("docker_ip")
    ports = challenge.get("docker_ports") or []
    if not host and not ports:
        return None
    return {
        "host": host,
        "ports": ports,
        "target": f"{host}:{ports[0]}" if host and ports else host,
    }


def _sherlock_summary(sherlock: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": sherlock.get("id"),
        "name": sherlock.get("name"),
        "difficulty": sherlock.get("difficulty"),
        "state": sherlock.get("state"),
        "category_id": sherlock.get("category_id"),
        "category": sherlock.get("category_name"),
        "solves": sherlock.get("solves"),
        "is_owned": sherlock.get("is_owned"),
        "progress": sherlock.get("progress"),
        "play_methods": sherlock.get("play_methods"),
        "release_date": sherlock.get("release_date"),
        "avatar": sherlock.get("avatar"),
        "labels": sherlock.get("labels"),
    }


def _sherlock_play_summary(sherlock: dict[str, Any]) -> dict[str, Any]:
    play_info = sherlock.get("play_info")
    return {
        "id": sherlock.get("id"),
        "scenario": sherlock.get("scenario"),
        "creators": sherlock.get("creators"),
        "blood": sherlock.get("blood"),
        "file_name": sherlock.get("file_name"),
        "file_size": sherlock.get("file_size"),
        "play_info": play_info if isinstance(play_info, dict) else None,
    }


def _sherlock_task_summary(task: dict[str, Any]) -> dict[str, Any]:
    task_type = task.get("task_type")
    type_info = task.get("type")
    return {
        "id": task.get("id"),
        "title": task.get("title"),
        "description": task.get("description"),
        "hint": task.get("hint"),
        "type": type_info.get("text") if isinstance(type_info, dict) else type_info,
        "task_type": task_type.get("text") if isinstance(task_type, dict) else task_type,
        "prerequisite_id": task.get("prerequisite_id"),
        "completed": task.get("completed"),
        "masked_flag": task.get("masked_flag"),
        "options": task.get("options"),
    }


def create_server() -> FastMCP:
    mcp = FastMCP(
        "htb-mcp",
        instructions=(
            "Hack The Box MCP server for listing machines and challenges, starting targets, "
            "downloading challenge files, and submitting flags."
        ),
    )

    @mcp.tool(description="List Hack The Box machines.")
    def list_htb_machines() -> list[dict[str, Any]]:
        return [_machine_summary(machine) for machine in list_machines(_api_config())]

    @mcp.tool(description="Get one Hack The Box machine by exact name or numeric id.")
    def get_htb_machine(machine: str) -> dict[str, Any]:
        return _machine_summary(get_machine(_api_config(), machine))

    @mcp.tool(description="Start a Hack The Box machine by exact name or numeric id.")
    def start_htb_machine(machine: str) -> dict[str, Any]:
        config = _api_config()
        target = get_machine(config, machine)
        started = start_machine(config, int(target["id"]))
        return _machine_summary(started)

    @mcp.tool(description="Get the status of one Hack The Box machine by exact name or numeric id.")
    def get_htb_machine_status(machine: str) -> dict[str, Any]:
        config = _api_config()
        target = get_machine(config, machine)
        active = get_active_machine(config)
        return _machine_status(target, active)

    @mcp.tool(description="Show the currently active Hack The Box machine, if any.")
    def get_active_htb_machine() -> dict[str, Any] | None:
        active = get_active_machine(_api_config())
        return _machine_summary(active) if active else None

    @mcp.tool(description="Submit a flag for a machine. Uses the active machine if no id is provided.")
    def submit_htb_machine_flag(flag: str, machine_id: int | None = None) -> dict[str, Any]:
        response = submit_machine_flag(_api_config(), flag, machine_id=machine_id)
        return {"machine_id": machine_id, "response": response}

    @mcp.tool(description="List Hack The Box challenges.")
    def list_htb_challenges() -> list[dict[str, Any]]:
        return [_challenge_summary(challenge) for challenge in list_challenges(_api_config())]

    @mcp.tool(description="Get one Hack The Box challenge by exact name or numeric id.")
    def get_htb_challenge(challenge: str) -> dict[str, Any]:
        return _challenge_summary(get_challenge(_api_config(), challenge))

    @mcp.tool(description="Download Hack The Box challenge files into a destination directory.")
    def download_htb_challenge(
        challenge: str,
        destination: str = ".",
    ) -> dict[str, Any]:
        result = prepare_challenge(
            _api_config(),
            challenge,
            Path(destination).expanduser(),
            start_instance=False,
        )
        return {
            "challenge": _challenge_summary(result["challenge"]),
            "downloaded_to": result["downloaded_to"],
        }

    @mcp.tool(description="Start a Hack The Box challenge instance by exact name or numeric id.")
    def start_htb_challenge(challenge: str) -> dict[str, Any]:
        config = _api_config()
        target = get_challenge(config, challenge)
        started = start_challenge_instance(config, int(target["id"]))
        return {
            "challenge": _challenge_summary(started),
            "instance": _challenge_instance_summary(started),
        }

    @mcp.tool(description="Get the current instance status for a Hack The Box challenge by exact name or numeric id.")
    def get_htb_challenge_status(challenge: str) -> dict[str, Any]:
        target = get_challenge(_api_config(), challenge)
        return {
            "challenge": _challenge_summary(target),
            "instance": _challenge_instance_summary(target),
        }

    @mcp.tool(
        description=(
            "Download Hack The Box challenge files into a destination directory and optionally start "
            "its remote instance."
        )
    )
    def setup_htb_challenge(
        challenge: str,
        destination: str = ".",
        start_instance: bool = True,
    ) -> dict[str, Any]:
        result = prepare_challenge(
            _api_config(),
            challenge,
            Path(destination).expanduser(),
            start_instance=start_instance,
        )
        return {
            "challenge": _challenge_summary(result["challenge"]),
            "downloaded_to": result["downloaded_to"],
            "instance": result["instance"],
        }

    @mcp.tool(description="Submit a flag for a Hack The Box challenge by exact name or numeric id.")
    def submit_htb_challenge_flag(challenge: str, flag: str, difficulty: int = 1) -> dict[str, Any]:
        config = _api_config()
        target = get_challenge(config, challenge)
        response = submit_challenge_flag(config, int(target["id"]), flag, difficulty=difficulty)
        return {
            "challenge": _challenge_summary(target),
            "response": response,
        }

    @mcp.tool(description="List Hack The Box sherlocks. Optionally filter by keyword.")
    def list_htb_sherlocks(keyword: str | None = None) -> list[dict[str, Any]]:
        data = list_sherlocks(_api_config(), keyword=keyword)
        items = data.get("data")
        if not isinstance(items, list):
            raise HtbApiError("HTB API response did not contain a sherlock list.")
        return [_sherlock_summary(sherlock) for sherlock in items if isinstance(sherlock, dict)]

    @mcp.tool(description="Get one Hack The Box sherlock by exact name or numeric id.")
    def get_htb_sherlock(sherlock: str) -> dict[str, Any]:
        return _sherlock_summary(get_sherlock(_api_config(), sherlock))

    @mcp.tool(description="Get play details for a Hack The Box sherlock by exact name or numeric id.")
    def get_htb_sherlock_play(sherlock: str) -> dict[str, Any]:
        return _sherlock_play_summary(get_sherlock_play(_api_config(), sherlock))

    @mcp.tool(description="List tasks for a Hack The Box sherlock by exact name or numeric id.")
    def list_htb_sherlock_tasks(sherlock: str) -> list[dict[str, Any]]:
        return [_sherlock_task_summary(task) for task in list_sherlock_tasks(_api_config(), sherlock)]

    @mcp.tool(description="Submit a flag for a Hack The Box sherlock task.")
    def submit_htb_sherlock_task_flag(sherlock: str, task_id: int, flag: str) -> dict[str, Any]:
        config = _api_config()
        target = get_sherlock(config, sherlock)
        response = submit_sherlock_task_flag(config, sherlock, task_id, flag)
        return {
            "sherlock": _sherlock_summary(target),
            "task_id": task_id,
            "response": response,
        }

    return mcp
