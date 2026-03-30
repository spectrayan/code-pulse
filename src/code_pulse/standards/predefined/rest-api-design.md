# REST API Design Standards

Best practices for designing, building, and maintaining scalable and user-friendly RESTful APIs.

## Resource-Based Naming
Use nouns instead of verbs for resource names (e.g., `/users`, `/orders`). Use plural nouns for collections.

## HTTP Methods
- **GET**: Retrieve a resource or collection.
- **POST**: Create a new resource.
- **PUT**: Update an existing resource (full replacement).
- **PATCH**: Partially update an existing resource.
- **DELETE**: Remove a resource.

## HTTP Status Codes
- **200 OK**: Success.
- **201 Created**: Resource successfully created.
- **204 No Content**: Success, but no response body (often used for DELETE).
- **400 Bad Request**: Invalid input.
- **401 Unauthorized**: Missing or invalid authentication.
- **403 Forbidden**: Authenticated but lacks permissions.
- **404 Not Found**: Resource not found.
- **429 Too Many Requests**: Rate limited.
- **500 Internal Server Error**: Unexpected server-side failure.

## Versioning
Include a version number in the URL (e.g., `/v1/users`) or use custom headers to ensure backward compatibility as the API evolves.

## Pagination and Filtering
For collections, provide ways to filter results (e.g., `/users?role=admin`) and paginate data (e.g., `/users?limit=10&offset=0`).

## Error Responses
Provide consistent, machine-readable error messages with unique error codes and human-readable descriptions.

## Use JSON
Use JSON as the standard data format for requests and responses.

## Security
- Use HTTPS for all communications.
- Implement robust authentication (e.g., OAuth2, JWT).
- Apply rate limiting to prevent abuse.

## Documentation
Maintain clear and comprehensive API documentation using tools like OpenAPI (Swagger) to help developers understand and use the API.
