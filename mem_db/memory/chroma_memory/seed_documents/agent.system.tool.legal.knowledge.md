# Legal_knowledge

Accesses the CourtListener legal database for case law, statutes, and other legal information.

**Description:** This tool provides access to a comprehensive legal database, allowing the agent to research case law, statutes, court dockets, and other legal information.  It uses the CourtListener API.

**Arguments:**

*   `query`: (Required) The legal question or search term.  Can be a specific case name, a legal concept, or a factual scenario.  For complex queries, consider using the `endpoint` and `params` arguments for more control.
*   `jurisdiction`: (Optional) Specifies the relevant jurisdiction (e.g., "US Federal," "California," "scotus"). Defaults to a general US legal context.  Use CourtListener jurisdiction codes when possible (e.g., "FD" for Federal District Courts).  See the CourtListener API documentation for a complete list.
*   `type`: (Optional) Specifies the type of information to retrieve (e.g., "case law," "statute," "docket," "opinion").  If not specified, the tool will attempt to infer the type from the query.
*   `endpoint`: (Optional, Advanced)  Allows direct specification of a CourtListener API endpoint (e.g., "/api/rest/v4/dockets/").  Use this for advanced queries not covered by the `query` argument.
*   `params`: (Optional, Advanced)  A dictionary of key-value pairs representing GET parameters for the CourtListener API.  Use this in conjunction with `endpoint` for fine-grained control over filtering, ordering, and field selection.  See the CourtListener API documentation for available parameters.
*   `authentication_token`: (Required) Your CourtListener API authentication token. This is required for all requests and is provided by the environment. DO NOT HARDCODE THE TOKEN.

**Usage Examples:**

```json
{
    "thoughts": ["Need to find cases related to probable cause in extortion cases in federal courts."],
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

{
  "thoughts": ["I need to find all dockets from the Supreme Court (court ID 'scotus') with IDs between 500 and 1000."],
  "tool_name": "legal_knowledge",
  "tool_args": {
    "endpoint": "/api/rest/v4/dockets/",
    "params": {
      "court": "scotus",
      "id__range": "500,1000"
    }
  }
}

{
    "thoughts": ["I need to get all opinions citing opinion ID 32239, but only need the count."],
      "tool_name": "legal_knowledge_tool",
        "tool_args": {
            "endpoint": "/api/rest/v4/opinions/",
            "params": {
              "cited_opinion": "32239",
              "count": "on"
            }
        }
}

{
 "thoughts": ["Find opinions from the Supreme Court."],
 "tool_name": "legal_knowledge",
 "tool_args": {
 "endpoint": "/api/rest/v4/opinions/",
 "params": {
 "cluster__docket__court": "scotus"
 }
 }
}