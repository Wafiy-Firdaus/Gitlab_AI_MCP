import os

# Force test values BEFORE any project module is imported so the Settings
# singleton always picks these up instead of any local .env or shell-exported
# variables on the developer's machine.
os.environ["GITLAB_URL"] = "https://gitlab.example.com"
os.environ["GITLAB_TOKEN"] = "test-token"
