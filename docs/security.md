# Security and data handling (SOC 2-oriented, not audited)

Status: design intent only. No SOC 2 audit has been performed.

| Control area | v1 approach |
|---|---|
| Secrets | API keys via env or OS keychain (`keyring`); never stored in repo or DB |
| Network exposure | Server binds 127.0.0.1 only; no telemetry |
| Audit log | Append-only revision and event tables |
| Data export/delete | `drillpad export` / planned `drillpad purge` |
| Encryption | Sync bundles encrypted client-side before upload |
| Dependencies | Pinned via uv lock; `pip-audit` in CI |
| Third-party data flow | Code and transcripts go to Anthropic API only when interviewer features are enabled; Anki media never sent |
| Code execution | Subprocess + rlimits + timeout (self-run only); consumer version requires container/microVM isolation |
