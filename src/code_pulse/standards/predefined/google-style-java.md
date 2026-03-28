# Google Java Style Guide (Summary)

Key conventions from Google's Java style guide.

## Formatting
- 2-space indentation (no tabs)
- Column limit: 100 characters
- One statement per line

## Naming
- `ClassName`, `methodName`, `localVariable`, `CONSTANT_NAME`
- Package names are all lowercase with no underscores

## Braces
Use K&R style braces. Braces are required for all control structures, even single-line bodies.

## Javadoc
Required for every public class and public/protected member. Use `@param`, `@return`, `@throws` tags.

## Best Practices
- Avoid wildcard imports
- Use `@Override` annotation consistently
- Prefer interfaces over abstract classes
- Minimize mutability; prefer immutable objects
