# Use a slim Python image for a smaller footprint
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /app

# Copy all project files to allow the build backend to find the code
COPY . .

# Install runtime and local test dependencies.
# The public compose stack doubles as a validation environment for contributors.
RUN pip install --no-cache-dir . pytest pytest-asyncio

# Expose the port if running as an SSE server (optional for stdio)
EXPOSE 8000

# Default command: run the MCP server via stdio
# Note: When using with Claude Code via stdio, you might run 'docker run -i ...'
CMD ["python", "server.py"]
