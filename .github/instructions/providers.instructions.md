---
description: "Use when implementing or modifying storage providers, the provider ABC, LocalProvider, or AWSProvider."
applyTo: "**/providers/**,**/providers.py"
---
# Provider Layer

## ABC, Not Protocol (KTD-14)

The provider interface uses `ABC` with `@abstractmethod`, not `Protocol`. This gives immediate `TypeError` at instantiation if a method is missing. See `docs/docs-03-03-api-contracts.md` (BB-09) for the exact interface contract and method signatures.

## Fine-Grained Methods (KTD-15)

Each provider method performs a single primitive storage operation. Do not combine multiple operations into a single method. Refer to `docs/docs-03-03-api-contracts.md` for the full method list.

## Isolation Rule

**Core modules (SDK, registry, validation, join engine) must never import provider-specific libraries** (e.g., `boto3`, `sqlite3` in non-provider code). All storage I/O is routed through the provider abstraction.

## Error Wrapping

Provider methods wrap backend-specific errors in `ProviderError`, preserving the original cause via `raise ... from e`. Every error message must be actionable (NFR-UX-001): what failed, what input caused it, how to fix it.

## Implementations

- **`LocalProvider`**: Filesystem for offline store + registry; SQLite for online store
- **`AWSProvider`** (optional): S3 for offline store + registry; DynamoDB for online store
