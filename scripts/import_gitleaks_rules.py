#!/usr/bin/env python3
"""Turn a gitleaks release's rules into plugins/okwow/scripts/gitleaks-rules.json for okwow-capture's redaction.

Capture runs in a hook on the system Python, with no gitleaks binary, so it reads gitleaks' rules as data: each
rule's regex, the group that holds the secret, its entropy floor, its keywords and its allowlists. Rerun this
when gitleaks releases new rules, then run tests/check_redaction.py:

    python3 scripts/import_gitleaks_rules.py v8.30.1

Go's regexp (RE2) and Python's re read almost every rule the same way; this rewrites the rest: a flag group in
mid-pattern, `\\z` and POSIX classes. A rule Python still cannot compile fails the import. Path allowlists are
dropped (capture scans text, not files), and so is an allowlist that needs a path to be met.
"""

import json
import re
import sys
import tomllib
import urllib.request
import warnings
from pathlib import Path

OUTPUT = Path(__file__).resolve().parent.parent / "plugins" / "okwow" / "scripts" / "gitleaks-rules.json"
SOURCE = "https://raw.githubusercontent.com/gitleaks/gitleaks/{version}/config/gitleaks.toml"
POSIX = {"alnum": "A-Za-z0-9", "alpha": "A-Za-z", "digit": "0-9", "lower": "a-z", "upper": "A-Z",
         "xdigit": "0-9A-Fa-f", "space": r"\s", "word": r"\w", "punct": r"!-/:-@\[-`{-~"}


def scoped_flags(regex: str) -> str:
    """Go applies `(?i)` from where it stands to the end of its group; Python only takes it at the start."""
    out, i, depth, in_class, opened = [], 0, 0, False, []
    while i < len(regex):
        c = regex[i]
        if c == "\\":
            out.append(regex[i:i + 2])
            i += 2
            continue
        if in_class:
            in_class = c != "]"
        elif c == "[":
            in_class = True
            if regex[i + 1:i + 2] == "^":
                out.append("[^")
                i += 2
            else:
                out.append("[")
                i += 1
            if regex[i:i + 1] == "]":  # a leading ] is a literal
                out.append("]")
                i += 1
            continue
        elif c == "(":
            flag = re.match(r"\(\?([a-zA-Z-]+)\)", regex[i:])
            if flag and (i > 0 or depth > 0):
                out.append(f"(?{flag.group(1)}:")
                opened.append(depth)
                i += flag.end()
                continue
            depth += 1
        elif c == ")":
            while opened and opened[-1] == depth:
                out.append(")")
                opened.pop()
            depth -= 1
        out.append(c)
        i += 1
    out.extend(")" for _ in opened)
    return "".join(out)


def python_regex(regex: str) -> str:
    regex = re.sub(r"\[\[:(\w+):\]\]", lambda m: f"[{POSIX[m.group(1)]}]", regex)
    regex = re.sub(r"\[:(\w+):\]", lambda m: POSIX[m.group(1)], regex)
    regex = regex.replace(r"\z", r"\Z")
    regex = scoped_flags(regex)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        re.compile(regex, re.ASCII)
    return regex


def allowlist(entry: dict) -> dict | None:
    if entry.get("condition", "OR").upper() == "AND" and entry.get("paths"):
        return None
    kept = {"target": entry.get("regexTarget", "secret"),
            "regexes": [python_regex(r) for r in entry.get("regexes", [])],
            "stopwords": [w.lower() for w in entry.get("stopwords", [])]}
    return kept if kept["regexes"] or kept["stopwords"] else None


def main() -> int:
    if len(sys.argv) != 2 or not re.fullmatch(r"v\d+\.\d+\.\d+", sys.argv[1]):
        print(__doc__)
        return 2
    version = sys.argv[1]
    url = SOURCE.format(version=version)
    with urllib.request.urlopen(url, timeout=60) as response:
        config = tomllib.loads(response.read().decode())
    rules = []
    for entry in config["rules"]:
        if "regex" not in entry:  # matches a file's name only
            continue
        rule = {"id": entry["id"], "regex": python_regex(entry["regex"]), "keywords": [k.lower() for k in entry.get("keywords", [])]}
        if entry.get("secretGroup"):
            rule["group"] = entry["secretGroup"]
        if entry.get("entropy"):
            rule["entropy"] = entry["entropy"]
        allow = [a for a in map(allowlist, entry.get("allowlists", [])) if a]
        if allow:
            rule["allow"] = allow
        rules.append(rule)
    data = {"source": url, "license": "MIT, Copyright (c) 2019 Zachary Rice",
            "allow": allowlist(config.get("allowlist", {})), "rules": rules}
    OUTPUT.write_text(json.dumps(data, indent=1) + "\n")
    print(f"{len(rules)} rules from gitleaks {version} written to {OUTPUT.relative_to(OUTPUT.parents[3])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
