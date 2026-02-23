# AGENTS.md - Guidelines for Agentic Coding Agents in Smart Document Organizer

This document provides essential guidelines for agentic coding agents working on the Smart Document Organizer repository. It includes build/lint/test commands, code style guidelines, and best practices to ensure consistent, high-quality code contributions.
ALWAYS USE THE BEST SKILLS WHEN YOU NEED THEM

You must always do the following:
    "Before making edits, gather and summarize context.",
    "Document assumptions before applying nontrivial changes.",
    "Break large tasks into verifiable subtasks.",
    "Prefer explicit and minimal code changes.",
    "When refactoring, preserve observable behavior.",
    "Evaluate edge cases and error handling paths.",
    "Produce structured design outlines for architectural work.",
    "Think before editing.",
    "Plan before refactoring.",
    "Evaluate impact radius of every change.",
    "Prefer clarity over cleverness.",
    "Avoid introducing hidden state.",
    "Avoid silent failures.",
    "Never remove logging without reason.",
    "Validate assumptions explicitly."
End of mandatory Guidance


### Python Environment Setup
- Install dependencies: `pip install -r requirements.txt`
- For development: `pip install -e .` (if pyproject.toml supports editable installs)
- Use Python 3.11+ as specified in the codebase



### Ruff (Primary Linter and Formatter)
When asked to Lint or Format this is the process:
- Lint all files: `ruff check .`
- Fix auto-fixable issues: `ruff check --fix .`
- Format code: `ruff format .`
- Lint specific file: `ruff check path/to/file.py`
- Check imports: `ruff check --select I .`

These are reccomended:
### MyPy (Type Checking)
- Type check all files: `mypy .`
- Type check specific file: `mypy path/to/file.py`
- Strict mode: `mypy --strict .`

### Other Tools

- Check for unused imports: `ruff check --select F401 .`

## Test Commands

### Pytest (Testing Framework)
- Run all tests: `pytest`
- Run tests in verbose mode: `pytest -v`
- Run tests with coverage: `pytest --cov=. --cov-report=html`
- Run a single test file: `pytest tests/test_filename.py`
- Run a single test function: `pytest tests/test_filename.py::test_function_name`
- Run tests matching a pattern: `pytest -k "test_pattern"`
- Run tests in parallel: `pytest -n auto`

### Test Structure
- Tests are located in the `tests/` directory (if it exists)
- Use descriptive test names following the pattern `test_<feature>_<scenario>`
- For integration tests, use `tests/integration/`
- For unit tests, place alongside the module or in `tests/unit/`

### Running Tests in Development
- Before committing: `pytest --tb=short`
- Continuous integration: `pytest --ci`

## Code Style Guidelines

### General Principles
- Write clean, readable, maintainable code
- Follow PEP 8 style guide with some modifications for readability
- Use type hints for all function parameters and return values
- Prefer explicit over implicit
- Keep functions small and focused (max 50 lines)
- Use descriptive variable and function names
- Avoid magic numbers; use named constants
- Write self-documenting code; use comments sparingly for complex logic

### Imports
- Use `from __future__ import annotations` at the top of all Python files
- Group imports: standard library, third-party, local modules
- Use absolute imports for local modules
- Avoid wildcard imports (`from module import *`)
- Sort imports alphabetically within groups
- Example:
  ```python
  from __future__ import annotations

  import logging
  from pathlib import Path
  from typing import Any, Dict, List

  import fastapi
  from pydantic import BaseModel

  from services.agent_service import AgentService
  ```

### Formatting
- Use Ruff for formatting (based on Black style)
- Line length: 88 characters (Black default)
- Use double quotes for strings, single quotes for character literals
- Use trailing commas in multi-line structures
- Example:
  ```python
  def process_data(
      data: Dict[str, Any],
      options: Optional[Dict[str, str]] = None,
  ) -> List[Dict[str, Any]]:
      """Process data with given options."""
      if not data:
          return []
      
      results = []
      for key, value in data.items():
          processed = process_item(key, value, options)
          results.append(processed)
      
      return results
  ```

### Types
- Use type hints for all public APIs
- Use `typing` module for complex types
- Use `Optional` for nullable types instead of `Union[Type, None]`
- Use `Any` sparingly; prefer specific types
- Example:
  ```python
  from typing import Any, Dict, List, Optional

  def analyze_text(text: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
      """Analyze text with optional configuration."""
      config = options or {}
      # ... implementation
      return {"result": "analyzed"}
  ```

### Naming Conventions
- Functions and variables: `snake_case`
- Classes: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`
- Private members: prefix with `_`
- Module-level variables: avoid unless necessary
- Examples:
  ```python
  class DocumentProcessor:
      MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
      
      def __init__(self, config: Dict[str, Any]) -> None:
          self._config = config
      
      def process_file(self, file_path: str) -> Dict[str, Any]:
          """Process a single file."""
          # implementation
          pass
      
      def _validate_file(self, file_path: str) -> bool:
          """Private method to validate file."""
          # implementation
          pass
  ```

### Error Handling
- Use try/except blocks for expected errors
- Catch specific exceptions, not bare `Exception`
- Log errors with appropriate levels
- Re-raise exceptions with context when appropriate
- Use custom exceptions for domain-specific errors
- Example:
  ```python
  import logging

  logger = logging.getLogger(__name__)

  def load_config(config_path: str) -> Dict[str, Any]:
      """Load configuration from file."""
      try:
          with open(config_path, 'r', encoding='utf-8') as f:
              config = json.load(f)
          return config
      except FileNotFoundError:
          logger.error("Configuration file not found: %s", config_path)
          raise ValueError(f"Configuration file not found: {config_path}")
      except json.JSONDecodeError as e:
          logger.error("Invalid JSON in config file: %s", e)
          raise ValueError(f"Invalid configuration file: {e}")
  ```

### Logging
- Use the standard `logging` module
- Get loggers with `logger = logging.getLogger(__name__)`
- Use appropriate log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
- Include relevant context in log messages
- Avoid logging sensitive information
- Example:
  ```python
  import logging

  logger = logging.getLogger(__name__)

  def process_document(file_path: str) -> Dict[str, Any]:
      """Process a document file."""
      logger.info("Processing document: %s", file_path)
      try:
          # processing logic
          result = {"status": "success"}
          logger.info("Document processed successfully: %s", file_path)
          return result
      except Exception as e:
          logger.error("Failed to process document %s: %s", file_path, e)
          raise
  ```

### Async/Await
- Use async functions for I/O operations
- Use `await` for async calls
- Handle cancellation properly
- Example:
  ```python
  import asyncio

  async def process_files_async(file_paths: List[str]) -> List[Dict[str, Any]]:
      """Process multiple files asynchronously."""
      tasks = [process_single_file(path) for path in file_paths]
      results = await asyncio.gather(*tasks, return_exceptions=True)
      return results

  async def process_single_file(file_path: str) -> Dict[str, Any]:
      """Process a single file asynchronously."""
      # async I/O operations here
      await asyncio.sleep(0.1)  # simulate async work
      return {"file": file_path, "processed": True}
  ```

### File Handling
- Use `pathlib.Path` for path operations
- Use context managers for file operations
- Handle encoding explicitly (UTF-8)
- Example:
  ```python
  from pathlib import Path

  def read_text_file(file_path: str) -> str:
      """Read text content from file."""
      path = Path(file_path)
      try:
          return path.read_text(encoding='utf-8')
      except FileNotFoundError:
          raise ValueError(f"File not found: {file_path}")
  ```

### API Design
- Use PydQ for GUI design
- Use Pydantic models for request/response validation
- Return structured responses with success/error fields
- Use HTTP status codes appropriately
- Example:
  ```python
  from fastapi import APIRouter, HTTPException
  from pydantic import BaseModel

  router = APIRouter()

  class ProcessRequest(BaseModel):
      file_path: str
      options: Optional[Dict[str, Any]] = None

  class ProcessResponse(BaseModel):
      success: bool
      data: Dict[str, Any]
      error: Optional[str] = None

  @router.post("/process", response_model=ProcessResponse)
  async def process_file(request: ProcessRequest) -> ProcessResponse:
      """Process a file."""
      try:
          result = await process_file_logic(request.file_path, request.options)
          return ProcessResponse(success=True, data=result)
      except Exception as e:
          raise HTTPException(status_code=500, detail=str(e))
  ```

### Database Operations
- Use async database drivers when possible
- Use context managers for connections
- Validate inputs to prevent SQL injection
- Log database operations appropriately
- Example:
  ```python
  import asyncpg

  async def get_user(user_id: int) -> Optional[Dict[str, Any]]:
      """Get user from database."""
      async with asyncpg.connect(DATABASE_URL) as conn:
          row = await conn.fetchrow(
              "SELECT id, name, email FROM users WHERE id = $1",
              user_id
          )
          return dict(row) if row else None
  ```

### Performance
- Avoid unnecessary computations in loops
- Use efficient data structures
- Cache results when appropriate
- Profile code for bottlenecks
- Use async I/O for concurrent operations

### Documentation
- Use docstrings for all public functions and classes
- Follow Google-style docstrings
- Document parameters, return values, and exceptions
- Keep documentation up-to-date

### Version Control
- Commit frequently with clear messages
- Use feature branches for new work
- Write tests before or alongside code
- Review code changes thoroughly


### Best Practices
- Always run tests before committing
- Use type checking in your IDE
- Follow the existing code patterns in the repository
- Consult existing services and modules for similar functionality
- Log important operations for debugging
- Handle errors gracefully and provide meaningful messages

This document should be updated as the codebase evolves and new patterns emerge.