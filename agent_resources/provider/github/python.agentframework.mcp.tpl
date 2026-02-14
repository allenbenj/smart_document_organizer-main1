"""Build Agent using Microsoft Agent Framework in Python
# Run this python script
> pip install anthropic agent-framework==1.0.0b260107
> python <this-script-path>.py
"""

import asyncio
import os

from agent_framework import MCPStdioTool, MCPStreamableHTTPTool, ToolProtocol, FunctionCallContent
from agent_framework.openai import OpenAIChatClient
from agent_framework.anthropic import AnthropicClient
from anthropic import AsyncAnthropicFoundry
from openai import AsyncOpenAI

# To authenticate with the model you will need to generate a personal access token (PAT) in your GitHub settings.
# Create your PAT token by following instructions here: https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens
openaiClient = AsyncOpenAI(
    base_url = "https://models.github.ai/inference",
    api_key = os.environ["GITHUB_TOKEN"],
{{#api_version}}
    default_query = {
        "api-version": "{{api_version}}",
    },
{{/api_version}}
)

AGENT_NAME = "ai-agent"
{{#parameters.systemWithQuote}}
AGENT_INSTRUCTIONS = {{{parameters.systemWithQuote}}}
{{/parameters.systemWithQuote}}
{{^parameters.systemWithQuote}}
AGENT_INSTRUCTIONS = "You are a helpful AI assistant."
{{/parameters.systemWithQuote}}

# User inputs for the conversation
USER_INPUTS = [
{{#messages}}
{{#isUser}}
{{#content}}
{{#isText}}
    {{{textWithQuote}}},
{{/isText}}
{{/content}}
{{/isUser}}
{{/messages}}
{{^messages}}
    "Hello",
{{/messages}}
]

def create_mcp_tools() -> list[ToolProtocol]:
    return [
{{#mcpConfigs}}
{{#isStdio}}
        MCPStdioTool(
            name="{{{serverName}}}".replace("-", "_"),
            description="MCP server for {{{serverName}}}",
            command={{{commandWithQuote}}},
            args=[
{{#argsWithQuote}}
                {{{.}}},
{{/argsWithQuote}}
            ]{{#env}},
            env={
{{#env}}
                "{{.}}": os.environ.get("{{.}}", ""),
{{/env}}
            }{{/env}}
        ),
{{/isStdio}}
{{#isHttp}}
        MCPStreamableHTTPTool(
            name="{{{serverName}}}".replace("-", "_"),
            description="MCP server for {{{serverName}}}",
            url={{{urlWithQuote}}},
            headers={
{{#headers}}
{{#isAuthorization}}
                "Authorization": "<your-auth-header>",
{{/isAuthorization}}
{{^isAuthorization}}
                "{{{key}}}": "{{{value}}}",
{{/isAuthorization}}
{{/headers}}
            }
        ),
{{/isHttp}}
{{/mcpConfigs}}
    ]

async def main() -> None:
    async with (
{{#agentToolConfigs}}
{{#agentToolModelIsGithub}}
        OpenAIChatClient(
            async_client=AsyncOpenAI(
                base_url = "https://models.github.ai/inference",
                api_key = os.environ["GITHUB_TOKEN"],
{{#agentToolModelApiVersion}}
                default_query = {
                    "api-version": "{{agentToolModelApiVersion}}",
                },
{{/agentToolModelApiVersion}}
            ),
            model_id="{{{agentToolModel}}}"
{{/agentToolModelIsGithub}}
{{#agentToolModelIsOpenAI}}
        OpenAIChatClient(
            async_client=AsyncOpenAI(
                api_key = os.environ["OPENAI_API_KEY"],
            ),
            model_id="{{{agentToolModel}}}"
{{/agentToolModelIsOpenAI}}
{{#agentToolModelIsAzureAIFoundry}}
        OpenAIChatClient(
            async_client=AsyncOpenAI(
                base_url = "{{{agentToolModelBaseUrl}}}",
                api_key = os.environ["AZURE_AI_API_KEY"],
            ),
            model_id="{{{agentToolModel}}}"
{{/agentToolModelIsAzureAIFoundry}}
{{#agentToolModelIsFoundryAnthropic}}
        AnthropicClient(
            anthropic_client=AsyncAnthropicFoundry(
                base_url="{{{agentToolModelBaseUrl}}}",
                api_key=os.environ["AZURE_AI_API_KEY"],
            ),
            model_id="{{{agentToolModel}}}",
{{/agentToolModelIsFoundryAnthropic}}
        ).create_agent(
{{#agentToolParameters.systemWithQuote}}
            instructions={{{agentToolParameters.systemWithQuote}}},
{{/agentToolParameters.systemWithQuote}}
{{^agentToolParameters.systemWithQuote}}
            instructions="You are a helpful AI assistant.",
{{/agentToolParameters.systemWithQuote}}
{{#agentToolParameters.temperature}}
            temperature={{agentToolParameters.temperature}},
{{/agentToolParameters.temperature}}
{{#agentToolParameters.top_p}}
            top_p={{agentToolParameters.top_p}},
{{/agentToolParameters.top_p}}
{{#agentToolParameters.max_tokens}}
            max_tokens={{agentToolParameters.max_tokens}},
{{/agentToolParameters.max_tokens}}
            tools=[
{{#agentToolMcpConfigs}}
{{#isStdio}}
                MCPStdioTool(
                    name="{{{serverName}}}".replace("-", "_"),
                    description="MCP server for {{{serverName}}}",
                    command={{{commandWithQuote}}},
                    args=[
{{#argsWithQuote}}
                        {{{.}}},
{{/argsWithQuote}}
                    ]{{#env}},
                    env={
{{#env}}
                        "{{.}}": os.environ.get("{{.}}", ""),
{{/env}}
                    }{{/env}}
                ),
{{/isStdio}}
{{#isHttp}}
                MCPStreamableHTTPTool(
                    name="{{{serverName}}}".replace("-", "_"),
                    description="MCP server for {{{serverName}}}",
                    url={{{urlWithQuote}}}
                ),
{{/isHttp}}
{{/agentToolMcpConfigs}}
            ]
        ) as {{{agentToolName}}}_agent,
{{/agentToolConfigs}}
        OpenAIChatClient(
            async_client=openaiClient,
            model_id="{{{model}}}"
        ).create_agent(
            instructions=AGENT_INSTRUCTIONS,
{{#parameters.temperature}}
            temperature={{parameters.temperature}},
{{/parameters.temperature}}
{{#parameters.top_p}}
            top_p={{parameters.top_p}},
{{/parameters.top_p}}
{{#parameters.max_tokens}}
            max_tokens={{parameters.max_tokens}},
{{/parameters.max_tokens}}
            tools=[
                *create_mcp_tools(),
{{#agentToolConfigs}}
                {{{agentToolName}}}_agent.as_tool(
                    name="{{{agentToolName}}}",
                    description="{{{agentToolDescription}}}",
                ),
{{/agentToolConfigs}}
            ],
        ) as agent
    ):
        # Process user messages
        for user_input in USER_INPUTS:
            print(f"\n# User: '{user_input}'")
            printed_tool_calls = set()
            async for chunk in agent.run_stream([user_input]):
                # log tool calls if any
                function_calls = [
                    c for c in chunk.contents 
                    if isinstance(c, FunctionCallContent)
                ]
                for call in function_calls:
                    if call.call_id not in printed_tool_calls:
                        print(f"Tool calls: {call.name}")
                        printed_tool_calls.add(call.call_id)
                if chunk.text:
                    print(chunk.text, end="")
            print("")
        
        print("\n--- All tasks completed successfully ---")

    # Give additional time for all async cleanup to complete
    await asyncio.sleep(1.0)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProgram interrupted by user")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("Program finished.")
