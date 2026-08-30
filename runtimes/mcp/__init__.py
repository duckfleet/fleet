"""DuckFleet remote MCP runtime adapter (FastMCP, Streamable HTTP).

A hosting adapter only (Principle 3): it exposes the runtime-agnostic core as MCP tools so the
product is reachable from inside Claude / ChatGPT. No fleet/guardrail/schema logic lives here.
"""
