# okWOW refusals and what to do

A refused call stored nothing, so you can fix the call and send it again. The
message says why; the quoted text below is how it begins.

## Connection

- **"Connection expired or revoked. Reconnect to okWOW."** Ask the user to
  reconnect the okwow MCP server in their app.
- **"This connection was not granted okwow:write."** (or `okwow:read`) The
  user approved less access. Ask them to reconnect okWOW and approve "Read
  and write". `list_spaces` shows it ahead of time: every `operations` list
  holds only `read`.
- **`create_invites` is not among your tools.** The connection lacks "Manage
  account", or the user is not an organization owner or admin. Say which;
  reconnecting with "Manage account" helps only an owner or admin.

## Mode

- **"This connection is in private mode, where saves are the user's alone;
  organizations, tasks and edits to the team's items need shared mode."** You
  tried to save in `org:`, create a task, or edit a team item. Tell the user
  what you wanted to do and that it needs shared mode. Call `switch_mode` with
  `shared` only on their yes, then retry.
- **"in: me keeps things for the user alone, which needs private mode."** You
  saved to `me` in shared mode. Ask the user: save in a space instead, or
  switch to private.

## Role

- **"This action requires workspace role editor or higher; yours is
  viewer"** (or another role). Say who can do it: an editor or admin of that
  space (`list_spaces` with `members: true` names them). Do not retry.
  Changing a space's details or members needs admin; changing its audience
  needs the owner.
- **"Your role in this space cannot delete this item; nothing was
  deleted".** Same: name who can.
- **"Only a space open to the whole organization can be joined".** An admin
  of that space must add the user.

## Place and id

- **"in must be an exact space:UUID, org:UUID or me from list_spaces".**
  Call `list_spaces` and pass a row's `id`.
- **"Content can be saved in a space only"** or **"An organization holds
  skills only"** or **"me holds memories and inline SKILL.md skills only".**
  Save the item in a space.
- **"Tasks live in a space only".** Pass a `space:` id.
- **"A source must be a readable vault item in the same place".** Save the
  cited item in the same place as the memory first.
- **"id must be an exact ..."**, or a bare UUID refused. Use the prefixed id
  from search, a list or a receipt (`memory:`, `group:`, `vault:`, `task:`,
  `upload:`, `space:`, `org:`). Never build one.
- **"... not found"** (memory, item, space, organization, task). It does not
  exist, was deleted, or this user cannot read it in this mode. Do not guess
  another id. If it should exist, check the mode: in shared mode the user's
  own items are hidden.

## Versions

- **"Memory changed; fetch it again before updating."**, **"... changed
  since version ..."**, **"Skill changed since it was fetched"**, **"The
  transcript changed"**. Someone wrote it after you read it. `fetch` it, merge
  your change into the new text (show the user when both edits matter), and
  update with the new `version`.
- **"version must be the exact version from fetch, a list result or a
  receipt".** Pass the token unchanged.
- **Another person's checkout lock, or another agent's edit.** Someone is
  editing the item now. Wait, `fetch` again, and retry, or tell the user.

## People

- **"owner needs exactly one of user_id, email, person or slack_user_id; a
  name is never resolved"**, or **"... is not a member of the
  organization".** Find the person with `search_entities` (or `list_spaces`
  with `members: true`) and pass their id or email. If two people match, ask
  the user which one.

## Tasks

- **"Another run (...) is doing this task since ...".** Another agent holds
  the claim. Do not work on it; see the save skill's tasks reference, "If
  another agent holds it".
- **"This task is blocked: ... A person must unblock it before an agent works
  on it; tell the user."** Tell the user what the block says. Only a person
  unblocks it, in okWOW.
- **"This task is closed; reopen it before working on it."** `reopen` it only
  if the user wants the work done again.
- **"Only a tracked task can be blocked".** Ask the user in chat instead.
- **"Only a person can ... a task".** Some changes are for people only; tell
  the user.

## Content

- **"content: must be at most 1000 characters".** Split the fact, or save
  the long version with `create_content` and cite it.
- **"A skill with this name already exists ..."**. `fetch` the existing
  skill (`list_items` with `kind: "skill"` finds it) and `update_content` it.
- **"Content conversion is pending or this item has no readable text".** Retry
  later or give the user the item's `url`.
- **"Item exceeds the complete-text fetch limit".** okWOW never returns
  truncated text: give the user the `url` and do not guess the rest.
- **"Session capture is paused".** Point the user to the settings link in the
  message.

## Connected-account tools

- **"Not run: this action needs the user's approval in okWOW. Nothing was
  changed."** Tell the user; they approve it in okWOW.
- **"This tool is not available to this client."** The user shares the
  account with this connection in okWOW.
- **"Not run: the user blocked this connector in okWOW."** Do not retry.

## Timeouts

**"The operation could not complete."** The server did not finish. For a
create, retry the same call with the same place and exactly the same content:
okWOW returns the item already created, with `duplicate: true`. For an update
or delete, `fetch` first, then retry.
