# Default: list all available commands
default:
    @just --list

# Run the project locally
dev:
    uv run python -m kitefs

# Run all tests
test:
    uv run pytest

# Check code for lint issues
lint:
    uv run ruff check src/ tests/

# Auto-format code
format:
    uv run ruff format src/ tests/

# Check formatting without modifying files
format-check:
    uv run ruff format --check src/ tests/

# Auto-fix lint issues
fix:
    uv run ruff check --fix src/ tests/

# Run static type checking
typecheck:
    uv run pyright

# Run lint + format-check + typecheck + tests (quick pre-commit check)
check: lint format-check typecheck test

# Run all checks, if successful then build the project
build: check
    uv build

# Remove build artifacts and caches
clean:
    rm -rf dist/ build/ .pytest_cache/ .ruff_cache/
    find . -type d -name "__pycache__" -exec rm -rf {} +
    find . -type d -name "*.egg-info" -exec rm -rf {} +

# Clean then build from scratch
clean-build: clean build
