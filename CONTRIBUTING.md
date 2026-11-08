# Contributing to Antigravity Mobile Daemon

We welcome contributions, bug fixes, and feature requests. Follow these guidelines to ensure professional, secure collaboration.

---

## Invariants & Principles

1. **Absolute Technical Honesty & Privacy**:
   - Never commit hardcoded private IP addresses, personal email addresses, machine hostnames, or authentication tokens.
   - All tests must be hermetic and execute cleanly on any environment without dependencies on specific host paths.

2. **Style & Formatting**:
   - **Strictly ZERO emojis** anywhere in code, docstrings, markdown documentation, or commit messages.
   - Adhere to PEP 8 standards with type annotations on all public functions.

---

## Development Setup

```bash
git clone https://github.com/ijstt/antigravity-mobile-daemon.git
cd antigravity-mobile-daemon

# Create virtualenv and install dependencies
uv venv .venv
source .venv/bin/activate
uv pip install -e ".[test]"

# Run tests
pytest
```

---

## Pull Request Guidelines

1. Create a descriptive feature branch from `main`.
2. Ensure all tests pass (`pytest`).
3. Commit using Conventional Commits (`feat:`, `fix:`, `docs:`, `ci:`).
4. Open a Pull Request with a clear explanation of changes and test verification.
