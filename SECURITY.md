# Security policy

Fieldnotes is a local-first, single-user research workspace. It currently has no login or role system and is not hardened for LAN or public-internet exposure. Keep it bound to localhost and protect the Windows/WSL account and Docker volumes.

## Reporting a vulnerability

Please do not open a public issue containing exploit details, real investigation records, API keys, or provider responses. Use GitHub's private vulnerability reporting for this repository if available; otherwise contact the repository maintainer privately through GitHub and provide a minimal synthetic reproduction.

## Sensitive data

Never include real-person investigation material, source excerpts, database backups, `.env` files, API keys, or private Docker volume contents in bug reports, pull requests, screenshots, or tests. If a secret is accidentally published, revoke it with its provider immediately; deleting it from a commit does not invalidate it.
