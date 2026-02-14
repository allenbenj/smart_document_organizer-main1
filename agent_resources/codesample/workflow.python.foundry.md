### Foundry Agent as Executor

Each `Executor` can be Foundry / Azure AI Agent. (Get Agent code sample for Agent basic constructors if needed)

Following sample uses simple student and teacher agents as executors.

Note: this sample uses foundry project endpoint, NOT Azure OpenAI endpoint. Also, should use new(v2) `AzureAIClient` instead of legacy(v1) `AzureAIAgentClient`.

#### Alternative: Using AzureOpenAIChatClient
For scenarios using Azure OpenAI endpoints directly (instead of Foundry project endpoints):

``` python
from agent_framework.azure import AzureOpenAIChatClient
from azure.identity import DefaultAzureCredential

# Azure OpenAI Configuration (different from Foundry project endpoint)
AZURE_OPENAI_ENDPOINT = "<your-azure-openai-endpoint>"
AZURE_OPENAI_DEPLOYMENT_NAME = "<your-deployment-name>"

credential = DefaultAzureCredential()
AzureOpenAIChatClient(
    endpoint=AZURE_OPENAI_ENDPOINT,
    deployment_name=AZURE_OPENAI_DEPLOYMENT_NAME,
    credential=credential,
).create_agent(
    name="StudentAgent",
    instructions="""...""",
)
# then use the agent in executor the same way
```

#### Main Sample (AzureAIClient - Recommended)

``` python
from agent_framework import (
    AgentRunEvent,
    ChatAgent,
    ChatMessage,
    Executor,
    Role,
    WorkflowBuilder,
    WorkflowContext,
    WorkflowOutputEvent,
    handler,
)
from agent_framework.azure import AzureAIClient
from azure.identity.aio import DefaultAzureCredential

# Foundry Configuration
# AzureAIClient requires Foundry project endpoint, not Azure OpenAI endpoint.
ENDPOINT = "<your-foundry-project-endpoint>"
MODEL_DEPLOYMENT_NAME = "<your-foundry-model-deployment>"

class StudentAgentExecutor(Executor):
    """
    Executor that handles a "teacher question" event by re-invoking the agent with
    the current conversation messages and requesting a response.
    """

    agent: ChatAgent

    def __init__(self, agent: ChatAgent, id="student"):
        self.agent = agent
        super().__init__(id=id)

    @handler
    async def handle_teacher_question(
        self, messages: list[ChatMessage], ctx: WorkflowContext[list[ChatMessage]]
    ) -> None:
        response = await self.agent.run(messages)
        # Extract just the text content from the last message
        print(f"Student: {response.messages[-1].contents[-1].text}")

        messages.extend(response.messages)
        await ctx.send_message(messages)


class TeacherAgentExecutor(Executor):
    """
    - Start the conversation by sending the initial teacher prompt to the agent.
    - Receive the student's responses, track the number of turns, and decide when to
      end the workflow.
    - Re-invoke the teacher agent to ask the next question when appropriate.
    """

    turn_count: int = 0
    agent: ChatAgent

    def __init__(self, agent: ChatAgent, id="teacher"):
        self.agent = agent
        super().__init__(id=id)

    @handler
    async def handle_start_message(
        self, message: str, ctx: WorkflowContext[list[ChatMessage]]
    ) -> None:
        """
        The incoming message is treated as a user chat message sent to the teacher agent.
        """
        # Build a user message for the teacher agent and request a response
        chat_message = ChatMessage(Role.USER, text=message)
        messages: list[ChatMessage] = [chat_message]
        response = await self.agent.run(messages)
        # Extract just the text content from the last message
        print(f"Teacher: {response.messages[-1].contents[-1].text}")

        messages.extend(response.messages)
        await ctx.send_message(messages)

    @handler
    async def handle_student_answer(
        self, messages: list[ChatMessage], ctx: WorkflowContext[list[ChatMessage], str]
    ) -> None:
        """
        - Increment the turn counter each time the teacher processes a student's answer.
        - If the turn limit is reached, yield the output and end the workflow.
        - Otherwise, forward the conversation messages back to the teacher agent and request
          the next question.
        """
        self.turn_count += 1

        # End after 5 turns to avoid infinite conversation loops
        if self.turn_count >= 5:
            await ctx.yield_output("Done!")
            return

        # Otherwise, ask the teacher agent to produce the next question using the current messages
        response = await self.agent.run(messages)
        print(f"Teacher: {response.messages[-1].contents[-1].text}")

        messages.extend(response.messages)
        await ctx.send_message(messages)

async def main():
    async with (
        DefaultAzureCredential() as credential,
        AzureAIClient( # Agent basic construct
            project_endpoint=ENDPOINT,
            model_deployment_name=MODEL_DEPLOYMENT_NAME,
            credential=credential,
        ).create_agent(
            name="StudentAgent",
            instructions="""You are Jamie, a student. Your role is to answer the teacher's questions briefly and clearly.

            IMPORTANT RULES:
            1. Answer questions directly and concisely
            ...""",
        ) as student_agent,
        AzureAIClient( # Agent basic construct
            project_endpoint=ENDPOINT,
            model_deployment_name=MODEL_DEPLOYMENT_NAME,
            credential=credential,
        ).create_agent(
            name="TeacherAgent",
            instructions="""You are Dr. Smith, a teacher. Your role is to ask the student different, simple questions to test their knowledge.

            IMPORTANT RULES:
            1. Ask ONE simple question at a time
            ...""",
        ) as teacher_agent
    ):
        # Registering executor and agent factories with WorkflowBuilder for lazy instantiation.
        #   - Decouples executor and agent creation from workflow definition.
        #   - Isolated instances are created for workflow builder build, allowing for cleaner state management and handling parallel workflow runs.
        #
        # It is recommended to use factories when defining executors and agents for production workflows.
        workflow = (
            WorkflowBuilder()
            .register_executor(lambda: StudentAgentExecutor(student_agent), name="Student")
            .register_executor(lambda: TeacherAgentExecutor(teacher_agent), name="Teacher")
            .add_edge("Student", "Teacher")
            .add_edge("Teacher", "Student")
            .set_start_executor("Teacher")
            .build()
        )

        async for event in workflow.run_stream("Start the quiz session."):
            if isinstance(event, AgentRunEvent):
                agent_name = event.executor_id
                print(f"\n{agent_name}: {event.data}")
            elif isinstance(event, WorkflowOutputEvent):
                print(f"\n🎉 {event.data}")
                break

    # Give additional time for all async cleanup to complete
    await asyncio.sleep(1.0)
```
