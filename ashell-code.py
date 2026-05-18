#!/usr/bin/env python3
"""
ashell-code v1.0
Agentic coding CLI for a-Shell (iOS) - Inspired by opencode and openclaude
Compatible with any OpenAI-compatible endpoint.
"""

import os, sys, json, sqlite3, subprocess, difflib, time, hashlib, importlib.util
from datetime import datetime
from urllib.request import Request, urlopen
from urllib.error import HTTPError

# ══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════════════════════

CFG_PATH = os.path.expanduser("~/Documents/ashell-code.json")
DB_PATH  = os.path.expanduser("~/Documents/ashell-code.db")
ALLOWLIST_PATH = os.path.expanduser("~/Documents/ashell-code/allowlist.txt")

DEFAULT_CFG = {
    "api_key":     "",
    "base_url":    "",
    "model":       "",
    "max_tokens":  262144,
    "temperature": 0.8,
    "system":      "",
    "format":      "none",
    "plugins_enabled": True,
    "mcp_servers": {},
}

PLUGINS_DIR = os.path.expanduser("~/Documents/ashell-code/plugins")
MCP_SERVERS  = {}   # name → {"url": ..., "tools": [...]}
ALLOWLIST    = []   # populated in main()
TOOL_CACHE   = {}   # cache: hash → result (read_file, list_files, search_files only)
SESSION_COST = 0.0  # accumulated USD cost for current session

# Pricing per 1M tokens (input, output). Add models as needed.
MODEL_PRICING = {
    "gpt-4o":           (2.50,  10.00),
    "gpt-4o-mini":      (0.15,   0.60),
    "gpt-4-turbo":      (10.00, 30.00),
    "gpt-4":            (30.00, 60.00),
    "gpt-3.5-turbo":    (0.50,   1.50),
    "o1":               (15.00, 60.00),
    "o3":               (10.00, 40.00),
    "claude-3-5-sonnet":(3.00,  15.00),
    "claude-3-5-haiku": (0.80,   4.00),
    "claude-3-opus":    (15.00, 75.00),
    "claude-sonnet-4":  (3.00,  15.00),
    "claude-haiku-4":   (0.80,   4.00),
    "mistral-large":    (2.00,   6.00),
    "mistral-small":    (0.20,   0.60),
}

def get_pricing(model):
    m = model.lower()
    for key, (inp, out) in MODEL_PRICING.items():
        if key in m:
            return inp, out
    return None, None

# ══════════════════════════════════════════════════════════════════════════════
# PERMISSIONS
# ══════════════════════════════════════════════════════════════════════════════
def load_allowlist():
    if not os.path.exists(ALLOWLIST_PATH):
        return []
    with open(ALLOWLIST_PATH) as f:
        return [l.strip() for l in f if l.strip() and not l.startswith("#")]

def save_allowlist(entries):
    os.makedirs(os.path.dirname(ALLOWLIST_PATH), exist_ok=True)
    with open(ALLOWLIST_PATH, "w") as f:
        f.write("# ashell-agent allowlist\n# One entry per line. Prefix match for commands.\n")
        for e in entries:
            f.write(e + "\n")

def is_allowed(value, allowlist):
    """True if value starts with any allowlist entry."""
    for pattern in allowlist:
        if value.strip().startswith(pattern):
            return True
    return False

def ask_permission(action, detail):
    """Prompt user. Returns: 'y' yes once, 'a' always, 'n' no."""
    pr(C_T, f"\n  ⚠  Agent wants to {action}:")
    pr(C_D, f"     {detail[:200]}")
    try:
        ans = input(f"  Allow? [{C_A}y{R}]es / [{C_A}a{R}]lways / [{C_E}n{R}]o: ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        ans = "n"
    return ans if ans in ("y", "a", "n") else "n"

DEFAULT_SYSTEM = (
    "You are an expert agentic coding assistant running inside a-Shell on iOS. "
    "Use tools autonomously and iteratively to complete tasks — read files, write code, "
    "run commands, search. Never ask the user to do what a tool can do. "
    "Be terse. Think step by step. Prefer minimal, correct solutions. "
    "Available shell tools on device: python3, git, rg, sqlite3, base64, llvm/clang, nnn."
)
SYSTEM = DEFAULT_SYSTEM  # mutable; override via /system

# ══════════════════════════════════════════════════════════════════════════════
# ANSI
# ══════════════════════════════════════════════════════════════════════════════
R    = "\033[0m"
BOLD = "\033[1m"
C_U  = "\033[36m"   # user prompt
C_A  = "\033[32m"   # assistant
C_T  = "\033[33m"   # tool call
C_E  = "\033[31m"   # error
C_I  = "\033[34m"   # info
C_D  = "\033[90m"   # dim

def pr(color, text, end="\n"):
    print(f"{color}{text}{R}", end=end, flush=True)

def clear_line():
    print("\033[2K\r", end="", flush=True)

# ══════════════════════════════════════════════════════════════════════════════
# MODEL CONTEXT WINDOWS
# ══════════════════════════════════════════════════════════════════════════════
MODEL_CONTEXT_WINDOWS = {
    "gpt-4o":                   128_000,
    "gpt-4o-mini":              128_000,
    "gpt-4-turbo":              128_000,
    "gpt-4":                      8_192,
    "gpt-3.5-turbo":             16_385,
    "o1":                       200_000,
    "o3":                       200_000,
    "claude-3-5-sonnet":        200_000,
    "claude-3-5-haiku":         200_000,
    "claude-3-opus":            200_000,
    "claude-sonnet-4":          200_000,
    "claude-haiku-4":           200_000,
    "llama-3.3":                128_000,
    "llama-3.1":                128_000,
    "mistral-large":            128_000,
    "mistral-small":            128_000,
    "deepseek":                 128_000,
    "qwen":                     131_072,
    "gemma-3":                  128_000,
}

def get_context_window(model):
    m = model.lower()
    for key, size in MODEL_CONTEXT_WINDOWS.items():
        if key in m:
            return size
    return None

# ══════════════════════════════════════════════════════════════════════════════
# PLUGIN SYSTEM & TOOL DEFINITIONS
# ══════════════════════════════════════════════════════════════════════════════
def load_plugins():
    """Auto-discover plugins from PLUGINS_DIR. Each file must define:
       TOOL_DEF  = { "type": "function", "function": { ... } }
       def run(args: dict) -> str: ...
    """
    os.makedirs(PLUGINS_DIR, exist_ok=True)
    loaded = {}
    for fname in sorted(os.listdir(PLUGINS_DIR)):
        if not fname.endswith(".py") or fname.startswith("_"):
            continue
        path = os.path.join(PLUGINS_DIR, fname)
        try:
            spec   = importlib.util.spec_from_file_location(fname[:-3], path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            name = module.TOOL_DEF["function"]["name"]
            loaded[name] = {"def": module.TOOL_DEF, "fn": module.run}
            pr(C_D, f"  plugin: {name} ✓")
        except Exception as e:
            pr(C_E, f"  plugin load fail {fname}: {e}")
    return loaded

PLUGIN_REGISTRY = {}   # populated in main()

BASE_TOOL_DEFS = [
    {"type": "function", "function": {
        "name": "read_file",
        "description": "Read the full contents of a file from disk.",
        "parameters": {"type": "object",
            "properties": {"path": {"type": "string", "description": "Absolute or relative file path"}},
            "required": ["path"]}}},

    {"type": "function", "function": {
        "name": "write_file",
        "description": "Write (create or overwrite) a file with given content.",
        "parameters": {"type": "object",
            "properties": {
                "path":    {"type": "string"},
                "content": {"type": "string"}},
            "required": ["path", "content"]}}},

    {"type": "function", "function": {
        "name": "run_command",
        "description": "Execute a shell command. Returns stdout + stderr. Use for: python3, git, rg, sqlite3, llvm, etc.",
        "parameters": {"type": "object",
            "properties": {
                "cmd":     {"type": "string", "description": "Shell command to run"},
                "timeout": {"type": "integer", "default": 30, "description": "Max seconds to wait"}},
            "required": ["cmd"]}}},

    {"type": "function", "function": {
        "name": "list_files",
        "description": "List files/directories at a path.",
        "parameters": {"type": "object",
            "properties": {
                "path":      {"type": "string", "default": ".", "description": "Directory to list"},
                "recursive": {"type": "boolean", "default": False}},
            "required": []}}},

    {"type": "function", "function": {
        "name": "search_files",
        "description": "Search for a pattern in files using ripgrep (rg). Returns matching lines with line numbers.",
        "parameters": {"type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Regex or literal pattern"},
                "path":    {"type": "string", "default": ".", "description": "Directory to search"},
                "glob":    {"type": "string", "description": "File glob filter e.g. '*.py'"}},
            "required": ["pattern"]}}},

    {"type": "function", "function": {
        "name": "patch_file",
        "description": "Replace an exact string in a file with new content (for surgical edits).",
        "parameters": {"type": "object",
            "properties": {
                "path":    {"type": "string"},
                "old_str": {"type": "string", "description": "Exact string to find (must be unique in file)"},
                "new_str": {"type": "string", "description": "Replacement string"}},
            "required": ["path", "old_str", "new_str"]}}},
]
def get_tool_defs():
    defs = list(BASE_TOOL_DEFS)
    for p in PLUGIN_REGISTRY.values():
        defs.append(p["def"])
    for srv in MCP_SERVERS.values():
        defs.extend(srv.get("tools", []))
    return defs

# ══════════════════════════════════════════════════════════════════════════════
# TOOL IMPLEMENTATIONS
# ══════════════════════════════════════════════════════════════════════════════
def _expand(p): return os.path.expanduser(p)

def tool_read_file(path):
    try:
        with open(_expand(path), "r", errors="replace") as f:
            content = f.read()
        lines = content.splitlines()
        if len(lines) > 5000:
            content = "\n".join(lines[:5000]) + f"\n... (truncated, {len(lines)} total lines)"
        return content
    except Exception as e:
        return f"ERROR: {e}"

def show_diff(path, new_content):
    """Print colored unified diff of existing file vs new_content."""
    try:
        with open(_expand(path), "r", errors="replace") as f:
            old_lines = f.readlines()
        label = f"a/{path}"
    except FileNotFoundError:
        old_lines = []
        label = "/dev/null"
    new_lines = new_content.splitlines(keepends=True)
    diff = list(difflib.unified_diff(old_lines, new_lines,
                                     fromfile=label, tofile=f"b/{path}", lineterm=""))
    if not diff:
        pr(C_D, "  (no changes)")
        return
    for line in diff[:500]:
        if line.startswith("+"):
            print(f"{C_A}{line}{R}")
        elif line.startswith("-"):
            print(f"{C_E}{line}{R}")
        else:
            print(f"{C_D}{line}{R}")
    if len(diff) > 500:
        pr(C_D, f"  … ({len(diff) - 500} more lines)")

def tool_write_file(path, content, allowlist=None):
    allowlist = allowlist or []
    # Always show diff first
    print()
    show_diff(path, content)
    print()
    if not is_allowed(path, allowlist):
        ans = ask_permission("write file", path)
        if ans == "n":
            return "DENIED: user rejected file write"
        if ans == "a":
            allowlist.append(path)
            save_allowlist(allowlist)
    try:
        path = _expand(path)
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w") as f:
            f.write(content)
        return f"OK: wrote {len(content)} bytes → {path}"
    except Exception as e:
        return f"ERROR: {e}"

def tool_run_command(cmd, timeout=99999, allowlist=None):
    allowlist = allowlist or []
    if not is_allowed(cmd, allowlist):
        ans = ask_permission("run command", cmd)
        if ans == "n":
            return "DENIED: user rejected command"
        if ans == "a":
            # Save the first token (e.g. "git", "python3 script.py")
            entry = cmd.strip().split()[0]
            ans2  = input(f"  Save '{entry}' or full command? [t]oken/[f]ull: ").strip().lower()
            allowlist.append(cmd.strip() if ans2 == "f" else entry)
            save_allowlist(allowlist)
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            timeout=timeout, cwd=os.getcwd()
        )
        out = (result.stdout + result.stderr).strip()
        if len(out) > 50000:
            out = out[:50000] + "\n... (truncated)"
        return out if out else "(exit 0, no output)"
    except subprocess.TimeoutExpired:
        return f"ERROR: command timed out after {timeout}s"
    except Exception as e:
        return f"ERROR: {e}"

def tool_list_files(path=".", recursive=False):
    try:
        path = _expand(path)
        if recursive:
            result = []
            for root, dirs, files in os.walk(path):
                dirs[:] = [d for d in sorted(dirs) if not d.startswith(".")]
                rel = os.path.relpath(root, path)
                for f in sorted(files):
                    result.append(os.path.join(rel, f) if rel != "." else f)
                if len(result) > 3000:
                    result.append("... (truncated at 3000 entries)")
                    break
            return "\n".join(result)
        else:
            entries = sorted(os.listdir(path))
            annotated = []
            for e in entries:
                full = os.path.join(path, e)
                suffix = "/" if os.path.isdir(full) else ""
                annotated.append(e + suffix)
            return "\n".join(annotated)
    except Exception as e:
        return f"ERROR: {e}"

def tool_search_files(pattern, path=".", glob=None):
    cmd = f"rg --color=never -n {json.dumps(pattern)} {json.dumps(path)}"
    if glob:
        cmd += f" -g {json.dumps(glob)}"
    return tool_run_command(cmd, allowlist=ALLOWLIST)

def tool_patch_file(path, old_str, new_str):
    try:
        with open(_expand(path), "r") as f:
            content = f.read()
        count = content.count(old_str)
        if count == 0:
            return "ERROR: old_str not found in file"
        if count > 1:
            return f"ERROR: old_str found {count} times — must be unique"
        new_content = content.replace(old_str, new_str, 1)
        with open(_expand(path), "w") as f:
            f.write(new_content)
        return f"OK: patched {path}"
    except Exception as e:
        return f"ERROR: {e}"

TOOL_MAP = {
    "read_file":    lambda a: tool_read_file(a["path"]),
    "write_file":  lambda a: tool_write_file(a["path"], a["content"], ALLOWLIST),
    "run_command": lambda a: tool_run_command(a["cmd"], int(a.get("timeout", 99999)), ALLOWLIST),
    "list_files":   lambda a: tool_list_files(a.get("path", "."), bool(a.get("recursive", False))),
    "search_files": lambda a: tool_search_files(a["pattern"], a.get("path", "."), a.get("glob")),
    "patch_file":   lambda a: tool_patch_file(a["path"], a["old_str"], a["new_str"]),
}

# ══════════════════════════════════════════════════════════════════════════════
# MCP CLIENT  (HTTP/SSE transport)
# ══════════════════════════════════════════════════════════════════════════════
def mcp_fetch(url, method="GET", body=None):
    req = Request(url, data=json.dumps(body).encode() if body else None,
                  headers={"Content-Type": "application/json", "Accept": "application/json"})
    req.get_method = lambda: method
    with urlopen(req, timeout=15) as r:
        return json.loads(r.read())

def mcp_discover(url):
    """Fetch tool list from an MCP server."""
    try:
        data  = mcp_fetch(url.rstrip("/") + "/tools/list")
        tools = data.get("tools", [])
        # Convert MCP schema → OpenAI function-calling schema
        converted = []
        for t in tools:
            converted.append({"type": "function", "function": {
                "name":        t["name"],
                "description": t.get("description", ""),
                "parameters":  t.get("inputSchema", {"type": "object", "properties": {}}),
            }})
        return converted
    except Exception as e:
        pr(C_E, f"MCP discover failed: {e}")
        return []

def mcp_call_tool(tool_name, args):
    """Route tool call to the MCP server that owns it."""
    for srv_name, srv in MCP_SERVERS.items():
        owned = [t["function"]["name"] for t in srv.get("tools", [])]
        if tool_name in owned:
            try:
                url  = srv["url"].rstrip("/") + "/tools/call"
                body = {"name": tool_name, "arguments": args}
                resp = mcp_fetch(url, method="POST", body=body)
                # MCP returns {"content": [{"type":"text","text":"..."}]}
                parts = resp.get("content", [])
                return "\n".join(p.get("text", "") for p in parts if p.get("type") == "text")
            except Exception as e:
                return f"MCP error ({srv_name}): {e}"
    return None   # not handled by any MCP server

def cmd_mcp(arg, cfg):
    """Handle /mcp subcommands."""
    parts = arg.strip().split(None, 2)
    sub   = parts[0].lower() if parts else ""

    if sub == "add" and len(parts) >= 3:
        name, url = parts[1], parts[2]
        pr(C_D, f"  Connecting to MCP server '{name}'…")
        tools = mcp_discover(url)
        MCP_SERVERS[name] = {"url": url, "tools": tools}
        # Persist
        cfg["mcp_servers"][name] = url
        save_cfg(cfg)
        pr(C_I, f"✓ {name}: {len(tools)} tools registered")
        for t in tools:
            pr(C_D, f"    · {t['function']['name']}")

    elif sub == "list":
        if not MCP_SERVERS:
            pr(C_D, "No MCP servers connected.")
        for name, srv in MCP_SERVERS.items():
            pr(C_I, f"  [{name}] {srv['url']}  ({len(srv['tools'])} tools)")

    elif sub == "remove" and len(parts) >= 2:
        name = parts[1]
        MCP_SERVERS.pop(name, None)
        cfg["mcp_servers"].pop(name, None)
        save_cfg(cfg)
        pr(C_I, f"Removed {name}")

    elif sub == "tools" and len(parts) >= 2:
        name = parts[1]
        srv  = MCP_SERVERS.get(name)
        if not srv:
            pr(C_E, f"No server '{name}'")
        else:
            for t in srv["tools"]:
                print(f"    {C_T}{t['function']['name']}{R}  — {C_D}{t['function']['description'][:80]}{R}")

    else:
        pr(C_I, "Usage: /mcp add <name> <url> | /mcp list | /mcp remove <name> | /mcp tools <name>")

CACHEABLE_TOOLS = {"read_file", "list_files", "search_files"}
WRITE_TOOLS     = {"write_file", "patch_file"}

def _cache_key(name, args_str):
    h = hashlib.md5(f"{name}:{args_str}".encode()).hexdigest()
    return h

def dispatch_tool(name, args_str):
    try:
        args = json.loads(args_str) if args_str else {}

        # Cache hit
        if name in CACHEABLE_TOOLS:
            key = _cache_key(name, args_str)
            if key in TOOL_CACHE:
                pr(C_D, f"  ↩ cached")
                return TOOL_CACHE[key]

        # Invalidate cache on writes
        if name in WRITE_TOOLS:
            TOOL_CACHE.clear()

        fn = TOOL_MAP.get(name)
        if not fn:
            if name in PLUGIN_REGISTRY:
                return PLUGIN_REGISTRY[name]["fn"](args)
            result = mcp_call_tool(name, args)
            if result is not None:
                return result
            return f"ERROR: Unknown tool '{name}'"
        result = fn(args)

        # Store in cache
        if name in CACHEABLE_TOOLS:
            TOOL_CACHE[_cache_key(name, args_str)] = result

        return result
    except json.JSONDecodeError as e:
        return f"ERROR: bad JSON args: {e}"
    except Exception as e:
        return f"ERROR: {e}"

# ══════════════════════════════════════════════════════════════════════════════
# DATABASE  (session history)
# ══════════════════════════════════════════════════════════════════════════════
def db_init():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id      INTEGER PRIMARY KEY,
            created TEXT,
            name    TEXT,
            cwd     TEXT
        )""")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id         INTEGER PRIMARY KEY,
            session_id INTEGER,
            role       TEXT,
            content    TEXT,
            tool_calls TEXT,
            ts         TEXT
        )""")
    # Migration: add cwd if missing (existing DBs)
    try:
        conn.execute("ALTER TABLE sessions ADD COLUMN cwd TEXT")
    except Exception:
        pass
    conn.commit()
    return conn

def db_new_session(conn, name=None):
    now = datetime.now().isoformat()
    name = name or f"session {now[:16].replace('T',' ')}"
    cwd = os.getcwd()
    cur = conn.execute("INSERT INTO sessions (created, name, cwd) VALUES (?, ?, ?)", (now, name, cwd))
    conn.commit()
    return cur.lastrowid

def db_update_cwd(conn, sid):
    conn.execute("UPDATE sessions SET cwd=? WHERE id=?", (os.getcwd(), sid))
    conn.commit()

def db_save_msg(conn, sid, role, content, tool_calls=None):
    conn.execute(
        "INSERT INTO messages (session_id, role, content, tool_calls, ts) VALUES (?,?,?,?,?)",
        (sid, role, content,
         json.dumps(tool_calls) if tool_calls else None,
         datetime.now().isoformat())
    )
    conn.commit()

def db_list_sessions(conn, n=15):
    return conn.execute(
        "SELECT id, name, created FROM sessions ORDER BY id DESC LIMIT ?", (n,)
    ).fetchall()

def db_load_session(conn, sid):
    # Restore cwd
    row = conn.execute("SELECT cwd FROM sessions WHERE id=?", (sid,)).fetchone()
    if row and row[0]:
        try:
            os.chdir(row[0])
        except Exception:
            pass
    rows = conn.execute(
        "SELECT role, content, tool_calls FROM messages WHERE session_id=? ORDER BY id", (sid,)
    ).fetchall()
    msgs = []
    for role, content, tc in rows:
        m = {"role": role, "content": content or ""}
        if tc:
            m["tool_calls"] = json.loads(tc)
        msgs.append(m)
    return msgs

def db_delete_session(conn, sid):
    conn.execute("DELETE FROM messages WHERE session_id=?", (sid,))
    conn.execute("DELETE FROM sessions WHERE id=?", (sid,))
    conn.commit()

# ══════════════════════════════════════════════════════════════════════════════
# API
# ══════════════════════════════════════════════════════════════════════════════
def api_call(cfg, messages, retries=3):
    global SESSION_COST
    fmt = cfg.get("format", "none")
    sys_msg = SYSTEM
    if fmt == "json":
        sys_msg += "\n\nRespond ONLY with valid JSON. No prose, no markdown fences."
    elif fmt == "yaml":
        sys_msg += "\n\nRespond ONLY with valid YAML. No prose, no markdown fences."

    payload = {
        "model":       cfg["model"],
        "messages":    [{"role": "system", "content": sys_msg}] + messages,
        "tools":       get_tool_defs(),
        "tool_choice": "auto",
        "max_tokens":  int(cfg["max_tokens"]),
        "temperature": float(cfg["temperature"]),
    }
    if fmt == "json":
        payload["response_format"] = {"type": "json_object"}

    body = json.dumps(payload).encode()
    url  = cfg["base_url"].rstrip("/") + "/chat/completions"
    last_err = None
    for attempt in range(retries):
        req = Request(url, data=body, headers={
            "Content-Type":  "application/json",
            "Authorization": f"Bearer {cfg['api_key']}",
        })
        try:
            with urlopen(req, timeout=90) as r:
                data = json.loads(r.read())
            # Track cost
            usage = data.get("usage", {})
            inp_tok = usage.get("prompt_tokens", 0)
            out_tok = usage.get("completion_tokens", 0)
            inp_price, out_price = get_pricing(cfg["model"])
            if inp_price is not None:
                SESSION_COST += (inp_tok * inp_price + out_tok * out_price) / 1_000_000
            return data
        except HTTPError as e:
            body_text = e.read().decode(errors="replace")
            if e.code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                wait = 2 ** attempt
                pr(C_D, f"  HTTP {e.code} — retrying in {wait}s…")
                time.sleep(wait)
                last_err = RuntimeError(f"HTTP {e.code}: {body_text}")
                continue
            raise RuntimeError(f"HTTP {e.code}: {body_text}")
    raise last_err

# ══════════════════════════════════════════════════════════════════════════════
# TOKEN ESTIMATION & AUTOCOMPACT
# ══════════════════════════════════════════════════════════════════════════════
AUTOCOMPACT_TOKENS = 200_000

def estimate_tokens(messages):
    """Rough token estimate: chars / 4."""
    total = 0
    for m in messages:
        total += len(m.get("content") or "")
        if m.get("tool_calls"):
            total += len(json.dumps(m["tool_calls"]))
    return total // 4

def maybe_autocompact(cfg, conn, sid, messages):
    tokens = estimate_tokens(messages)
    if tokens < AUTOCOMPACT_TOKENS:
        return messages
    pr(C_D, f"  ⚡ Context ~{tokens//1000}k tokens — auto-compacting…")
    summary_req = (
        "Summarize this conversation into a dense bullet-point recap. "
        "Preserve: all decisions, code written, file paths, errors, and next steps. "
        "Output only the summary, no preamble."
    )
    try:
        resp = api_call(cfg, messages + [{"role": "user", "content": summary_req}])
        summary = resp["choices"][0]["message"].get("content", "")
        new_msgs = [{"role": "assistant", "content": f"[Auto-compacted context]\n{summary}"}]
        db_save_msg(conn, sid, "assistant", f"[Auto-compacted context]\n{summary}")
        pr(C_I, f"  ✓ Compacted → ~{estimate_tokens(new_msgs)} tokens")
        return new_msgs
    except Exception as e:
        pr(C_E, f"  Compact failed: {e}")
        return messages

# ══════════════════════════════════════════════════════════════════════════════
# AGENT LOOP  (the core agentic engine)
# ══════════════════════════════════════════════════════════════════════════════
MAX_ITERS = 32  # max tool-call rounds per user message

def agent_loop(cfg, conn, sid, messages, user_msg):
    messages.append({"role": "user", "content": user_msg})
    db_save_msg(conn, sid, "user", user_msg)

    for iteration in range(MAX_ITERS):
        # Show spinner
        pr(C_D, f"  ↻ step {iteration + 1}…", end="\r")

        try:
            resp = api_call(cfg, messages)
        except RuntimeError as e:
            clear_line()
            pr(C_E, f"API error: {e}")
            return messages

        clear_line()

        # Context window usage warning
        tokens = estimate_tokens(messages)
        ctx_window = get_context_window(cfg["model"])
        if ctx_window:
            pct = int(tokens / ctx_window * 100)
            if pct >= 90:
                pr(C_E, f"  ⚠  {pct}% of {ctx_window//1000}k context used — compact soon")
            elif pct >= 75:
                pr(C_T, f"  ⚠  {pct}% of {ctx_window//1000}k context used")

        choice  = resp["choices"][0]
        msg     = choice["message"]
        text    = msg.get("content") or ""
        tcalls  = msg.get("tool_calls")

        # Persist assistant turn
        asst_entry = {"role": "assistant", "content": text}
        if tcalls:
            asst_entry["tool_calls"] = tcalls
        messages.append(asst_entry)
        db_save_msg(conn, sid, "assistant", text, tcalls)

        # Print text portion
        if text:
            print()
            pr(C_A, f"◆ {text}")

        # Done if no tool calls
        if not tcalls:
            if not text:
                pr(C_D, "  (empty response)")
            break

        # ── Execute tool calls ──
        for tc in tcalls:
            fn   = tc["function"]
            name = fn["name"]
            args = fn.get("arguments", "{}")

            # Show invocation
            args_display = args if len(args) <= 500 else args[:497] + "…"
            pr(C_T, f"\n  ⚙  {name}({args_display})")

            result = dispatch_tool(name, args)

            # Show truncated result
            result_display = str(result)
            if len(result_display) > 2000:
                result_display = result_display[:1997] + "…"
            pr(C_D, f"  →  {result_display}")

            # Feed result back
            tool_msg = {
                "role":        "tool",
                "tool_call_id": tc["id"],
                "content":     str(result),
            }
            messages.append(tool_msg)
            db_save_msg(conn, sid, "tool", str(result))

    else:
        pr(C_E, f"  Reached max iterations ({MAX_ITERS}). Stopping.")

    return messages

# ══════════════════════════════════════════════════════════════════════════════
# CONFIG HELPERS
# ══════════════════════════════════════════════════════════════════════════════
def load_cfg():
    cfg = json.loads(json.dumps(DEFAULT_CFG))  # deep copy — avoids sharing nested dicts
    if os.path.exists(CFG_PATH):
        try:
            with open(CFG_PATH) as f:
                cfg.update(json.load(f))
        except Exception:
            pass
    # Env overrides
    for env in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        val = os.getenv(env)
        if val:
            cfg["api_key"] = val
            break
    return cfg

def save_cfg(cfg):
    with open(CFG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)

# ══════════════════════════════════════════════════════════════════════════════
# SLASH COMMANDS
# ══════════════════════════════════════════════════════════════════════════════
HELP = f"""
{BOLD}ashell-code — slash commands:{R}

  {C_U}/help{R}                   This message
  {C_U}/config{R}                 Show current config
  {C_U}/config key=value{R}       Set a config value
  {C_U}/model <name>{R}           Switch model
  {C_U}/url <base_url>{R}         Switch API endpoint
  {C_U}/new [name]{R}             Start new session
  {C_U}/sessions{R}               List recent sessions
  {C_U}/load <id>{R}              Load a past session
  {C_U}/delete <id>{R}            Delete a session
  {C_U}/clear{R}                  Clear context (keep session)
  {C_U}/context{R}                Show messages, tokens, cost
  {C_U}/format [json|yaml|none]{R} Set structured output mode
  {C_U}/export [filename]{R}      Export session to .md
  {C_U}/system{R}                 Show current system prompt
  {C_U}/system <text>{R}          Set system prompt
  {C_U}/system reset{R}           Restore default system prompt
  {C_U}/pick [dir]{R}             Interactive file picker → inject into context
  {C_U}/allowlist{R}              List allowlist entries
  {C_U}/allowlist add <entry>{R}  Add to allowlist
  {C_U}/allowlist rm <entry>{R}   Remove from allowlist
  {C_U}/mcp add <n> <url>{R}      Connect MCP server
  {C_U}/mcp list{R}               List connected servers
  {C_U}/mcp remove <n>{R}         Disconnect server
  {C_U}/mcp tools <n>{R}          List server's tools
  {C_U}/plugins{R}                List loaded plugins
  {C_U}/read <path>{R}            Inject file into context
  {C_U}/run <cmd>{R}              Run command, inject output
  {C_U}/ls [path]{R}              List directory
  {C_U}/search <pattern>{R}       Ripgrep search
  {C_U}/cd <path>{R}              Change working directory
  {C_U}/pwd{R}                    Print working directory
  {C_U}/exit{R}                   Quit

{C_D}Tip: export OPENAI_API_KEY=... in your shell profile to skip /config{R}
"""

def cmd_config(cfg, args):
    if not args:
        pr(C_I, "Current config:")
        for k, v in cfg.items():
            display = "***" if k == "api_key" and v else v
            print(f"    {k} = {display}")
    else:
        try:
            k, v = args.split("=", 1)
            k, v = k.strip(), v.strip()
            if k not in cfg:
                pr(C_E, f"Unknown key '{k}'. Keys: {', '.join(cfg.keys())}")
                return
            # Type-preserve
            orig = cfg[k]
            cfg[k] = type(orig)(v) if not isinstance(orig, str) else v
            save_cfg(cfg)
            pr(C_I, f"✓ {k} = {'***' if k=='api_key' else v}")
        except ValueError:
            pr(C_E, "Usage: /config key=value")


def cmd_allowlist(arg):
    global ALLOWLIST
    parts = arg.strip().split(None, 1)
    sub   = parts[0].lower() if parts else ""
    val   = parts[1].strip() if len(parts) > 1 else ""

    if not sub or sub == "list":
        if not ALLOWLIST:
            pr(C_D, "  Allowlist is empty.")
        else:
            pr(C_I, "Allowlist entries:")
            for i, e in enumerate(ALLOWLIST):
                print(f"    [{i}] {e}")

    elif sub == "add" and val:
        if val not in ALLOWLIST:
            ALLOWLIST.append(val)
            save_allowlist(ALLOWLIST)
            pr(C_I, f"  Added: {val}")
        else:
            pr(C_D, f"  Already present: {val}")

    elif sub in ("rm", "remove", "del"):
        # Accept index or value
        try:
            idx = int(val)
            removed = ALLOWLIST.pop(idx)
            save_allowlist(ALLOWLIST)
            pr(C_I, f"  Removed [{idx}]: {removed}")
        except (ValueError, IndexError):
            if val in ALLOWLIST:
                ALLOWLIST.remove(val)
                save_allowlist(ALLOWLIST)
                pr(C_I, f"  Removed: {val}")
            else:
                pr(C_E, f"  Not found: {val}")
    else:
        pr(C_I, "Usage: /allowlist [list] | /allowlist add <entry> | /allowlist rm <entry|index>")

def cmd_export(msgs, sid, arg):
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    name = arg.strip() if arg.strip() else f"ashell-export-{ts}.md"
    if not name.endswith(".md"):
        name += ".md"
    path = os.path.expanduser(f"~/Documents/ashell-code/{name}")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    lines = [f"# ashell-code export — session #{sid}\n", f"_{ts}_\n\n---\n"]
    for m in msgs:
        role    = m["role"].upper()
        content = m.get("content") or ""
        if m.get("tool_calls"):
            for tc in m["tool_calls"]:
                fn   = tc["function"]
                content += f"\n\n> ⚙ `{fn['name']}({fn.get('arguments','')[:200]})`"
        lines.append(f"**{role}**\n\n{content}\n\n---\n")
    try:
        with open(path, "w") as f:
            f.write("\n".join(lines))
        pr(C_I, f"  Exported → {path}")
    except Exception as e:
        pr(C_E, f"  Export failed: {e}")

def cmd_system(cfg, arg):
    global SYSTEM
    arg = arg.strip()
    if not arg:
        pr(C_I, "Current system prompt:")
        pr(C_D, SYSTEM)
    elif arg == "reset":
        SYSTEM = DEFAULT_SYSTEM
        cfg["system"] = ""
        save_cfg(cfg)
        pr(C_I, "System prompt reset to default.")
    else:
        SYSTEM = arg
        cfg["system"] = arg
        save_cfg(cfg)
        pr(C_I, f"System prompt set ({len(arg)} chars)")

def cmd_pick(arg, msgs, conn, sid):
    path = _expand(arg.strip() or ".")
    entries = []
    try:
        for root, dirs, files in os.walk(path):
            dirs[:] = sorted(d for d in dirs if not d.startswith("."))
            rel_root = os.path.relpath(root, path)
            for fname in sorted(files):
                rel = os.path.join(rel_root, fname) if rel_root != "." else fname
                entries.append((rel, os.path.join(root, fname)))
            if len(entries) >= 60:
                break
    except Exception as e:
        pr(C_E, f"  {e}")
        return msgs
    if not entries:
        pr(C_D, "  No files found.")
        return msgs
    pr(C_I, f"Files in {path}:")
    for i, (rel, _) in enumerate(entries):
        print(f"  {C_D}[{i:2d}]{R} {rel}")
    try:
        sel = input(f"  {C_U}Select (number or path): {R}").strip()
    except (KeyboardInterrupt, EOFError):
        print()
        return msgs
    try:
        _, chosen = entries[int(sel)]
    except (ValueError, IndexError):
        chosen = _expand(sel) if sel else None
    if not chosen:
        return msgs
    content = tool_read_file(chosen)
    inject  = f"[File: {chosen}]\n```\n{content}\n```"
    msgs.append({"role": "user", "content": inject})
    db_save_msg(conn, sid, "user", inject)
    pr(C_I, f"Injected {chosen} ({content.count(chr(10)) + 1} lines)")
    return msgs

# ══════════════════════════════════════════════════════════════════════════════
# BANNER
# ══════════════════════════════════════════════════════════════════════════════
BANNER = f"""
{BOLD}{C_A}  ╔══════════════════════════════════════╗
  ║  ashell-code  v1.0                   ║
  ║  agentic coding CLI · a-Shell · iOS  ║
  ╚══════════════════════════════════════╝{R}
  {C_D}OpenAI-compatible endpoint{R}
  Type {C_U}/help{R} for commands · {C_U}/exit{R} to quit · Ctrl+C to interrupt
"""

# ══════════════════════════════════════════════════════════════════════════════
# MAIN REPL
# ══════════════════════════════════════════════════════════════════════════════
def main():
    cfg  = load_cfg()
    global PLUGIN_REGISTRY, ALLOWLIST, SYSTEM, SESSION_COST
    SYSTEM = cfg.get("system") or DEFAULT_SYSTEM
    PLUGIN_REGISTRY = load_plugins()
    ALLOWLIST = load_allowlist()
    for name, url in cfg.get("mcp_servers", {}).items():
        pr(C_D, f"  Reconnecting MCP '{name}'…")
        tools = mcp_discover(url)
        MCP_SERVERS[name] = {"url": url, "tools": tools}
    conn = db_init()
    sid  = db_new_session(conn)
    msgs = []  # current conversation

    print(BANNER)
    pr(C_D, f"  Model:   {cfg['model']}")
    pr(C_D, f"  URL:     {cfg['base_url']}")
    pr(C_D, f"  Session: #{sid}")
    pr(C_D, f"  CWD:     {os.getcwd()}")

    if not cfg["api_key"]:
        pr(C_E, "\n  ⚠  No API key found.")
        pr(C_E, "     Run: /config api_key=YOUR_KEY")
        pr(C_E, "     Or:  export OPENAI_API_KEY=... in your shell profile\n")
    else:
        print()

    while True:
        # Prompt shows cwd basename
        cwd_short = os.path.basename(os.getcwd()) or "/"
        try:
            raw = input(f"{C_U}({cwd_short}) ▶ {R}").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            pr(C_D, "bye.")
            break

        if not raw:
            continue

        # ── Slash commands ──────────────────────────────────────────────────
        if raw.startswith("/"):
            parts = raw[1:].split(" ", 1)
            cmd   = parts[0].lower()
            arg   = parts[1] if len(parts) > 1 else ""

            if cmd in ("exit", "quit", "q"):
                pr(C_D, "bye.")
                break

            elif cmd == "mcp":
                cmd_mcp(arg, cfg)

            elif cmd == "plugins":
                if not PLUGIN_REGISTRY:
                    pr(C_D, "No plugins loaded.")
                for name in PLUGIN_REGISTRY:
                    pr(C_I, f"  · {name}")

            elif cmd == "help":
                print(HELP)

            elif cmd == "config":
                cmd_config(cfg, arg)

            elif cmd == "model":
                if arg:
                    cfg["model"] = arg
                    save_cfg(cfg)
                    pr(C_I, f"Model → {arg}")
                else:
                    pr(C_I, f"Current: {cfg['model']}")

            elif cmd == "url":
                if arg:
                    cfg["base_url"] = arg.rstrip("/")
                    save_cfg(cfg)
                    pr(C_I, f"URL → {cfg['base_url']}")
                else:
                    pr(C_I, cfg["base_url"])

            elif cmd == "new":
                name = arg or None
                sid  = db_new_session(conn, name)
                msgs = []
                SESSION_COST = 0.0
                TOOL_CACHE.clear()
                pr(C_I, f"New session #{sid}" + (f" '{name}'" if name else ""))

            elif cmd == "clear":
                msgs = []
                pr(C_I, "Context cleared.")

            elif cmd == "context":
                tokens = estimate_tokens(msgs)
                ctx_window = get_context_window(cfg["model"])
                if ctx_window:
                    pct = int(tokens / ctx_window * 100)
                    bar = f" ({pct}% of {ctx_window//1000}k ctx window)"
                else:
                    bar = ""
                cost_str = f"  ·  session cost ~${SESSION_COST:.4f}" if SESSION_COST > 0 else ""
                pr(C_I, f"{len(msgs)} messages · ~{tokens:,} tokens{bar}{cost_str}  [session #{sid}]")

            elif cmd == "format":
                arg_lower = arg.strip().lower()
                if arg_lower in ("json", "yaml", "none", ""):
                    mode = arg_lower or "none"
                    cfg["format"] = mode
                    save_cfg(cfg)
                    pr(C_I, f"Format → {mode}")
                else:
                    pr(C_E, "Usage: /format [json|yaml|none]")

            elif cmd == "system":
                cmd_system(cfg, arg)

            elif cmd == "pick":
                msgs = cmd_pick(arg, msgs, conn, sid)

            elif cmd == "export":
                cmd_export(msgs, sid, arg)

            elif cmd == "allowlist":
                cmd_allowlist(arg)

            elif cmd == "sessions":
                rows = db_list_sessions(conn)
                if not rows:
                    pr(C_D, "No sessions yet.")
                else:
                    pr(C_I, "Recent sessions:")
                    for row_id, name, created in rows:
                        marker = " ◀ current" if row_id == sid else ""
                        print(f"    [{row_id:3d}] {name}  {C_D}{created[:16]}{R}{C_A}{marker}{R}")

            elif cmd == "load":
                try:
                    target = int(arg)
                    loaded = db_load_session(conn, target)
                    msgs   = loaded
                    sid    = target
                    pr(C_I, f"Loaded session #{target} — {len(msgs)} messages")
                except (ValueError, TypeError):
                    pr(C_E, "Usage: /load <session_id>")

            elif cmd == "delete":
                try:
                    target = int(arg)
                    db_delete_session(conn, target)
                    if target == sid:
                        sid  = db_new_session(conn)
                        msgs = []
                        pr(C_I, f"Deleted current session. New session #{sid}")
                    else:
                        pr(C_I, f"Deleted session #{target}")
                except (ValueError, TypeError):
                    pr(C_E, "Usage: /delete <session_id>")

            elif cmd == "read":
                if not arg:
                    pr(C_E, "Usage: /read <path>")
                else:
                    content = tool_read_file(arg)
                    inject  = f"[File: {arg}]\n```\n{content}\n```"
                    msgs.append({"role": "user", "content": inject})
                    db_save_msg(conn, sid, "user", inject)
                    lines = content.count("\n") + 1
                    pr(C_I, f"Injected {arg} ({lines} lines)")

            elif cmd == "run":
                if not arg:
                    pr(C_E, "Usage: /run <command>")
                else:
                    out    = tool_run_command(arg, allowlist=ALLOWLIST)
                    inject = f"[Command: {arg}]\n```\n{out}\n```"
                    msgs.append({"role": "user", "content": inject})
                    db_save_msg(conn, sid, "user", inject)
                    pr(C_D, out[:5000])

            elif cmd == "ls":
                print(tool_list_files(arg or "."))

            elif cmd == "search":
                if not arg:
                    pr(C_E, "Usage: /search <pattern>")
                else:
                    print(tool_search_files(arg))

            elif cmd == "cd":
                try:
                    os.chdir(_expand(arg))
                    db_update_cwd(conn, sid)
                    pr(C_I, f"→ {os.getcwd()}")
                except Exception as e:
                    pr(C_E, f"cd: {e}")

            elif cmd == "pwd":
                print(os.getcwd())

            else:
                pr(C_E, f"Unknown command: /{cmd}  (try /help)")

            continue

        # ── Agent turn ──────────────────────────────────────────────────────
        if not cfg["api_key"]:
            pr(C_E, "No API key. Run: /config api_key=YOUR_KEY")
            continue

        try:
            msgs = agent_loop(cfg, conn, sid, msgs, raw)
            db_update_cwd(conn, sid)
            msgs = maybe_autocompact(cfg, conn, sid, msgs)
        except KeyboardInterrupt:
            print()
            pr(C_D, "  Interrupted.")
        except Exception as e:
            pr(C_E, f"Error: {e}")

    conn.close()

if __name__ == "__main__":
    main()
