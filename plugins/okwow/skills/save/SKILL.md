---
name: save
description: Use whenever the user asks to remember, save, record, note, or write something up in okWOW (for example "remember this in okWOW", "save this to okWOW", "add this to our team knowledge"), or when you learn a decision, convention or finding a teammate will need later. Load this before calling create_memory, create_content, prepare_upload, create_task or update_task, and before working on an okWOW task; it covers choosing memory vs artifact vs file, the place and its audience, updates, and safe retries.
argument-hint: "[what to save]"
---

# Save to okWOW

Saves go through the `okwow` MCP server and act as the signed-in user. Members
of the chosen place can see what you save. Save what the user asks you to, and
save on your own when you learn something a teammate will need later: a
decision, a convention, a gotcha, a reference to an external system. Save it to
okWOW instead of your local memory, then tell the user what you saved and
where. If the user's instructions say to offer each fact first, offer it
instead. In private mode (`switch_mode`) saves stay the
user's own; in shared mode they reach the place's members.

## 1. Choose the place

Call `list_spaces` first. Each row has an `id`, a `label`, its audience and the
operations this connection may perform there. Pass the `id` as `in`:

- `space:<uuid>`: visible to every member of that space (a team area).
  Required for artifacts, files, skills, transcripts and tasks.
- `org:<uuid>`: visible to the whole organization. Memories only.
- `me`: the user alone, in every space. Listed in private mode. Memories only.

If the user did not say who should see it, ask which place before you save.

## 2. Choose what to save

- **Memory** (`create_memory`): one self-contained fact or decision a teammate
  could act on later, **at most 1,000 characters**. Example: "Release builds are
  signed in CI, never on a laptop." Split
  unrelated facts into separate memories.
- **Vault content** (`create_content`): anything longer. `kind` is `auto`
  (default), `artifact`, `file`, `skill` or `transcript`. Pass `content` with a
  `title` for text; for an artifact set `format` to `markdown` (default),
  `html`, `python` or `tsx`. Optional `description` and `source_urls`. A `SKILL.md` becomes a skill (needs
  space admin; no description or source URLs). Pass `kind` when a filename is
  ambiguous.
- **File or large text**: call `prepare_upload` with the exact byte size
  (up to 40 MB), `PUT` the bytes to the returned `upload_url` (valid 15
  minutes), then call `create_content` with `upload` set to the returned
  `upload:<uuid>` id.
  Images go this way too (`kind: file`). To embed one in an `html` artifact,
  create the image first and use the receipt's `download_url` as the `<img src>`.
- **Task** (`create_task`): a to-do with an owner and optional due date,
  not a fact. See Tasks.

## 3. File memories in groups

A memory without `group` lands in the place's Inbox. `list_memories` for the
place also lists its groups; pass a group's `group:<uuid>` id as `group`, or
`group_name` to file it in the group of that name (created when missing).

## 4. Update instead of duplicating

`fetch` the item first; it returns a `version`. Pass that `version` back
unchanged to the matching update:

- `update_memory` for a stale or wrong fact (still 1,000 characters at most;
  `group` optionally moves it).
- `update_content` for an artifact, skill or transcript (text or `upload`).
- `update_memory` with a `group:<uuid>` id and `name` to rename a group.

A stale `version` fails and writes nothing: fetch again and reconcile. Never
edit or invent a version.

## 5. Write it so it holds up later

- Save only what you verified. Say how you know: implemented, tested,
  deployed, or only planned. Name the repository, branch, or PR when relevant.
- Put web pages or PRs an artifact relies on in `source_urls`.
- A memory has no URL field. To cite a web source, save it as an artifact
  first, then pass its `vault:<uuid>` id as the memory's `source`. The cited
  item must be readable in the same audience.
- Never save secrets, tokens, or personal data the user did not ask you to
  keep.

## Tasks

`create_task` needs a space (`in`), a title and an `owner` (`"me"`, or a user id
or email). The user is recorded as a watcher. The same title and owner again
returns the first task with `duplicate: true`. Use `list_tasks` to find tasks
(ids are `task:<uuid>`), then `update_task` to `start`, `complete`, `drop` (with a
reason), `reopen`, `assign` or `set_due`; this needs the editor role in that
space.

Before you work on a task (claim it, update its checklist, block, complete or
drop it), read `references/tasks.md` and follow it: it covers passing your
session, claims and how they lapse, asking a person, and the completion
report.

## 6. Retries

There is no idempotency key. If a save fails or times out, retry the same call
with the same place and the exact same content: okWOW recognizes content it
already holds and returns the existing item with `duplicate: true`. Retrying
`create_content` with the same `upload` returns the item it became. Do not
change the text between attempts, or you will create a second copy.

## 7. Report

Tell the user what you saved, where (the receipt's `in.label`), who can see it,
and which group a memory went into, and give the `url` from the receipt.

## Errors

- A write is refused on a read-only connection: the user approved "Read"
  access. Ask them to reconnect okWOW with "Read and write".
- `Connection expired or revoked`: ask the user to reconnect the okwow MCP
  server in their app.
- Ids always carry their prefix (`space:`, `org:`, `memory:`, `group:`,
  `vault:`, `task:`, `upload:`); bare UUIDs are refused.
