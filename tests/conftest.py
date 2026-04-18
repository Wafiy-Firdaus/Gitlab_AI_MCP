import os

# Set before any project module is imported so the Settings singleton picks
# these up instead of any local .env file that may exist on the developer's machine.
os.environ.setdefault("GITLAB_URL", "https://gitlab.example.com")
os.environ.setdefault("GITLAB_TOKEN", "test-token")
