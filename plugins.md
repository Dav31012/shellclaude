# Plugins
Plugins are loaded on shellclaude start. They can be accessed in Documents/shellclaude/plugins
## Template 
```
TOOL_DEF = {
    "type": "function",
    "function": {
        "name": "search_npm",                     # unique name
        "description": "Search for npm packages",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Package name or keyword"}
            },
            "required": ["query"]
        }
    }
}

def run(args: dict) -> str:
    query = args.get("query", "")
    # your code here
    return f"Found packages matching '{query}'..."
```

## Rules
•  Must define TOOL_DEF and run(args: dict) -> str
•  Filename must end in .py and not start with _
•  Placed in ~/Documents/shellclaude/plugins/