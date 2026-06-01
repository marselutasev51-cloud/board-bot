#!/usr/bin/env bash
set -e

REPO_NAME="board-bot"
REMOTE_URL="https://${GITHUB_USERNAME}:${GITHUB_TOKEN}@github.com/${GITHUB_USERNAME}/${REPO_NAME}.git"

echo "Setting up git identity..."
git config user.email "bot@replit.com"
git config user.name "Replit Agent"

echo "Adding GitHub remote..."
git remote remove github 2>/dev/null || true
git remote add github "$REMOTE_URL"

echo "Pushing to github.com/${GITHUB_USERNAME}/${REPO_NAME}..."
git push github main --force

echo "Done! Repository available at: https://github.com/${GITHUB_USERNAME}/${REPO_NAME}"
