# shellclaude
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.13-blue.svg)](https://www.python.org)
![Platform](https://img.shields.io/badge/Platform-iOS%20%2F%20iPadOS-brightgreen)

Terminal coding tool for [a-Shell](https://github.com/holzschu/a-Shell) on iOS. Supports OpenAI, Anthropic, and compatible endpoints.

```
shellclaude v1.5.0
```

## Quick start

```bash
pip install rich
# openai type endpoint
export OPENAI_API_KEY=
#anthropic endpoint
export ANTHROPIC_API_KEY=
shellclaude.py
```

First run sets up your model and endpoint. Settings save to `~/Documents/shellclaude.json`.

## Tools

shellclaude exposes these to the model:

- **read_file** — read code or configs, with line ranges for big files
- **write_file** — create or overwrite files (shows diff first, makes .bak)
- **patch_file** — surgical edits, preferred over write_file for changes
- **run_command** — shell commands, 30s timeout, pipes blocked for safety
- **search_files** — ripgrep across your project, respects .gitignore
- **list_files** — directory listing, recursive capped at 3000 entries
- **web_search** — DuckDuckGo search
- **read_url** — fetch docs or GitHub raw files, strips HTML
- **run_python** — Python 3 snippets with traceback parsing
- **run_node** — JavaScript via Node.js
- **run_rust** — cargo check/build/test/clippy with error highlighting

Cancel a running turn with `c` + Enter.

## Commands

### Setup
| Command | What it does |
|---------|--------------|
| `/config [key=val]` | Show or change settings |
| `/model <name>` | Switch model |
| `/url <base_url>` | Set API URL (OpenAI mode) |
| `/endpoint [openai\|anthropic]` | Switch provider |
| `/stream [on\|off]` | Toggle streaming |
| `/debug [on\|off]` | Print full API traffic |

### Sessions
| Command | What it does |
|---------|--------------|
| `/new [name]` | New session |
| `/sessions` | List past sessions |
| `/load <id>` | Load a session |
| `/delete <id>` | Delete one |
| `/clear` | Wipe context, keep session |
| `/compact` | Force context summarization |
| `/context` | Show tokens, cost, usage bar |
| `/branch [name]` | Branch from current session |
| `/tag [id tags]` | Tag for searching |
| `/export [file]` | Save as Markdown |

### Context control
| Command | What it does |
|---------|--------------|
| `/rewind [N]` | Drop last N turns |
| `/forget <N>` | Drop last N messages |
| `/pin [index]` | Pin a message (survives compaction) |
| `/unpin <index>` | Unpin |
| `/import <sid> <idx...>` | Copy messages between sessions |

### Tools
| Command | What it does |
|---------|--------------|
| `/websearch <query>` | Search, inject results |
| `/browse <url>` | Fetch page, inject text |
| `/read <path>` | Inject file into chat |
| `/run <cmd>` | Run command, inject output |
| `/ls [path]` | List directory |
| `/search <pattern>` | Ripgrep search |
| `/cd <path>` | Change directory |
| `/pwd` | Current directory |

### System
| Command | What it does |
|---------|--------------|
| `/system [text]` | View or set system prompt |
| `/system save <name>` | Save prompt as template |
| `/system load <name>` | Load template |
| `/system list` | List templates |
| `/system reset` | Restore default prompt |
| `/agents [reload]` | Show or reload AGENTS.md |
| `/pick [dir]` | iOS file picker, inject selection |
| `/format [json\|yaml\|none]` | Structured output mode |

### Safety
| Command | What it does |
|---------|--------------|
| `/safe [on\|off]` | Confirm every tool call |
| `/diff [on\|off]` | Dry-run mode: show diffs, don't write |
| `/budget <N>\|off` | Limit iterations this turn |
| `/thinking-budget <N>\|off` | Anthropic extended thinking |
| `/allowlist [add\|rm]` | Manage command allowlist |

### Git
| Command | What it does |
|---------|--------------|
| `/git [s\|d\|l\|commit...]` | Shortcuts: status, diff, log, commit |

### Project smarts
| Command | What it does |
|---------|--------------|
| `/scope` | Detect project type (Cargo.toml, package.json, etc.) |
| `/scope inject` | Inject project info into context |

### Developer helpers
| Command | What it does |
|---------|--------------|
| `/clip` | Copy last AI response to clipboard |
| `/save <name>` | Save last response as snippet |
| `/persona <name>` | Switch persona file |
| `/persona list` | List personas |
| `/persona reset` | Restore default system prompt |
| `/skills [reload\|<name>]` | Load SKILL.md guides |
| `/trail [clear]` | View edit history |
| `/undo` | Revert last file write |
| `/edit --revert <path>` | Restore from .bak |
| `/cache [list\|clear]` | Tool result cache |

### MCP and plugins
| Command | What it does |
|---------|--------------|
| `/mcp add <name> <url>` | Connect MCP server |
| `/mcp list` | List servers |
| `/mcp remove <name>` | Disconnect |
| `/mcp tools <name>` | List server tools |
| `/plugins` | List loaded plugins |

### Help and exit
| Command | What it does |
|---------|--------------|
| `/help` | Show all commands |
| `/exit` | Quit |

## Key features

### Phase labels
Tool calls get colored labels: gathering, acting, verifying. You know what the model is doing at a glance.

### Context management
- **Auto-compaction**: Old messages summarize automatically when you approach the model's context limit (~80%)
- **Pinned messages**: `/pin` marks context that survives compaction
- **Cost tracking**: Running dollar total per session
- **Context bar**: Token usage as a visual percentage

### Project detection
Auto-detects Cargo.toml, package.json, pyproject.toml, go.mod, and others. Pulls out name, version, scripts. Inject with `/scope inject`.

### AGENTS.md
Drop an `AGENTS.md` in your project root. shellclaude finds it up the directory tree, loads it, and appends the rules to the system prompt. Capped at 8000 chars. Checks for injection patterns. Reloads on directory change.

### Security
- **SSRF protection**: Blocks private IPs and metadata endpoints in URL fetching
- **Sensitive files**: Blocks reads of .env, .pem, credentials, SSH keys
- **Safe mode**: Every tool call needs confirmation
- **Diff mode**: Preview changes without writing
- **Allowlist**: Auto-approve trusted commands with prefix wildcards (`cargo *`)
- **Symlink checks**: Warns if config resolves outside ~/Documents
- **Blocked patterns**: 31 dangerous constructs (rm -rf /, sudo, credential exfiltration, etc.)
- **a-Shell safety**: Pipes, command substitution, background jobs, and here-strings are blocked. These hang a-Shell permanently because it runs everything in a single process.

### Session persistence
SQLite at `~/Documents/shellclaude.db`:
- Full message history
- Working directory restoration
- Branching and tagging
- Pinned message preservation
- Per-message cost tracking

## iOS specifics

- **Sandboxed**: Write only to `~/Documents`, `~/Library`, `~/tmp`
- **Python 3.13** built in. Use `python3`, never `python`
- **Packages**: `pkg install <name>` for WASM commands
- **No bash**: POSIX `sh` only
- **No pipes**: Single-process architecture
- **BSD tools**: `sed -i ''`, `grep -E`, `date -v` — not GNU
- **C/C++**: Compiles to WASM via `clang`. No sockets, no fork
- **Git**: Uses `lg2` (libgit2 wrapper)

## Config

```json
{
  "api_key": "",
  "base_url": "https://api.openai.com/v1",
  "model": "gpt-4o",
  "max_tokens": 8192,
  "temperature": 0.8,
  "system": "",
  "format": "none",
  "stream": true,
  "endpoint_type": "openai",
  "plugins_enabled": true,
  "mcp_servers": {}
}
```

Priority: `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` env vars beat config file. Env keys never get written to disk.

## Directory layout

```
~/Documents/shellclaude/
├── shellclaude.json      # Config
├── shellclaude.db        # Session database
├── allowlist.txt         # Command allowlist
├── plugins/              # Python plugin files
├── snippets/             # Saved responses
├── personas/             # Persona .md files
└── skills/               # SKILL.md guides
```

## Plugins

Drop Python files in `~/Documents/shellclaude/plugins/`. Each needs:

```python
TOOL_DEF = {
    "type": "function",
    "function": {
        "name": "my_tool",
        "description": "...",
        "parameters": {"type": "object", "properties": {...}}
    }
}

def run(args: dict) -> str:
    return "result"
```

## Skills

Create `~/Documents/shellclaude/skills/<name>/SKILL.md`. Content gets injected into the system prompt under `## Skills`.

## Personas

Drop `.md` files in `~/Documents/shellclaude/personas/`. Switch with `/persona <name>`.

## Security notes

- **API keys**: Config stores plaintext. On iOS this may sync to iCloud. Use env vars instead.
- **Plugins**: Run with full Python stdlib access. Only install what you trust.
- **MCP servers**: Your conversation goes to the server. Use HTTPS only.
- **History**: `shellclaude.db` stores everything unencrypted.
- **Secrets**: No automatic redaction. Don't paste credentials into chat.
- **Paths**: Protected paths stop self-modification, but symlink edge cases might exist.

## Requirements

- a-Shell on iOS (or any POSIX terminal)
- Python 3.13+
- `rich` (optional, for colors)
- API key for OpenAI, Anthropic, or compatible endpoint

## License

MIT

