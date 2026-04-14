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

# Auto-fix lint issues
fix:
    uv run ruff check --fix src/ tests/

# Run lint + tests (quick pre-commit check)
check: lint test

# Build the package
build:
    uv build

# Remove build artifacts and caches
clean:
    rm -rf dist/ build/ .pytest_cache/ .ruff_cache/
    find . -type d -name "__pycache__" -exec rm -rf {} +
    find . -type d -name "*.egg-info" -exec rm -rf {} +

# Clean then build from scratch
clean-build: clean build
