# okWOW plugin

Search and save your okWOW knowledge from your coding agent. One plugin serves
every supported app (see [Install the plugin](#install-the-plugin)). It
connects your agent to the okWOW MCP server and adds four skills:

- **recall**: searches okWOW before answering questions about past decisions,
  conventions and project facts, then fetches and cites what it used.
- **save**: saves a verified fact as a memory or a write-up as a document, in a
  destination you choose.
- **setup**: a guided setup in chat (`/okwow:setup`): reads your okWOW account
  and your agent's setup first, then sets up people, spaces, skills,
  transcripts and session capture, and can move your agent's local memory
  into okWOW.
- **capture**: checks and changes session capture, which saves your agent
  sessions as okWOW chats (see [Send your sessions to okWOW](#send-your-sessions-to-okwow)).

The agent acts as you, with the access you have in okWOW. You choose "Read",
"Read and write" or "Manage account" when you connect, and you can revoke a
connection at any time in okWOW under Settings → Authorized apps.

## Releases

The commands below install the latest plugin, from `main`, and follow it as it
moves. Every change reaches `main` through a reviewed pull request. To stay on
one version instead, see [Pin a version](#pin-a-version). Releases are listed on
[GitHub](https://github.com/ok-wow/plugin/releases).

## Install the plugin

### Claude Code

```bash
claude plugin marketplace add ok-wow/plugin
claude plugin install okwow@okwow
```

Start Claude Code. Your browser opens okWOW once: sign in and approve access.
The plugin's tools and session capture share this one sign-in. In the session
that was open while you signed in, run `/mcp` and reconnect
`plugin:okwow:okwow`; later sessions connect on their own. Session capture
needs "Read and write".

Then run `/okwow:setup` to set up your spaces, people and knowledge in chat.

Capture reads Claude Code's session files in `~/.claude/projects` and routes
each session by the project folder Claude Code started it in
(`CLAUDE_PROJECT_DIR`), even after the session moves to another folder.

### Codex

```bash
codex plugin marketplace add ok-wow/plugin
codex plugin add okwow@okwow
codex mcp login okwow
```

`codex plugin marketplace add` also takes a local folder holding this
repository. `codex mcp login` opens okWOW in your browser to sign in and
approve access. It is a sign-in of its own for the okWOW tools in Codex:
Codex does not use the plugin's shared sign-in for its MCP connection, so
session capture still opens okWOW once on its own. Then ask Codex to run the
okWOW setup skill.

Codex runs the plugin's own session capture hooks (`hooks/hooks.json`). It asks
you once to trust them, and asks again whenever a hook or a script it runs
changes, for example after a plugin update. Capture reads Codex's session files
in `~/.codex/sessions` and routes each session by the folder recorded in the
file's first line, where Codex started it.

### Gemini CLI

```bash
gemini extensions install https://github.com/ok-wow/plugin
```

Then run `/mcp auth okwow` in Gemini CLI. Your browser opens okWOW: sign in and
approve access. The Gemini extension includes the recall and save skills; it
does not include setup or session capture.

### Pin a version

To install one release and stay on it, add its tag (the latest is on the
[releases page](https://github.com/ok-wow/plugin/releases)):

```bash
claude plugin marketplace add https://github.com/ok-wow/plugin.git#v0.1.48
codex plugin marketplace add ok-wow/plugin --ref v0.1.48
gemini extensions install https://github.com/ok-wow/plugin --ref v0.1.48
```

A pinned install does not move until you add the marketplace again with a newer
tag.

## Send your sessions to okWOW

Session capture saves each coding session as one of your okWOW chats, so your
conversations with every AI end up in one place and feed your team's
knowledge. okWOW stores the session in its model-neutral chat format and
processes it like a chat in the app: a title, a summary and the memories it
learns, which start as yours. A session is sent when it ends or after 30 idle
minutes; if you resume it, the new turns are added to the same chat.

There is nothing to set up. The first session after you install the plugin
opens okWOW in your browser once to sign in, the same sign-in the okWOW tools
use. From then on each session is routed by where it started: its folder, and
inside git its remote and repository root. With no rules, sessions go to your
default space ([Choose where sessions go](#choose-where-sessions-go)). Ask
your agent "are my sessions going to okWOW?" for the current state.

- **Private to you.** A captured session is your chat; other members cannot
  open it.
- **Secrets stay on your machine.** API keys and tokens for the common cloud,
  AI and developer services, JWTs, passwords, connection strings, credentials
  in URLs and headers, and the output of commands and files that hold
  credentials (`.env`, keys, `printenv`, `gh auth token`, Terraform state and
  more) are redacted before upload; okWOW redacts again before storing.
  System prompts and encrypted reasoning are never sent. Run
  `upload <session file> --dry-run` to see exactly what would be sent.
- **Only okWOW, only your sessions.** Capture talks only to okwow.ai over
  https and reads only the apps' own session files. It asks okWOW where a
  session goes, with only where it started, before reading the session's
  messages; a session your rules skip is never read further or sent.
  Repositories are named by their remote, with any credentials in the URL
  left out.
- **One connection.** The plugin signs in to okWOW once, as "okWOW plugin",
  and both its MCP tools and session capture use that sign-in. You can revoke
  it in okWOW under Settings → Authorized apps. On macOS its tokens are kept
  in your Keychain; elsewhere in a file only you can read. The plugin refuses
  a token or config file that other users could change.

Every app runs capture from the plugin's one set of hooks. The hooks name no
app: capture detects it from the session file's folder and the hook's
environment.

## Choose where sessions go

Ask your coding agent. It confirms each change with you before saving it:

- "Send this repo's sessions to Engineering."
- "Stop syncing this folder."

okWOW → Settings → Authorized apps → Agent sessions shows every rule and
edits them, and is where you pause capture.

## Connect without the plugin

The server is `https://api.okwow.ai/mcp` (Streamable HTTP, OAuth). These
paths add the tools without the skills.

### Claude Code

```bash
claude mcp add --transport http okwow https://api.okwow.ai/mcp
```

Then run `/mcp` in Claude Code and authenticate `okwow`.

### Codex

```bash
codex mcp add okwow --url https://api.okwow.ai/mcp
codex mcp login okwow
```

### Claude (claude.ai and Claude Desktop)

Open Customize → Connectors, choose Add custom connector, name it okWOW and
enter `https://api.okwow.ai/mcp`. Connect, then sign in to okWOW and
approve access.

### ChatGPT

In ChatGPT settings, open Apps & Connectors, turn on developer mode under
Advanced settings, and create a connector with the URL
`https://api.okwow.ai/mcp` and OAuth authentication. Sign in to okWOW and
approve access.

## Tools

| Tool | Access | What it does |
| --- | --- | --- |
| `get_profile` | Read | Shows the signed-in user, this connection, the organization and the user's role there |
| `switch_mode` | Read | Switches this connection between private and shared saving |
| `list_spaces` | Read | Lists available spaces, organizations and allowed actions, optionally with members |
| `create_space`, `update_space` | Read and write | Creates spaces; joins, leaves or changes one and who belongs |
| `list_invites` | Read | Lists organization invites sent and received |
| `create_invites` | Manage account | Invites people to the organization (admins and owners) |
| `update_invite` | Read and write | Accepts or declines an invite; admins revoke one |
| `get_session_capture` | Read | Shows where sessions that start in a folder go, and which rule applies |
| `set_session_capture_rule` | Read and write | Sends a folder's or repository's sessions to a space, or skips them |
| `remove_session_capture_rule` | Read and write | Removes a folder's or repository's rule |
| `search`, `fetch` | Read | Finds knowledge and reads exact items with source links |
| `list_memories`, `list_tasks` | Read | Browses saved knowledge and tasks |
| `create_memory`, `create_content`, `create_task` | Read and write | Saves knowledge, content and tasks |
| `update_memory`, `update_content`, `update_task` | Read and write | Changes existing items within your permissions |

The server may expose additional tools. The live connection defines its current
contract; see [MCP documentation](https://okwow.ai/docs/okwow-mcp/).

## Layout

One set of files serves every app:

```
.claude-plugin/marketplace.json   plugin marketplace
.agents/plugins/marketplace.json  marketplace metadata some apps read
plugins/okwow/
  .claude-plugin/plugin.json      plugin manifest
  .mcp.json                       okWOW MCP server
  hooks/hooks.json                session capture hooks, for every app
  scripts/okwow-capture           session capture client (Python 3, no dependencies)
  skills/recall/SKILL.md
  skills/save/SKILL.md
  skills/setup/SKILL.md           plus references/ loaded on demand
  skills/capture/SKILL.md
```

Check capture with `python3 tests/check_redaction.py` (planted secrets) and
`python3 tests/check_capture.py` (end to end against a fake okWOW). Check changes with `claude plugin validate --strict .` and
`claude plugin validate --strict plugins/okwow`. Bump `version` in
`plugin.json` to publish an update.

## License

MIT
