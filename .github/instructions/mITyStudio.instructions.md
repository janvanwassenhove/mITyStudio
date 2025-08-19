---
applyTo: '**'
---
Follow established coding standards, domain knowledge, and project preferences at all times.
If you create temporary test scripts for validation purposes, ensure they are removed after use.
By default use terminal commands instead of powershell commands.
If you need to use powershell, ensure it is removed after use.
Avoid large code files (> 500 lines) and instead break them into smaller, manageable components.
Don't create documentation files unless specifically requested (always add them in 'docs' directory).
When adding text or messages, ensure they are translated into all supported languages.
When testing with langchain & langgraph integrations in code, don't use the most expensive models like `gpt-4o` or `gpt-4o-mini` or `claude-sonnet-4` unless specifically requested.
When wrapping up, ensure all resources are released and any temporary files are deleted.
All functionality should be thoroughly tested and validated before deployment, including edge cases and error handling. Tests should be automated where possible and cover a range of scenarios to ensure robustness and stored in the appropriate test directory (depending project and programming language).
In GUI, don't create alert messages to display info, instead use dialogs aligned with style guidelines project.