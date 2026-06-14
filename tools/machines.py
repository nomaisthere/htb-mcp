from mcp.server.fastmcp import FastMCP
import requests

@mcp.tool()
def get_user(username: str):
    r = requests.get(
        f"https://api.example.com/users/{username}"
    )
    r.raise_for_status()
    return r.json()

