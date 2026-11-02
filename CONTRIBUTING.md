# Contributing

## Setup

```bash
uv venv --python 3.12 .venv
uv pip install -e ".[dev]"
```

## Checks

```bash
ruff check src tests
mypy src
pytest -q
```

CI runs the same suite on push/PR (`.github/workflows/ci.yml`).

## Local demo

```bash
curricula demo
curricula quality
curricula topics list
```

## Design rules

- Keep raw evidence, inferred structure, and generated content separated
- Never overwrite source artifacts
- Require human approval before publishing AI material
- Prefer offline-safe tests with fake adapters
