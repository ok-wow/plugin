# okWOW for team bots

Skills for a shared Grok Bot that works as an okWOW Coworker:

- **recall**: searches the team's okWOW knowledge before answering questions
  about past decisions, conventions, people and open tasks, then fetches and
  cites what it used.
- **save**: saves a verified fact as a memory or a write-up as a document, and
  shows the bot how to claim, work and complete okWOW tasks.

This plugin has no MCP server of its own. Each team bot connects to the
address of the Coworker it works as, so that several bots on one Grok account
can each be a different Coworker:

1. In okWOW, open the Coworker's page under Settings, then its Connections
   tab, and copy its address (`https://api.okwow.ai/mcp/coworkers/<id>`).
2. In Grok Bot, add a custom MCP server for the team bot named `okwow`, the
   name the skills use, with that address, and sign in to okWOW. Under
   "Works as?", pick the same Coworker.
3. Install this plugin on the bot.

The bot then reads and saves as that Coworker, in shared mode: what it saves
reaches the members of the place it saves to. Personal agents use the okWOW
plugin at https://github.com/ok-wow/plugin and `https://api.okwow.ai/mcp`
instead.

[Documentation](https://okwow.ai/docs/how-okwow-works/) · [Support](https://okwow.ai/docs/support/) · [Privacy](https://okwow.ai/legal/privacy-policy/) · [Terms](https://okwow.ai/legal/terms-of-use/)
