# 2026-09-25 — `tapestry deploy` (Render service creation from the terminal)

Added a `deploy` subcommand to `tapestry-cli` ([packages/cli/tapestry_cli/deploy.py](../../packages/cli/tapestry_cli/deploy.py)) that creates a Render service for the current repo via the Render REST API, from a small committed spec (`deploy/render-service.json`) or flags. It resolves the repo from `git origin`, resolves the Render owner, is idempotent (skips if a same-named service exists), posts `POST /v1/services` (build/start correctly nested under `serviceDetails.envSpecificDetails`), and attaches an existing env group by name. Stdlib-only (urllib), matching the rest of the CLI.

`--dry-run` prints the exact request without any network call or API key, and masks resolved secret values. 14 unit tests (mocked transport); version bumped to 0.1.6.

**Why:** creating + wiring a new Render service by hand in the dashboard for every project was the operator's most-repeated deploy chore. The Render CLI can't manage env groups and the dashboard is manual; the API can do all of it. Grounded in the 2026-09-21 research pass (official CLI vs REST API vs Terraform/Pulumi) — the REST API was the most complete surface, and this rides the existing `tapestry-cli` PyPI publish pipeline. The one irreducible manual step remains the one-time GitHub↔Render account authorization.
