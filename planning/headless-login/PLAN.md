# Plan: headless-login

Session `headless-login`, home repo `ok-wow/plugin`.

## Pass 1 — 2026-11-20 — specs none (follow-ups from HLG-2.1 staging verification)

No spec file; the input was the follow-up list from the 2026-11-20 staging run of headless sign-in
(0.1.52 from PR #17), refined in a planning conversation. Specs planned: none registered.

### Goal

Headless and browser sign-in are both first-class, and setup caters to both. Browser sign-in stays
intact. The server the CLI, the hook and the MCP relay talk to is resolved one way, and a mismatch is
visible instead of surfacing as an opaque error.

### What was found (verified against 0.1.52, `plugins/okwow/scripts/okwow-capture`)

- `server()` (CLI, uploads) prefers the saved `capture.json` server. `plugin_server()` (MCP relay)
  ignores it and uses `OKWOW_MCP_URL`, else prod. The token file records one server, so the two
  disagree: `status` showed prod with the staging variable set, and the relay answered "sign-in is
  for another server".
- `command_login` writes `capture.json`'s `server` for every login (first value wins:
  `--server`, saved pin, `OKWOW_MCP_URL`, prod), so an install-time login in a shell without
  `OKWOW_MCP_URL` pinned prod.
- The `SessionStart` hook and the relay's first call each spawn `login --quiet` once per app
  (`ask_once`). With no browser it cannot open, the one-time marker is spent, and the relay text says
  "okWOW opened in your browser".
- `hooks.json` and `.mcp.json` run bare `python3`; `.mcp.json` passes only `OKWOW_MCP_URL` through
  `env_vars`, so `OKWOW_CAPTURE_HOME` and `OKWOW_CAPTURE_STATE` (already honored, lines 70-71) never
  reach the relay.
- Hook processes inherit Claude Code's environment, so env vars set there reach the hook. The relay
  only receives what `env_vars` lists.

### Technical design

Business logic (all in `plugins/okwow/scripts/okwow-capture`):
- One `resolve_server(explicit=None) -> (url, source)` with the order `--server`, `OKWOW_MCP_URL`,
  saved pin in `capture.json`, production. `source` is one of `flag`, `env`, `config`, `default`.
  `server()`, `plugin_server()`, `command_login` and `command_mcp` all call it.
- `login` writes the pin only when `--server` was passed explicitly (or finishing a headless sign-in
  that was started with `--server`). The env var and the default never pin.
- `status` prints the server and its source, and warns when the saved token's server differs from the
  resolved one. Relay and upload errors for a server mismatch name both servers.
- Browser detection `browser_available()`: `webbrowser.get()` succeeds and, on Linux, `DISPLAY` or
  `WAYLAND_DISPLAY` is set and `SSH_CONNECTION` is not. macOS and Windows count as available.
  The hook and the relay auto-open sign-in only when it is true; otherwise they print both commands
  (browser and `--headless`) and do not spend the `ask_once` marker. `status` reports the result.
- Interpreter fallback and config-home passthrough in `.mcp.json` and `hooks.json`.

Views/UX: the setup skill asks which sign-in to use (browser here, or from another device with
`--headless`), with the detected default marked and both described as equals. `login --agent x` stays
the browser flow.

APIs and DB: none.

Out of scope, decided in planning:
- Per-server token and config layout. Decision 1 was "minimal": keep one token file. Revisit if
  staging and prod sign-ins need to coexist.
- Session capture default for sandboxes. Decision 3 was "leave": capture uploaded sandbox sessions to
  the user's staging chats with no failure; documented behavior, unchanged.
- Prod verification of headless sign-in stays under HLG-2.1 (needs an ok-wow-infra release carrying
  HLG-1.1).

### Tasks

| Task | Repo | Title | Depends on | Complexity / model | Hours |
|---|---|---|---|---|---|
| HLG-3.1 | ok-wow/plugin | fix: resolve the okWOW server one way across CLI, hook and relay | — | 3 / sonnet | 3 |
| HLG-3.2 | ok-wow/plugin | feat: show the server's source in status and name both servers on a mismatch | 3.1 | 2 / haiku | 2 |
| HLG-3.3 | ok-wow/plugin | feat: open sign-in automatically only when a browser is available | 3.1 | 3 / sonnet | 3 |
| HLG-3.4 | ok-wow/plugin | docs: let setup offer browser and headless sign-in as equals | 3.3, 1.3 | 2 / haiku | 1 |
| HLG-3.5 | ok-wow/plugin | fix: fall back to python and pass config-home variables to the relay | — | 2 / haiku | 2 |
| HLG-3.6 | ok-wow/plugin | docs: document sign-in modes, staging, allow-list prefix and config location (0.1.53) | 3.1–3.5, 1.3 | 2 / haiku | 2 |

### Dependency map

```
[PRIOR] HLG-1.3 (PR #17, pr_open) — edits setup SKILL.md and both READMEs
[START]
  ├─ HLG-3.1 resolve_server
  │     ├─ HLG-3.2 status source and mismatch
  │     └─ HLG-3.3 browser detection, first-run behavior
  │           └─ HLG-3.4 setup skill offers both (also needs 1.3)
  ├─ HLG-3.5 interpreter fallback, env passthrough (no deps)
  └─ HLG-3.6 docs and release (needs 3.1-3.5 and 1.3)
```

3.1, 3.2 and 3.3 edit the same script and are ordered so no two run at once on it.

### Breaking change safety

All six tasks are safe to deploy standalone.
- 3.1 changes precedence: a user with both a saved pin and `OKWOW_MCP_URL` now follows the env var.
  That is the intended fix and the documented order. Existing pins stay in place and still apply when
  the env var is unset. No consumers outside the plugin read these files.
- 3.2 and 3.3 add output lines and a detection helper; no removal or rename.
- 3.5 adds fallbacks and extra env pass-through; no behavior removed.
- Version bump and `clientInfo` change together in 3.6, as in HLG-1.3.

### Decision Log

- Server and config layout: minimal (one token file, unified precedence, no auto-pin) — chosen by
  the owner over a per-server token layout.
- First-run sign-in: detect (auto-open only when a browser is available) — chosen over never
  auto-opening and over always auto-opening.
- Session capture for headless machines: leave as is — chosen by the owner; the staging uploads
  caused no failure.
