# Code Generator Standards

Principles for creating and using code generation tools to ensure maintainability, readability, and consistency.

## Separation of Concerns
- Generated code MUST be separated from manually written code.
- Avoid modifying generated files directly.
- Use base classes, interfaces, or partial classes (if supported) to extend generated functionality.

## Clear Ownership
- Always include a header in generated files stating that they are generated and should not be edited.
- Example: `// Generated code - do not modify manually.`

## Predictability
- Generators should be deterministic; the same input MUST always produce the same output.
- Avoid dependencies on environmental factors like the current date, time, or local file system path in the generated content.

## Template Quality
- Code generation templates SHOULD follow the project's coding standards (e.g., naming conventions, formatting).
- Use a code formatter on the generated output to ensure it matches the rest of the codebase.

## Version Control
- Decide whether to commit generated files based on the project's needs.
- If generated files are NOT committed, the generation step MUST be part of the build process.
- If generated files ARE committed, they should be clearly marked as such to avoid manual changes during code reviews.

## Error Handling
- Generators should provide clear error messages if the input (e.g., a specification file) is invalid.
- Use validation tools to check the input before starting the generation process.

## Tooling
- Prefer industry-standard tools for code generation (e.g., OpenAPI Generator, JHipster, Yeoman) over custom-built generators when possible.
- If a custom generator is necessary, use a template engine like Jinja2 or Handlebars for better maintainability.
