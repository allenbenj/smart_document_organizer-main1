# AI Contribution Guide

## Overview

This folder has many python scripts for various model functionalities.:

- **modelLab**: a shared library
- **tests**: python unit tests for modelLab
- **tests/assets**: assets for python unit tests

## Programming Principles

### Code Organization
- **Reusability**: Extract common functionality into reusable components
- **Direct Modification**: Directly modify code files when possible, instead of writing scripts to modify them
- **Don't Repeat yourself**: When adding new logic, don't copy paste existing code if possible. If new logic is similar to existing logic, prefer to extract and generalize existing code to utilities or other common places and re-use them in the new code.

## Testing and Validation

### Compilation Testing

```bash
pytest ./tests --verbose
```

### Testing Strategy
- **Incremental Testing**: Only check compilation for the parts you have changed after you finish editing
- **Requirements**: Code must compile successfully

---

**Note for AI Assistants**: This project follows strict architectural patterns and coding standards. Always prioritize code maintainability, follow the established conventions, and ensure compilation success before considering any task complete.
