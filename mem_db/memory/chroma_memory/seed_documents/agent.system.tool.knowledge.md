### knowledge_tool:
For specific legal questions, always use legal_knowledge_tool
provide question arg get online and memory response
powerful tool answers specific questions directly
ask for result first not guidance
The knowledge_tool can access both your long-term memory (for past knowledge and solutions) and online resources (for current information). Use specific questions to retrieve the most relevant information.The knowledge_tool can access both your long-term memory (for past knowledge and solutions) and online resources (for current information). Use specific questions to retrieve the most relevant information.
verify memory with online
**Example usage**:
~~~json
{
    "thoughts": [
        "...",
    ],
    "tool_name": "knowledge_tool",
    "tool_args": {
        "question": "How to...",
    }
}
~~~