# Custom Evaluator Guidance

This document describes how to create and update custom evaluators for the pytest-agent-evals plugin.

## Imports

Required imports for defining custom evaluators:

```python
from typing import Any
from pytest_agent_evals import (
    evals,
    EvaluatorResults,
    CustomCodeEvaluatorConfig,
    CustomPromptEvaluatorConfig
)
```
## 1. Custom Code Evaluators

Custom code evaluators allow you to define a Python function to grade the agent's response.

### Usage

Use the `@evals.evaluator` decorator to apply the configuration `CustomCodeEvaluatorConfig` to a test method.

```python
@evals.evaluator(CustomCodeEvaluatorConfig(name="my_evaluator", grader=my_grader_function, threshold=0.5))
def test_my_evaluator(self, evaluator_results: EvaluatorResults):
    # Verify the result of your custom evaluator
    assert evaluator_results.my_evaluator.result == "pass"
```

### Configuration Details

```python
@dataclass
class CustomCodeEvaluatorConfig:
    """
    Configuration for a custom evaluator using a Python function.

    Args:
        name: A unique name for your evaluator.
        grader: A Python function used for grading.
                See **Grader Function** below for signature details.
        threshold: The passing score threshold. Must be a float value between 0.0 and 1.0. If the grader's score is >= this value, the result is 'pass'.

    ### Grader Function
    
    The grader function must follow this signature:
    
    ```python
    def grade(sample: dict[str, Any], item: dict[str, Any]) -> float:
        ...
    ```

    **Arguments**:
    - `sample`: The output from the agent. Contains:
        - `'output_text'`: The string response.
        - `'tool_calls'`: List of tool calls made.
        - `'tool_definitions'`: List of tools available.
    - `item`: The input data row. Contains keys from your dataset (e.g., `'query'`, `'context'`).

    **Returns**:
    - A float score (e.g., 0.0 to 1.0).

    Example:
        ```python
        def length_check(sample, item):
            # Pass if response is shorter than 100 chars
            return 1.0 if len(sample['output_text']) < 100 else 0.0
            
        CustomCodeEvaluatorConfig("short_response", grader=length_check, threshold=0.9)
        ```
    """
```

## 2. Custom Prompt Evaluators

Custom prompt evaluators allow you to use an LLM as a judge with a custom prompt template.

### Usage

Use the `@evals.evaluator` decorator to apply the configuration `CustomPromptEvaluatorConfig` to a test method.

```python
@evals.evaluator(CustomPromptEvaluatorConfig(name="my_prompt_eval", prompt=MY_PROMPT_TEMPLATE, threshold=3))
def test_my_prompt_eval(self, evaluator_results: EvaluatorResults):
    # Verify the result of your custom evaluator
    assert evaluator_results.my_prompt_eval.result == "pass"
```

### Configuration Details

```python
@dataclass
class CustomPromptEvaluatorConfig:
    """
    Configuration for a custom evaluator using a prompt template.

    Args:
        name: A unique name for your evaluator (e.g., "my_style_check").
        prompt: The prompt template string or a path to a prompt file. 
                See **Template Variables** and **Output Requirements** below for details.
        threshold: The passing threshold. Can be either:
                   - `int`: A score value (e.g., 1-5). Use this when your prompt instructs the LLM to return an ordinal value. 
                     If the evaluator's score is >= this threshold, the result is 'pass'.
                   - `float`: A score value (e.g., 0.0-1.0). Use this when your prompt instructs the LLM to return a continuous value.
                     If the evaluator's score is >= this threshold, the result is 'pass'.
                   - `bool`: Use this when your prompt instructs the LLM to return a boolean value (true/false).
                     If the evaluator's returned boolean matches this threshold, the result is 'pass'.

    ### Template Variables
    
    The prompt supports the following **Jinja2 variables**:
    - `{{query}}`: The input query string (from dataset).
    - `{{response}}`: The agent's final text response.
    - `{{tool_calls}}`: List of tool calls made by the agent.
    - `{{tool_definitions}}`: List of tools available to the agent.
    - `{{context}}`, `{{ground_truth}}`: Any other columns from your dataset.

    ### Output Requirements
    
    The prompt must instruct the LLM to output a JSON object with the following keys:
    - `"result"`: The value must be one of the following:
        - `int`: A rating (e.g. 1 to 5).
        - `float`: A score (e.g. 0.0 to 1.0).
        - `bool`: A boolean (True/False).
        - `str`: A string "true" or "false".
    - `"reason"`: A brief string explanation for the score.

    Example:
        ```python
        prompt_tmpl = \"\"\"
        Score the response relevance from 1 to 5.
        
        Q: {{query}}
        A: {{response}}
        
        Output JSON format: {"result": int, "reason": str}
        \"\"\"
        
        CustomPromptEvaluatorConfig("relevance_check", prompt=prompt_tmpl, threshold=3.5)
        ```
    """
```
