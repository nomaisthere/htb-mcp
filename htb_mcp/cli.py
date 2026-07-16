from __future__ import annotations

import argparse
import getpass

from .config import config_path, set_token
from .server import create_server


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="htb-mcp",
        description="FastMCP server for Hack The Box machines and challenges.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    token = subparsers.add_parser("token", help="Manage the stored HTB token.")
    token_subparsers = token.add_subparsers(dest="token_command", required=True)

    token_set = token_subparsers.add_parser("set", help="Store an HTB API token in the local config file.")
    token_set.add_argument("value", nargs="?", help="The HTB API token. If omitted, prompt securely.")

    serve = subparsers.add_parser("serve", help="Start the FastMCP server.")
    serve.add_argument(
        "--transport",
        choices=("stdio", "sse", "streamable-http"),
        default="stdio",
        help="FastMCP transport to expose.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "token" and args.token_command == "set":
        token = args.value or getpass.getpass("HTB token: ").strip()
        if not token:
            parser.error("token cannot be empty")
        path = set_token(token)
        print(f"Saved HTB token to {path}")
        return 0

    if args.command == "serve":
        server = create_server()
        server.run(transport=args.transport)
        return 0

    parser.print_help()
    return 1
