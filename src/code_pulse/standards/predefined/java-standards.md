# Java Coding Standards

## 1. General Principles
- **Naming Conventions**: Follow standard Java naming conventions (PascalCase for classes, camelCase for methods/variables, UPPER_SNAKE_CASE for constants).
- **Encapsulation**: Use private fields with public/protected getters/setters where appropriate. Favor immutability.
- **Documentation**: Use Javadoc for public APIs. Explain the *why*, not just the *what*.

## 2. Code Structure
- **Package Organization**: Organize classes by feature or domain, not by technical type (e.g., `com.app.user` instead of `com.app.controllers`).
- **Class Size**: Keep classes focused and small. Follow the Single Responsibility Principle.
- **Method Length**: Aim for short methods (usually < 20 lines) that do one thing.

## 3. Modern Java Features
- **Streams API**: Use Streams for collection processing for better readability and parallelism potential.
- **Optionals**: Use `Optional` for return types that might be empty. Avoid returning `null`.
- **Records**: Use `record` for transparent data carriers (Java 14+).
- **Var**: Use `var` for local variables when the type is obvious from the initializer.

## 4. Exception Handling
- **Specific Exceptions**: Catch and throw specific exceptions, not `Exception` or `Throwable`.
- **Custom Exceptions**: Create custom exceptions for domain-specific errors.
- **Resource Management**: Use try-with-resources for all `AutoCloseable` resources.

## 5. Performance and Memory
- **StringBuilder**: Use `StringBuilder` for string concatenation in loops.
- **Collections Choice**: Choose the right collection type (e.g., `ArrayList` vs `LinkedList`, `HashMap` vs `TreeMap`).
- **Minimize Object Creation**: Reuse objects where it makes sense, but don't sacrifice readability.

## 6. Concurrency
- **Utility Classes**: Use `java.util.concurrent` utilities instead of manual `wait()` and `notify()`.
- **Thread Safety**: Ensure shared mutable state is properly synchronized or uses atomic variables.
- **Virtual Threads**: Consider using Virtual Threads (Project Loom) for I/O bound tasks in modern Java.
