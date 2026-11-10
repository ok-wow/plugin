#!/usr/bin/env python3
"""End-to-end check of session capture against a fake okWOW server.

Installs the plugin into a throwaway HOME, then fires its hooks.json commands
the way each supported app does: each app signs in once on its own, as itself,
the plugin's MCP server (a local relay each app starts) and the app's sessions
use that app's sign-in and no other app's, each session is routed by where it started (the start folder, its git remote and its
repository root), and nothing is read past the start or sent when okWOW says
skip, or when a file, server or endpoint is not one capture trusts. Nothing
leaves the machine. Writes a JSON report of every case.

Run: python3 tests/check_capture.py [--report path.json]
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import http.client
import importlib.machinery
import importlib.util
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "plugins" / "okwow"
FIXTURES = ROOT / "tests" / "fixtures"
# Fixture tokens carry an invisible separator so secret scanners skip them; it is removed before use.
SEPARATOR = "\u2063"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8").replace(SEPARATOR, "")
SPACE = {"id": "space:11111111-1111-1111-1111-111111111111", "label": "My Workspace"}
START_FIELDS = {"folder", "repository", "repository_root", "project"}


def start_error(start: Any) -> str:
    """okWOW's SessionStart rules; an empty string when start is valid."""
    if start is None:
        return ""
    if not isinstance(start, dict) or set(start) - START_FIELDS:
        return f"unexpected start fields: {start}"
    folder, root = start.get("folder"), start.get("repository_root")
    if not isinstance(folder, str) or not folder.startswith("/") or len(folder) > 1024:
        return "folder must be an absolute path of at most 1024 characters"
    if "repository" in start and not (isinstance(start["repository"], str) and 0 < len(start["repository"]) <= 512):
        return "repository must be 1 to 512 characters"
    if root is not None and not (folder == root or folder.startswith(root.rstrip("/") + "/")):
        return "repository_root must be folder or one of its parents"
    return ""


class Fake:
    """okWOW's MCP, OAuth and upload endpoints, with settings the cases change."""

    def __init__(self) -> None:
        # okWOW's rules: what a session that started at `start` does.
        self.decide: Callable[[Any], str] = lambda start: "send"
        self.reason = "rule"
        self.space: dict[str, Any] | None = SPACE
        self.settings_url = "https://app.example/settings/authorized-apps"
        # Called while get_session_capture is answered, before its reply is sent.
        self.on_settings: Callable[[], None] = lambda: None
        self.has_settings_tool = True
        self.upload_url: Callable[[str], str] = lambda base: f"{base}/upload/1"
        self.calls: list[dict[str, Any]] = []
        # Every MCP request: its method, bearer token and Mcp-Session-Id.
        self.requests: list[dict[str, Any]] = []
        # Registered clients, by id, with the name each registered under.
        self.clients: dict[str, str] = {}
        # Live access tokens, by the client they were issued to.
        self.tokens: dict[str, str] = {}
        # Every token grant: its type and the name of the client it was for.
        self.grants: list[tuple[str, str]] = []
        self.issued = 0
        # Authorization codes by value: the client, redirect and PKCE challenge they were issued for, and whether spent.
        self.codes: dict[str, dict[str, Any]] = {}
        self.redirects: dict[str, list[str]] = {}
        self.refresh_ok = True
        # Answer MCP requests as an event stream instead of JSON.
        self.sse = False
        self.puts: list[bytes] = []
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def reset(self) -> None:
        self.calls.clear()
        self.requests.clear()
        self.puts.clear()

    @property
    def registrations(self) -> int:
        return len(self.clients)

    def client(self, token: str) -> str:
        """The name of the client a token was issued to."""
        return self.clients.get(self.tokens.get(token, ""), "")

    def revoke(self, name: str) -> None:
        for token in [t for t in self.tokens if self.client(t) == name]:
            del self.tokens[token]

    def tools(self) -> list[str]:
        return [c["name"] for c in self.calls]

    def _handler(self) -> type[BaseHTTPRequestHandler]:
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args: Any) -> None:
                pass

            def reply(self, status: int, body: Any = None, headers: dict[str, str] | None = None) -> None:
                data = json.dumps(body).encode() if body is not None else b""
                self.send_response(status)
                for k, v in (headers or {"Content-Type": "application/json"}).items():
                    self.send_header(k, v)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def rpc(self, message_id: Any, result: Any, headers: dict[str, str] | None = None) -> None:
                message = {"jsonrpc": "2.0", "id": message_id, "result": result}
                if not fake.sse:
                    return self.reply(200, message, {"Content-Type": "application/json", **(headers or {})})
                data = f"event: message\ndata: {json.dumps(message)}\n\n".encode()
                self.send_response(200)
                for k, v in {"Content-Type": "text/event-stream", **(headers or {})}.items():
                    self.send_header(k, v)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def body(self) -> bytes:
                return self.rfile.read(int(self.headers.get("Content-Length") or 0))

            def do_GET(self) -> None:  # noqa: N802
                path = urllib.parse.urlsplit(self.path)
                if path.path == "/.well-known/oauth-protected-resource/mcp":
                    return self.reply(200, {"resource": f"{fake.base}/mcp", "authorization_servers": [fake.base]})
                if path.path == "/.well-known/oauth-authorization-server":
                    return self.reply(200, {
                        "authorization_endpoint": f"{fake.base}/authorize",
                        "token_endpoint": f"{fake.base}/token",
                        "registration_endpoint": f"{fake.base}/register",
                    })
                if path.path == "/authorize":
                    # Consent granted at once: redirect back with a code.
                    q = dict(urllib.parse.parse_qsl(path.query))
                    code = f"code-{len(fake.codes) + 1}"
                    fake.codes[code] = {"client_id": q["client_id"], "redirect_uri": q["redirect_uri"],
                                        "challenge": q["code_challenge"], "used": False}
                    target = q["redirect_uri"] + "?" + urllib.parse.urlencode({"code": code, "state": q["state"]})
                    return self.reply(302, None, {"Location": target})
                self.reply(404, {})

            def do_POST(self) -> None:  # noqa: N802
                path = urllib.parse.urlsplit(self.path).path
                raw = self.body()
                if path == "/register":
                    client_id = f"client-{fake.registrations + 1}"
                    registration = json.loads(raw)
                    fake.clients[client_id] = registration.get("client_name", "")
                    fake.redirects[client_id] = registration.get("redirect_uris", [])
                    return self.reply(201, {"client_id": client_id})
                if path == "/token":
                    fields = dict(urllib.parse.parse_qsl(raw.decode()))
                    client_id = fields.get("client_id", "")
                    fake.grants.append((fields.get("grant_type", ""), fake.clients.get(client_id, "")))
                    if fields.get("grant_type") == "authorization_code":
                        issued = fake.codes.get(fields.get("code", ""))
                        verifier = fields.get("code_verifier", "").encode()
                        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier).digest()).rstrip(b"=").decode()
                        if (not issued or issued["used"] or issued["client_id"] != client_id
                                or issued["redirect_uri"] != fields.get("redirect_uri")
                                or issued["challenge"] != challenge):
                            return self.reply(400, {"error": "invalid_grant", "error_description": "bad code"})
                        issued["used"] = True
                    if fields.get("grant_type") == "refresh_token" and not fake.refresh_ok:
                        return self.reply(400, {"error": "invalid_grant"})
                    fake.issued += 1
                    token = f"access-{client_id}-{fake.issued}"
                    fake.tokens[token] = client_id
                    return self.reply(200, {"access_token": token, "refresh_token": f"refresh-{client_id}",
                                            "expires_in": 3600})
                if path != "/mcp":
                    return self.reply(404, {})
                token = (self.headers.get("Authorization") or "").removeprefix("Bearer ")
                if token not in fake.tokens:
                    return self.reply(401, {})
                message = json.loads(raw)
                session = self.headers.get("Mcp-Session-Id")
                fake.requests.append({"method": message.get("method"), "token": token, "session": session})
                if "id" not in message:
                    return self.reply(202)
                if message["method"] == "initialize":
                    return self.rpc(message["id"], {
                        "protocolVersion": message["params"].get("protocolVersion"), "capabilities": {"tools": {}},
                        "serverInfo": {"name": "fake-okwow", "version": "1"}}, {"Mcp-Session-Id": "mcp-1"})
                if session != "mcp-1":
                    return self.reply(400, {"jsonrpc": "2.0", "id": message["id"],
                                            "error": {"code": -32600, "message": "missing Mcp-Session-Id"}})
                if message["method"] == "tools/list":
                    return self.rpc(message["id"], {"tools": [{"name": "get_profile", "inputSchema": {"type": "object"}}]})
                name = message["params"]["name"]
                arguments = message["params"]["arguments"]
                fake.calls.append({"name": name, "arguments": arguments, "token": token})
                self.rpc(message["id"], self.tool(name, arguments))

            def tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
                def ok(data: dict[str, Any]) -> dict[str, Any]:
                    return {"content": [{"type": "text", "text": json.dumps(data)}], "structuredContent": data}

                if name == "get_profile":
                    return ok({"user": {"name": "Pat", "email": "pat@example.com"}})
                def refuse(text: str) -> dict[str, Any]:
                    return {"isError": True, "content": [{"type": "text", "text": text}]}

                start = (arguments.get("session") or {}).get("start") if name == "create_content" else arguments.get("start")
                if start_error(start):
                    return refuse(start_error(start))
                if name == "get_session_capture" and fake.has_settings_tool:
                    if set(arguments) - {"start"}:
                        return refuse(f"unexpected arguments: {sorted(arguments)}")
                    fake.on_settings()
                    action = fake.decide(start)
                    return ok({"action": action, "in": fake.space if action == "send" else None,
                               "reason": None if action == "send" else fake.reason,
                               "settings_url": fake.settings_url})
                if name in ("prepare_upload", "create_content") and "in" in arguments:
                    # Capture leaves the space to okWOW's settings; a stale local choice must not win.
                    return refuse("capture sent its own space")
                if name in ("prepare_upload", "create_content") and fake.decide(start) != "send":
                    return refuse("Not saved: your session capture settings skip sessions started here.")
                if name == "create_content" and set(arguments["session"]) - {"id", "label", "agent", "start"}:
                    return refuse(f"unexpected session fields: {sorted(arguments['session'])}")
                if name == "prepare_upload":
                    return ok({"upload_id": "upload:1", "upload_url": fake.upload_url(fake.base),
                               "headers": {"Content-Type": "text/plain"}})
                if name == "create_content":
                    return ok({"id": "chat:22222222-2222-2222-2222-222222222222", "duplicate": False})
                return {"isError": True, "content": [{"type": "text", "text": f"Unknown tool: {name}"}]}

            def do_PUT(self) -> None:  # noqa: N802
                fake.puts.append(self.body())
                self.reply(200, {})

        return Handler


class Relay:
    """The plugin's MCP server as an app runs it, spoken to over stdio."""

    def __init__(self, command: list[str], cwd: Path, env: dict[str, str]) -> None:
        self.process = subprocess.Popen(command, cwd=cwd, env=env, text=True, stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.stdout: list[str] = []
        self.lines: queue.Queue[str] = queue.Queue()
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()

    def _read(self) -> None:
        for line in self.process.stdout:
            self.stdout.append(line)
            self.lines.put(line)

    def send(self, message: dict[str, Any]) -> None:
        self.process.stdin.write(json.dumps(message) + "\n")
        self.process.stdin.flush()

    def request(self, message_id: int, method: str, params: dict[str, Any] | None = None) -> Any:
        """Send a request and return the next line the server writes, parsed."""
        self.send({"jsonrpc": "2.0", "id": message_id, "method": method, **({"params": params} if params else {})})
        try:
            line = self.lines.get(timeout=30)
        except queue.Empty:
            return None
        try:
            return json.loads(line)
        except ValueError:
            return {"not json": line}

    def close(self) -> list[str]:
        """End the input as the app does when it quits; everything the server wrote."""
        self.process.stdin.close()
        try:
            self.process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            self.process.kill()
        self.reader.join(5)
        return self.stdout


INITIALIZE = {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "check", "version": "1"}}


def round_trip(relay: Relay) -> dict[str, Any]:
    """What an app sends first: initialize, the initialized notification, tools/list, then a tool call."""
    replies = {"initialize": relay.request(1, "initialize", INITIALIZE)}
    relay.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
    replies["tools/list"] = relay.request(2, "tools/list")
    replies["tools/call"] = relay.request(3, "tools/call", {"name": "get_profile", "arguments": {}})
    replies["stdout"] = relay.close()
    return replies


def round_trip_error(fake: Fake, replies: dict[str, Any], agent: str) -> str:
    """Why a round trip did not go through the fake as `agent`; empty when it did."""
    if (replies["initialize"] or {}).get("id") != 1 or "result" not in (replies["initialize"] or {}):
        return f"initialize: {replies['initialize']}"
    if [t["name"] for t in ((replies["tools/list"] or {}).get("result") or {}).get("tools", [])] != ["get_profile"]:
        return f"tools/list: {replies['tools/list']}"
    result = (replies["tools/call"] or {}).get("result") or {}
    if (replies["tools/call"] or {}).get("id") != 3 or (result.get("structuredContent") or {}).get("user", {}).get(
            "email") != "pat@example.com":
        return f"tools/call: {replies['tools/call']}"
    # The notification is answered by nothing: one line per request, each JSON-RPC.
    if len(replies["stdout"]) != 3:
        return f"stdout: {replies['stdout']}"
    methods = [r["method"] for r in fake.requests]
    if methods != ["initialize", "notifications/initialized", "tools/list", "tools/call"]:
        return f"requests: {methods}"
    if [r["session"] for r in fake.requests] != [None, "mcp-1", "mcp-1", "mcp-1"]:
        return f"Mcp-Session-Id: {[r['session'] for r in fake.requests]}"
    if {fake.client(r["token"]) for r in fake.requests} != {agent}:
        return f"signed in as {sorted({fake.client(r['token']) for r in fake.requests})}"
    return ""


class Home:
    """A throwaway HOME with the plugin installed and a browser that consents."""

    def __init__(self, fake: Fake) -> None:
        self.dir = Path(tempfile.mkdtemp(prefix="okwow-capture-e2e-"))
        # The repository layout: Gemini CLI installs it whole, the other apps its plugin folder.
        self.ext = self.dir / "ext"
        self.plugin = self.ext / "plugins" / "okwow"
        shutil.copytree(PLUGIN, self.plugin)
        shutil.copy(ROOT / "gemini-extension.json", self.ext)
        self.server = json.loads((self.plugin / ".mcp.json").read_text())["mcpServers"]["okwow"]
        self.url = f"{fake.base}/mcp"
        browser = self.dir / "browser"
        browser.write_text('#!/bin/sh\nexec curl -fsSL -o /dev/null "$1"\n')
        browser.chmod(0o755)
        self.env = {
            "HOME": str(self.dir),
            "PATH": os.environ["PATH"],
            "BROWSER": str(browser),
            "OKWOW_CAPTURE_KEYCHAIN": "0",
            "CLAUDE_PLUGIN_ROOT": str(self.plugin),
            "OKWOW_MCP_URL": self.url,
        }
        self.config = self.dir / ".config" / "okwow"
        self.config.mkdir(parents=True)
        self.hooks = json.loads((self.plugin / "hooks" / "hooks.json").read_text())["hooks"]
        self.projects = self.dir / ".claude" / "projects" / "-repo"
        self.projects.mkdir(parents=True)
        self.codex_sessions = self.dir / ".codex" / "sessions" / "2026" / "11" / "01"
        self.codex_sessions.mkdir(parents=True)

    def repo(self, name: str, remote: str | None) -> Path:
        path = self.dir / "code" / name
        path.mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(path)], check=True)
        if remote:
            subprocess.run(["git", "-C", str(path), "remote", "add", "origin", remote], check=True)
        return path

    def worktree(self, repo: Path, name: str) -> Path:
        path = self.dir / "code" / name
        git = ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.com"]
        subprocess.run([*git, "commit", "-q", "--allow-empty", "-m", "start"], check=True)
        subprocess.run([*git, "worktree", "add", "-q", str(path)], check=True)
        return path

    def codex_session(self, session_id: str, cwd: Path) -> Path:
        """A Codex session file with planted secrets, for a session that started in cwd."""
        lines = []
        for line in fixture("planted-secrets-codex.jsonl").splitlines():
            entry = json.loads(line)
            if entry.get("type") == "session_meta":
                entry["payload"].update({"id": session_id, "cwd": str(cwd)})
            lines.append(json.dumps(entry))
        path = self.codex_sessions / f"rollout-2026-11-01T10-00-00-{session_id}.jsonl"
        path.write_text("\n".join(lines) + "\n")
        return path

    def session(self, session_id: str, cwd: Path) -> Path:
        """A Claude Code session file with planted secrets, for a session in cwd."""
        lines = []
        for line in fixture("planted-secrets.jsonl").splitlines():
            entry = json.loads(line)
            entry["sessionId"] = session_id
            if "cwd" in entry:
                entry["cwd"] = str(cwd)
            lines.append(json.dumps(entry))
        path = self.projects / f"{session_id}.jsonl"
        path.write_text("\n".join(lines) + "\n")
        return path

    def fire(self, event: str, session_id: str = "", path: Path | str = "", cwd: Path | str = "",
             extra_env: dict[str, str] | None = None, app: str = "claude",
             project: Path | str | None = None) -> subprocess.CompletedProcess[str]:
        """Run the hook command from hooks.json the way the app runs it: Claude Code
        sets CLAUDE_PROJECT_DIR (the start folder, `project`, by default cwd); Codex
        sets CLAUDE_PLUGIN_ROOT (in self.env), CLAUDE_PLUGIN_DATA and its own CODEX_* variables."""
        command = self.hooks[event][0]["hooks"][0]["command"]
        payload = {"hook_event_name": event, "session_id": session_id, "transcript_path": str(path), "cwd": str(cwd)}
        if app == "codex":
            # The extra fields Codex Desktop 0.166 sends.
            payload.update({"SessionStart": {"source": "startup", "model": "gpt-5", "permission_mode": "default"},
                            "SessionEnd": {"reason": "exit"},
                            "Stop": {"turn_id": "t1", "last_assistant_message": "done", "stop_hook_active": False},
                            }.get(event, {}))
        if app == "claude":
            app_env = {"CLAUDE_CODE_ENTRYPOINT": "cli"}
            if project != "":
                app_env["CLAUDE_PROJECT_DIR"] = str(project or cwd)
        else:
            # What Codex Desktop 0.166 sets for plugin hooks.
            app_env = {"CLAUDE_PLUGIN_DATA": str(self.dir / "plugin-data"), "CODEX_SHELL": "1",
                       "CODEX_INTERNAL_ORIGINATOR_OVERRIDE": "Codex Desktop"}
        return subprocess.run(["/bin/sh", "-c", command], input=json.dumps(payload), text=True,
                              capture_output=True, env={**self.env, **app_env, **(extra_env or {})}, timeout=15)

    def relay(self, app: str) -> Relay:
        """Start the okWOW MCP server the way each app starts it. Claude Code expands
        ${CLAUDE_PLUGIN_ROOT}, names the plugin folder in the server's environment and
        runs it in the project folder. Codex 0.139 expands nothing, runs it in `cwd`
        under the plugin folder, and passes only a few variables of its own plus those
        named in `env_vars`. Gemini CLI expands ${extensionPath}."""
        if app == "gemini":
            server = json.loads((self.ext / "gemini-extension.json").read_text())["mcpServers"]["okwow"]
            args = [a.replace("${extensionPath}", str(self.ext)) for a in server["args"]]
            return Relay([server["command"], *args], self.dir, self.env)
        server = self.server
        if app == "claude":
            args = [a.replace("${CLAUDE_PLUGIN_ROOT}", str(self.plugin)) for a in server["args"]]
            return Relay([server["command"], *args], self.dir,
                         {**self.env, "CLAUDE_PLUGIN_ROOT": str(self.plugin), "CLAUDE_CODE_ENTRYPOINT": "cli"})
        env = {k: self.env[k] for k in ("HOME", "PATH", *server.get("env_vars", [])) if k in self.env}
        # For the test only: no real Keychain, and the browser that consents.
        env.update({k: self.env[k] for k in ("OKWOW_CAPTURE_KEYCHAIN", "BROWSER")})
        cwd = self.plugin / server["cwd"] if "cwd" in server else self.dir
        return Relay([server["command"], *server["args"]], cwd, env)

    def capture(self, *args: str, env: dict[str, str] | None = None,
                cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, "-I", str(self.plugin / "scripts" / "okwow-capture"), *args],
                              text=True, capture_output=True, env={**self.env, **(env or {})}, cwd=cwd, timeout=60)

    def start(self, *args: str, env: dict[str, str] | None = None, cwd: Path | None = None) -> Any:
        """The `start` command's JSON, or its exit code and error when it prints none."""
        done = self.capture("start", *args, env=env, cwd=cwd)
        try:
            return json.loads(done.stdout) if done.returncode == 0 else {"exit": done.returncode, "error": done.stderr}
        except ValueError:
            return {"exit": done.returncode, "stdout": done.stdout, "stderr": done.stderr}

    def log(self) -> str:
        path = self.dir / ".local" / "state" / "okwow" / "capture.log"
        return path.read_text() if path.exists() else ""

    def token(self, agent: str = "claude") -> Path:
        return self.config / f"capture-token-{agent}.json"

    def stop(self) -> None:
        subprocess.run(["pkill", "-f", str(self.plugin)], check=False)
        shutil.rmtree(self.dir, ignore_errors=True)


def wait(predicate: Callable[[], bool], seconds: float = 20) -> bool:
    deadline = time.time() + seconds
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.2)
    return predicate()


def settle(seconds: float = 3) -> None:
    """Time for a background upload that must not happen to have happened."""
    time.sleep(seconds)


def call(fake: Fake, tool: str) -> dict[str, Any]:
    return next((c["arguments"] for c in fake.calls if c["name"] == tool), {})


def under(start: Any, prefix: str) -> bool:
    return isinstance(start, dict) and (start.get("repository") or "").startswith(prefix)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report")
    args = parser.parse_args()
    secrets = json.loads(fixture("planted-secrets.json"))
    fake = Fake()
    home = Home(fake)
    results: list[dict[str, Any]] = []

    def case(name: str, passed: bool, detail: Any = None) -> None:
        results.append({"case": name, "pass": bool(passed), "detail": detail})
        print(f"{'PASS' if passed else 'FAIL'} {name}" + ("" if passed else f": {detail}"))

    try:
        app = home.repo("app", "git@github.com:acme/app.git")
        mirror = home.repo("mirror", "https://someone:hunter3@github.com/acme/mirror.git")
        secret = home.repo("secret", "https://github.com/acme/secret")
        loose = home.repo("loose", None)
        plain = home.dir / "code" / "plain"
        plain.mkdir()
        real = os.path.realpath

        # One plugin for every app: the hook commands name none.
        commands = [h["command"] for groups in home.hooks.values() for g in groups for h in g["hooks"]]
        named = [c for c in commands if re.search(r"claude|codex", c.replace("CLAUDE_PLUGIN_ROOT", ""), re.I)
                 or not c.rstrip().endswith("okwow-capture\" hook")]
        case("the hook commands name no app", commands and not named, named)

        default = home.capture("status", env={"OKWOW_MCP_URL": ""})
        case("with OKWOW_MCP_URL unset the plugin talks to production",
             "Server: https://api.okwow.ai/mcp" in default.stdout, default.stdout + default.stderr)
        override = home.capture("status")
        case("OKWOW_MCP_URL points the plugin at another okWOW server", f"Server: {home.url}" in override.stdout,
             override.stdout + override.stderr)

        # A fresh install does nothing until its first session start, then
        # signs in once, on its own, and never asks again.
        home.fire("Stop", "s0", home.session("s0", app), app)
        settle(1)
        case("not signed in: a turn starts nothing and sends nothing",
             not home.token().exists() and fake.registrations == 0 and not fake.calls)
        # A new session starts the MCP server and fires SessionStart at about the same time.
        first = home.relay("claude")
        refused = first.request(1, "initialize", INITIALIZE) or {}
        lines = first.close()
        case("before sign-in the MCP server answers with an error naming the sign-in step, and writes nothing else",
             refused.get("id") == 1 and "sign in" in (refused.get("error") or {}).get("message", "").lower()
             and len(lines) == 1, lines)
        home.fire("SessionStart", "s0", "", app)
        signed_in = wait(lambda: home.token().exists() and "get_session_capture" in fake.tools())
        case("the first session signs in through the browser on its own", signed_in, home.log())
        settle(1)
        case("the MCP server and capture open one sign-in between them, named after the app",
             list(fake.clients.values()) == ["Claude Code"], fake.clients)
        fake.reset()
        shared = round_trip(home.relay("claude"))
        case("Claude Code's okWOW tools go through the relay with Claude Code's sign-in",
             not round_trip_error(fake, shared, "Claude Code"), round_trip_error(fake, shared, "Claude Code"))
        saved = json.loads(home.token().read_text())
        home.token().write_text(json.dumps({**saved, "expires_at": 0}))
        fake.grants.clear()
        relay = home.relay("claude")
        refreshed = relay.request(1, "initialize", INITIALIZE) or {}
        relay.close()
        case("an expired sign-in is refreshed, never sent stale",
             fake.grants == [("refresh_token", "Claude Code")] and "result" in refreshed,
             {"grants": fake.grants, "reply": refreshed})
        saved = json.loads(home.token().read_text())
        home.token().write_text(json.dumps({**saved, "server": "http://127.0.0.1:1/mcp"}))
        fake.reset()
        relay = home.relay("claude")
        other = relay.request(1, "initialize", INITIALIZE) or {}
        relay.close()
        home.token().write_text(json.dumps(saved))
        case("a sign-in for another server is never sent", "error" in other and not fake.requests, other)
        mode = oct(home.token().stat().st_mode & 0o777) if home.token().exists() else None
        case("the token file is private", mode == "0o600", mode)
        before = fake.registrations
        home.capture("logout", "--agent", "claude")
        home.fire("SessionStart", "s0", "", app)
        settle(2)
        relay = home.relay("claude")
        signed_out = relay.request(1, "initialize", INITIALIZE) or {}
        relay.close()
        settle(2)
        case("after declining or signing out, nothing opens sign-in again",
             fake.registrations == before and not home.token().exists() and "error" in signed_out,
             {"registrations": fake.registrations, "reply": signed_out})
        done = home.capture("login", "--agent", "claude")
        case("signing in again by hand works and names the destination",
             done.returncode == 0 and SPACE["label"] in done.stdout and home.token().exists(),
             done.stdout + done.stderr)

        # On by default: a session ends and is saved to the default space.
        fake.reset()
        path = home.session("s1", app)
        home.fire("SessionEnd", "s1", path, app)
        sent = wait(lambda: "create_content" in fake.tools())
        create = call(fake, "create_content")
        case("a session is saved on session end with no setup", sent, fake.tools())
        case("it leaves the space to okWOW's settings",
             create.get("kind") == "chat" and all("in" not in c["arguments"] for c in fake.calls), create)
        case("the app is detected as Claude Code from its session folder and environment",
             create.get("session", {}).get("agent") == "Claude Code", create.get("session"))
        expected = {"folder": real(app), "repository": "github.com/acme/app", "repository_root": real(app)}
        case("its start names the folder, the remote and the repository root",
             create.get("session", {}).get("start") == expected, create.get("session"))
        case("the same start reaches get_session_capture, prepare_upload and create_content",
             call(fake, "get_session_capture").get("start") == expected
             and call(fake, "prepare_upload").get("start") == expected, fake.calls)
        case("the repository is never sent outside start", "repository" not in create.get("session", {}),
             create.get("session"))
        body = b"".join(fake.puts).decode()
        leaks = sorted(k for k, v in secrets.items() if v in body)
        case("no planted secret is uploaded", bool(body) and not leaks, leaks)
        order = fake.tools()
        case("settings are read before anything is sent",
             order[:1] == ["get_session_capture"], order)
        fake.reset()
        titled = home.session("s1t", app)
        with titled.open("a") as f:
            f.write(json.dumps({"type": "custom-title", "customTitle": "fix/api\\retry:\tlogin", "sessionId": "s1t"}) + "\n")
        home.fire("SessionEnd", "s1t", titled, app)
        wait(lambda: "create_content" in fake.tools())
        title = call(fake, "create_content").get("title", "")
        case("a session title with path separators or control characters is still saved, as a plain name",
             title and not re.search(r"[\\/\x00-\x1f\x7f]", title) and all(w in title for w in ("fix", "api", "login")),
             title)

        # The session moves: later hooks run in another folder, and the app gives
        # no start folder of its own, so the first hook's folder is the start.
        fake.reset()
        moved = app / "packages" / "web"
        moved.mkdir(parents=True)
        path = home.session("s1m", app)
        home.fire("Stop", "s1m", path, app, project="")
        home.fire("SessionEnd", "s1m", path, moved, project="")
        wait(lambda: "create_content" in fake.tools())
        start = call(fake, "create_content").get("session", {}).get("start") or {}
        case("a session that moves keeps the folder it started in", start.get("folder") == real(app), start)

        # Claude Code's project folder wins over the hook's cwd, at every hook.
        fake.reset()
        path = home.session("s1p", app)
        home.fire("SessionEnd", "s1p", path, moved, project=app)
        wait(lambda: "create_content" in fake.tools())
        start = call(fake, "create_content").get("session", {}).get("start") or {}
        case("the app's own start folder is used over the current folder", start.get("folder") == real(app), start)

        # A session started in a subfolder of a worktree.
        fake.reset()
        tree = home.worktree(app, "app-feature")
        inside = tree / "pkg"
        inside.mkdir()
        home.fire("SessionEnd", "s1w", home.session("s1w", inside), inside)
        wait(lambda: "create_content" in fake.tools())
        start = call(fake, "create_content").get("session", {}).get("start")
        case("a worktree start reports the repository and the worktree's root",
             start == {"folder": real(inside), "repository": "github.com/acme/app", "repository_root": real(tree)},
             start)

        fake.reset()
        home.fire("SessionEnd", "s2", home.session("s2", mirror), mirror)
        wait(lambda: "create_content" in fake.tools())
        start = call(fake, "create_content").get("session", {}).get("start") or {}
        case("credentials in a remote URL never reach okWOW", start.get("repository") == "github.com/acme/mirror"
             and "hunter3" not in json.dumps(fake.calls), start)

        fake.reset()
        home.fire("SessionEnd", "s3", home.session("s3", loose), loose)
        wait(lambda: "create_content" in fake.tools())
        start = call(fake, "create_content").get("session", {}).get("start")
        case("a git folder with no remote sends its folder and root, no repository",
             start == {"folder": real(loose), "repository_root": real(loose)}, start)

        fake.reset()
        home.fire("SessionEnd", "s3p", home.session("s3p", plain), plain)
        wait(lambda: "create_content" in fake.tools())
        start = call(fake, "create_content").get("session", {}).get("start")
        case("a folder outside git sends its folder only", start == {"folder": real(plain)}, start)

        # Codex signs in on its own, as itself, at its first session. The sign-in
        # every app once shared, as "okWOW plugin", is removed then.
        legacy = home.config / "capture-token.json"
        legacy.write_text(json.dumps({"server": home.url, "client_id": "client-0", "store": "file",
                                      "access_token": "legacy-access", "refresh_token": "legacy-refresh"}))
        legacy.chmod(0o600)
        claude_token = home.token().read_text()
        fake.grants.clear()
        home.fire("SessionStart", "c0", home.codex_session("c0", app), app, app="codex")
        codex_signed_in = wait(lambda: home.token("codex").exists() and "get_session_capture" in fake.tools())
        settle(1)
        case("Codex's first session signs it in as Codex, alongside Claude Code",
             codex_signed_in and sorted(set(fake.clients.values())) == ["Claude Code", "Codex"]
             and list(fake.clients.values())[-1] == "Codex", fake.clients)
        case("Codex's sign-in leaves Claude Code's sign-in as it was",
             home.token().read_text() == claude_token and all(c != "Claude Code" for _, c in fake.grants),
             fake.grants)
        case("the shared sign-in from before is removed after an app's first sign-in, and the user told to revoke it",
             not legacy.exists() and "okWOW plugin" in home.log(), home.log()[-600:])

        # Each app's sessions upload with that app's sign-in.
        fake.reset()
        home.fire("SessionEnd", "s1c", home.session("s1c", app), app)
        wait(lambda: "create_content" in fake.tools())
        home.fire("SessionEnd", "c1c", home.codex_session("c1c", app), app, app="codex")
        wait(lambda: fake.tools().count("create_content") == 2)
        signed = {c["arguments"]["session"]["id"]: fake.client(c["token"]) for c in fake.calls
                  if c["name"] == "create_content"}
        case("a Claude Code session uploads as Claude Code and a Codex session as Codex",
             signed == {"s1c": "Claude Code", "c1c": "Codex"}, signed)

        # Each app's okWOW tools go through the relay with that app's own sign-in,
        # answered as JSON or as an event stream.
        for sse in (False, True):
            fake.sse = sse
            for agent, name in (("claude", "Claude Code"), ("codex", "Codex")):
                fake.reset()
                replies = round_trip(home.relay(agent))
                case(f"the relay round-trips {name}'s tool calls as {name}"
                     f" ({'event stream' if sse else 'JSON'})",
                     not round_trip_error(fake, replies, name), round_trip_error(fake, replies, name))
        fake.sse = False

        # A token okWOW no longer takes: refreshed, then retried once.
        fake.reset()
        fake.grants.clear()
        fake.revoke("Codex")
        replies = round_trip(home.relay("codex"))
        case("on a 401 the relay refreshes the app's sign-in and retries",
             not round_trip_error(fake, replies, "Codex") and fake.grants == [("refresh_token", "Codex")],
             {"grants": fake.grants, "error": round_trip_error(fake, replies, "Codex")})
        # Refused as well: an error, and the other app's sign-in untouched.
        fake.refresh_ok = False
        fake.revoke("Codex")
        fake.grants.clear()
        relay = home.relay("codex")
        refused = relay.request(1, "initialize", INITIALIZE) or {}
        lines = relay.close()
        fake.refresh_ok = True
        fake.reset()
        still = round_trip(home.relay("claude"))
        case("when the refresh is refused the relay answers with an error, and Claude Code's sign-in still works",
             refused.get("id") == 1 and "error" in refused and len(lines) == 1
             and home.token().read_text() == claude_token and not round_trip_error(fake, still, "Claude Code")
             and all(c != "Claude Code" for _, c in fake.grants),
             {"reply": refused, "grants": fake.grants, "claude": round_trip_error(fake, still, "Claude Code")})
        home.capture("login", "--agent", "codex")

        # Gemini CLI runs only the relay: its first use opens its own sign-in.
        relay = home.relay("gemini")
        refused = relay.request(1, "initialize", INITIALIZE) or {}
        lines = relay.close()
        case("Gemini CLI before its sign-in gets an error naming the sign-in step, and nothing else",
             refused.get("id") == 1 and "sign in" in (refused.get("error") or {}).get("message", "").lower()
             and len(lines) == 1, lines)
        gemini_signed_in = wait(lambda: "Gemini CLI" in fake.clients.values() and home.token("gemini").exists())
        settle(1)
        fake.reset()
        replies = round_trip(home.relay("gemini"))
        case("after signing in, Gemini CLI's tools go through as Gemini CLI",
             gemini_signed_in and not round_trip_error(fake, replies, "Gemini CLI"),
             {"clients": fake.clients, "error": round_trip_error(fake, replies, "Gemini CLI")})

        # Codex: the start comes from the session file's session_meta, not from the
        # hook's cwd or a project folder inherited from another app's environment.
        fake.reset()
        codex_path = home.codex_session("c1", app)
        home.fire("SessionStart", "c1", codex_path, moved, app="codex",
                  extra_env={"CLAUDE_PROJECT_DIR": str(secret)})
        settle(1)
        home.fire("SessionEnd", "c1", codex_path, moved, app="codex",
                  extra_env={"CLAUDE_PROJECT_DIR": str(secret)})
        sent = wait(lambda: "create_content" in fake.tools())
        session = call(fake, "create_content").get("session", {})
        case("the app is detected as Codex from its session folder", sent and session.get("agent") == "Codex",
             session)
        case("a Codex session's start comes from its session_meta",
             session.get("start") == expected, session)
        body = b"".join(fake.puts).decode()
        leaks = sorted(k for k, v in secrets.items() if v in body)
        case("no planted secret in a Codex session is uploaded", bool(body) and not leaks, leaks)

        # Two sessions end back to back while okWOW is slow: the second
        # session's sweep waits for the first instead of dropping its session.
        fake.reset()
        fake.on_settings = lambda: time.sleep(1.5)
        home.fire("SessionEnd", "s1a", home.session("s1a", app), app)
        home.fire("SessionEnd", "s1b", home.session("s1b", app), app)
        both = wait(lambda: fake.tools().count("create_content") == 2, 30)
        fake.on_settings = lambda: None
        ids = sorted(c["arguments"]["session"]["id"] for c in fake.calls if c["name"] == "create_content")
        case("two sessions that end back to back are both saved", both and ids == ["s1a", "s1b"], fake.tools())

        # Settings are asked before the messages are read: a turn written while
        # okWOW answers is in the upload.
        fake.reset()
        path = home.session("s1o", app)

        def add_turn() -> None:
            entry = {"type": "user", "sessionId": "s1o", "cwd": str(app), "timestamp": "2026-11-01T11:00:00Z",
                     "message": {"role": "user", "content": "written-after-settings"}}
            with path.open("a") as f:
                f.write(json.dumps(entry) + "\n")

        fake.on_settings = add_turn
        home.fire("SessionEnd", "s1o", path, app)
        wait(lambda: "create_content" in fake.tools())
        fake.on_settings = lambda: None
        case("okWOW is asked before the session's messages are read",
             "written-after-settings" in b"".join(fake.puts).decode(), fake.tools())

        # okWOW skips sessions that started in this repository: nothing past
        # the start is read, nothing is sent.
        fake.reset()
        fake.decide = lambda start: "skip" if under(start, "github.com/acme/secret") else "send"
        home.fire("SessionEnd", "s4", home.session("s4", secret), secret)
        settle()
        home.fire("SessionEnd", "c4", home.codex_session("c4", secret), secret, app="codex")
        settle()
        asked = [c["arguments"].get("start", {}).get("repository") for c in fake.calls
                 if c["name"] == "get_session_capture"]
        case("a session okWOW skips is never sent",
             asked == ["github.com/acme/secret"] * 2 and "prepare_upload" not in fake.tools() and not fake.puts,
             fake.calls)
        case("a skipped session is logged as skipped, not as an error",
             home.log().count("skip claude:s4") == 1 and "skip codex:c4" in home.log()
             and "error claude:s4" not in home.log(), home.log()[-600:])

        # Paused in okWOW: skip for every start.
        fake.reset()
        fake.decide = lambda start: "skip"
        fake.reason = "paused"
        home.fire("SessionEnd", "s5", home.session("s5", app), app)
        settle()
        case("capture paused in okWOW sends nothing", not fake.puts and "create_content" not in fake.tools(),
             fake.tools())
        case("a paused skip is logged as paused, not as a rule",
             "skip claude:s5: session capture is paused in okWOW" in home.log()
             and "s5: okWOW's rule" not in home.log(), home.log()[-400:])
        fake.decide = lambda start: "send"
        fake.reason = "rule"

        # send with no space: nothing is uploaded.
        fake.reset()
        fake.space = None
        home.fire("SessionEnd", "s5n", home.session("s5n", app), app)
        settle()
        case("send with no space uploads nothing", not fake.puts and "prepare_upload" not in fake.tools(),
             fake.tools())
        fake.space = SPACE

        # An older server with no settings tool: fail closed.
        fake.reset()
        fake.has_settings_tool = False
        home.fire("SessionEnd", "s6", home.session("s6", app), app)
        settle()
        case("a server without capture settings gets nothing", not fake.puts, fake.tools())
        fake.has_settings_tool = True

        # A file outside the harness's session folders, directly or by symlink.
        fake.reset()
        outside = home.dir / "notes.jsonl"
        shutil.copy(home.session("s7", app), outside)
        (home.projects / "s7.jsonl").unlink()
        (home.projects / "s7.jsonl").symlink_to(outside)
        home.fire("SessionEnd", "s7", home.projects / "s7.jsonl", app)
        home.fire("SessionEnd", "s8", outside, app)
        settle()
        case("a session file outside ~/.claude/projects is never read or sent",
             not fake.puts and "prepare_upload" not in fake.tools(), fake.tools())

        # A non-https upload URL off this machine.
        fake.reset()
        fake.upload_url = lambda base: "http://198.51.100.7/upload/1"
        home.fire("SessionEnd", "s9", home.session("s9", app), app)
        settle()
        case("an upload URL that is not https is refused", not fake.puts and "create_content" not in fake.tools(),
             fake.tools())
        fake.upload_url = lambda base: f"{base}/upload/1"

        # The configured server swapped for another host.
        fake.reset()
        config = home.config / "capture.json"
        saved_config = config.read_text()
        config.write_text(json.dumps({"server": "https://okwow.ai.attacker.example/mcp"}))
        refused = home.capture("upload", str(home.session("s10", app)))
        config.write_text(saved_config)
        case("a server outside okwow.ai is refused", refused.returncode != 0 and not fake.calls,
             refused.stderr.strip())

        # A token file others can read is not trusted.
        fake.reset()
        home.token().chmod(0o644)
        loose_token = home.capture("upload", str(home.session("s11", app)))
        home.token().chmod(0o600)
        case("a token file readable by others is refused", loose_token.returncode != 0 and not fake.calls,
             loose_token.stderr.strip())

        # Background runs ignore PYTHON* variables.
        fake.reset()
        inject = home.dir / "inject"
        inject.mkdir()
        marker = home.dir / "injected"
        (inject / "sitecustomize.py").write_text(f"open({str(marker)!r}, 'w').write('x')\n")
        home.fire("SessionEnd", "s12", home.session("s12", app), app, {"PYTHONPATH": str(inject)})
        wait(lambda: "create_content" in fake.tools())
        case("PYTHONPATH cannot inject code into the hook or its uploads", not marker.exists())

        # `start` prints where this session started, for the agent to pass to
        # okWOW's rule tools; it sends nothing itself.
        fake.reset()
        registrations = fake.registrations
        app_start = {"folder": real(app), "repository": "github.com/acme/app", "repository_root": real(app)}
        claude_env = {"CLAUDE_CODE_ENTRYPOINT": "cli", "CLAUDE_CODE_SESSION_ID": "s1m"}
        remembered = home.start(env=claude_env, cwd=moved)
        case("start prints the remembered start of the current Claude Code session", remembered == app_start,
             remembered)
        remembered = home.start(env={"CODEX_SHELL": "1", "CODEX_THREAD_ID": "c1"}, cwd=moved)
        case("start prints the remembered start of the current Codex session", remembered == app_start, remembered)
        project = home.start(env={"CLAUDE_CODE_ENTRYPOINT": "cli", "CLAUDE_CODE_SESSION_ID": "unseen",
                                  "CLAUDE_PROJECT_DIR": str(app)}, cwd=moved)
        case("with no remembered start, Claude Code's project folder is the start", project == app_start, project)
        here = home.start(cwd=plain)
        case("with neither, the current folder is the start", here == {"folder": real(plain)}, here)
        link = home.dir / "web-link"
        link.symlink_to(moved)
        named = home.start("--folder", str(link), cwd=plain)
        case("--folder resolves the real path of a folder the user names",
             named == {"folder": real(moved), "repository": "github.com/acme/app", "repository_root": real(app)},
             named)
        missing = home.start("--folder", str(home.dir / "no-such-folder"), cwd=plain)
        case("--folder refuses a folder that does not exist",
             missing.get("exit", 0) != 0 and "no-such-folder" in missing.get("error", ""), missing)
        top = home.start("--repository", "--folder", str(inside), cwd=plain)
        case("--repository gives the repository's top folder and its remote",
             top == {"folder": real(tree), "repository": "github.com/acme/app", "repository_root": real(tree)}, top)
        current = home.start("--repository", env=claude_env, cwd=moved)
        case("--repository starts from the current session's start", current == app_start, current)
        outside_git = home.start("--repository", "--folder", str(plain), cwd=plain)
        case("--repository refuses a folder outside git", outside_git.get("exit", 0) != 0, outside_git)
        case("start sends nothing to okWOW", not fake.calls and not fake.puts and fake.registrations == registrations,
             fake.tools())



        # Headless sign-in: print an authorize URL now, finish with the code later.
        loader = importlib.machinery.SourceFileLoader("okwow_capture_under_test", str(PLUGIN / "scripts" / "okwow-capture"))
        module = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
        sys.modules[loader.name] = module
        loader.exec_module(module)

        def mapped(url: str) -> str:
            try:
                return module.headless_redirect(url, None)
            except module.CaptureError as error:
                return f"refused: {error}"

        case("headless: production's api host maps to app.okwow.ai",
             mapped("https://api.okwow.ai/mcp") == "https://app.okwow.ai/mcp-login/code", mapped("https://api.okwow.ai/mcp"))
        case("headless: staging's api host maps to staging.app.okwow.ai",
             mapped("https://staging.api.okwow.ai/mcp") == "https://staging.app.okwow.ai/mcp-login/code",
             mapped("https://staging.api.okwow.ai/mcp"))
        unmapped = [mapped(u) for u in ("http://127.0.0.1:9/mcp", "https://okwow.ai/mcp", "https://mcp.okwow.ai/mcp")]
        case("headless: a host that does not fit is refused without --redirect-uri",
             all(u.startswith("refused:") and "--redirect-uri" in u for u in unmapped), unmapped)
        case("headless: --redirect-uri overrides when https, and must be https",
             module.headless_redirect("http://127.0.0.1:9/mcp", "https://app.example/mcp-login/code")
             == "https://app.example/mcp-login/code" and mapped("http://127.0.0.1:9/mcp").startswith("refused")
             and module.headless_redirect("https://api.okwow.ai/mcp", "https://x.example/c") == "https://x.example/c",
             None)
        try:
            module.headless_redirect("https://api.okwow.ai/mcp", "http://evil.example/c")
            plain_http_refused = False
        except module.CaptureError:
            plain_http_refused = True
        case("headless: a non-https --redirect-uri is refused", plain_http_refused)

        redirect = "https://app.example/mcp-login/code"
        pending = home.config / "capture-pending-gemini.json"

        def start_headless(*extra: str) -> tuple[subprocess.CompletedProcess[str], dict[str, str]]:
            done = home.capture("login", "--agent", "gemini", "--headless", *extra)
            found = re.search(r"https?://\S+/authorize\?\S+", done.stdout)
            return done, dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(found.group(0)).query)) if found else {}

        def consent(query: dict[str, str]) -> tuple[str, str]:
            """What the browser does at the authorize URL: the code and state okWOW's page shows."""
            conn = http.client.HTTPConnection(urllib.parse.urlsplit(fake.base).netloc)
            conn.request("GET", "/authorize?" + urllib.parse.urlencode(query))
            location = urllib.parse.urlsplit(conn.getresponse().getheader("Location") or "")
            got = dict(urllib.parse.parse_qsl(location.query))
            return got["code"], got["state"]

        home.capture("logout", "--agent", "gemini")
        before = fake.registrations
        bare = home.capture("login", "--agent", "gemini", "--headless")
        case("headless: a host that does not fit needs --redirect-uri; nothing is registered or written",
             bare.returncode != 0 and "--redirect-uri" in bare.stderr and fake.registrations == before
             and not pending.exists(), bare.stdout + bare.stderr)
        done, query = start_headless("--redirect-uri", redirect)
        data = json.loads(pending.read_text()) if pending.exists() else {}
        case("headless start prints the authorize URL for the derived redirect and exits",
             done.returncode == 0 and query.get("redirect_uri") == redirect and query.get("code_challenge_method") == "S256"
             and query.get("state") and fake.redirects.get(query.get("client_id", "")) == [redirect], done.stdout + done.stderr)
        case("headless start writes a private pending file with the verifier, state and client",
             oct(pending.stat().st_mode & 0o777) == "0o600" and data.get("state") == query.get("state")
             and data.get("client_id") == query.get("client_id") and data.get("redirect_uri") == redirect
             and data.get("server") == home.url and data.get("verifier") and data.get("created_at"),
             {k: v for k, v in data.items() if k != "verifier"})
        case("headless start stores no tokens", not home.token("gemini").exists())

        code, state = consent(query)
        fake.reset()
        done = home.capture("login", "--agent", "gemini", "--finish", f"{code}#{state}")
        saved = json.loads(home.token("gemini").read_text()) if home.token("gemini").exists() else {}
        case("headless finish signs in and reports the email and capture settings",
             done.returncode == 0 and "pat@example.com" in done.stdout and SPACE["label"] in done.stdout
             and "get_session_capture" in fake.tools(), done.stdout + done.stderr)
        case("headless finish deletes the pending file", not pending.exists())
        loopback_keys = set(json.loads(home.token("codex").read_text())) - {"port"}
        case("headless finish stores the same token file as the loopback sign-in",
             set(saved) - {"port"} == loopback_keys and saved.get("store") == "file"
             and saved.get("profile", {}).get("email") == "pat@example.com"
             and oct(home.token("gemini").stat().st_mode & 0o777) == "0o600", sorted(saved))
        fake.reset()
        fake.grants.clear()
        saved["expires_at"] = 0
        home.token("gemini").write_text(json.dumps(saved))
        replies = round_trip(home.relay("gemini"))
        case("a headless sign-in refreshes like any other",
             fake.grants == [("refresh_token", "Gemini CLI")] and not round_trip_error(fake, replies, "Gemini CLI"),
             {"grants": fake.grants, "error": round_trip_error(fake, replies, "Gemini CLI")})

        done = home.capture("login", "--agent", "gemini", "--finish", f"{code}#{state}")
        case("finish with no pending file is refused with a message",
             done.returncode != 0 and "--headless" in done.stderr, done.stderr)

        _, query = start_headless("--redirect-uri", redirect)
        code, state = consent(query)
        grants = len(fake.grants)
        done = home.capture("login", "--agent", "gemini", "--finish", f"{code}#wrong-{state}")
        case("a wrong state is refused before any exchange, and the pending file is gone",
             done.returncode != 0 and "state" in done.stderr and len(fake.grants) == grants and not pending.exists(),
             done.stderr)

        _, query = start_headless("--redirect-uri", redirect)
        code, state = consent(query)
        data = json.loads(pending.read_text())
        data["created_at"] -= 11 * 60
        pending.write_text(json.dumps(data))
        pending.chmod(0o600)
        done = home.capture("login", "--agent", "gemini", "--finish", f"{code}#{state}")
        case("an expired pending file is refused before any exchange, and removed",
             done.returncode != 0 and "expired" in done.stderr and len(fake.grants) == grants and not pending.exists(),
             done.stderr)

        _, query = start_headless("--redirect-uri", redirect)
        spent, state = consent(query)
        done = home.capture("login", "--agent", "gemini", "--finish", f"{spent}#{state}")
        _, query = start_headless("--redirect-uri", redirect)
        _, state = consent(query)
        done = home.capture("login", "--agent", "gemini", "--finish", f"{spent}#{state}")
        case("a reused code is refused with a message, and the pending file is removed",
             done.returncode != 0 and "start again" in done.stderr and not pending.exists(), done.stderr)

        _, query = start_headless("--redirect-uri", redirect)
        code, state = consent(query)
        done = home.capture("login", "--agent", "gemini", "--finish", code)
        case("finish accepts a bare code", done.returncode == 0 and "pat@example.com" in done.stdout
             and not pending.exists(), done.stdout + done.stderr)
        case("no code or state lands in the log", code not in home.log() and state not in home.log(), None)

        # Codex runs the plugin's own hooks: nothing writes its hooks file.
        gone = home.capture("install-codex")
        case("there is no install-codex command", gone.returncode != 0 and "invalid choice" in gone.stderr,
             gone.stderr.strip())
        case("nothing writes ~/.codex/hooks.json", not (home.dir / ".codex" / "hooks.json").exists(),
             sorted(str(p) for p in (home.dir / ".codex").iterdir()))
    finally:
        home.stop()
        fake.httpd.shutdown()

    report = {"passed": all(r["pass"] for r in results), "cases": results}
    if args.report:
        Path(args.report).write_text(json.dumps(report, indent=2))
    print(f"{sum(r['pass'] for r in results)}/{len(results)} cases passed")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
