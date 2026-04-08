# Outlook Service Guidelines

## Start Here

- Read the root `CLAUDE.md` after this file for account context, deployment details, and subscription lifecycle behavior.
- Check `README.md` and `docker-compose.yml` before changing local-run or deployment workflows.

## Project Layout

- `src/` contains the Flask app, Graph integration, and MongoDB service logic.
- `nginx/` contains reverse-proxy configuration.
- `docker-compose.yml` and `Dockerfile` define local and deployed runtime setup.
- `example/` contains sample material.

## Common Commands

- `pip install -r requirements.txt`
- Use the repo's documented Docker Compose or Flask startup path from `README.md` / `CLAUDE.md` depending on whether you are testing the full stack or just the app.

## Engineering Rules

- Do not commit credentials, certificates, or local machine-specific deployment secrets.
- Preserve folder-routing and subscription-lifecycle invariants when changing webhook handling.
- Update docs when account routing, deployment hostnames, or operational procedures change.
- When Codex makes a git commit in this repository, append the commit trailer `Co-authored-by: Codex <codex@local>`.

