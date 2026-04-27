# Contributing to mcpguard

Thanks for wanting to contribute! mcpguard is a security tool, so we value clarity, simplicity, and correctness above all else.

## Getting Started

```bash
git clone https://github.com/regstrtn/mcpguard.git
cd mcpguard

python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Development Workflow

1. **Create a branch** from `main`:
   ```bash
   git checkout -b your-feature
   ```

2. **Make your changes.** Follow the coding principles below.

3. **Run tests** (all must pass):
   ```bash
   pytest tests/ -v
   ```

4. **Submit a pull request** with a clear description of what changed and why.

## Coding Principles

- **Readable over clever.** If a reviewer can't understand a function in 30 seconds, rewrite it.
- **Small functions.** Each function does one thing.
- **No magic.** Prefer explicit over implicit. Name things clearly. Comment *why*, not *what*.
- **No new dependencies** without discussion. mcpguard is a security tool — it should be lightweight and auditable.

## Project Structure

```
mcpguard/
├── mcpguard/          # Source code
│   ├── cli.py         # Click CLI commands
│   ├── policy.py      # Policy engine (YAML → evaluation)
│   ├── proxy.py       # MCP stdio proxy
│   ├── middleware.py   # FastMCP middleware
│   ├── audit.py       # JSON-lines audit logger
│   ├── approval.py    # Interactive TTY approval
│   ├── dashboard.py   # HTML stats dashboard
│   └── exceptions.py  # Custom exceptions
├── tests/             # pytest test suite
├── policies/          # Example policy templates
├── mcpguard.yaml      # Default policy (source of truth)
└── docs/              # Build spec and documentation
```

## Writing Tests

- Put tests in `tests/test_<module>.py`.
- Use `pytest` with `pytest-asyncio` for async tests.
- Aim for test coverage on all new functionality.
- Use `tempfile` for any files created during tests — clean up in fixtures.

## Adding a New Policy Rule Type

1. Add the matching logic in `PolicyEngine._rule_matches()` in `policy.py`.
2. Add tests in `tests/test_policy.py`.
3. Document in `docs/policy-reference.md`.
4. Add an example to `mcpguard.yaml` if it's commonly useful.

## Adding a New CLI Command

1. Add the command in `mcpguard/cli.py` using Click.
2. Add subprocess tests in `tests/test_e2e.py`.
3. Update `README.md` with usage examples.

## Style

- Python 3.10+, type hints everywhere.
- `ruff` for linting.
- `mypy` for type checking.
- No line length limit, but keep lines reasonable (~100 chars).

## Security

If you find a security vulnerability, please **do not** open a public issue. Email the maintainer directly.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
