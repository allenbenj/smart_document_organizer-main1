### Important Tips

Agent Framework supports various implementation patterns. These are quite useful tips to ensure stability and avoid common errors:

- Two Foundry/Azure client options: Use `AzureAIClient` (recommended) for Foundry project endpoints with full agent management. Use `AzureOpenAIChatClient` for Azure OpenAI endpoints directly. Note: `AzureAIClient` requires async credential from `azure.identity.aio`, while `AzureOpenAIChatClient` uses sync credential from `azure.identity`.
- Agent instance can be created via either `client.create_agent(...)` method or `ChatAgent(...)` constructor.
- There are several ways to define workflow's node,
  - directly use agent, like `client.create_agent(name="...", ...)` or `ChatAgent(name="...", ...)` (must provide `name` for further workflow reference)
  - function-based executor decorator, like
    ```python
    @executor(id="my_executor")
    async def my_func(text: str, ctx: WorkflowContext[Never, str]) -> None:
    ```
  - subclassing `Executor` (not `AgentExecutor`) with custom handlers, like
    ```python
    class MyExecutor(Executor):
        def __init__(self, id: str):
            super().__init__(id=id)

        @handler
        async def my_handler(self, text: str, ctx: WorkflowContext[str]) -> None:
            result = text.upper()
            await ctx.send_message(result)
    ```
  - wrapping via `AgentExecutor` (not subclassing), like `AgentExecutor(agent=..., id="...")`
- If using `AzureAIClient` to create Foundry agent, the agent name "must start and end with alphanumeric characters, can contain hyphens in the middle, and must not exceed 63 characters". E.g., good names: ["SampleAgent", "agent-1", "myagent"], and bad names: ["-agent", "agent-", "sample_agent"].
- In workflow, the previous node's output could be next node's input, so carefully check those types, especially when nodes are defined in different ways.
