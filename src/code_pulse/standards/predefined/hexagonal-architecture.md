# Hexagonal Architecture (Ports and Adapters)

A design pattern that aims to create loosely coupled application components that can be easily connected to their software environment by means of ports and adapters.

## Core Application Logic
The heart of the application should be isolated from external concerns (databases, UI, external APIs). It defines business rules and entities.

## Ports (Interfaces)
The application communicates with the outside world through ports. Ports are interfaces that define the operations the application can perform (Output Ports) and those that the outside world can trigger (Input Ports).

## Adapters (Implementations)
Adapters implement or use the ports to bridge the gap between the application core and external technologies. 
- **Primary (Driving) Adapters**: Trigger actions in the application (e.g., Controllers, CLI).
- **Secondary (Driven) Adapters**: Are used by the application (e.g., Repositories, External API Clients).

## Dependency Inversion
Dependencies must always point inwards, toward the application core. The core should not depend on external libraries or frameworks (where possible).

## Decoupled Testing
The application core should be testable in isolation from infrastructure components like databases and web servers by using mocks or stubs for the ports.
