      
### memory_manager:

Manages long-term memory using MemGPT.

**Description:** This tool allows the agent to save, load, delete, and search for information in its long-term memory, which is managed by MemGPT.  This overcomes the limitations of the LLM's context window and allows the agent to remember information across multiple interactions.

**Arguments:**
`command`: (Required) The action to perform.  Valid values are:
`save`: Store information in memory.
`load`: Retrieve information from memory.
`delete`: Delete information from memory.
`search`: Search for information in memory (similar to `load`, but returns metadata instead of the full content).  This is important for efficient memory management.
`text`: (Required for `save`) The text to be stored in memory.  This could be a summary of a document, a legal rule, a conclusion, or any other relevant information.
`memory_type`: (Optional for `save`, defaults to `recall`) Specifies where to save. recall, archival.
`query`: (Required for `load` and `search`) The search query used to retrieve information.
`message`: (Optional). Contextual message from conversation.
`metadata`: (Optional for `save`) A JSON object containing additional metadata to associate with the memory.  This can include:
`type`: (e.g., "fact", "rule", "argument", "conclusion", "summary")
`source`: (e.g., "Document X", "User Input", "Legal Knowledge Tool")
`case_id`: (If applicable, a unique identifier for the legal case)
`related_entities`: (A list of related entities, if applicable).
`ids`: (Required for `delete`) A comma-separated list of memory IDs to delete.
`limit`: (Optional for `load` and `search`, defaults to 5) The maximum number of results to return.
`embedding_search`: (Optional defaults to True).  Do embedding vector search
`return_text`: (Optional, default to `false`). Returns text of the memory item.

**Usage Examples:**

```json
// Save a key fact
{
    "thoughts": ["I need to remember that the defendant's fingerprints were found on the weapon."],
    "tool_name": "memory_manager",
    "tool_args": {
        "command": "save",
        "text": "The defendant's fingerprints were found on the weapon.",
        "metadata": {
            "type": "fact",
            "source": "Police Report",
            "case_id": "XYZ123"
        }
    }
}

// Retrieve information about a specific legal rule
{
    "thoughts": ["I need to recall the legal rule for negligence."],
    "tool_name": "memory_manager",
    "tool_args": {
        "command": "load",
        "query": "legal rule negligence",
        "limit": 3
    }
}
 // Search information about a specific legal rule, without returing text
    {
        "thoughts": ["I need to check if I have information on negligence."],
        "tool_name": "memory_manager",
        "tool_args": {
            "command": "search",
            "query": "legal rule negligence",
            "limit": 3
        }
    }

// Delete an outdated memory
{
    "thoughts": ["I need to delete the memory about the initial suspect, as they have been cleared."],
    "tool_name": "memory_manager",
    "tool_args": {
        "command": "delete",
        "ids": "memory_id_1, memory_id_2"
    }
}

    