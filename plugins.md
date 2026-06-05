# Plugins
Plugins are loaded on shellclaude start. They can be accessed in Documents/shellclaude/plugins
## Template 
```
# ~/Documents/shellclaude/plugins/my_tool.py

TOOL_DEF = {
    "type": "function",
    "function": {
        "name": "my_custom_tool",           # ← must be unique
        "description": "Does something useful. Be very clear in the description.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What to search for"},
                "count": {"type": "integer", "description": "Number of results", "default": 5}
            },
            "required": ["query"]
        }
    }
}

def run(args: dict) -> str:
    """This function will be called when the model uses the tool."""
    query = args.get("query", "")
    count = args.get("count", 5)
    
    # Your logic here
    result = f"Processed query: {query} (showing {count} results)"
    
    return result
```

## Rules
•  Must define TOOL_DEF and run(args: dict) -> str

•  Filename must end in .py and not start with _

•  Placed in ~/Documents/shellclaude/plugins/