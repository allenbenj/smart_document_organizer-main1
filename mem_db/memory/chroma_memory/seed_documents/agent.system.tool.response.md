### response:
This tool signals that the current task is complete and provides the final result to the user
ends task processing use only when done or no task active
result in text arg required
always write full file paths
file_path argument for returning results saved in files
usage:
~~~json
{
    "thoughts": [
        "...",
    ],
    "tool_name": "response",
    "tool_args": {
        "text": "Answer to the user",
    }
}
~~~