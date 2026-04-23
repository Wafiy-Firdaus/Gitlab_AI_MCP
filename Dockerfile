# Use a slim Python image for a smaller footprint
FROM python:3.14-slim

# Set the working directory in the container
WORKDIR /app

# Copy all project files to allow the build backend to find the code
COPY . .

# Install dependencies
RUN pip install --no-cache-dir .

# Expose the port if running as an SSE server (optional for stdio)
EXPOSE 8000

# Default command: run the MCP server via stdio
# Note: When using with Claude Code via stdio, you might run 'docker run -i ...'
CMD ["python", "server.py"]
