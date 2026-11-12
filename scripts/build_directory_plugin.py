"""Write the Claude directory plugin: the okwow plugin's skills and the hosted
okWOW MCP server, with no hooks or local scripts. Session capture stays in the
full plugin at plugins/okwow.

Run after changing a skill it ships: python3 scripts/build_directory_plugin.py
"""
import argparse
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / 'plugins/okwow'
DEFAULT_OUTPUT = ROOT / 'directory/okwow'
SKILLS = ('recall', 'save', 'setup')
HOSTED_SERVER = 'https://api.okwow.ai/mcp'


def encoded(value):
    return (json.dumps(value, indent=2) + '\n').encode()


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
    for skill in SKILLS:
        for path in sorted((PLUGIN / 'skills' / skill).rglob('*')):
            if path.is_file():
                out[str(path.relative_to(PLUGIN))] = path.read_bytes()
    return out


def write(output):
    if output.exists():
        shutil.rmtree(output)
    for name, content in files().items():
        path = output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    write(parser.parse_args().output)


if __name__ == '__main__':
    main()
