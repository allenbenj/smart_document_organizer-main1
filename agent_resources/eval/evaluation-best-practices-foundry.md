# Evaluation Code Generation Best Practices (Foundry Runtime)

## Core Principles

- Use **Azure AI Projects SDK v2** (`azure-ai-projects` v2)
- Generate a plan before writing code

## Prerequisites

Ensure the following packages are installed:
```bash
pip install "azure-ai-projects>=2.0.0b2"
```

## Workflow Overview

1.  **Initialize Client**: Create an `AIProjectClient` and retrieve the `OpenAI` client (via `project_client.get_openai_client()`).
2.  **Upload Dataset**: Upload your evaluation dataset (JSONL) to the project using `project_client.datasets.upload_file`.
3.  **Create Custom Evaluator (Optional)**: Create custom evaluators using `project_client.evaluators.create_version` if built-in ones don't meet requirements.
4.  **Define Configuration**: Set up data source configuration and testing criteria.
5.  **Create Evaluation**: Create an evaluation definition using the `OpenAI` client (`openai_client.evals.create`).
6.  **Run Evaluation**: Submit an evaluation run using the `OpenAI` client (`openai_client.evals.runs.create`).
7.  **Check Results**: Monitor the run status using `openai_client.evals.runs.retrieve` and print the report URL upon completion.

## Implement Evaluators

### Choose Your Evaluator Type

Azure AI Projects SDK supports three types of evaluators:

| Type | Best For | Complexity | Priority |
|------|----------|------------|----------|
| **🔌 Built-in** | Common AI metrics (task adherence, intent resolution, tool accuracy, etc.) | Low | **1st Choice** |
| **🔧 Custom Code-based** | Business-specific objective metrics with custom logic | Medium | 2nd Choice |
| **🤖 Custom Prompt-based** | Business-specific subjective metrics requiring LLM judgment | High | 3rd Choice |

For each evaluator you need to implement, follow this decision tree:

1. **Check Built-in Evaluators First**: Always start by checking if your evaluator can be satisfied via SDK's built-in evaluators
   - ✅ **If available**: Use the built-in evaluator
   - ❌ **If not available**: Proceed to step 2

2. **Determine Custom Evaluator Type**: If no built-in evaluator meets your needs, choose the appropriate custom implementation:
   - **Code-based Evaluator**: For objective, measurable criteria that require specific business logic
   - **Prompt-based Evaluator**: For subjective criteria requiring human-like judgment that an LLM can assess

### 1. Built-in Evaluators

Foundry provides a set of built-in evaluators that can be referenced by name.

**Usage Pattern:**
```python
{
    "type": "azure_ai_evaluator",
    "name": "evaluator_alias", # Your custom name for this check
    "evaluator_name": "builtin.<evaluator_type>", # e.g., builtin.coherence, builtin.f1_score
    # Maps dataset columns to evaluator inputs (e.g., "query" column → evaluator's "query" parameter)
    "data_mapping": {
        "query": "{{item.query}}",
        "response": "{{item.response}}"
    },
    # Optional: Model deployment for prompt-based evaluators
    "initialization_parameters": {"deployment_name": "<your_deployment_name>"}
}
```

**Common Built-in Evaluators:**

| Evaluator Name | Required Data Columns | Description |
|----------------|-----------------------|-------------|
| **Agent Evaluators** | | |
| `builtin.intent_resolution` | `query`, `response`<sup>1</sup> (optional: `tool_definitions`<sup>2</sup>) | Assesses whether the user intent was correctly identified and resolved. |
| `builtin.task_adherence` | `query`, `response`<sup>1</sup> (optional: `tool_definitions`<sup>2</sup>) | Assesses how well an AI-generated response follows the assigned task based on alignment with instructions and definitions, accuracy and clarity of the response, and proper use of provided tool definitions. |
| `builtin.task_completion` | `query`, `response`<sup>1</sup> (optional: `tool_definitions`<sup>2</sup>) | Evaluates whether an AI agent successfully completed the requested task end to end by analyzing the conversation history and agent response to determine if all task requirements were met, ignoring rule adherence or intent understanding. |
| `builtin.tool_call_accuracy` | `query`, `tool_definitions`<sup>2</sup> (optional: `tool_calls`<sup>3</sup>, `response`<sup>1</sup>) | Assesses how accurately an AI uses tools by examining relevance to the conversation, parameter correctness according to tool definitions, and parameter value extraction from the conversation. |
| `builtin.tool_input_accuracy` | `query`, `response`<sup>1</sup>, `tool_definitions`<sup>2</sup> | Checks whether all parameters in an agent’s tool call are correct, validating grounding, type, format, completeness, and contextual appropriateness using LLM-based analysis. |
| `builtin.tool_selection` | `query`, `response`<sup>1</sup>, `tool_definitions`<sup>2</sup> (optional: `tool_calls`<sup>3</sup>) | Evaluates whether an AI agent selected the most appropriate and efficient tools for a given task, avoiding redundancy or missing essentials. |
| `builtin.tool_output_utilization` | `query`, `response`<sup>1</sup> (optional: `tool_definitions`<sup>2</sup>) | Checks if an agent correctly interprets and contextually uses the outputs returned by invoked tools (e.g., APIs, DB queries, search results) without fabrication or omission. |
| `builtin.tool_call_success` | `response`<sup>1</sup> (optional: `tool_definitions`<sup>2</sup>) | Evaluates whether all tool calls were successful or not. It checks all tool calls to determine if any of these resulted in technical failure like exception, error or timeout. |
| **General Purpose Evaluators** | | |
| `builtin.coherence` | `query`, `response` | Assesses the ability of the language model to generate text that reads naturally, flows smoothly, and resembles human-like language in its responses. |
| `builtin.fluency` | `response` | Assesses the extent to which the generated text conforms to grammatical rules, syntactic structures, and appropriate vocabulary usage. |
| **Textual Similarity Evaluators** | | |
| `builtin.similarity` | `query`, `response`, `ground_truth` | Evaluates the likeness between a ground truth sentence and the AI model's generated prediction using sentence-level embeddings. Similarity scores range from 1 to 5. |
| `builtin.f1_score` | `response`, `ground_truth` | Calculates F1 score. |
| `builtin.bleu_score` | `response`, `ground_truth` | Calculates BLEU score. |
| `builtin.gleu_score` | `response`, `ground_truth` | Calculates GLEU score. |
| `builtin.rouge_score` | `response`, `ground_truth` | Calculates ROUGE score. |
| `builtin.meteor_score` | `response`, `ground_truth` | Calculates METEOR score. |
| **Retrieval-Augmented Generation (RAG) Evaluators** | | |
| `builtin.groundedness` | `response`, `context` (optional: `query`) | Assesses the correspondence between claims in an AI-generated answer and the source context, making sure that these claims are substantiated by the context. |
| `builtin.relevance` | `query`, `response` | Assesses the ability of answers to capture the key points of the context and produce coherent and contextually appropriate outputs. |
| `builtin.retrieval` | `query`, `context` | Assesses the AI system's performance in retrieving information for additional context (e.g. a RAG scenario). |
| `builtin.response_completeness` | `response`, `ground_truth` | Assesses how thoroughly an AI model's generated response aligns with the key information, claims, and statements established in the ground truth. |
| `builtin.document_retrieval` | `retrieval_ground_truth` (List of `{"document_id": str, "query_relevance_label": int}`), `retrieved_documents` (List of `{"document_id": str, "relevance_score": float}`) | Calculates document retrieval metrics, such as NDCG, XDCG, Fidelity, Top K Relevance and Holes. |

<sup>1</sup> `response`: Can be a string or a list of messages. If it is a list, each message must strictly follow this structure:
- `role`: A string (e.g., "user", "assistant", "tool").
- `content`: A list of objects.
  - For tool calls: `{"type": "tool_call", "name": str, ...}` inside `content`.
  - For tool results: `{"type": "tool_result", "tool_result": ...}` inside `content`.
**Note: Tool calls and tool results must be included within the `content` list, not as separate fields.** Example:
```json
[
    {
        "role": "assistant",
        "content": [
            {
                "type": "tool_call",
                "tool_call_id": "call_CUdbkBfvVBla2YP3p24uhElJ",
                "name": "fetch_weather",
                "arguments": {"location": "Seattle"}
            }
        ]
    },
    {
        "tool_call_id": "call_CUdbkBfvVBla2YP3p24uhElJ",
        "role": "tool",
        "content": [{"type": "tool_result", "tool_result": {"weather": "Rainy, 14\u00b0C"}}]
    },
    {
        "role": "assistant",
        "content": [
            {
                "type": "text",
                "text": "The current weather in Seattle is rainy with a temperature of 14\u00b0C."
            }
        ]
    }
]
```

<sup>2</sup> `tool_definitions`: List of `{"name": str, "description": str, "parameters": dict}`.

<sup>3</sup> `tool_calls`: List of `{"type": "tool_call", "name": str, ...}`. Optional if `response` already contains tool calls.

### 2. Custom Prompt-based Evaluators

For custom subjective metrics, define a prompt-based evaluator.

**Creation:**
```python
from azure.ai.projects.models import EvaluatorCategory, EvaluatorDefinitionType

prompt_evaluator = project_client.evaluators.create_version(
    name="my_prompt_evaluator",
    evaluator_version={
        "name": "my_prompt_evaluator",
        "categories": [EvaluatorCategory.QUALITY],
        "display_name": "My Prompt Evaluator",
        "description": "Evaluates X based on prompt",
        "definition": {
            "type": EvaluatorDefinitionType.PROMPT,
            "prompt_text": """
                [Please provide your prompt here]

                ---
                ### Input:
                Query:
                {{query}}
                Response:
                {{response}}

                ---
                ### Output Format (JSON):
                {
                    "result": <int or float or boolean>,
                    "reason": "<brief explanation for the result>"
                }
            """,
            "init_parameters": {
                # Note: deployment_name and threshold are required parameters
                "required": ["deployment_name", "threshold"],
                "type": "object",
                "properties": {
                    "deployment_name": {"type": "string"},
                    "threshold": {"type": "number"}
                },
            },
            "metrics": {
                "result": {
                    "type": "ordinal", # or "continuous", "boolean"
                    "min_value": 1.0,
                    "max_value": 5.0,
                }
            },
            "data_schema": {
                "required": ["item"],
                "type": "object",
                "properties": {
                    "item": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                            "response": {"type": "string"}
                        }
                    }
                }
            }
        }
    }
)
```

**Usage in Testing Criteria:**
```python
{
    "type": "azure_ai_evaluator",
    "name": "my_prompt_eval",
    "evaluator_name": "my_prompt_evaluator", # Name used in create_version
    "data_mapping": {"query": "{{item.query}}", "response": "{{item.response}}"},
    "initialization_parameters": {
        # Note: deployment_name and threshold are required parameters
        "deployment_name": "<your_deployment_name>",
        "threshold": 3
    }
}
```

### 3. Custom Code-based Evaluators

For custom objective metrics with Python logic.

**Creation:**
```python
code_evaluator = project_client.evaluators.create_version(
    name="my_code_evaluator",
    evaluator_version={
        "name": "my_code_evaluator",
        "definition": {
            "type": EvaluatorDefinitionType.CODE,
            "code_text": """
# It takes in two arguments and outputs a float value
# item is a dict that includes the data fields defined in the schema of data source config
def grade(sample, item):
   # add your logic here.
   return 1.0
""",
            "init_parameters": {
                # Note: deployment_name and pass_threshold are required parameters
                "required": ["deployment_name", "pass_threshold"],
                "type": "object",
                "properties": {
                    "deployment_name": {"type": "string"},
                    "pass_threshold": {"type": "number"}
                },
            },
            "metrics": {
                "result": {
                    "type": "ordinal", # or "continuous", "boolean"
                    "min_value": 1.0,
                    "max_value": 5.0,
                }
            },
            "data_schema": {
                "required": ["item"],
                "type": "object",
                "properties": {
                    "item": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                            "response": {"type": "string"}
                        }
                    }
                }
            }
        }
    }
)
```

**Usage in Testing Criteria:**
```python
{
    "type": "azure_ai_evaluator",
    "name": "my_code_eval",
    "evaluator_name": "my_code_evaluator", # Name used in create_version
    "initialization_parameters": {
        # Note: deployment_name and pass_threshold are required parameters
        "deployment_name": "<your_deployment_name>",
        "pass_threshold": 3
    }
}
```

## Complete Example

```python
import os
import time
import json
import logging
from datetime import datetime, timezone
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from openai.types.eval_create_params import DataSourceConfigCustom
from openai.types.evals.create_eval_jsonl_run_data_source_param import CreateEvalJSONLRunDataSourceParam, SourceFileID

timestamp = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')

# Configure logging to output to both console and a file
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f"evaluation_run_{timestamp}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger()

endpoint = "<your-foundry-project-endpoint>"
model_deployment_name = "<your-model-deployment-name>"
data_file = "path/to/your/data.jsonl"

# Create an `AIProjectClient` and retrieve the `OpenAI` client
# DO NOT use `AIProjectClient.from_connection_string()` or `project_client.inference.get_azure_openai_client()` because it is removed in azure-ai-projects v2
with (
    DefaultAzureCredential() as credential,
    AIProjectClient(endpoint=endpoint, credential=credential) as project_client,
    project_client.get_openai_client() as openai_client,
):
    # 1. Upload Dataset
    logger.info("Uploading dataset...")
    dataset = project_client.datasets.upload_file(
        name=f"<short-scenario-name>-eval-data-{timestamp}",
        version="1",
        file_path=data_file,
    )
    logger.info(f"Dataset uploaded: {dataset.name} (ID: {dataset.id})")

    # 2. Define Data Source Config
    data_source_config = DataSourceConfigCustom(
        {
            "type": "custom",
            "item_schema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "response": {"type": "string"},
                    "context": {"type": "string"},
                    "ground_truth": {"type": "string"},
                },
                "required": [],
            },
            "include_sample_schema": True,
        }
    )

    # 3. Define Testing Criteria (Evaluators)
    testing_criteria = [
        # Built-in Evaluator
        {
            "type": "azure_ai_evaluator",
            "name": "coherence",
            "evaluator_name": "builtin.coherence",
            # Maps the columns from the dataset to the required inputs of the evaluator
            "data_mapping": {"query": "{{item.query}}", "response": "{{item.response}}"},
            "initialization_parameters": {"deployment_name": model_deployment_name},
        }
    ]

    # 4. Create Evaluation
    logger.info("Creating evaluation...")
    evaluation = openai_client.evals.create(
        name=f"<short-scenario-name>-eval-{timestamp}",
        data_source_config=data_source_config,
        testing_criteria=testing_criteria,
    )
    logger.info(f"Evaluation created: {evaluation.id}")

    # 5. Create Evaluation Run
    logger.info("Starting evaluation run...")
    run = openai_client.evals.runs.create(
        eval_id=evaluation.id,
        name=f"<short-scenario-name>-eval-run-{timestamp}",
        data_source=CreateEvalJSONLRunDataSourceParam(
            type="jsonl", 
            source=SourceFileID(type="file_id", id=dataset.id)
        )
    )
    logger.info(f"Run created: {run.id}")

    # 6. Wait for Completion and Save Results
    while run.status not in ["completed", "failed"]:
        run = openai_client.evals.runs.retrieve(run_id=run.id, eval_id=evaluation.id)
        logger.info(f"Status: {run.status}")
        time.sleep(3)

    logger.info(f"Eval Run Report URL: {run.report_url}")

    if run.status == "completed":
        logger.info("Evaluation completed successfully.")
        
        # Retrieve and save output items
        output_items = list(openai_client.evals.runs.output_items.list(run_id=run.id, eval_id=evaluation.id))
        json_output = json.dumps([item.model_dump() for item in output_items], indent=4)
        
        output_file = f"eval_results_{timestamp}.json"
        with open(output_file, "w") as f:
            f.write(json_output)
        logger.info(f"Evaluation results saved to {output_file}")
    else:
        logger.info(f"Evaluation failed with status: {run.status}")
```
