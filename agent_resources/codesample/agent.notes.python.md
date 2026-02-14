### Important Tips

Agent Framework supports various implementation patterns. These are quite useful tips to ensure stability and avoid common errors:

- Two Foundry/Azure client options: Use `AzureAIClient` (recommended) for Foundry project endpoints with full agent management. Use `AzureOpenAIChatClient` for Azure OpenAI endpoints directly. Note: `AzureAIClient` requires async credential from `azure.identity.aio`, while `AzureOpenAIChatClient` uses sync credential from `azure.identity`.
- Agent instance can be created via either `client.create_agent(...)` method or `ChatAgent(...)` constructor.
- If using `AzureAIClient` to create Foundry agent, the agent name "must start and end with alphanumeric characters, can contain hyphens in the middle, and must not exceed 63 characters". E.g., good names: ["SampleAgent", "agent-1", "myagent"], and bad names: ["-agent", "agent-", "sample_agent"].
- When using MCP tools for tools only (without prompts), explicitly set `load_prompts=False` on `MCPStdioTool` or `MCPStreamableHTTPTool`. Default is `load_prompts=True`.
