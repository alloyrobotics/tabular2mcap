# Contributing to tabular2mcap

Thank you for your interest in contributing! This guide will help you set up your development environment and understand our workflow.

## Development Setup

### 1. Install Dependencies

We use `uv` for dependency management:

```bash
# Install all dependencies including dev tools
uv sync --dev
```

### 2. Install Pre-commit Hooks

Pre-commit hooks automatically check your code before each commit:

```bash
uv run pre-commit install
```

## Development Workflow

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=tabular2mcap --cov-report=term

# Run specific test
uv run pytest tests/test_mcap_conversion.py::test_mcap_conversion
```

### Code Quality Tools

#### Linting and Formatting

We use [Ruff](https://docs.astral.sh/ruff/) for both linting and formatting:

```bash
# Check for linting issues
uv run ruff check .

# Auto-fix issues
uv run ruff check . --fix

# Format code
uv run ruff format .

# Run both
uv run ruff check . --fix && uv run ruff format .
```

#### Type Checking

We use `mypy` for static type checking:

```bash
uv run mypy tabular2mcap/ --ignore-missing-imports --no-strict-optional
```

Note: Type checking is informational and won't block commits while we improve coverage.

### Pre-commit Hooks

Pre-commit hooks run automatically before each commit. They will:
- ✅ Auto-fix code formatting with Ruff
- ✅ Check for common issues (trailing whitespace, file endings, etc.)
- ✅ Run type checking (informational only)

To manually run all hooks:

```bash
# Run on all files
uv run pre-commit run --all-files

# Run on staged files only
uv run pre-commit run
```

To skip hooks (not recommended):

```bash
git commit --no-verify
```

## Pull Request Process

1. **Fork and Clone**: Fork the repository and clone your fork
2. **Create a Branch**: Create a feature branch from `main`
3. **Make Changes**: Write code following our style guidelines
4. **Test**: Ensure all tests pass and add tests for new features
5. **Lint**: Run `ruff check . --fix` and `ruff format .`
6. **Commit**: Commit with clear, descriptive messages
7. **Push**: Push to your fork
8. **PR**: Open a pull request with a clear description

## Code Style

- **Line length**: 88 characters (Black-compatible)
- **Quotes**: Double quotes for strings
- **Imports**: Sorted automatically by Ruff (isort compatible)
- **Type hints**: Encouraged but not required

## CI/CD

All pull requests must pass:
- ✅ Ruff linting and formatting checks
- ✅ All tests on Python 3.10, 3.11, 3.12
- ✅ Tests on Ubuntu, macOS, and Windows

The CI pipeline runs automatically on all PRs and pushes to main branches.

## Questions?

Feel free to open an issue if you have questions or need help!
