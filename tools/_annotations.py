"""
Pre-built MCP ToolAnnotations for consistent tool classification.

MCP annotations are OPTIONAL metadata — clients that don't support them
silently ignore the fields.  No change to tool execution or parameters.

READ_ONLY:      No side-effects; safe for auto-execution.
WRITE_IDEMPOTENT: Mutates state; repeating the call with same params
                   produces the same result (safe to retry).
WRITE_DESTRUCTIVE: Mutates state; each call may produce a new side-effect
                    (creates, triggers, posts).
"""

from mcp.types import ToolAnnotations

READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=True,
)

WRITE_IDEMPOTENT = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=True,
    idempotentHint=True,
    openWorldHint=True,
)

WRITE_DESTRUCTIVE = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=True,
    idempotentHint=False,
    openWorldHint=True,
)
