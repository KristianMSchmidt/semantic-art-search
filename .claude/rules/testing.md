---
paths:
  - "**/tests/**"
  - "pyproject.toml"
---

# Testing

## Framework

- **pytest with Django integration** (NOT Django's built-in test runner)
- **Test database**: Isolated `test_artsearch_dev` database
- **No coverage reporting**: Removed for faster, cleaner output

## Philosophy

- **What-focused**: Test business outcomes, not implementation details
- **Integration over unit**: Test entire pipeline flows
- **Fewer, better tests**: High-value tests that catch real problems
- **Mock expensive dependencies**: External APIs (museum APIs, Jina), remote services (Qdrant, S3), slow operations (CLIP inference)
- **Use real database**: PostgreSQL via pytest-django is fast and reliable - use `@pytest.mark.django_db` and fixtures, don't mock the ORM

### What to Mock vs What to Test Real

| Dependency | Mock? | Reason |
|------------|-------|--------|
| PostgreSQL | NO | Fast, Django handles test DB, catches real query bugs |
| Qdrant | YES | External service, network-dependent |
| S3/Linode Storage | YES | External service, costs money |
| CLIP model | YES | Slow GPU inference |
| Jina API | YES | External API, rate-limited |
| Museum APIs | SOMETIMES | Mock for unit tests, real for integration tests |

## Commands

```bash
make test              # All tests
make test-unit         # Unit tests only
make test-integration  # Integration tests only
make test-etl          # ETL tests only
make test-app          # App tests only
```

## When to Run Tests

- **ETL tests** (`make test-etl`): After changes to extractors, transformers, loaders, ETL models/services
- **App tests** (`make test-app`): After changes to artsearch views, context builders, search services
- **All tests** (`make test`): After architectural changes affecting both components

## Test Markers & Decorators

```python
@pytest.mark.unit           # Fast, no external dependencies
@pytest.mark.integration    # Broader integration tests
@pytest.django_db           # Database access needed
@pytest.fixture             # Clean test data setup
@patch                      # Mock external dependencies
@pytest.mark.parametrize    # Parameterized tests
```

All tests must work with pytest, not `python manage.py test`.

## Updating Test Database After Migrations

The test suite uses `--nomigrations` (creates from model introspection). After new migrations:

```bash
pytest etl/tests --create-db
```

**When needed:**
- After creating new migrations
- When tests fail with "column does not exist" errors
- After pulling changes with new migrations

## Configuration

**pyproject.toml flags:**
- `--reuse-db`: Reuses test database for speed
- `--nomigrations`: Uses model introspection
- `--tb=short`: Shorter tracebacks
- `-v`: Verbose output
