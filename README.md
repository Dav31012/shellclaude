# shellclaude
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.13-blue.svg)](https://www.python.org)
![Platform](https://img.shields.io/badge/Platform-iOS%20%2F%20iPadOS-brightgreen)

AI coding CLI for a-Shell, written in python. Supports OpenAI and anthropic endpoints.

# DISCLAIMER
Good readme conming soon.
If you havent guessed im looking for feedback :)

# Quick start

I recommend installing rich for better UI
```
pip install rich
curl -L https://raw.githubusercontent.com/dav31012/shellclaude/main/shellclaude.py -o shellclaude.py
shellclaude.py
```

# Features
• Full agentic tool use: `read_file`, `write_file`, `run_command`, `list_files`, `search_files` (ripgrep), `patch_file`, `web_search`

• Persistent SQLite sessions with `/new`, `/load`, `/sessions`, `/delete` and auto cwd restore

• Streaming responses with Rich UI (live markdown + syntax highlighting) + ANSI fallback

• Colored unified diffs + automatic backups before file writes

• Permission system + persistent allowlist for commands and file operations

• AGENTS.md auto-discovery from project directory

• Plugin system + MCP (Model Context Protocol) support

• Interactive file picker (`/pick`)

• Session branching, tagging, and export to markdown

• Auto context compaction + real-time cost tracking

• Strong protected paths (prevents self-modification)

• iOS-specific error hints and soft cancel support

# Plugins

Plugin template details in plugin.md

# Security Concerns

•  Filesystem access: agent can read and write almost any file in a-Shell’s sandbox

•  Plugin system auto-executes arbitrary Python code from ~/Documents/shellclaude/plugins

•  MCP servers allow connecting to external (potentially malicious) tool servers

•  Persistent shellclaude.db stores full conversation history, including sensitive file contents and command outputs

•  API key can fall back to plaintext JSON if Keychain fails or is not used

•  Allowlist “always” entries can grant broad command permissions

•  No automatic secret redaction in tool outputs sent back to the model

•  Path validation exists but is not perfect (symlinks and edge cases possible)

•  iOS sandbox is the main containment — agent cannot escape a-Shell

# Use at your own risk. This tool intentionally gives powerful access to the LLM.

## Legal Disclaimer
This CLI is an independent, open-source project and is not affiliated, 
associated, authorized, endorsed by, or in any way officially connected 
with Anthropic PBC. 

"Claude" and "Anthropic" are registered trademarks of Anthropic PBC. 
This tool acts solely as a local interface utilizing the official Anthropic API 
endpoints. Users are bound by Anthropic's Terms of Service and API consumer 
agreements when using this software. The software is provided "as is", 
without warranty of any kind.
