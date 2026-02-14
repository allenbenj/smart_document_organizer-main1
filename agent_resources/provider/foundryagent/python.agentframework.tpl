"""Build Agent using Microsoft Agent Framework in Python
# Run this python script
> pip install agent-framework==1.0.0b260107 agent-framework-azure-ai==1.0.0b260107
> python <this-script-path>.py
"""

import asyncio

from agent_framework import ChatAgent, FunctionCallContent
from agent_framework.azure import AzureAIClient
from azure.ai.projects.aio import AIProjectClient
from azure.identity.aio import DefaultAzureCredential

# User inputs for the conversation
USER_INPUTS = [
{{#userInputs}}
    {{{.}}},
{{/userInputs}}
{{^userInputs}}
    "Hello",
{{/userInputs}}
]

async def main() -> None:
    async with (
        # For authentication, DefaultAzureCredential supports multiple authentication methods. Run `az login` in terminal for Azure CLI auth.
        DefaultAzureCredential() as credential,
        AIProjectClient(endpoint="{{{projectEndpoint}}}", credential=credential) as project_client,
        ChatAgent(
            chat_client=AzureAIClient(
                project_client=project_client,
                agent_name="{{{agentName}}}",
                model_deployment_name="{{{modelName}}}",
                use_latest_version=True,
            ),
        ) as agent,
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
