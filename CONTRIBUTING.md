# Contributing

Thank you for contributing! Here's how to get started.

## Setup

```bash
# Install dependencies
uv sync --group dev

# Install pre-commit hooks
uv run pre-commit install
```

## Development

### Tests
```bash
uv run pytest                    # Run all tests
uv run pytest --cov=tabular2mcap # With coverage
```

### Linting & Formatting
```bash
uv run ruff check . --fix        # Lint and auto-fix
uv run ruff format .             # Format code
```

### Type Checking (optional)
```bash
uv run mypy tabular2mcap/ --ignore-missing-imports
```

### Documentation
```bash
uv sync --group docs             # Install docs dependencies
uv run mkdocs serve              # Preview at localhost:8000
```

### Foxglove JSON Schema Updates

JSON schemas are included in the repo to avoid download caching. To update to the latest version:
```bash
cd tabular2mcap/external
uv run python update_foxglove_schema.py
```

## Pull Request Process

1. Fork the repository and create a feature branch
2. Make changes following the code style below
3. Add tests for new features
4. Run `ruff check . --fix && ruff format .`
5. Push and open a PR with a clear description

### Code Style

- **Line length**: 88 characters
- **Quotes**: Double quotes
- **Imports**: Auto-sorted by Ruff
- **Type hints**: Encouraged

### CI Requirements

PRs must pass:

- ✅ Ruff linting and formatting
- ✅ Tests on Python 3.10, 3.11, 3.12
- ✅ Tests on Ubuntu, macOS, Windows

## Questions?

Open an issue if you need help!
