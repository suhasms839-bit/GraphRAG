import asyncio
import shlex
import sys
from asyncio.subprocess import PIPE
from typing import Optional

from ..core.config import settings


class MCPClient:
    """Simple stdio-based MCP client manager. Launches configured command and
    communicates via stdin/stdout. Designed to be optional and fail-safe.
    """

    def __init__(self):
        self.proc: Optional[asyncio.subprocess.Process] = None

    async def start(self):
        if not settings.GMAIL_MCP_ENABLED:
            return
        cmd = [settings.GMAIL_MCP_COMMAND]
        # allow args to be a comma or space separated list
        args = shlex.split(settings.GMAIL_MCP_ARGS)
        cmd.extend(args)
        try:
            self.proc = await asyncio.create_subprocess_exec(
                *cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE
            )
        except Exception:
            self.proc = None

    async def stop(self):
        if self.proc is None:
            return
        try:
            self.proc.terminate()
            await self.proc.wait()
        except Exception:
            pass
        finally:
            self.proc = None

    async def run(self, input_text: str, timeout: Optional[int] = None) -> str:
        """Send input_text to MCP and return its stdout. Timeout uses
        settings.GMAIL_MCP_TIMEOUT by default.
        """
        if not settings.GMAIL_MCP_ENABLED:
            return ""
        if self.proc is None:
            await self.start()
            if self.proc is None:
                return ""

        timeout = timeout or settings.GMAIL_MCP_TIMEOUT
        try:
            self.proc.stdin.write(input_text.encode("utf-8") + b"\n")
            await self.proc.stdin.drain()
            out = await asyncio.wait_for(self.proc.stdout.readline(), timeout=timeout)
            return out.decode("utf-8").strip()
        except Exception:
            return ""


_mcp_client: Optional[MCPClient] = None


def get_mcp_client() -> MCPClient:
    global _mcp_client
    if _mcp_client is None:
        _mcp_client = MCPClient()
    return _mcp_client
