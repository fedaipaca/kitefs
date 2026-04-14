---
description: "Use when working on CLI commands, Click groups, or command-line interface code for KiteFS."
applyTo: "**/cli/**"
---
# CLI Conventions

## Thin CLI, Fat SDK (KTD-4)

The CLI is a **thin delegation layer**. Every command (except `init`) follows this pattern:

1. Parse arguments via Click
2. Instantiate `FeatureStore`
3. Call the corresponding SDK method
4. Format and print the result
5. Handle exceptions → user-friendly error message + appropriate exit code

**No business logic in CLI commands.** Validation, registry operations, ingestion logic — all live in the SDK.

## Exception: `kitefs init`

`init` is the only self-contained CLI command because it creates the project structure (`kitefs.yaml`, `definitions/`, etc.) before a `FeatureStore` instance can exist.

## Click Patterns

- Use `@click.group()` for the top-level `kitefs` command
- Use `@cli.command()` for subcommands (`apply`, `ingest`, `list`, etc.)
- CLI options use `kebab-case`: `--format`, `--storage-target`
- Use `click.echo()` for output, not `print()`

## Error Handling

Catch `KiteFSError` subtypes at the CLI boundary and convert to user-friendly messages:

```python
try:
    result = fs.apply()
except KiteFSError as e:
    click.echo(f"Error: {e}", err=True)
    raise SystemExit(1)
```

## Output Formats

Commands that return structured data (e.g., `list`, `describe`) support `--format` with values like `json` and a human-readable default. The SDK method returns data; the CLI formats it.
