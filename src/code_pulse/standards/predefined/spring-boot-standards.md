# Spring Boot Coding Standards

## 1. Project Structure
- **Spring Initializr**: Start with standard structure. Use Maven or Gradle with standard layouts.
- **Layered Architecture**: Use standard layers: Controller, Service, Repository, DTO, Entity.
- **Main Class**: Place `@SpringBootApplication` in the root package to ensure component scanning works correctly.

## 2. Dependency Injection
- **Constructor Injection**: ALWAYS prefer constructor injection over field injection (`@Autowired` on fields).
- **Lombok**: Use `@RequiredArgsConstructor` to simplify constructor injection.
- **Interfaces**: Program to interfaces for services to allow easy mocking and swapping.

## 3. Controllers and REST
- **HTTP Methods**: Use `@GetMapping`, `@PostMapping`, `@PutMapping`, `@DeleteMapping` appropriately.
- **Status Codes**: Return correct HTTP status codes (e.g., 201 Created, 204 No Content, 404 Not Found).
- **Response Entities**: Return `ResponseEntity<T>` to have control over headers and status codes.
- **DTOs**: Never expose internal entities directly in the API. Use DTOs and a mapper (e.g., MapStruct).

## 4. Configuration
- **Externalized Config**: Use `application.yaml` or `application.properties`. Use profiles (dev, prod) for environment-specific settings.
- **ConfigurationProperties**: Use `@ConfigurationProperties` for type-safe configuration instead of `@Value`.
- **Sensible Defaults**: Provide defaults for configuration where possible.

## 5. Persistence
- **Spring Data JPA**: Use Repository interfaces. Avoid manual boilerplate for common CRUD operations.
- **Query Methods**: Use derived query methods for simple lookups. Use `@Query` for complex ones.
- **Caching**: Use `@Cacheable` for frequently accessed, rarely changing data.

## 6. Testing
- **Test Slices**: Use `@DataJpaTest`, `@WebMvcTest`, etc., for focused, faster tests.
- **Testcontainers**: Use Testcontainers for integration tests involving databases or message brokers.
- **Mocking**: Use `@MockBean` to mock external dependencies in Spring tests.

## 7. Security and Observability
- **Spring Security**: Use a stateless approach (JWT) for REST APIs. Secure all endpoints by default.
- **Actuator**: Enable Spring Boot Actuator for health checks and metrics.
- **Logging**: Use SLF4J with standard logging levels (DEBUG, INFO, WARN, ERROR).
