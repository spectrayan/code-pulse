# Angular Standards

Best practices for building scalable, maintainable, and high-performance Angular applications.

## Project Structure
- Follow the official Angular style guide for folder structure (e.g., `core`, `shared`, `features`).
- Use feature-based folders to group related components, services, and modules.

## Component Design
- Keep components small and focused on a single responsibility.
- Use `@Input()` and `@Output()` for communication between components.
- Use Change Detection Strategy `OnPush` for improved performance.

## Modules and Routing
- Use Lazy Loading for feature modules to reduce the initial bundle size.
- Define routes in separate routing modules for each feature.

## Dependency Injection
- Use `providedIn: 'root'` for singleton services.
- Prefer constructor injection over manual injection using `inject()`.

## State Management
- Use `RxJS` for reactive programming and state management.
- For complex applications, consider using a dedicated state management library like `NgRx`, `NGXS`, or `Akita`.

## Testing
- Write unit tests for all components, services, and pipes using `Jasmine` and `Karma` or `Jest`.
- Use `Cypress` or `Playwright` for end-to-end testing.

## Security
- Use Angular's built-in security features to prevent common vulnerabilities like Cross-Site Scripting (XSS).
- Sanitize user-provided content using `DomSanitizer`.

## Styling
- Use SCSS for more flexible and maintainable styles.
- Follow the BEM (Block, Element, Modifier) methodology for naming CSS classes.
- Use Angular's component-scoped styling to avoid global style leakage.
