# shellclaude
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.13-blue.svg)](https://www.python.org)
![Platform](https://img.shields.io/badge/Platform-iOS%20%2F%20iPadOS-brightgreen)

AI coding CLI for iOS app a-Shell, written in python. 

# DISCLAIMER
THIS PYTHON CLI IS STILL IN A *VERY* PRIMITIVE STATE. If you havent guessed im looking for feedback :)

# Features
•  Full agentic tool use: read_file, write_file, run_command, list_files, search_files (ripgrep), patch_file and web_search

•  Persistent SQLite sessions with /new, /load, /sessions, /delete, and auto cwd restore

•  Session export to markdown (/export)

•  Permission system + persistent allowlist for commands and file writes

•  Colored unified diffs shown before every file modification

•  Auto context compaction at 200k tokens (for now)

•  Real-time session cost tracking (model-specific pricing, very inaccurate)

•  Full plugin system with auto-discovery

•  MCP server support (connect external tool servers)

•  Interactive file picker (/pick)

•  Direct file and command injection (/read, /run)

•  Custom system prompt with /system

•  Output format modes: JSON, YAML, or none

•  Runtime config switching (/model, /url, /config)

•  Protected paths (prevents self-modification of config, db, and plugins)

•  iCloud sync warnings

•  Single-file Python script

# Security Concerns
•  Full shell command execution via run_command (shell=True) — can run arbitrary commands if approved

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
