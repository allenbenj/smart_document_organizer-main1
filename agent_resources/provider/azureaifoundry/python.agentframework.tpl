"""Build Agent using Microsoft Agent Framework in Python
# Run this python script
> pip install agent-framework==1.0.0b260107 agent-framework-azure-ai==1.0.0b260107
> python <this-script-path>.py
"""

import asyncio

from agent_framework import FunctionCallContent
from agent_framework.azure import AzureAIClient
from azure.identity.aio import DefaultAzureCredential

# Microsoft Foundry Agent Configuration
ENDPOINT = "{{{projectEndpoint}}}"
MODEL_DEPLOYMENT_NAME = "{{{model}}}"

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

{{#tools.length}}
# Tool functions
{{#tools}}
def {{name}}(*args, **kwargs):
    """{{description}}"""
    return "{{toolResult}}"

{{/tools}}
{{/tools.length}}

async def main() -> None:
    async with (
        # For authentication, DefaultAzureCredential supports multiple authentication methods. Run `az login` in terminal for Azure CLI auth.
        DefaultAzureCredential() as credential,
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
{{#tools.length}}
            tools=[
{{#tools}}
                {{name}},
{{/tools}}
            ],
{{/tools.length}}
{{^tools.length}}
            tools=None,
{{/tools.length}}
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
