### Foundry Agent as Executor

Each `Executor` can be Foundry / Azure AI Agent. (Get Agent code sample for Agent basic constructors if needed)

Following sample uses simple student and teacher agents as executors.

Note: this sample uses foundry project endpoint, which is different from previous foundation samples which use Azure OpenAI endpoint.

``` csharp
// dotnet add package Azure.AI.Projects --prerelease (or version *-*)
// dotnet add package Azure.Identity --prerelease (or version *-*)
// dotnet add package Microsoft.Agents.AI.AzureAI --prerelease (or version *-*)
// dotnet add package Microsoft.Agents.AI.Workflows --prerelease (or version *-*)
// dotnet add package Microsoft.Extensions.AI --prerelease (or version *-*)
using Azure.AI.Projects;
using Azure.Identity;
using Microsoft.Agents.AI;
using Microsoft.Agents.AI.Workflows;
using Microsoft.Extensions.AI;
namespace MyWorkflow;
public static class Program
{
    private static async Task Main()
    {
        // Foundry Agent Configuration
        // Foundry project endpoint, not Azure OpenAI endpoint.
        var endpoint = "<your-foundry-project-endpoint>";
        var deployment = "<your-foundry-model-deployment>";

        Console.WriteLine($"Using Foundry project endpoint: {endpoint}");
        Console.WriteLine($"Using deployment: {deployment}");

        // Create AIProjectClient for Microsoft Foundry (formerly Azure AI Foundry)
        var aiProjectClient = new AIProjectClient(new Uri(endpoint), new DefaultAzureCredential());
        AIAgent? teacherAgent = null;
        AIAgent? studentAgent = null;

        try
        {
            // Create teacher agent
            teacherAgent = await CreateTeacherAgentAsync(aiProjectClient, deployment);
            FoundryTeacherExecutor? teacherExec = new("Teacher", teacherAgent);

            // Create student agent
            studentAgent = await CreateStudentAgentAsync(aiProjectClient, deployment);
            FoundryStudentExecutor? studentExec = new("Student", studentAgent);

            var builder = new WorkflowBuilder(teacherExec)
                .AddEdge(teacherExec, studentExec)
                .AddEdge(studentExec, teacherExec)
                .WithOutputFrom(studentExec);

            var workflow = builder.Build();
            var run = await InProcessExecution
                .StreamAsync(
                    workflow,
                    new List<ChatMessage>
                    {
                        new(ChatRole.User, "start the conversation please."),
                    }
                )
                .ConfigureAwait(false);

            // Wait for workflow completion (executors also handle their own output)
            await foreach (WorkflowEvent evt in run.WatchStreamAsync().ConfigureAwait(false))
            {
                switch (evt)
                {
                    case ExecutorCompletedEvent executorComplete when executorComplete.Data is not null:
                        // Don't print internal executor outputs, let them handle their own printing
                        break;
        
                    case WorkflowOutputEvent workflowOutputEvent:
                        // Workflow completed - complete output is already printed by executor
                        break;
                }
            }
        }
        catch (Exception ex)
        {
            var errorMessage = $"Error running workflow: {ex.Message}";
            Console.Error.WriteLine(errorMessage);
            throw;
        }
        finally
        {
            // Clean up all resources
            await CleanupAll(
                aiProjectClient,
                studentAgent,
                teacherAgent
            );
        }
    }

    private static async Task<ChatClientAgent> CreateTeacherAgentAsync(
        AIProjectClient aiProjectClient,
        string model
    )
    {
        var agent = await aiProjectClient.CreateAIAgentAsync(
            model: model,
            name: "DrSmith-Teacher",
            instructions: @"You are Dr. Smith, a teacher. Your role is to ask the student different, simple questions to test their knowledge.

IMPORTANT RULES:
1. Ask ONE simple question at a time
..."
        );

        return agent;
    }

    private static async Task<ChatClientAgent> CreateStudentAgentAsync(
        AIProjectClient aiProjectClient,
        string model
    )
    {
        var agent = await aiProjectClient.CreateAIAgentAsync(
            model: model,
            name: "Jamie-Student",
            instructions: @"You are Jamie, a student. Your role is to answer the teacher's questions briefly and clearly.

IMPORTANT RULES:
1. Answer questions directly and concisely
..."
            );

        return agent;
    }

    private static async Task CleanupAll(
        AIProjectClient aiProjectClient,
        AIAgent? studentAgent,
        AIAgent? teacherAgent
    )
    {
        Console.WriteLine("🧹 Cleaning up agents and Azure resources...");
        try
        {
            // Delete agents from Microsoft Foundry (formerly Azure AI Foundry)
            if (studentAgent != null)
            {
                await aiProjectClient.Agents.DeleteAgentAsync(studentAgent.Name);
            }
            if (teacherAgent != null)
            {
                await aiProjectClient.Agents.DeleteAgentAsync(teacherAgent.Name);
            }

            Console.WriteLine("✅ Cleanup completed successfully.");
        }
        catch (Exception e)
        {
            Console.WriteLine($"Cleanup failed: {e.Message}");
        }
    }
}

/// <summary>
/// Teacher Executor - uses Microsoft Foundry (formerly Azure AI Foundry) Agent
/// </summary>
internal sealed class FoundryTeacherExecutor : Executor<List<ChatMessage>>
{
    private readonly AIAgent _agent;
    private int _turnCount = 0;

    public FoundryTeacherExecutor(string id, AIAgent agent)
        : base(id)
    {
        _agent = agent;
    }

    public override async ValueTask HandleAsync(
        List<ChatMessage> messages,
        IWorkflowContext context,
        CancellationToken cancellationToken = default
    )
    {
        if (_turnCount >= 5)
        {
            Console.WriteLine("Student-teacher conversation completed after 5 turns!");
            await context.YieldOutputAsync(messages, cancellationToken).ConfigureAwait(false);
            return;
        }

        _turnCount++;
        var response = await _agent
            .RunAsync(messages, cancellationToken: cancellationToken)
            .ConfigureAwait(false);
        var question = response.Text;

        var questionId = Guid.NewGuid().ToString();
        var newMessage = new ChatMessage(ChatRole.Assistant, question) { MessageId = questionId };

        Console.WriteLine($"Teacher: {question}");
        await context
            .AddEventAsync(
                new AgentRunUpdateEvent(
                    Id,
                    new AgentRunResponseUpdate(ChatRole.Assistant, $"Teacher: {question}")
                    {
                        ResponseId = questionId,
                    }
                ),
                cancellationToken
            )
            .ConfigureAwait(false);

        var updatedMessages = new List<ChatMessage>(messages) { newMessage };

        // Manually send the message to continue the workflow
        await context
            .SendMessageAsync(updatedMessages, cancellationToken: cancellationToken)
            .ConfigureAwait(false);
    }
}

/// <summary>
/// Student Executor - uses Microsoft Foundry (formerly Azure AI Foundry) Agent
/// </summary>
internal sealed class FoundryStudentExecutor : Executor<List<ChatMessage>>
{
    private readonly AIAgent _agent;

    public FoundryStudentExecutor(string id, AIAgent agent)
        : base(id)
    {
        _agent = agent;
    }

    public override async ValueTask HandleAsync(
        List<ChatMessage> messages,
        IWorkflowContext context,
        CancellationToken cancellationToken = default
    )
    {
        var response = await _agent.RunAsync(messages).ConfigureAwait(false);
        var answer = response.Text;

        var newMessage = new ChatMessage(ChatRole.User, answer);

        Console.WriteLine($"Student: {answer}");
        await context
            .AddEventAsync(
                new AgentRunUpdateEvent(
                    Id,
                    new AgentRunResponseUpdate(ChatRole.User, $"Student: {answer}")
                    {
                        ResponseId = messages.LastOrDefault()?.MessageId,
                    }
                ),
                cancellationToken
            )
            .ConfigureAwait(false);

        var updatedMessages = new List<ChatMessage>(messages) { newMessage };

        await context
            .SendMessageAsync(updatedMessages, cancellationToken: cancellationToken)
            .ConfigureAwait(false);
    }
}
```
