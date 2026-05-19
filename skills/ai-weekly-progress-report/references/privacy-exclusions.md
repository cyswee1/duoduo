# Privacy Exclusions

The collector is read-only and must skip sensitive or noisy assets by default.

## Excluded Names

- `.env`, `.env.*`
- `auth.json`, `credentials.json`, `secrets.json`
- files or folders containing: `token`, `secret`, `credential`, `password`, `private-key`, `id_rsa`, `id_ed25519`
- dependency/cache folders: `node_modules`, `.cache`, `.npm`, `.pnpm-store`, `vendor`, `.venv`, `venv`, `__pycache__`
- build outputs: `dist`, `build`, `target`, `.next`, `.nuxt`, `coverage`
- Git internals except read-only `git` commands: `.git`

## Excluded Content

- environment variables and API keys
- personal chat exports
- Feishu, DingTalk, Notion, Jira/TAPD, email, and CRM data
- binary files larger than the collector limit

## Allowed V1 Evidence

- Git commit metadata and changed file names from user-provided project roots
- local skill metadata and file names
- AI tool session index titles and update timestamps
- explicitly provided leader/team-member supplements
