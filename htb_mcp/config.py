from __future__ import annotations

import configparser
import os
from pathlib import Path


APP_NAME = "htb-mcp"
ENV_TOKEN = "HTB_TOKEN"
ENV_CONFIG = "HTB_MCP_CONFIG"


def config_path() -> Path:
    configured = os.environ.get(ENV_CONFIG, "").strip()
    if configured:
        return Path(configured).expanduser()
    xdg_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return xdg_home / APP_NAME / "config.ini"


def load_parser() -> tuple[Path, configparser.ConfigParser]:
    path = config_path()
    parser = configparser.ConfigParser()
    if path.exists():
        parser.read(path)
    return path, parser


def save_parser(path: Path, parser: configparser.ConfigParser) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        parser.write(handle)
    path.chmod(0o600)
    return path


def get_token() -> str | None:
    env_token = os.environ.get(ENV_TOKEN, "").strip()
    if env_token:
        return env_token

    _, parser = load_parser()
    token = parser.get("auth", "token", fallback="").strip()
    return token or None


def set_token(token: str) -> Path:
    path, parser = load_parser()
    if "auth" not in parser:
        parser["auth"] = {}
    parser["auth"]["token"] = token.strip()
    return save_parser(path, parser)
