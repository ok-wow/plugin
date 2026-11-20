"""Write the plugins generated from plugins/okwow, which run no local code:

- directory/okwow, the Claude directory plugin: its skills and the hosted
  okWOW MCP server, with no hooks or scripts. Session capture stays in the
  full plugin at plugins/okwow.
- bots/okwow-team, the Grok Bot plugin for a shared team bot: recall and save
  only, with no MCP server. A manager connects the bot to its Coworker's own
  address in Grok Bot, since one plugin cannot carry a per-bot address and
  /mcp is for personal agents.

Run after changing a skill it ships: python3 scripts/build_directory_plugin.py
"""
import argparse
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / 'plugins/okwow'
DEFAULT_OUTPUT = ROOT / 'directory/okwow'
BOT_OUTPUT = ROOT / 'bots/okwow-team'
SKILLS = ('recall', 'save', 'setup')
BOT_SKILLS = ('recall', 'save')
HOSTED_SERVER = 'https://api.okwow.ai/mcp'


def encoded(value):
    return (json.dumps(value, indent=2) + '\n').encode()


def skill_files(skills):
    out = {}
    for skill in skills:
        for path in sorted((PLUGIN / 'skills' / skill).rglob('*')):
            if path.is_file():
                out[str(path.relative_to(PLUGIN))] = path.read_bytes()
    return out


def files():
    """Every file of the directory plugin, by its path inside the plugin."""
    manifest = json.loads((PLUGIN / '.claude-plugin/plugin.json').read_text())
    manifest['description'] = 'Search and save your okWOW knowledge from your coding agent, as you.'
    manifest['keywords'] = [k for k in manifest['keywords'] if k not in ('transcripts', 'sessions')]
    out = {
        '.claude-plugin/plugin.json': encoded(manifest),
        '.mcp.json': encoded({'mcpServers': {'okwow': {'type': 'http', 'url': HOSTED_SERVER}}}),
        'LICENSE': (ROOT / 'LICENSE').read_bytes(),
        'README.md': (ROOT / 'submission/directory-README.md').read_bytes(),
    }
    return out | skill_files(SKILLS)


def bot_files():
    """Every file of the Grok Bot team plugin, by its path inside the plugin."""
    source = json.loads((PLUGIN / '.claude-plugin/plugin.json').read_text())
    manifest = {
        'name': 'okwow-team',
        'version': source['version'],
        'description': "Your team bot's okWOW skills: search and save the team's knowledge as its Coworker.",
        **{k: source[k] for k in ('author', 'homepage', 'repository', 'license')},
        'keywords': ['okwow', 'memory', 'knowledge', 'team bot', 'coworker'],
        'logo': 'assets/icon.png',
    }
    return {
        '.grok-plugin/plugin.json': encoded(manifest),
        'assets/icon.png': (PLUGIN / 'assets/icon.png').read_bytes(),
        'LICENSE': (ROOT / 'LICENSE').read_bytes(),
        'README.md': (ROOT / 'submission/team-bot-README.md').read_bytes(),
    } | skill_files(BOT_SKILLS)


def write(output, contents):
    if output.exists():
        shutil.rmtree(output)
    for name, content in contents.items():
        path = output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--bot-output', type=Path, default=BOT_OUTPUT)
    args = parser.parse_args()
    write(args.output, files())
    write(args.bot_output, bot_files())


if __name__ == '__main__':
    main()
