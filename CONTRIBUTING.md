# Contributing Guidelines

## Repository Structure

Every project follows a three-part structure:

| Component | Description |
|-----------|-------------|
| Code Repository | GitHub repo following conventions below |
| Data Storage | Git LFS for large files, or S3 bucket |
| Docker Environment | Containerized dev environment with all dependencies |

Example: [docker-hku-avenir](https://github.com/example/docker-hku-avenir)

### Why This Setup?

| Benefit | Description |
|---------|-------------|
| No System Bugs | Same dev environment eliminates "works on my machine" issues |
| Cloud Ready | Easy deployment to GPU servers like [vast.ai](https://vast.ai) |
| Industry Standard | Production-like environment gives you an edge in job applications |

## Git Workflow

### Branches

| Branch | Purpose |
|--------|---------|
| `main` | Protected, production-ready code |
| `develop` | Optional integration branch |
| `feature/*` | New features (e.g., `feature/signal-ema-tuning`) |
| `bugfix/*` | Bug fixes |
| `hotfix/*` | Urgent production fixes |
| `exp/*` | Experiments |

### Rules

| Rule | Description |
|------|-------------|
| Protected Branches | No direct pushes to `main` or `develop` |
| Pull Requests | All changes require PR with at least one reviewer |
| Commit Messages | Descriptive messages explaining what changed and why |
| Rebasing | Rebase on latest parent branch before PR to keep history linear |

## Package Management

**Preferred:** `uv`

**Alternatives:** `poetry`, `venv`

Every project must have a lock file that anyone can install to resolve dependencies consistently.

## Folder Structure

```
project-root/
├── README.md           # How to run/reproduce
├── pyproject.toml      # Dependencies + tooling
├── src/                # Clean, reusable code
├── tests/              # Test coverage (use pytest-cov)
├── examples/           # Usage examples and demos
```

## CI/CD

All projects should have GitHub Actions for automated checks on pull requests.

### Lint Checking (Required)

| Tool | Purpose |
|------|---------|
| `ruff` | Fast Python linter and formatter |
| `mypy` | Static type checking (optional but recommended) |

Example workflow (`.github/workflows/lint.yml`):

```yaml
name: Lint

on:
  pull_request:
    branches: [main, develop]
  push:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - run: uv sync --dev
      - run: uv run ruff check .
      - run: uv run ruff format --check .
```

### Library Development (Optional)

For projects developing reusable libraries or APIs, add these additional workflows:

| Workflow | Purpose |
|----------|---------|
| Tests | Run pytest on multiple Python versions |
| Build | Verify package builds correctly |
| Publish | Auto-publish to PyPI on release tags |

#### Test workflow (`.github/workflows/test.yml`):

```yaml
name: Test

on:
  pull_request:
    branches: [main, develop]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - run: uv python install ${{ matrix.python-version }}
      - run: uv sync --dev
      - run: uv run pytest --cov=src --cov-report=xml
```

#### Publish workflow (`.github/workflows/publish.yml`):

```yaml
name: Publish

on:
  release:
    types: [published]

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - run: uv build
      - run: uv publish
        env:
          UV_PUBLISH_TOKEN: ${{ secrets.PYPI_TOKEN }}
```

> **Note:** Set up `PYPI_TOKEN` in repository secrets before using the publish workflow.
