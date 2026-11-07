# okWOW

Find team decisions and project context before you work, and save team knowledge back to okWOW as you learn it.

The plugin connects to the hosted MCP server at `https://api.okwow.ai/mcp`. Each app signs in once, under its own name, for its okWOW tools and its session capture; web hosts connect through their own OAuth flow. Review the account and permissions before approving. The `recall` skill searches and cites your available knowledge; `save` helps choose an audience and save a memory or document.

An okWOW account is required.

This plugin also includes opt-in session capture for coding agents. It saves coding conversations to okWOW as private chats after the user signs in. Use the capture skill for setup and revocation. Local capture requires Python 3 and a coding agent that runs plugin hooks. The `setup` skill (`/okwow:setup`) walks the user through people, spaces, knowledge, memory, okWOW as the agent's default, capture and a scheduled task check in chat. The web-compatible distribution includes only recall and save.

Install instructions for each app are in the [documentation](https://okwow.ai/docs/okwow-mcp/#install-plugin).

[Documentation](https://okwow.ai/docs/okwow-mcp/) · [Support](https://okwow.ai/docs/support/) · [Privacy](https://okwow.ai/legal/privacy-policy/) · [Terms](https://okwow.ai/legal/terms-of-use/)
