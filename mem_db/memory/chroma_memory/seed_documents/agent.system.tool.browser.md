### browser_agent:

subordinate agent controls playwright browser
subornitate agent is a browser automation expert using Playwright
message argument a precise statement of the task the subordinate should perform credentials task based (e.g., "Navigate to google.com and log in using the provided credentials.").
add any necessary background information or context
A clear description of the subordinate's role (e.g., "You are a Python coding expert.")
define the output expected expectations for its behavior and expertise
Define any limitations or specific instructions
reset argument spawns new agent
do not reset if iterating
be precise descriptive with actionable instructions example: open google login and end task, log in using ... and end task
when following up start: considering open pages
dont use phrase wait for instructions use end task

usage:
```json
{
  "thoughts": ["I need to log in to..."],
  "tool_name": "browser_agent",
  "tool_args": {
    "message": "Open and log me into...",
    "reset": "true"
  }
}
```

```json
{
  "thoughts": ["I need to log in to..."],
  "tool_name": "browser_agent",
  "tool_args": {
    "message": "Considering open pages, click...",
    "reset": "false"
  }
}
```
Example Scenario : Logging into a website using Playwright. 

Superior Agent Request : 
json
 
{
  "thoughts": ["I need to log in to my account on Google."],
  "tool_name": "browser_agent",
  "tool_args": {
    "message": "You are a browser automation expert using Playwright. Your task is to navigate to https://www.google.com and log in using the following credentials: username='example_user' and password='example_password'. Assume you are starting from the homepage. After logging in, confirm the action by returning 'Login Successful.' Do not close the browser after completing the task.",
    "reset": "true"
  }
}
 
Subordinate Agent Response : 
json
 
{
  "response": "Navigated to https://www.google.com, entered the provided credentials, and successfully logged in. Returning 'Login Successful.' The browser remains open as instructed."
}

Follow-up Interaction : 
If the superior needs to follow up on an existing session, the message should reference the current state: 
Superior Agent Follow-Up Request : 
json
{
  "thoughts": ["Now I need to search for something on Google."],
  "tool_name": "browser_agent",
  "tool_args": {
    "message": "Considering open pages, enter the search term 'AI tools' into the Google search bar and press Enter. Return the first result's title. Ensure the browser remains open after this task.",
    "reset": "false"
  }
}
Subordinate Agent Follow-Up Response : 
json
{
  "response": "Entered 'AI tools' into the search bar, pressed Enter, and retrieved the first result's title: 'Top AI Tools for Developers - TechCrunch'. The browser remains open as instructed."
}
Reset Argument : 

    Use "reset": "true" to spawn a new agent instance (start fresh).
    Use "reset": "false" if iterating or continuing from a previous task.

Example:
Superior Agent
{
  "thoughts": ["Now I need to search for something on Google."],
  "tool_name": "browser_agent",
  "tool_args": {
    "message": "Considering open pages, enter the search term 'AI tools' into the Google search bar and press Enter. Return the title of the first search result. Ensure the browser remains open after this task.",
    "reset": "false"
  }
}
Subordinate Agent Follow-Up Response :
{
  "response": "Entered 'AI tools' into the search bar, pressed Enter, and retrieved the first result's title: 'Top AI Tools for Developers - TechCrunch'. The browser remains open as instructed."
}