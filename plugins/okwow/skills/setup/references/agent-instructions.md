# Make okWOW your agent's default

Skills load only when a request matches them, so they cannot change what the
agent does by default. This step writes a short okWOW block into the user's
own instruction file, which the agent reads at the start of every session.
After it, the agent checks okWOW before it works and saves team knowledge to
okWOW instead of its local memory, without being asked each time.

## 1. Find the file

Use your user-level instruction file: the one that applies to every project
(for example `AGENTS.md`, or your own equivalent; check your documentation
for its location). If the user wants okWOW only in some projects, use each
project's instruction file instead. Read the file first. If it already holds
an okWOW block between the markers below, this run updates that block and
leaves everything else alone.

## 2. Agree on the terms

Show the block below and ask about the parts that vary:

- **Saving:** save team knowledge on its own (the default), or offer each
  fact first.
- **Where team knowledge goes:** a default space from `list_spaces` (for
  example Engineering), and which kinds of facts go to the organization.
- **What stays local:** by default, personal preferences, machine setup and
  notes about the agent's own tooling.
- **Skills and tasks:** keep or drop those items.
- **Mode:** a new connection is in private mode, where every save is the
  user's alone. Ask whether to switch this connection to shared mode, so team
  saves reach the members of the place. Switch with `switch_mode` only on
  their yes, and say that other connections keep their own mode.

Apply their changes to the text. Then show the exact text and the file path,
and write nothing until the user says yes.

## 3. Write it

Insert the block at the end of the file, or replace the old block between the
markers. Change nothing outside the markers. It takes effect in new sessions.
To undo it, the user deletes the block, or runs this step again to change it.

```markdown
<!-- okwow:start: written by okWOW setup; edit freely, run setup again to change -->
## okWOW

okWOW (the `okwow` MCP server) holds this user's team knowledge: memories,
Vault items, tasks and the knowledge graph of people and subjects. It takes
precedence over local notes. Current instructions take precedence over older
memories.

1. **Check okWOW first.** Before you start any task, find out what is already
   recorded and what others are doing:
   - `search` for the task's topic twice: once for the concept, and once for
     exact names (PR numbers, services, tables, features). Memories match by
     meaning only; Vault titles and descriptions also match exact words.
   - `search_entities` for the people, teams, customers and projects
     involved, then `get_node` and `list_edges` for what they own and know.
   - `list_tasks` for work already in flight on the same thing.
   Report what overlaps before you build alongside it.
2. **Escalate in cost order.** Stop at the first step that answers:
   1. Results you already have: `search`, `search_entities`, `list_tasks`.
   2. `fetch` the items you will rely on; `list_paths` for who knows or owns
      a subject and how two things connect.
   3. The source a result points to (an issue, a document, a thread), through
      your own tools for that system.
   4. Ask the person `list_paths` names as owner, or ask the user.
3. **Save team knowledge to okWOW, not local memory.** When you learn
   something a teammate will need later (a decision, a convention, a gotcha,
   a reference to an external system), save it with the okWOW save skill,
   without waiting to be asked, to the place whose topic and members fit
   (<default space> when nothing fits better), and tell the user what you
   saved, where and who can see it. Ask when no place clearly fits. Save in
   the connection's current mode: in private mode a save is the user's
   alone, so suggest shared mode when teammates need the fact, and switch
   only when the user says so. Keep <what stays local> in local memory.
   - One fact per memory, at most 1,000 characters, third person, absolute
     dates. No local paths, ports or secrets. Save longer material as an
     artifact and cite it.
   - Ask before you save anything about a person or a customer, an
     unreleased plan, or anything near a secret, and check who can see the
     place.
   - Correct a stale memory with `update_memory`; do not add a duplicate.
4. **Skills live in okWOW.** Save a reusable skill to a space so teammates can
   use it. A local pointer file fetches the okWOW copy each time it runs.
   To change the skill, `fetch` it and `update_content` it with that
   `version`; never edit the pointer.
5. **Track work as okWOW tasks** (they need shared mode). Give each
   workstream a task, claim it with your session, keep its todos current, ask
   the user before you block it on a person, and complete it with a report. The okWOW save skill's tasks reference has
   the details.
<!-- okwow:end -->
```

Fill `<default space>` and `<what stays local>` from the user's answers. If
they chose to be asked before each save, item 3 says "offer to save it"
instead of "save it without waiting to be asked".

## A skill pointer

When the user moves a local skill into okWOW (setup step 5) and wants it to
keep loading locally, replace the body of its `SKILL.md` with a pointer. The
pointer is not a copy: it fetches the okWOW skill every time it runs, so
everyone uses the current text, and it stops working while okWOW is not
connected. Keep the frontmatter, so the skill still loads on the same
requests:

```markdown
---
name: <same name>
description: <same description>
---

The instructions for this skill live in okWOW: `vault:<uuid>` (<url>).
Call the okwow MCP `fetch` tool with that id and follow the returned text as
this skill's instructions, skipping its frontmatter. If okWOW is not
connected, say so and stop.
```

Leave any files next to `SKILL.md` (references, scripts) where they are.
They stay local and do not reach teammates, who get only the okWOW
`SKILL.md` text.

To change the skill, edit the okWOW copy: `fetch` its `vault:` id, then call
`update_content` with the same id, the returned `version` and the new
`content`. Never edit the pointer to change the instructions.
