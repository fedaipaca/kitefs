---
description: "Use when implementing or modifying the FeatureStore SDK class or its orchestration logic."
applyTo: "**/sdk/**,**/sdk.py"
---
# SDK (FeatureStore) Conventions

## Thin Orchestration Only (KTD-4)

`FeatureStore` is the orchestration layer. It delegates all work to the appropriate manager or engine:

- **Registry operations** → BB-04 (Registry Manager)
- **Validation** → BB-05 (Validation Engine)
- **Offline read/write** → BB-06 (Offline Store Manager)
- **Online read/write** → BB-07 (Online Store Manager)
- **Joins** → BB-08 (Join Engine)

The SDK must never contain validation logic, storage I/O, or join algorithms directly.

## Provider Isolation

The SDK accesses storage exclusively through the provider layer (BB-09). Never import filesystem, database, or cloud libraries in the SDK module.

## Method Contracts

See `docs/docs-03-03-api-contracts.md` for all SDK method signatures, parameters, and return types. See `docs/docs-00-02-flow-charts.md` for the step-by-step flow of each operation.
