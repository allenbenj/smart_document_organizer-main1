# Legal_knowledge

Accesses a legal knowledge base (case law, statutes, legal principles, etc.).
query: (Required) The legal question or search term. Can be a specific case name, a legal concept, or a factual scenario.
jurisdiction: (Optional) Specifies the relevant jurisdiction (e.g., "US Federal," "California"). Defaults to a general US legal context.
type: (Optional) Specifies the type of information to retrieve (e.g., "case law," "statute," "definition").
implement error handling cases where no relevant information is found.
Usage Examples:

      
{
    "thoughts": ["Need to find cases related to probable cause in extortion cases."],
    "tool_name": "legal_knowledge",
    "tool_args": {
        "query": "probable cause extortion",
        "jurisdiction": "US Federal"
    }
}

{
    "thoughts": ["What's the definition of 'extortion' under California law?"],
    "tool_name": "legal_knowledge",
    "tool_args": {
        "query": "extortion",
        "jurisdiction": "California",
        "type": "definition"
    }
}

    