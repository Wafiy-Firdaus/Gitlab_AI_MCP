import logging
import sys

import structlog
from mcp.server.fastmcp import FastMCP

from config import settings
from tools.ci_cd import register_ci_cd_tools
from tools.issues import register_issue_tools
from tools.merge_requests import register_merge_request_tools
from tools.projects import register_project_tools
from tools.repository import register_repository_tools
from tools.search import register_search_tools

# Configure structured logging
structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer() if not settings.debug else structlog.processors.ConsoleRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO if not settings.debug else logging.DEBUG),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
    cache_logger_on_first_use=True,
)
logger = structlog.get_logger(__name__)

# Initialize FastMCP server
mcp = FastMCP(
    "Gitlab_AI_MCP",
    dependencies=["httpx", "pydantic", "pydantic-settings", "structlog"]
)

# Register tools from various modules
register_project_tools(mcp)
register_issue_tools(mcp)
register_merge_request_tools(mcp)
register_search_tools(mcp)
register_repository_tools(mcp)
register_ci_cd_tools(mcp)

# MCP Prompt Templates
@mcp.prompt()
def review_mr(project_id: str, mr_iid: str) -> str:
    """
    Guides the AI through a structured, high-performance Merge Request review.
    """
    p_id = str(project_id).strip().rstrip(",")
    m_iid = str(mr_iid).strip().rstrip(",")
    
    return f"""You are a senior staff engineer performing an exhaustive review of Merge Request !{m_iid} in project {p_id}.
    
Goal: Ensure code quality, security, and architectural alignment while providing actionable feedback.

Recommended Workflow:
1. **Context Gathering**: Fetch MR details ('get_merge_request_details') to understand the intent.
2. **Deep Dive**: Examine all code changes ('get_merge_request_diffs'). Look for performance bottlenecks or security flaws.
3. **Historical Context**: Read existing discussions ('get_merge_request_notes') to avoid repeating previous feedback.
4. **Comprehensive Review**: 
   - Summarize the changes concisely.
   - Categorize findings into: Critical, Major, and Minor.
   - Propose specific code improvements.
5. **Finalize**: Post your review as a comment using 'create_merge_request_note'.

Execute step 1 now."""

@mcp.prompt()
def debug_job(project_id: str, job_id: str) -> str:
    """
    Guides the AI through rapid debugging of a failed CI/CD job.
    """
    p_id = str(project_id).strip().rstrip(",")
    j_id = str(job_id).strip().rstrip(",")
    
    return f"""You are a DevOps expert debugging a failed pipeline job (ID: {j_id}) in project {p_id}.
    
Goal: Identify the root cause and provide a clear path to resolution.

Recommended Workflow:
1. **Analyze Logs**: Use 'analyze_failed_job' to surgically extract error segments from the log.
2. **Inspect Code**: If the error points to a specific file, read its content using 'get_file_content'.
3. **Verify Environment**: Check relevant project structure if needed with 'list_repository_files'.
4. **Diagnose**: Determine if it's a transient infra issue, a test failure, or a code-level regression.
5. **Resolve**: Provide a detailed explanation and a suggested fix.

Start by analyzing the failed job log."""

def main():
    """Main entrypoint for the high-performance MCP server."""
    mcp.run()

if __name__ == "__main__":
    main()
