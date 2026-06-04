# Use a slim Python image for a smaller footprint
FROM python:3.12-slim@sha256:090ba77e2958f6af52a5341f788b50b032dd4ca28377d2893dcf1ecbdfdfe203

# Set the working directory in the container
WORKDIR /app

# Copy all project files to allow the build backend to find the code
COPY . .

# Install dependencies
RUN pip install --no-cache-dir .

# Create non-root user for least-privilege execution
RUN adduser --disabled-password --gecos '' appuser \
    && chown -R appuser:appuser /app

# Expose the port if running as an SSE server (optional for stdio)
EXPOSE 8000

# Switch to non-root user
USER appuser

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Default command: run the MCP server via stdio
# Note: When using with Claude Code via stdio, you might run 'docker run -i ...'
CMD ["python", "server.py"]
