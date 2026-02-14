### Microsoft Agent Framework code samples (Python)

#### Quick Start
Connect foundry model and reference/create agent using `AzureAIClient`.
(There was legacy(v1) `AzureAIAgentClient` in previous versions, now should use the new(v2) `AzureAIClient`)

``` python
from agent_framework.azure import AzureAIClient
from azure.identity.aio import DefaultAzureCredential

async def quick_start() -> None:
    # The named agent will be automatically created if it does not exist
    async with (
        DefaultAzureCredential() as credential,
        AzureAIClient(
            project_endpoint="<your-foundry-project-endpoint>",
            model_deployment_name="<your-foundry-model-deployment>",
            credential=credential,
        ).create_agent(
            name="MyAgent",
            instructions="You are a helpful agent.",
        ) as agent,
    ):
        # use run_stream for best practice and production-grade app
        print("Agent: ", end="", flush=True)
        async for chunk in agent.run_stream("hello"):
            if chunk.text:
                print(chunk.text, end="", flush=True)
        print("\n")
        # Agent: Hello! How can I assist you today?
        # or, use run for testing
        # result = await agent.run("hello")
        # print(f"Agent: {result.text}") # Agent: Hello! How can I assist you today?
```

#### Alternative: Using AzureOpenAIChatClient
For scenarios using Azure OpenAI endpoints directly (instead of Foundry project endpoints):

``` python
from agent_framework.azure import AzureOpenAIChatClient
from azure.identity import DefaultAzureCredential

async def quick_start_aoai() -> None:
    # Azure OpenAI Configuration (different from Foundry project endpoint)
    credential = DefaultAzureCredential()
    async with (
        AzureOpenAIChatClient(
            endpoint="<your-azure-openai-endpoint>",
            deployment_name="<your-deployment-name>",
            credential=credential,
        ).create_agent(
            name="MyAgent",
            instructions="You are a helpful agent.",
        ) as agent,
    ):
        print("Agent: ", end="", flush=True)
        async for chunk in agent.run_stream("hello"):
            if chunk.text:
                print(chunk.text, end="", flush=True)
        print("\n")
```

**Note**: Tool, MCP, and thread patterns work the same as shown in sections below.

#### Add tool
Tools (or Function Callings) can let Agent interact with external APIs or services, enhancing its capabilities.

``` python
from random import randint
from typing import Annotated

# Define tool(s) and add to 'ChatAgent'
def get_weather(
    location: Annotated[str, "The location to get the weather for."],
) -> str:
    """Get the weather for a given location."""
    conditions = ["sunny", "cloudy", "rainy", "stormy"]
    return f"The weather in {location} is {conditions[randint(0, 3)]} with a high of {randint(10, 30)}°C."

async def quick_start_tools() -> None:
    #...
    async with (
        DefaultAzureCredential() as credential,
        AzureAIClient(
            project_endpoint="<your-foundry-project-endpoint>",
            model_deployment_name="<your-foundry-model-deployment>",
            credential=credential,
        ).create_agent(
            name="MyAgent",
            instructions="You are a helpful agent.",
            tools=[get_weather],
        ) as agent,
    ):
        print("Agent: ", end="", flush=True)
        async for chunk in agent.run_stream("What's the weather like in Seattle?"):
            if chunk.text:
                print(chunk.text, end="", flush=True)
        print("\n")
        # Agent: The weather in Seattle is rainy with a high of 18°C.
```

#### Multi-turn Conversation with Thread
Thread persistence across multiple conversations.
Here uses the default in-memory store; For more scenarios like reusing server-side conversation or other persistent stores, search agent-framework source repo for more samples.

``` python
async def quick_start_thread() -> None:
    #...
    async with (
        ...(
            ...
        ) as agent,
    ):
        # Create a new thread that will be reused
        thread = agent.get_new_thread()

        # First conversation
        print("Agent: ", end="", flush=True)
        async for chunk in agent.run_stream("What's the weather like in Seattle?", thread=thread):
            if chunk.text:
                print(chunk.text, end="", flush=True)
        print("\n")
        # Agent: The weather in Seattle is rainy with a high of 18°C.

        # Second conversation using the same thread - maintains context
        print("Agent: ", end="", flush=True)
        async for chunk in agent.run_stream("Pardon?", thread=thread):
            if chunk.text:
                print(chunk.text, end="", flush=True)
        print("\n")
        # Agent: Sure. The weather in Seattle is rainy with a high of 18°C.

        # or, for testing
        # result = await agent.run("Pardon?", thread=thread)
        # print(f"Agent: {result.text}") # Agent: Sure. The weather in Seattle is rainy with a high of 18°C.
```

#### Model Context Protocol (MCP) tools
Connect with MCP tools

```python
from agent_framework import MCPStdioTool, ToolProtocol, MCPStreamableHTTPTool
from typing import Any

def create_mcp_tools() -> list[ToolProtocol | Any]:
    return [
        # stdio sample - playwright
        MCPStdioTool(
            name="Playwright MCP",
            description="provides browser automation capabilities using Playwright",
            command="npx",
            args=[
                "-y",
                "@playwright/mcp@latest",
            ],
            load_prompts=False # False if using tools only (MCP may not implement prompts)
        ),
        # streamable http sample - microsoft learn
        MCPStreamableHTTPTool(
            name="Microsoft Learn MCP",
            description="bring trusted and up-to-date information directly from Microsoft's official documentation",
            url="https://learn.microsoft.com/api/mcp",
            load_prompts=False # False if using tools only (MCP may not implement prompts)
        )
    ]

async def quick_start_mcp() -> None:
    #...
    async with (
        ...(
            ...,
            tools=create_mcp_tools(), # use MCP tools
        ) as agent,
    ):
        #...
        thread = agent.get_new_thread()
        async for chunk in agent.run_stream(USER_INPUTS, thread=thread):
            if chunk.text:
                print(chunk.text, end="", flush=True)
            elif chunk.raw_representation and chunk.raw_representation.raw_representation:
                event = chunk.raw_representation.raw_representation
                if (hasattr(event, 'type') 
                    and event.type == 'response.output_item.done' 
                    and hasattr(event, 'item') 
                    and hasattr(event.item, 'name')):
                    args = getattr(event.item, 'arguments', None)
                    status = getattr(event.item, 'status', None)
                    print(f"\n[Tool: {event.item.name}] args={args} status={status}")
        print("")
```
