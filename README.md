# ashell-code
AI coding CLI for iOS app a-Shell

# DISCLAIMER
THIS PYTHON CLI IS STILL IN A *VERY* PRIMITIVE STATE. 

# Features
•  Full agentic tool use: read_file, write_file, run_command, list_files, search_files (ripgrep), patch_file

•  Persistent SQLite sessions with /new, /load, /sessions, /delete, and auto cwd restore

•  Session export to markdown (/export)

•  iOS Keychain secure API key storage (/keychain set)

•  Permission system + persistent allowlist for commands and file writes

•  Colored unified diffs shown before every file modification

•  Auto context compaction at 200k tokens (for now)

•  Real-time session cost tracking (model-specific pricing)

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