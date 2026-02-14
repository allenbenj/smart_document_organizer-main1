### Collect Responses with agent-framework SDK
The agent-framework SDK provides built-in support for capturing both final outputs and conversation histories.

#### Collect responses for Agent

For agent (whose type is `ChatAgent`), the `agent.run()` result (whose type is `AgentRunResponse`) includes `messages` (whose type is `ChatMessage` or `list[ChatMessage]`), which is exactly the conversation histories and the last message is the final output. `ChatMessage` provides `to_dict()` method to convert the instance and any nested objects to a dictionary.

```python
result = agent.run(query)
conversation_histories = [message.to_dict() for message in result.messages]
final_output = result.messages[-1].text
```

#### Collect responses for Workflow

For workflow (whose type is `Workflow`), the `workflow.run()` result is list of workflow events (whose type is `WorkflowEvent`). The conversation histories are not applicable for workflow, and the final output is the last event whose `data` is not empty.

```python
events = workflow.run(query)
final_output = str([event for event in events if event.data][-1].data) # use str() in case data is not json serializable
```