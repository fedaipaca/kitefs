---
description: "Use when implementing or modifying the join engine or point-in-time join logic."
applyTo: "**/join/**,**/join.py"
---
# Join Engine Conventions

## Stateless Engine

The join engine receives DataFrames and configuration as arguments and returns results. It performs no I/O and holds no state. All data loading is the caller's responsibility.

## Point-in-Time Correctness (KTD-13)

Joins must enforce temporal correctness: `joined.event_timestamp ≤ base.event_timestamp`. Use backward-looking semantics — for each base row, find the most recent joined row that does not look into the future.

## Preservation of Unmatched Rows

Base rows that have no matching joined row are preserved in the output with `null` values in joined columns. No base rows are ever dropped.

## Column Conflict Resolution

When joined columns conflict with base columns, prefix the conflicting joined columns with `{joined_group_name}_`. Base columns are never renamed. The join key column is not duplicated.

## Contracts

See `docs/docs-03-03-api-contracts.md` (BB-08) for the join engine method contract. See `docs/docs-02-project-requirements.md` (FR-OFF) for the full join requirements.
