# Default: list all available commands
default:
    @just --list

# Run all tests
test:
    uv run pytest

# Run tests for a specific file, with optional extra args
test-file file +args='':
    uv run pytest {{file}} {{args}}

# Check code for lint issues
lint:
    uv run ruff check src/ tests/

# Auto-fix lint issues
lint-fix:
    uv run ruff check --fix src/ tests/

# Auto-format code
format:
    uv run ruff format src/ tests/

# Check formatting without modifying files
format-check:
    uv run ruff format --check src/ tests/

# Run static type checking
type-check:
    uv run pyright

# Run type-check + lint + format-check (matches docs/copilot-instructions)
check: type-check lint format-check

# Build the package
build:
    uv build

# Remove build artifacts and caches
clear:
    rm -rf dist/ build/ .pytest_cache/ .ruff_cache/
    find . -type d -name "__pycache__" -exec rm -rf {} +
    find . -type d -name "*.egg-info" -exec rm -rf {} +

# Clear, run all checks and tests, then build (fail-fast)
clean-build: clear check test build
