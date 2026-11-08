# Changelog

All notable releases are documented here.

## [0.3.0] — 2026-11-07

Initial public release.

### Added

- Local-first investigation workspaces with source-backed findings, evidence-backed relationships, graph visualization, export, and deletion.
- Shared person identities that can be linked across investigations while keeping case-specific notes, aliases, usernames, findings, and relationship evidence separate.
- Optional evidence-backed relationship creation while adding or linking a person.
- Multiple usernames per person and manually triggered, selected-site public profile URL checks. Checks are bounded HTTPS `HEAD` requests; candidate accounts remain unverified and no profile content is scraped or stored.
- Optional AI review of explicitly selected material, with per-request sharing confirmation and response citations checked against saved excerpts.
- Local AI provider settings stored outside the research database; API keys are not returned to the browser.
- MIT license, contribution guidance, security reporting guidance, and third-party notices.

### Safety and operational notes

- The application is a local-only, single-user MVP with no login and is not hardened for LAN or public deployment.
- Username search checks only one saved handle per user action and up to 25 selected sites; it does not run automatically or link accounts to people.
- AI analysis is disabled until configured and always requires explicit provider-sharing confirmation.
