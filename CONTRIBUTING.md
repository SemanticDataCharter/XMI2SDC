# Contributing to XMI2SDC

Thank you for your interest in contributing to XMI2SDC! This document provides guidelines for contributing to the project.

---

## Table of Contents

- [How Can I Contribute?](#how-can-i-contribute)
- [Getting Started](#getting-started)
- [Contribution Workflow](#contribution-workflow)
- [Development Guidelines](#development-guidelines)
- [Quality Standards](#quality-standards)
- [Review Process](#review-process)

---

## How Can I Contribute?

### Encouraged Contributions

- **Dialect support**: Add parsers for additional XMI dialects (e.g., Papyrus, StarUML)
- **Type mapping improvements**: Enhance UML-to-SDC4 type mapping rules and edge-case handling
- **Documentation**: Clarify agent specifications, fix typos, add usage examples
- **Bug reports**: Report issues with parsing, mapping, or API integration
- **Tests**: Expand test coverage, add integration tests, add dialect-specific test fixtures
- **Security improvements**: Strengthen agent isolation, audit logging, or credential handling

### Contributions Requiring Discussion

- **New agents**: Adding agents beyond the defined six requires architectural discussion
- **Breaking changes**: Modifications to ADK tool signatures, configuration format, or CLI interface
- **Credential handling**: Any changes to how agents access or store credentials
- **Network access changes**: Modifying which agents can make network calls

For these contributions, please open an issue first to discuss your proposal.

---

## Getting Started

### Prerequisites

- Python 3.11+
- Git
- A running SDCStudio instance (for integration tests)
- Familiarity with the [Google Agent Development Kit (ADK)](https://google.github.io/adk-docs/)

### Development Setup

1. **Fork the Repository**
   ```bash
   # Visit https://github.com/Axius-SDC/XMI2SDC
   # Click "Fork" to create your own copy
   ```

2. **Clone Your Fork**
   ```bash
   git clone git@github.com:YOUR_USERNAME/XMI2SDC.git
   cd XMI2SDC
   ```

3. **Create a Virtual Environment**
   ```bash
   conda create -n XMI2SDC python=3.12
   conda activate XMI2SDC
   # Or use venv:
   # python -m venv .venv && source .venv/bin/activate
   ```

4. **Install in Development Mode**
   ```bash
   pip install -e ".[dev]"
   ```

5. **Add Upstream Remote**
   ```bash
   git remote add upstream git@github.com:Axius-SDC/XMI2SDC.git
   ```

6. **Stay Updated**
   ```bash
   git fetch upstream
   git checkout dev
   git merge upstream/dev
   ```

---

## Contribution Workflow

### Branch Strategy

- **`main`**: Production code, protected (PR required)
- **`dev`**: Active development, all work targets this branch

### 1. Create an Issue

For significant changes, create an issue first:
- Describe the problem or enhancement
- Identify which agent(s) are affected
- Explain your proposed solution
- Wait for maintainer feedback

### 2. Create a Branch

```bash
git checkout dev
git pull upstream dev
git checkout -b feature/your-feature-name
```

Branch naming conventions:
- `feature/description` - New functionality or agent enhancements
- `fix/description` - Bug fixes
- `docs/description` - Documentation updates
- `security/description` - Security improvements

### 3. Make Your Changes

- Follow the [Development Guidelines](#development-guidelines) below
- Run tests locally before pushing
- Keep commits focused and atomic

### 4. Commit Your Changes

```bash
git add .
git commit -m "Brief description of changes"
```

### 5. Push and Create Pull Request

```bash
git push origin feature/your-feature-name
```

Then create a pull request targeting the `dev` branch on GitHub.

---

## Development Guidelines

### Project Structure

```
src/xmi2sdc/
├── agents/           # ADK agent definitions
├── toolsets/          # Agent tool implementations
├── common/            # Shared utilities (config, audit, cache, types)
└── cli.py             # Click CLI entry point
```

### Python Style

- Follow **PEP 8** for all Python code
- Use **Google style docstrings**
- Type hints are required for all public functions
- Maximum line length: **99 characters** (ruff + black)

### Agent Isolation Rules

When contributing agent code, respect these invariants:

1. **No agent imports another agent's code** — each agent has its own toolset
2. **Tool inputs come from function signatures only** — never accept raw file paths or connection strings as tool input; use named references from configuration
3. **Network access is explicit** — only specific agents may make HTTP calls
4. **File writes are scoped** — each agent writes only to its designated directory
5. **Credentials come from config** — never hardcode or accept credentials in tool parameters

### ADK Tool Definitions

Each tool is a Python `async def` function wrapped in `FunctionTool`. It must have:
- A clear, descriptive name following the `{agent}_{action}` convention
- Type-hinted parameters with Google-style docstring descriptions (ADK derives schemas from these)
- Return type annotation and documented return structure
- Side effects documented in the docstring (file writes, API calls)

### Testing

```bash
# Run all tests
pytest

# Run tests for a specific area
pytest tests/toolsets/

# Run with coverage
pytest --cov=xmi2sdc --cov-report=term-missing
```

**Required test categories**:
- **Unit tests**: Every tool function
- **Integration tests**: Against a running SDCStudio instance (marked with `@pytest.mark.integration`)

### Audit Log

All tool invocations must write to the structured audit log. Use the shared `audit.log_tool_call()` function — do not implement custom logging.

---

## Quality Standards

### Pull Request Requirements

1. All tests pass
2. `ruff check src/ tests/` passes
3. `black --check src/ tests/` passes
4. New tools have complete type hints and docstrings
5. New functionality has tests
6. Documentation updated if behavior changes
7. No credentials exposed in tool parameters

### Commit Messages

- Use imperative mood: "Add MagicDraw dialect support" not "Added MagicDraw dialect support"
- Reference issues where applicable: "Fix #42: Handle nullable attributes in EA export"

---

## Review Process

### What Reviewers Look For

1. **Security**: Does it maintain agent isolation boundaries?
2. **Correctness**: Do tools produce valid outputs matching their documented return types?
3. **Tests**: Are unit tests comprehensive?
4. **Documentation**: Are tool schemas and side effects documented?

### Timeline

- Initial Review: Within 5 business days
- Follow-up Reviews: Within 3 business days

---

## License & Ownership

XMI2SDC is copyright 2026 [Axius SDC, Inc.](https://axius-sdc.com/#contact) and is proprietary software. All rights reserved.

By contributing to XMI2SDC, you agree that your contributions become the property of Axius SDC, Inc. and are subject to the project's proprietary license.

---

## Questions?

- Open a [GitHub Issue](https://github.com/Axius-SDC/XMI2SDC/issues)

Thank you for contributing to XMI2SDC!
