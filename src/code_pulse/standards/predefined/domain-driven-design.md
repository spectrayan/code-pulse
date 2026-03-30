# Domain-Driven Design (DDD)

A software development approach that focuses on creating a model of the business domain to solve complex problems.

## Ubiquitous Language
A common language shared by both technical and non-technical stakeholders to ensure clear communication and to avoid misunderstandings.

## Bounded Contexts
Divide a large system into smaller, more manageable parts, each with its own model and language, to ensure internal consistency.

## Tactical Patterns
- **Entities**: Objects that have a distinct identity and remain the same even when their attributes change.
- **Value Objects**: Objects defined by their attributes and have no identity.
- **Aggregates**: Clusters of entities and value objects that are treated as a single unit, with an Aggregate Root managing its consistency.
- **Repositories**: Interfaces for accessing and storing aggregates to abstract away persistence details.
- **Domain Services**: Logic that doesn't naturally belong to an entity or value object, often involving multiple aggregates.

## Strategic Design
- **Context Mapping**: Defines how different bounded contexts interact and relate to each other.
- **Anti-Corruption Layer**: A layer that translates between different domain models to prevent concepts from leaking between contexts.

## Domain-Centric
The architecture should revolve around the domain model rather than the underlying database or infrastructure.
