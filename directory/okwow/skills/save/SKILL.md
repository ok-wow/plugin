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

Every result says the connection's `mode`; a new connection starts private.
In private mode a save is the user's alone; in shared mode it reaches the
place's members. Private mode refuses saves to `org:` and `create_task`;
shared mode refuses `me`.

Save in the mode you are in. When a private save holds something teammates
need, say so and suggest shared mode; call `switch_mode` only when the user
says so. How places, roles and modes work is explained at
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
  `html`, `python` or `tsx`. Optional `description` and `source_urls`.
- **Skill** (`create_content` with a `SKILL.md`): needs the editor role in a
  space. Only the `SKILL.md` text is saved, so inline what teammates need from
  its other files. To change one, update the existing skill.
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

`create_task` needs shared mode, a space (`in`) and a title. `owner` is
optional and never a bare name; give work to someone else only when the user
asks. `tracked: false` keeps a task off the team's board as your own
checklist.

Before you work on a task (claim it, update its checklist, block, complete or
drop it), read `references/tasks.md` and follow it.

## 6. Retries

If a create times out or fails without a reason, retry the same call with the
same place and exactly the same content: okWOW returns the item it already
saved, with `duplicate: true`. Changing the text between attempts creates a
second copy.

## 7. Report

Tell the user what you saved, where (the receipt's `in.label`), in which
`mode`, who can see it (the place's audience in shared mode, only the user in
private mode), and which group a memory went into, and give the `url` from the
receipt.

## Errors

A refusal stored nothing and its message says what to do next: follow it.
