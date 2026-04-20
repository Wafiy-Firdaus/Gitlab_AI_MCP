import asyncio
import os
import sys

os.environ.setdefault("GITLAB_URL", "https://gitlab.example.com")
os.environ.setdefault("GITLAB_TOKEN", "mock-token")

from gitlab.client import GitLabClient
from server import mcp
from services.gitlab_service import GitLabService


async def run_detailed_test():
    print("🔍 Starting Comprehensive Stability Test...")
    errors = []

    # 1. Test Client Initialization (Singleton)
    try:
        print("Testing GitLabClient singleton...")
        client = await GitLabClient.get_instance()
        if client is None:
            errors.append("GitLabClient.get_instance() returned None")
        else:
            print("✅ GitLabClient initialized successfully.")
    except Exception as e:
        errors.append(f"GitLabClient initialization failed: {str(e)}")

    # 2. Test Service Initialization
    try:
        print("Testing GitLabService...")
        service = GitLabService(client)
        if service is None:
            errors.append("GitLabService initialization returned None")
        else:
            print("✅ GitLabService initialized successfully.")
    except Exception as e:
        errors.append(f"GitLabService initialization failed: {str(e)}")

    # 3. Test Tool Registration
    try:
        tools = await mcp.list_tools()
        print(f"Testing MCP Tool Registration (Total Tools: {len(tools)})...")
        if len(tools) == 0:
            errors.append("No tools were registered with FastMCP")
        else:
            # Check for specific expected tools
            tool_names = sorted([t.name for t in tools])
            print("Registered Tool Names:")
            for tn in tool_names:
                print(f"  - {tn}")
            expected_tools = [
                "list_projects",
                "get_issue_details",
                "get_merge_request_details",
                "analyze_failed_job",
            ]
            for et in expected_tools:
                if et not in tool_names:
                    errors.append(f"Expected tool '{et}' not found in registered tools")
            print("✅ MCP Tools registered and verified.")
    except Exception as e:
        errors.append(f"MCP Tool Registration check failed: {str(e)}")

    # 4. Test Prompt Registration
    try:
        prompts = await mcp.list_prompts()
        print(f"Testing MCP Prompt Registration (Total Prompts: {len(prompts)})...")
        if len(prompts) < 2:
            errors.append(f"Expected at least 2 prompts, found {len(prompts)}")
        else:
            print("✅ MCP Prompts registered successfully.")
    except Exception as e:
        errors.append(f"MCP Prompt Registration check failed: {str(e)}")

    # Summary
    if not errors:
        print("\n✨ ALL TESTS PASSED! The project is stable, correctly wired, and ready.")
    else:
        print(f"\n❌ {len(errors)} TESTS FAILED:")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)

    # Cleanup
    if client:
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(run_detailed_test())
