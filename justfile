# Build the package
build: uv build

# Run all tests
test: uv run pytest

# Run tests for a specific file
test-file file: uv run pytest {{file}}

# Run linter
lint: uv run ruff check src/ tests/

# Check formatting without modifying files
format-check: uv run ruff format --check src/ tests/

# Run type checker
type-check: uv run pyright

# Fix lint errors automatically
lint-fix: uv run ruff check --fix src/ tests/

# Fix formatting automatically
format-fix: uv run ruff format src/ tests/

# Run all checks (type-check + lint + format-check)
check: type-check lint format-check

# Run checks, tests, then build
clean-build: check test build
