---
name: save
description: Use whenever the user asks to remember, save, record, note, or write something up in okWOW (for example "remember this in okWOW", "save this to okWOW", "add this to our team knowledge"), or when you learn a decision, convention or finding a teammate will need later. Load this before calling create_memory, create_content, prepare_upload, create_task or update_task, and before working on an okWOW task; it covers choosing memory vs artifact vs file, the place and its audience, updates, and safe retries.
argument-hint: "[what to save]"
---

# Save to okWOW

Saves go through the `okwow` MCP server and act as the signed-in user. Save
what the user asks you to, and save on your own when you learn something a
teammate will need later: a decision, a convention, a gotcha, a reference to an
external system. Save it to okWOW instead of your local memory, then tell the
user what you saved, where, and who can see it. If the user's instructions say
to offer each fact first, offer it instead.

## Mode: who sees a save

Every result carries the connection's `mode`. A new connection starts in
private mode.

- **private:** saves are the user's own, filed in the place you name, and
  nobody else sees them. You read the user's own items and the team's.
- **shared:** saves reach the members of the place. You read only what the
  team can see.

Before a save, know the mode (from the last result) and the place's
audience (its `list_spaces` row), and state both when you report the save.
Save in the mode you are in. When a private save holds something teammates
need, say it is private and suggest shared mode. Call `switch_mode` only when
the user says so. Switching changes where new saves land; an item saved
earlier keeps its audience. The mode belongs to this connection and stays
until someone switches it, across sessions. A space with a `private` audience
still has members: a shared-mode save there reaches them, and anyone added
later. Private mode refuses saves to `org:` and `create_task`; shared mode
refuses `me`.

How places, roles, modes and item kinds work is explained at
https://okwow.ai/docs/how-okwow-works/.

## 1. Choose the place

Call `list_spaces` first. Each row has an `id`, a `label`, its audience and the
operations this connection may perform there. Pass the `id` as `in`:

- `space:<uuid>`: a team area; in shared mode, visible to its members.
  Required for artifacts, files, transcripts and tasks.
- `org:<uuid>`: visible to the whole organization. Memories, memory groups
  and skills only; saving here needs shared mode.
- `me`: the user alone, in every space. Listed in private mode only.
  Memories and skills only.

Pick the place when the topic and a space's name and members make it obvious,
and say which. Ask when no place clearly fits, or when the save is about a
person or a customer, an unreleased plan, or anything near a secret: check who
can see a place before you put those there.

## 2. Choose what to save

- **Memory** (`create_memory`): one self-contained fact or decision a teammate
  could act on later, **at most 1,000 characters**. Example: "Release builds are
  signed in CI, never on a laptop." Split
  unrelated facts into separate memories.
- **Vault content** (`create_content`): anything longer. `kind` is `auto`
  (default), `artifact`, `file`, `skill` or `transcript`. Pass `content` with a
  `title` for text; for an artifact set `format` to `markdown` (default),
  `html`, `python` or `tsx`. Optional `description` and `source_urls`. The
  `title` is a plain name with no `/` or `\`. Up to 200,000 characters go
  inline; upload anything larger. Pass `kind` when a filename is ambiguous.
- **Skill** (`create_content` with a `SKILL.md`): needs editor in a space;
  any member may save one in the organization (shared mode) or in `me`
  (private mode). It takes no description or source URLs, and only the
  `SKILL.md` text goes with it, so inline what teammates need. A second skill
  with the same name is refused: update the existing one.
- **File or large text**: call `prepare_upload` with the exact byte size
  (up to 40 MB), `PUT` the bytes to the returned `upload_url` (valid 15
  minutes), then call `create_content` with `upload` set to the returned
  `upload:<uuid>` id.
  Images go this way too (`kind: file`). To embed one in an `html` artifact,
  create the image first and use the receipt's `download_url` as the `<img src>`.
- **Task** (`create_task`): a to-do, not a fact. See Tasks.

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
edit or invent a version. Search before you save a new fact: update a near
copy instead of adding a second one.

## Retract a wrong save

If you saved something wrong, or to the wrong place, `delete_content` with its
id removes it for every member of the place, and the user cannot restore it
themselves. Delete a save you made in this session when it is wrong, and tell
the user; confirm with the user before deleting anything else. Then save it
again in the right place.

To share an item you saved privately, save it again in shared mode, then
offer to delete the private copy so search does not return both.

## 5. Write it so it holds up later

- Save only what you verified. Say how you know: implemented, tested,
  deployed, or only planned. Name the repository, branch, or PR when relevant.
- Put web pages or PRs an artifact relies on in `source_urls`.
- A memory has no URL field. To cite a web source, save it as an artifact
  first, then pass its `vault:<uuid>` id as the memory's `source`. The cited
  item must be readable in the same place.
- Never save secrets, tokens, or personal data the user did not ask you to
  keep.

## Tasks

`create_task` needs shared mode, the editor role, a space (`in`) and a title.
`owner` is optional: `"me"`, or `{"email": ...}`, `{"user_id": ...}`,
`{"person": ...}` or `{"slack_user_id": ...}`; never a bare name. Give work to
someone else only when the user asks. `tracked: false` keeps a task off the
team's board as your own checklist, with no owner or due date. The user is
recorded as a watcher. The same title and owner again returns the first task
with `duplicate: true`. Use `list_tasks` to find tasks (ids are
`task:<uuid>`), then `update_task` to `start`, `complete`, `drop` (with a
reason), `reopen`, `assign` or `set_due`; this needs the editor role in that
space.

Before you work on a task (claim it, update its checklist, block, complete or
drop it), read `references/tasks.md` and follow it: it covers passing your
session, claims and how they lapse, asking a person, and the completion
report.

## 6. Retries

There is no idempotency key. If a create times out or fails without a reason
("The operation could not complete"), retry the same call with the same place
and the exact same content: okWOW recognizes content it already holds and
returns the existing item with `duplicate: true`. Retrying `create_content`
with the same `upload` returns the item it became. Do not change the text
between those attempts, or you will create a second copy. A refusal that gives
a reason stored nothing: fix the call and send it again.

## 7. Report

Tell the user what you saved, where (the receipt's `in.label`), in which
`mode`, who can see it (the place's audience in shared mode, only the user in
private mode), and which group a memory went into, and give the `url` from the
receipt.

## Errors

A refusal stored nothing and its message says what to do next: follow it.
