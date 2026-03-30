# OpenAPI Specification Standards

Best practices for writing and maintaining OpenAPI (formerly Swagger) specifications for RESTful APIs.

## Specification Version
Use OpenAPI 3.0 or 3.1 to take advantage of modern features like `oneOf`, `anyOf`, and improved security schemes.

## Metadata (Info Object)
- Provide a clear, descriptive `title`.
- Include a meaningful `version` that follows semantic versioning.
- Add `description` and `contact` information (e.g., `support@spectrayan.com`).

## Paths and Operations
- Each operation MUST have a unique `operationId`.
- Provide a concise `summary` and detailed `description` for every endpoint.
- Define specific `tags` to group related operations.

## Reusable Components
- Use the `components/schemas` section for data models to ensure consistency and readability.
- Use `$ref` to reference common schemas, parameters, and responses.

## Request and Response Models
- Define `required` properties for all objects.
- Use `format` (e.g., `uuid`, `email`, `date-time`) to provide additional semantic information for strings.
- Specify `example` values for all parameters and properties to improve documentation and mocking.

## Error Definitions
- Define standard error response schemas (e.g., 400, 401, 403, 404, 500).
- Ensure error schemas include machine-readable error codes and human-readable messages.

## Security Schemes
- Clearly define security requirements (e.g., `bearerAuth`, `apiKey`) in the `components/securitySchemes` section.
- Apply security globally or to specific operations as needed.

## Linting
- Use tools like `spectral` to lint the OpenAPI specification against these standards.
- Integrate specification linting into the CI/CD pipeline.
