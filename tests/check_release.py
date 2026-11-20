"""Exercise release archives at their host-facing boundary (stdlib only)."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
version = json.loads((ROOT / 'plugins/okwow/.claude-plugin/plugin.json').read_text())['version']
# The hook and relay commands live in the source plugin (release archives carry neither):
# they must try python3 then python, say so when neither runs, and pass the config-home variables.
plugin = ROOT / 'plugins/okwow'
hooks = json.loads((plugin / 'hooks/hooks.json').read_text())['hooks']
server = json.loads((plugin / '.mcp.json').read_text())['mcpServers']['okwow']
commands = [h['command'] for entries in hooks.values() for entry in entries for h in entry['hooks']] + [server['args'][1]]
for command in commands:
    assert 'python3 python' in command and 'no working Python 3 interpreter found' in command, 'Missing python3/python fallback'
    assert 'exec python3' not in command, 'A bare python3 must not be the only interpreter'
assert server['env_vars'] == ['OKWOW_MCP_URL', 'OKWOW_CAPTURE_HOME', 'OKWOW_CAPTURE_STATE']
# Behaviour: with a PATH holding only `python` (and no python3), the picker still runs it; with neither, it errors.
with tempfile.TemporaryDirectory() as tmp:
    for name, links, ok in [('only-python', ['python'], True), ('none', [], False)]:
        bin_dir = Path(tmp) / name
        bin_dir.mkdir()
        for link in links:
            (bin_dir / link).symlink_to(sys.executable)
        picked = subprocess.run(['/bin/sh', '-c', commands[0].split(' exec ')[0] + ' echo "picked $py"'],
                                capture_output=True, text=True, env={'PATH': str(bin_dir)})
        assert (picked.returncode == 0 and picked.stdout.strip() == 'picked python') == ok, (name, picked)
        assert ok or 'no working Python 3 interpreter found' in picked.stderr
with tempfile.TemporaryDirectory() as tmp:
    output = Path(tmp) / 'packages'
    bad = subprocess.run([sys.executable, str(ROOT / 'scripts/package_release.py'), '--tag', 'v99.99.99', '--output', str(output)], capture_output=True)
    assert bad.returncode != 0, 'A mismatched tag must not produce a release'
    subprocess.run([sys.executable, str(ROOT / 'scripts/package_release.py'), '--tag', 'v' + version, '--output', str(output)], check=True)
    for host, manifest in [('gemini', 'gemini-extension.json'), ('openai', 'plugin.json')]:
        with zipfile.ZipFile(output / f'okwow-{host}-{version}.zip') as archive:
            names = set(archive.namelist())
            data = json.loads(archive.read(manifest))
            assert data['name'] == 'okwow' and data['version'] == version
            assert {'skills/recall/SKILL.md', 'skills/save/SKILL.md', 'LICENSE'} <= names
            assert not any(n.startswith(('hooks/', 'scripts/', 'skills/capture/', '.git/', 'tests/')) for n in names)
            assert all(not n.startswith('/') and '..' not in Path(n).parts for n in names)
            if host == 'gemini':
                assert data['mcpServers']['okwow']['httpUrl'] == 'https://api.okwow.ai/mcp'
            else:
                assert json.loads(archive.read('mcp.json'))['mcpServers']['okwow']['url'] == 'https://api.okwow.ai/mcp'
                interface = data['extensions']['com.openai']['interface']
                for icon in (interface['logo'], interface['composerIcon']):
                    # OpenAI requires icon paths relative to the plugin root, starting with ./
                    assert icon.startswith('./'), f'Icon path must start with ./: {icon}'
                    assert archive.read(icon[2:]).startswith(b'\x89PNG\r\n\x1a\n')
                assert 0 < len(interface['shortDescription']) <= 30
                cases = data['extensions']['com.openai']['review']['test_cases']
                assert len(cases['positive']) == 5 and len(cases['negative']) == 3
print('Release archives passed host layout, version and scope checks.')
