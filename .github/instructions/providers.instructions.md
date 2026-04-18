---
description: "Use when implementing or modifying storage providers, the provider ABC, LocalProvider, or AWSProvider."
applyTo: "**/providers/**,**/providers.py"
---
# Provider Layer — Module-Specific Additions

Follows all rules in `copilot-instructions.md`.

## Fine-Grained Methods

Each provider method performs a single primitive storage operation. Do not combine multiple operations into a single method.

## Isolation Rule

**Core modules (SDK, registry, validation, join engine) must never import provider-specific libraries** (e.g., `boto3`, `sqlite3`). All storage I/O is routed through the provider abstraction.

## Error Wrapping

Provider methods wrap backend-specific errors in `ProviderError`, preserving the original cause via `raise ... from e`.

## Implementations

- **`LocalProvider`**: Filesystem for offline store + registry; SQLite for online store
- **`AWSProvider`** (optional): S3 for offline store + registry; DynamoDB for online store
