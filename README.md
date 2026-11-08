# Fieldnotes — Research Graph

A local-first, source-backed research workspace. It helps a researcher organize evidence and review documented connections; optional username checks return unverified public-profile candidates, never confirmed identities.

## What is in this MVP

- Separate investigations, each with its own people memberships, sources, findings, and relationships.
- A shared people directory: a canonical person identity can be linked into several investigations. Aliases, notes, usernames, findings, and relationship claims stay investigation-specific; matching names are never auto-merged.
- An interactive, searchable relationship graph. Search includes matching people and their direct connections.
- Source records with URL, title, publisher, and retrieval date.
- Findings and relationship claims that must cite a source in the same investigation; the Add Person form can create an initial sourced connection atomically.
- Multiple researcher-entered usernames per person, saved within the current investigation. Search each username individually against up to 25 explicitly selected public sites from a locally pinned 289-site HTTPS catalog.
- Username checks send bounded HTTPS `HEAD` requests only, with no proxies or profile-page/body scraping. Each check requires an authorization/public-interest acknowledgment. A returned URL is only a candidate and must be verified manually; site behavior, terms, and rate limits can vary.
- Researcher-entered confidence and review status (`unreviewed`, `corroborated`, `disputed`).
- JSON export and full investigation deletion.
- Optional AI review of explicitly selected saved sources; the model's output stays an unsaved draft.
- PostgreSQL data persisted in a Docker volume; API and browser UI are served by one container.

This MVP does not crawl pages, scrape profile content, search data brokers, infer sensitive traits, bulk-scan saved people, or automatically link candidate accounts to a person. Public availability alone does not establish that data collection or reuse is lawful or appropriate; follow applicable law, platform terms, editorial standards, consent/authorization requirements, and retention policies.

## Run on Windows + WSL2

Keep the project in the WSL Linux filesystem (not `/mnt/c`) for performance. In Ubuntu WSL:

```bash
cd ~/projects/persona-research-graph
./scripts/start.sh
```

Then open **http://127.0.0.1:8000** in your Windows browser. The API reference is at **http://127.0.0.1:8000/docs**.

The first run creates a random local database password in `.env` (ignored by Git), builds the app image, and starts PostgreSQL plus the app. If Docker's WSL integration is enabled, the script uses Docker Compose. If it is not, the script uses the Docker Desktop CLI through WSL interop and streams the source as a build archive; no host bind mount is used.

Stop the app without deleting data:

```bash
./scripts/stop.sh
```

The PostgreSQL volume is named `fieldnotes-db` and persists across restarts. **Do not run `docker compose down -v` or remove that volume** unless you intend to erase all saved investigations. If you need ordinary `docker` commands within Ubuntu, Docker Desktop → **Settings → Resources → WSL Integration** → enable Ubuntu, then Apply; this project script does not change Docker Desktop settings for you.

## Tests and backups

Run the backend API tests in a disposable Python container:

```bash
./scripts/test.sh
```

Run a live API, frontend-asset, and source-provenance smoke test. It creates and removes only fictional test records:

```bash
node scripts/smoke-live.mjs
```

To verify the PostgreSQL volume survives a container restart, run the persistence smoke test. It restarts the app and database containers, but removes its synthetic case afterward:

```bash
node scripts/smoke-persistence.mjs
```

Create a restricted-permission SQL backup in `backups/`:

```bash
./scripts/backup.sh
```

Backups and `.env` are private research data/secrets. Store them securely, do not commit them, and periodically test restoring a backup before relying on it.

## Shared people and username checks

A person identity is shared across the local people directory and can be linked into more than one investigation. Case-specific aliases, notes, usernames, findings, and relationship evidence stay attached to each investigation membership. Linking never copies notes from another workspace, and same-name records are not merged automatically.

Select a person on the map to add multiple usernames. Enter handles separated by commas or new lines, then check each handle separately. Pick up to 25 sites for each check from the locally pinned Sherlock Project metadata catalog. The app never scans every saved person or username in the background. Each check requires a confirmation that there is consent/authorization or a documented public-interest basis.

The username checker makes HTTPS `HEAD` requests only, capped at three concurrent requests per scan; it does not use proxy settings, impersonate a browser, follow redirects, or read/store profile response bodies. Adult sites and site definitions requiring non-HEAD methods are excluded. Sites may block checks or return misleading status codes. `candidate` means only that the profile URL responded as possibly available—it is not proof the investigated person owns the account. Verify candidate accounts manually with independent sources before recording a relationship or drawing a conclusion. Sherlock Project metadata attribution and license are in `THIRD_PARTY_NOTICES.md`.

## Optional AI review

AI is disabled by default. It analyzes only source records you select and their linked, already-saved claims/excerpts; it does **not** search the web or fetch pages. Each request requires a confirmation checkbox. The app sends selected source metadata, associated names and findings/relationship notes, and your question to the configured provider; it does not send source URLs or unrelated case records. AI replies are not saved automatically, and the server checks whether quoted evidence appears verbatim in the selected excerpts.

To configure OpenCode Console, create/copy an API key in OpenCode Console, open the **AI review** tab in Fieldnotes, and paste it into **AI provider settings**. Use:

- Provider: `OpenCode Console`
- Base URL: `https://opencode.ai/inference/openai/v1`
- Model: your paid or Go model ID

For OpenCode Go, use `https://opencode.ai/inference/go/openai/v1`. Other OpenAI-compatible providers can use their HTTPS base URL and model ID. OpenCode Console free-tier chat models are limited to OpenCode itself; this app needs a paid or Go model. The separate local `opencode serve` session/agent API is not connected.

Fieldnotes cannot read a key from another website's browser session; you must paste the key into Fieldnotes. The browser sends it to the local server, which stores it in the separate Docker volume `fieldnotes-settings` with restrictive file permissions. The key is never returned to the browser, stored in the research database, or included in SQL backups. This local volume is **not encrypted**; protect your Windows account and Docker data. Use the Clear local settings button to remove it. If server-side `.env` provider settings exist, saved Fieldnotes settings take precedence; clearing them returns to the environment configuration.

Provider retention and training policies still apply to anything you explicitly send. The model receives no tools and does not do live web search; a separate source-cited public search connector remains future work.

## Development

- Backend: Python 3.14, FastAPI, SQLAlchemy.
- Frontend: React 19, TypeScript 7, Vite 8, `react-force-graph-2d`.
- Database: PostgreSQL 17. Tests use isolated in-memory SQLite.
- Local app port is bound only to `127.0.0.1:8000`; PostgreSQL is not published to the host.

After changing UI code, rebuild with `./scripts/start.sh`. If WSL Docker integration is enabled, the frontend can also be developed with `cd frontend && npm run dev` (Vite at `http://localhost:5173`, API proxy to port 8000).

### Important operational limits

This MVP is single-user and has no login, access roles, encryption layer, or production hardening. The loopback binding reduces network exposure; it is not user authentication. Anyone with access to your Windows/WSL account or Docker data can access or copy the records. Use OS disk encryption, protect backups, and do not expose the port to a LAN or the public internet. Add authentication, database migrations, audit controls, formal retention/deletion policy, and a security review before any shared or production deployment.

## Contributing and license

Contributions are welcome; see [CONTRIBUTING.md](CONTRIBUTING.md) for setup, tests, and privacy/safety guardrails. Report vulnerabilities privately as described in [SECURITY.md](SECURITY.md). Fieldnotes is licensed under the [MIT License](LICENSE).
