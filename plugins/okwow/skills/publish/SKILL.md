---
name: publish
description: Use when work drafted in this session (a document, page, deck, sheet, plan or write-up) is ready for other people or agents to act on, or when the user asks to publish, share, hand off or finalize it. Covers when to move work into the organization's document repository, how to name drafts and finals, and how okWOW records where the work lives.
argument-hint: "[what to publish]"
---

# Publish to the organization's repository

Work you draft with the user (a local file, a chat canvas, a hosted page) is a
working copy. Nobody else treats it as the team's record. Publishing puts a
version into the organization's document repository, such as a shared drive, a
document library or a code repository, where teammates and their agents look.
okWOW keeps a pointer to where the document lives. It does not keep a copy.

Treat publishing like pushing a commit: do it only when a version is ready for
others to rely on.

## When to publish

- Publish only when the user says this version is ready, or asks you to
  publish, share, hand off or finalize it. What counts as ready is the user's
  call. Never publish on your own judgment, however finished the work looks.
- Publish work that is meant for others: a team, a reviewer, a customer or
  another agent. Personal notes and scratch work stay where they are.
- If you think something is ready, say so and ask.
- To get feedback before it is final, publish it as a draft (see Naming).

## Where

The organization's own repository: not your drafting tool, and not okWOW.

1. Use the place the user names.
2. Otherwise use the `recall` skill: search okWOW for where this team keeps
   this kind of document, and for a pointer to this document from an earlier
   publish. If one exists, update that document.
3. Otherwise ask the user once, and offer to save the answer as a memory
   with the `save` skill.

## How

1. Prefer the okWOW tool for that repository (tools named `<app>_<tool>`).
   Writing through it records the pointer in okWOW for you. It acts as the
   user, so confirm with the user before the call. If the result says the
   action needs the user's approval in okWOW, nothing ran: tell the user.
2. If you can reach the repository only through another connector, publish
   there anyway, and tell the user that okWOW has no pointer to it.
3. To publish a new version, update the same document in place. Never make a
   second copy. Find it from the pointer or from the user's link. The
   repository keeps the version history.
4. Where the repository supports a change note (a version comment, a commit
   message, a description), say what changed.
5. Report where the document lives (its link), whether it is Draft or Final,
   and whether okWOW recorded the pointer.

## Naming: Draft and Final

The title is the status signal for everyone who did not see your session.

- A draft shared for review ends its title with "(Draft)", for example
  "Q1 Plan (Draft)".
- When the user says it is final, remove "(Draft)" from the same document.
  Do not add "Final", "V2", "VF" or dates to the title; the repository's
  history keeps the versions.
- Later revisions are updates in place. If the user wants it back in review,
  add "(Draft)" again.
- If okWOW records a naming convention for this team, follow it instead.

## Errors

- No tool can write to the repository: tell the user where the work is so they
  can add it themselves. Do not save it to okWOW in its place.
- A refused okWOW call stored nothing: follow its message.
