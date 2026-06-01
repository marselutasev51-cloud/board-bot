"""
Push project files to GitHub via the Contents API (works on empty repos).
"""
import os
import sys
import json
import base64
import urllib.request
import urllib.error

TOKEN = os.environ["GITHUB_TOKEN"]
USERNAME = os.environ["GITHUB_USERNAME"]
REPO = "board-bot"
BRANCH = "main"
API = "https://api.github.com"


def gh(method: str, path: str, body=None):
    url = f"{API}{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"token {TOKEN}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body_text = e.read().decode()
        print(f"HTTP {e.code} on {method} {path}: {body_text}", file=sys.stderr)
        raise


def put_file(repo_path: str, content_bytes: bytes, message: str, sha: str = None):
    body = {
        "message": message,
        "content": base64.b64encode(content_bytes).decode(),
        "branch": BRANCH,
    }
    if sha:
        body["sha"] = sha
    return gh("PUT", f"/repos/{USERNAME}/{REPO}/contents/{repo_path}", body)


README = b"""\
# board-bot

Telegram bot that responds to any message as a board of 6 directors analyzing
content strategy tasks in Russian.

## Directors

| | Role | Focus |
|---|---|---|
| \xf0\x9f\x8f\xa2 | CEO | Strategy & brand positioning |
| \xf0\x9f\x92\xb0 | CFO | ROI, budget, financial risk |
| \xf0\x9f\x93\xa3 | CMO | Audience, channels, campaigns |
| \xf0\x9f\x8e\xa8 | Creative Director | Concepts, visuals, tone of voice |
| \xf0\x9f\x9a\x80 | Head of Virality | Viral mechanics, trends, reach |
| \xe2\x9a\x99\xef\xb8\x8f | COO | Execution, processes, timelines |

## Commands

- `/start` - introduction to the board
- `/help` - usage guide
- `/summary` - structured summary of key decisions from the conversation
- `/reset` - clear conversation history

## Setup

1. Create a bot via [@BotFather](https://t.me/BotFather) and get your token.
2. Get an [OpenAI API key](https://platform.openai.com/api-keys).
3. Set environment variables:
   ```
   TELEGRAM_BOT_TOKEN=your_token
   OPENAI_API_KEY=your_key
   ```
4. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
5. Run:
   ```bash
   python bot/main.py
   ```

## Features

- Each message is analyzed by all 6 directors in their own voice
- Per-chat conversation history (last 20 messages) for contextual follow-ups
- `/summary` generates a structured board meeting summary with decisions and action items
- Russian language throughout
"""

FILES = [
    ("README.md",        README),
    ("bot/main.py",      open("bot/main.py", "rb").read()),
    ("requirements.txt", open("requirements.txt", "rb").read()),
    (".gitignore",       open(".gitignore", "rb").read()),
]

print(f"Pushing to github.com/{USERNAME}/{REPO} ...")

for repo_path, content in FILES:
    print(f"  Uploading {repo_path} ...")
    put_file(repo_path, content, f"Add {repo_path}")
    print(f"  OK")

print(f"\nDone! https://github.com/{USERNAME}/{REPO}")
