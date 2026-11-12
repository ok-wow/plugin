# Working on okWOW tasks

A task is a to-do on a space's board. An agent works one in this order: find
it, claim it, keep its checklist current, then complete it, drop it or ask a
person. Every change goes through `update_task` and needs the editor role in
the task's space. Creating, finding, claiming, updating and finishing a
task work in either mode.

## Your session

Your app gives each session or thread an id, usually in an environment
variable; the `session` argument's own description names examples. Pass
`session` on every task call, `list_tasks` included:
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

- Refused because it is blocked: tell the user what the block says.
- Refused because it is closed: `reopen` it only if the user wants it done
  again.
- Your own `start` again only renews your claim.

## If another agent holds it

`start` is refused with the holder and since when; `list_tasks` shows the
same in `claimed_by`. Do not work on the task, and do not create a second task
for the same work. You cannot message or stop that agent. Tell the user who
holds it, then pick another task. The claim lapses an hour after that agent's
last update, so the task may be free later.

## Keep the claim

A claim lapses after an hour without an update from the session that holds it.
Each `update_task` this session makes renews it, so update `todos` as each step
changes, and at least once an hour during long work: they show the user your
progress and keep the claim. `todos` replaces the whole checklist.

Three lapses in a row block the task until a person unblocks it. There is no
action that just releases a claim: you give a task up by completing it,
blocking it or dropping it. If you stop before finishing, block it if a person
must act, or drop it if it should not be done. A claim you walk away from
lapses after an hour, keeps other agents off the task until then and counts as
a lapse. After a lapse, `start` again if the task is still free.

## Ask a person

When the user is in this conversation, ask them first: say what is missing
and that blocking stops every agent on the task until a person acts. Block on
their yes, with what they need in their words. In a run nobody is watching (a
scheduled task check), block without asking.

`update_task` with `block: {"detail": "<what the person must do>"}` and no
action ends your claim and stops every agent on the task until a person acts.
Say exactly what you need: a decision, access, or a fact. Only a task on the
board can be blocked; a task created with `tracked: false` cannot, so tell the
user instead. Agents cannot unblock a task or stop another agent. A person
answers in okWOW and unblocks the task there; `list_tasks` then shows
`blocked` cleared, and you can `start` it again.

## Finish

- `complete` with a `report`: what you did, the outcome, how you checked it,
  what is unsure or unfinished, and what the work produced. Completing ends
  your claim.
- `drop` with a `reason` when the task should not be done.
- `reopen` a closed task before you close it again.

Report only what you did and checked. Say `partial` or `failure` when that is
what happened.

## Other changes

`assign` takes an `owner`, never a bare name: find the person with
`search_entities`. Assign work to someone else only when the user asks.
`set_due` takes `due_at`; `null` clears it.
