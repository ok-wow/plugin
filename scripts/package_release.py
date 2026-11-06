"""Build host-specific review packages from the shared plugin; never publish."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / 'plugins/okwow'

def encoded(value):
    return (json.dumps(value, indent=2) + '\n').encode()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tag', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source = json.loads((PLUGIN / '.claude-plugin/plugin.json').read_text())
    version = source['version']
    if not re.fullmatch(r'\d+\.\d+\.\d+', version) or args.tag != 'v' + version:
        parser.error('Tag must match the plugin version exactly: v' + version)
    gemini = json.loads((ROOT / 'gemini-extension.json').read_text())
    if gemini['version'] != version:
        parser.error('Gemini and plugin versions must agree')
    # The package has no relay script: Gemini CLI signs in to the hosted server itself.
    gemini['mcpServers'] = {'okwow': {'httpUrl': 'https://api.okwow.ai/mcp'}}
    interface = json.loads((ROOT / 'submission/openai-interface.json').read_text())
    if not 0 < len(interface['shortDescription']) <= 30:
        parser.error('OpenAI subtitle must be 1–30 characters')
    shared = {'LICENSE': (ROOT / 'LICENSE').read_bytes(),
              'README.md': (ROOT / 'submission/knowledge-README.md').read_bytes()}
    # Explicit inventory: local capture scripts/hooks and test fixtures are not web components.
    for skill in ('recall', 'save'):
        shared[f'skills/{skill}/SKILL.md'] = (PLUGIN / f'skills/{skill}/SKILL.md').read_bytes()
    shared['skills/save/references/tasks.md'] = (PLUGIN / 'skills/save/references/tasks.md').read_bytes()
    shared['skills/recall/references/how-okwow-works.md'] = (PLUGIN / 'skills/recall/references/how-okwow-works.md').read_bytes()
    shared['skills/recall/references/errors.md'] = (PLUGIN / 'skills/recall/references/errors.md').read_bytes()
    openai = {key: source[key] for key in ('name', 'version', 'author', 'license')}
    openai.update({'$schema': 'https://agent-plugins.org/schemas/1.0.0/plugin.schema.json',
                   'description': 'Find team knowledge and save memories and documents in okWOW.',
                   'extensions': {'com.openai': {
                       'interface': interface,
                       'review': {'test_cases': json.loads((ROOT / 'submission/review-cases.json').read_text())},
                       'publication': {'release_notes': 'Initial marketplace knowledge package: recall and save with the hosted okWOW MCP connection.'}}}})
    mcp = {'$schema': 'https://agent-plugins.org/schemas/1.0.0/mcp.schema.json',
           'mcpServers': {'okwow': {'type': 'streamable-http', 'url': 'https://api.okwow.ai/mcp'}}}
    packages = {
        'gemini': {**shared, 'gemini-extension.json': encoded(gemini)},
        'openai': {**shared, 'plugin.json': encoded(openai), 'mcp.json': encoded(mcp),
                   'assets/icon.png': (PLUGIN / 'assets/icon.png').read_bytes()},
    }
    args.output.mkdir(parents=True, exist_ok=True)
    sums = []
    for host, files in packages.items():
        path = args.output / f'okwow-{host}-{version}.zip'
        with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as archive:
            for name, content in sorted(files.items()):
                info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                archive.writestr(info, content)
        sums.append(f'{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}')
        print(path)
    (args.output / 'SHA256SUMS').write_text('\n'.join(sums) + '\n')

if __name__ == '__main__':
    main()
