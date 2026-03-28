# CodePulse Default Coding Standards

These are the built-in system standards used by CodePulse for semantic code evaluation.

## Readability
- Code should be self-documenting with clear variable and function names
- Avoid deeply nested control structures (max 3 levels recommended)
- Keep lines under 120 characters where possible

## Naming Conventions
- Use descriptive, intention-revealing names for variables, functions, and classes
- Avoid single-letter names except for loop counters or well-known conventions
- Be consistent with the naming style of the language (e.g., snake_case for Python, camelCase for JS)

## Function Length
- Functions should do one thing and do it well
- Aim for functions under 30 lines; flag functions over 50 lines
- Extract helper functions when a function handles multiple responsibilities

## Complexity Thresholds
- Cyclomatic complexity per function: target ≤ 10, flag > 15
- Cognitive complexity: prefer flat, linear control flow
- Avoid functions with more than 5 parameters
