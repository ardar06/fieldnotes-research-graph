# Contributing

Thanks for helping improve Fieldnotes. Start with an issue describing the problem or proposal; keep proposed changes focused and explain their user impact.

## Development and tests

The supported development setup is Ubuntu on WSL2 with Docker Desktop:

```bash
cd ~/projects/persona-research-graph
./scripts/start.sh
./scripts/test.sh
```

The test script builds the frontend and runs backend tests in a disposable container. Do not use real investigations, API keys, or personal data in tests. Use synthetic fixtures and mock provider/network calls.

## Safety and privacy constraints

Please preserve these defaults unless a change has a clear, reviewed need:

- Keep investigation notes, evidence, usernames, and search results case-scoped; never auto-merge identities based only on matching names.
- Keep username checks user-initiated and limited to selected public sites. Do not add proxy rotation, stealth behavior, profile-body scraping, bulk/background searches, or automatic identity linking.
- Keep provider keys out of the browser response, database exports, logs, source control, and issue reports. Never send real investigation material from tests or CI.
- Keep source-backed claims distinguishable from assumptions and unverified candidate accounts.

## Pull requests

- Include a focused test for behavior changes and run `./scripts/test.sh`.
- Update README and `THIRD_PARTY_NOTICES.md` when behavior, configuration, or bundled third-party metadata changes.
- Do not commit `.env`, backups, database files, provider keys, real-person research, or private source material.
- Explain security, privacy, cost, and migration implications when a change affects collection, persistence, or provider requests.

## Reporting issues

Use synthetic names, URLs, and usernames. Redact provider keys, local database contents, source excerpts, and identifying details from logs or screenshots.
