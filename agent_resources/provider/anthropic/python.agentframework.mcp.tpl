"""Build Agent using Microsoft Agent Framework in Python
# Run this python script
> pip install agent-framework==1.0.0b260107 agent-framework-azure-ai==1.0.0b260107
> python <this-script-path>.py
"""

import asyncio
import os

from agent_framework import MCPStdioTool, MCPStreamableHTTPTool, ToolProtocol, FunctionCallContent
from agent_framework.azure import AzureAIClient
from agent_framework.openai import OpenAIChatClient
from openai import AsyncOpenAI
from azure.identity.aio import DefaultAzureCredential

# Microsoft Foundry Agent Configuration
ENDPOINT = "{{{projectEndpoint}}}"
MODEL_DEPLOYMENT_NAME = "{{{model}}}"

AGENT_NAME = "mcp-agent"
{{#parameters.systemWithQuote}}
AGENT_INSTRUCTIONS = {{{parameters.systemWithQuote}}}
{{/parameters.systemWithQuote}}
{{^parameters.systemWithQuote}}
AGENT_INSTRUCTIONS = "Use the provided tools to answer questions. You have access to MCP tools for various functionalities."
{{/parameters.systemWithQuote}}

# User inputs for the conversation
USER_INPUTS = [
{{#messages}}
{{#content}}
{{#isUser}}
{{#isText}}
    {{{textWithQuote}}},
{{/isText}}
{{/isUser}}
{{/content}}
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
        # For authentication, DefaultAzureCredential supports multiple authentication methods. Run `az login` in terminal for Azure CLI auth.
        DefaultAzureCredential() as credential,
{{#agentToolConfigs}}
{{#agentToolModelIsOpenAI}}
        OpenAIChatClient(
            async_client=AsyncOpenAI(
                api_key = os.environ["OPENAI_API_KEY"],
            ),
            model_id="{{{agentToolModel}}}"
{{/agentToolModelIsOpenAI}}
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
{{#agentToolModelIsAzureAIFoundry}}
        AzureAIClient(
            project_endpoint="{{{agentToolModelProjectEndpoint}}}",
            model_deployment_name="{{{agentToolModel}}}",
            credential=credential,
            agent_name="{{{agentToolName}}}",
            use_latest_version=True,  # This parameter will allow to re-use latest agent version instead of creating a new one
{{/agentToolModelIsAzureAIFoundry}}
{{#agentToolModelIsFoundryAnthropic}}
        AzureAIClient(
            project_endpoint="{{{agentToolModelProjectEndpoint}}}",
            model_deployment_name="{{{agentToolModel}}}",
            credential=credential,
            agent_name="{{{agentToolName}}}",
            use_latest_version=True,  # This parameter will allow to re-use latest agent version instead of creating a new one
{{/agentToolModelIsFoundryAnthropic}}
        ).create_agent(
{{#agentToolParameters.systemWithQuote}}
            instructions={{{agentToolParameters.systemWithQuote}}},
{{/agentToolParameters.systemWithQuote}}
{{^agentToolParameters.systemWithQuote}}
            instructions="You are a helpful AI assistant.",
{{/agentToolParameters.systemWithQuote}}
{{#agentToolParameters.max_tokens}}
            max_tokens={{agentToolParameters.max_tokens}},
{{/agentToolParameters.max_tokens}}
{{#agentToolParameters.temperature}}
            temperature={{agentToolParameters.temperature}},
{{/agentToolParameters.temperature}}
{{#agentToolParameters.top_p}}
            top_p={{agentToolParameters.top_p}},
{{/agentToolParameters.top_p}}
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
{{/agentToolMcpConfigs}}
            ]
        ) as {{{agentToolName}}}_agent,
{{/agentToolConfigs}}
        AzureAIClient(
            project_endpoint=ENDPOINT,
            model_deployment_name=MODEL_DEPLOYMENT_NAME,
            credential=credential,
            agent_name=AGENT_NAME,
            use_latest_version=True,  # This parameter will allow to re-use latest agent version instead of creating a new one
        ).create_agent(
            instructions=AGENT_INSTRUCTIONS,
{{#parameters.max_tokens}}
            max_tokens={{parameters.max_tokens}},
{{/parameters.max_tokens}}
{{#parameters.temperature}}
            temperature={{parameters.temperature}},
{{/parameters.temperature}}
{{#parameters.top_p}}
            top_p={{parameters.top_p}},
{{/parameters.top_p}}
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
