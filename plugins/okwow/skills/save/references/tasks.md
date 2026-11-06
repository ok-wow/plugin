# Working on okWOW tasks

A task is a to-do on a space's board. An agent works one in this order: find
it, claim it, keep its checklist current, then complete it, drop it or ask a
person. Every change goes through `update_task` and needs the editor role in
the task's space; each call returns the task as `list_tasks` shows it.

## Your session

If your app gives you a session or thread id (read it from your environment),
pass `session` on every task call, `list_tasks` included:
`{"id": "<that id>", "label": "<the repository or worktree you work in>"}`.
Use the same id for the whole session. With it, a claim belongs to this
session alone. Without it, every session on this connection shares one claim,
so two of them can work the same task at once.

## Find a task

`list_tasks` with `owner` (`me`, or `any` for the whole board), `status`
(`open`, `overdue`, `all`) and `claimed`: `unclaimed` lists the tasks no agent
is working on, `mine` the ones this session holds. Leave alone a row whose
`claimed_by` names another agent, or whose `blocked` is set: agents stop on a
blocked task until a person acts.

## Claim it before you work on it

Call `update_task` with `action: "start"` before any work. `start` takes
nothing else; send `todos` in a separate call. `create_task` with
`start: true` creates a task and claims it in one call.

- Refused because another agent is working on it: do not work on it. Pick
  another task or tell the user.
- Refused because it is blocked: tell the user what the block says.
- Your own `start` again only renews your claim.

## Keep the claim

A claim lapses after an hour without an update from the session that holds it.
Each `update_task` this session makes renews it, so update `todos` as each step
changes: they show the user your progress and keep the claim. `todos` replaces
the whole checklist. Each item has `content`, `activeForm` and `status`
(`pending`, `in_progress` or `completed`), and at most one is `in_progress`.

Three lapses in a row block the task until a person unblocks it. If you stop
before finishing, close it out rather than walking away: block it if a person
must act, or drop it if it should not be done. An abandoned claim keeps other
agents off the task for up to an hour and counts as a lapse.

## Ask a person

`update_task` with `block: {"detail": "<what the person must do>"}` and no
action ends your claim and stops every agent on the task until a person acts.
Say exactly what you need: a decision, access, or a fact. Only a task on the
board can be blocked; a task created with `tracked: false` cannot, so tell the
user instead. Agents cannot unblock a task or stop another agent; a person
does that in okWOW.

## Finish

- `complete` with a `report`: `summary` (one or two sentences) and `outcome`
  (`success`, `partial` or `failure`) are required. Add `how` (the steps or
  findings), `challenges` (what was hard, how you checked the result, what is
  unsure or unfinished), `lessons`, `artifacts` (the `vault:` ids the work
  produced), `outputs`, and `unmet_requirements` (access or sources the work
  needed and did not have). Optional `evidence` cites what proves it.
  Completing marks every checklist step done and ends your claim.
- `drop` with a `reason` when the task should not be done.
- `reopen` a closed task before you close it again.

Report only what you did and checked. Say `partial` or `failure` when that is
what happened.

## Other changes

`assign` takes `owner` (`"me"`, a member's `user_id` or email, or for someone
outside okWOW an email, Slack user id or `person` id; never a bare name).
`set_due` takes `due_at` in ISO 8601 with a time zone; `null` clears it.
