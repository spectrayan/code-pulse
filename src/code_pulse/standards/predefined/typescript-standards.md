# TypeScript Standards

Best practices for writing type-safe, maintainable, and high-quality TypeScript code.

## Strict Mode
- Always enable `strict` mode in `tsconfig.json` for the highest level of type safety.
- Fix all type errors instead of using `any`.

## Type Definitions
- Use `interface` for defining object shapes and `type` for unions, intersections, and aliases.
- Prefer `Record<K, V>` over generic objects when possible.

## Immutability
- Use `readonly` for properties that should not be changed after initialization.
- Prefer `const` over `let` and `var`.
- Use `ReadonlyArray<T>` or `readonly T[]` for arrays that should not be mutated.

## Null and Undefined
- Enable `strictNullChecks` to handle null and undefined values explicitly.
- Use optional chaining (`?.`) and nullish coalescing (`??`) for cleaner code.

## Classes and Interfaces
- Use Access Modifiers (`public`, `private`, `protected`) for class members.
- Use `abstract` classes for shared functionality that should not be instantiated directly.
- Ensure classes correctly `implement` required interfaces.

## Functions
- Define return types for all functions to improve documentation and catch errors.
- Use arrow functions for callbacks and closures.
- Use default parameters instead of manual null/undefined checks.

## Generics
- Use Generics for creating reusable components and functions that work with multiple types.
- Provide descriptive names for generic type parameters (e.g., `TData`, `TResponse`).

## Tooling
- Use `ESLint` with the `@typescript-eslint` plugin to enforce these standards.
- Use `Prettier` for consistent code formatting.
