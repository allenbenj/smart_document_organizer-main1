## Tracing
### Trigger
User asks to "monitor" or "trace".
### Details
- Use `aitk-get_tracing_code_gen_best_practices` to retrieve best practices, then apply them to instrument the code for tracing.

## Evaluation
### Trigger
User asks to "improve performance", "measure" or "evaluate".
### Details
- Use `aitk-evaluation_planner` for guiding users through clarifying evaluation metrics, test dataset and runtime via multi-turn conversation, call this first when either evaluation metrics, test dataset or runtime is unclear or incomplete
- Use `aitk-evaluation_agent_runner_best_practices` for best practices and guidance for using agent runners to collect responses from test datasets for evaluation
- Use `aitk-get_evaluation_code_gen_best_practices` for best practices for the evaluation code generation when working on evaluation for AI application or AI agent

## Deployment
### Trigger
User asks to "deploy", "publish", "ship", or "go production".
### Details
Ensure the app is wrapped as HTTP server (if not, use `aitk-agent_as_server` first). Then, call VSCode Command [Microsoft Foundry: Deploy Hosted Agent](azure-ai-foundry.commandPalette.deployWorkflow) to trigger the deployment command.
