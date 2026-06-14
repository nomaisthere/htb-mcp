from mcp.server.fastmcp import FastMCP

mcp = FastMCP("htb-mcp")

import tools.users
import tools.machines
import tools.search

if __name__ == "__main__":
    mcp.run()
