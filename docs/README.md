## Purpose

This file explains how to read `docs`. It provides the document map, reading order, and authority rules for the migrated KiteFS documentation.

## Owns

- How to read `docs`.
- Document map.
- Authority rules.
- Reading order.

## Does Not Own

- Any project explanation in detail.

## Document Map

- [00-project-context.md](00-project-context.md) - Problem statement, vision, goals, non-goals, personas, and project scope.
- [01-reference-use-case.md](01-reference-use-case.md) - Turkish real estate reference use case and concrete examples.
- [02-product-requirements.md](02-product-requirements.md) - Functional requirements, non-functional requirements, acceptance criteria, priorities, and constraints.
- [03-system-behavior.md](03-system-behavior.md) - End-to-end operation behavior, common rules, and Mermaid flow diagrams.
- [04-architecture.md](04-architecture.md) - Architectural design principles, system boundaries, building blocks, dependency direction, provider abstraction boundary, and packaging model.
- [05-data-and-storage-contracts.md](05-data-and-storage-contracts.md) - Registry schema, storage layouts, file naming, online store schemas, type mapping, and partition strategy.
- [06-api-and-cli-contracts.md](06-api-and-cli-contracts.md) - Public Python API, SDK and CLI contracts, exceptions, and internal provider interfaces.
- [07-implementation-plan.md](07-implementation-plan.md) - Implementation phases, tasks, status, scope, dependencies, and deliverables.
- [Glossary.md](Glossary.md) - Domain terms, abbreviations, and short definitions used across `docs`.

## Reading Order

1. Start here to understand the document map and authority rules.
2. Read [00-project-context.md](00-project-context.md) for project context.
3. Read [01-reference-use-case.md](01-reference-use-case.md) for the concrete reference example.
4. Read [02-product-requirements.md](02-product-requirements.md) through [06-api-and-cli-contracts.md](06-api-and-cli-contracts.md) in order for requirements, behavior, architecture, storage contracts, and API contracts.
5. Use [07-implementation-plan.md](07-implementation-plan.md) for the implementation phases, tasks, status, scope, dependencies.
6. Use [Glossary.md](Glossary.md) whenever a term or abbreviation needs definition.

## Authority Rules

When two files mention the same topic, the authoritative file wins. Other files may summarize or reference, but must not contradict the authority.

| Topic                                               | Authoritative File                                                   |
| --------------------------------------------------- | -------------------------------------------------------------------- |
| Problem statement                                   | [00-project-context.md](00-project-context.md)                       |
| Reference use case to high level real life behavior | [01-reference-use-case.md](01-reference-use-case.md)                 |
| What KiteFS must do (requirements)                  | [02-product-requirements.md](02-product-requirements.md)             |
| How each operation behaves step-by-step             | [03-system-behavior.md](03-system-behavior.md)                       |
| System structure, components, and boundaries        | [04-architecture.md](04-architecture.md)                             |
| Storage formats, schemas, and layouts               | [05-data-and-storage-contracts.md](05-data-and-storage-contracts.md) |
| Public SDK signatures, CLI commands, and exceptions | [06-api-and-cli-contracts.md](06-api-and-cli-contracts.md)           |
| Implementation sequencing and task scope            | [07-implementation-plan.md](07-implementation-plan.md)               |
| Domain terms and definitions                        | [Glossary.md](Glossary.md)                                           |
