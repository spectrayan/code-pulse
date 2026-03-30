# Python Standards

Best practices for writing clean, efficient, and idiomatic Python code.

## PEP 8 Adherence
- Follow the official PEP 8 style guide for indentation, line length, and naming conventions.
- Use tools like `flake8` or `ruff` to enforce PEP 8.

## Type Hinting
- Use type hints (`typing` module) for function signatures and variable declarations to improve code readability and catch errors early.
- Use static type checkers like `mypy` or `pyright`.

## Error Handling
- Use specific exception classes instead of broad `Exception` or `BaseException`.
- Use `try...except...finally` for resource management or the `with` statement.

## Concurrency
- Use `asyncio` for I/O-bound tasks.
- Use `multiprocessing` for CPU-bound tasks.
- Avoid using `threading` for CPU-bound tasks due to the Global Interpreter Lock (GIL).

## Dependency Management
- Use `pyproject.toml` for project configuration and dependencies.
- Use tools like `poetry`, `uv`, or `pipenv` for environment and dependency management.

## Testing
- Use `pytest` for writing and running unit and integration tests.
- Follow the AAA (Arrange, Act, Assert) pattern.

## Docstrings
- Use Google or NumPy style docstrings for classes and functions.
- Include descriptions of parameters, return types, and potential exceptions.

## Iterators and Generators
- Use list comprehensions, generator expressions, and built-in functions (e.g., `map`, `filter`) for more concise and efficient code.
- Prefer generators over large lists to save memory.
