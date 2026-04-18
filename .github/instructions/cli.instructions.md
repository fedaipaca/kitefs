---
description: "Use when working on CLI commands, Click groups, or command-line interface code for KiteFS."
applyTo: "**/cli/**,**/cli.py"
---
# CLI — Module-Specific Additions

Follows all rules in `copilot-instructions.md`.

## Command Pattern

Every command (except `init`) follows this flow:

1. Parse arguments via Click
2. Instantiate `FeatureStore`
3. Call the corresponding SDK method
4. Format and print the result
5. Handle exceptions → user-friendly message + appropriate exit code

## Exception: `kitefs init`

`init` is the only self-contained CLI command because it creates the project structure (`kitefs.yaml`, `definitions/`, etc.) before a `FeatureStore` instance can exist.

## Click Patterns

- Use `@click.group()` for the top-level `kitefs` command
- Use `@cli.command()` for subcommands (`apply`, `ingest`, `list`, etc.)
- CLI options use `kebab-case`: `--format`, `--storage-target`
- Use `click.echo()` for output, not `print()`

## Error Handling

Catch `KiteFSError` subtypes at the CLI boundary:

```python
try:
    result = fs.apply()
except KiteFSError as e:
    click.echo(f"Error: {e}", err=True)
    raise SystemExit(1)
```

## Output Formats

Commands that return structured data (e.g., `list`, `describe`) support `--format` with values like `json` and a human-readable default. The SDK method returns data; the CLI formats it.
