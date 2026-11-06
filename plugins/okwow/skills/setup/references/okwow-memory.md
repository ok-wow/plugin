# Start every session with okWOW memory

The okWOW block from step 7 says how to use okWOW. This step makes okWOW the
memory your sessions start with: each new session in this app begins with the
okWOW memory groups this app's connection can read (one line each, naming its
space), and your app's own memory setting is turned off. Offer it after the
block is written, or when the user asks for okWOW to be their agent's memory.

Tell the user, and get their yes:

- What the list holds follows this connection's mode: in private mode, the
  team's groups and the user's own; in shared mode, the team's only. Each app
  has its own connection and mode. The list holds names, not memory text, and
  is kept on this computer for the user alone.
- Your app's own memory is turned off, and its previous setting is kept so it
  can be put back. Local memory files are not deleted.
- If okWOW cannot be reached, a session starts with the last list, or with a
  note that okWOW is unreachable. It never waits on okWOW.

Then run `python3 "$CAPTURE" memory on --agent <app>`, where `<app>` is the
`--agent` value of this app's `login` command (`status` prints it) and
`$CAPTURE` is the plugin's `scripts/okwow-capture`, at
`../../../scripts/okwow-capture` relative to this file. It needs this app's
okWOW sign-in; if it reports that the app is not signed in, follow the capture
skill's Connect section. If it does not report turning off your own memory,
turn it off with your documented setting, as in step 4 of
`memory-migration.md`, after the user's yes.

It applies to new sessions. `python3 "$CAPTURE" memory status --agent <app>`
shows the state, and `python3 "$CAPTURE" memory off --agent <app>` stops it
and puts your app's own memory setting back.
