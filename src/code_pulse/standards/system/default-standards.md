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

## Error Handling
- Use exceptions instead of return codes; provide meaningful context in error messages
- Do not catch generic exceptions without specific handling logic
- Ensure resources (files, sockets, database connections) are always closed (e.g., using `with` or `try-finally`)

## Resource Management
- Follow RAII (Resource Acquisition Is Initialization) or language-equivalent resource management patterns
- Avoid memory leaks by ensuring all allocated resources are properly deallocated or managed by GC
- Be mindful of expensive resource creation; use pooling where appropriate

## Security
- Validate and sanitize all external inputs (e.g., user input, API responses, files)
- Avoid hardcoding secrets, API keys, or sensitive credentials; use environment variables or secret managers
- Follow the principle of least privilege for application permissions and access controls

## Concurrency
- Ensure thread safety when working with shared state or mutable data structures
- Use appropriate synchronization primitives (locks, semaphores, atomic operations) sparingly to avoid deadlocks
- Prefer immutable data structures and message-passing patterns over shared mutable state

## Performance and Scalability
- Avoid premature optimization; focus on readability first, then optimize identified bottlenecks
- Be mindful of time and space complexity, especially in core algorithms or data processing paths
- Design for scalability: ensure components can handle increased load without architectural changes

## Observability
- Include structured logging with appropriate levels (INFO, WARN, ERROR, DEBUG) and relevant context
- Instrument critical paths with metrics (e.g., latency, throughput, error rates) for monitoring
- Use unique trace IDs to follow requests across distributed system components

## Documentation
- Document complex logic, public APIs, and architectural decisions using appropriate formats (e.g., Docstrings, READMEs)
- Keep documentation up-to-date with code changes; avoid stale or misleading comments
- Use diagrams (e.g., Mermaid, UML) to explain complex workflows or system structures
