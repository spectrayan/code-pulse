# OWASP Secure Coding Practices

Summary of key secure coding guidelines from the OWASP foundation.

## Input Validation
Validate all input from untrusted sources. Use allowlists over denylists. Validate data type, length, and range.

## Output Encoding
Encode output based on context (HTML, URL, JavaScript, SQL) to prevent injection attacks.

## Authentication & Session Management
Use proven authentication frameworks. Enforce strong passwords. Protect session tokens.

## Access Control
Deny by default. Enforce access control on every request. Use principle of least privilege.

## Error Handling & Logging
Do not expose sensitive information in error messages. Log security-relevant events with sufficient detail.

## Data Protection
Encrypt sensitive data at rest and in transit. Do not store secrets in source code. Use parameterized queries.
