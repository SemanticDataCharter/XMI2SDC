# Security Policy

## Overview

XMI2SDC is a suite of agentic tools that parse UML models and interact with the SDCStudio Assembly API. Built for air-gapped, self-hosted environments, security is foundational — every design decision prioritizes least-privilege access, agent isolation, and auditability.

---

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 4.0.x   | :white_check_mark: |
| < 4.0   | :x:                |

Only the current major version (4.x.x) aligned with SDC Generation 4 receives updates.

---

## Security Model

### Agent Isolation

XMI2SDC enforces strict isolation between its agents. Each agent has a narrowly scoped toolset:

| Agent | Network Access | File Access | Description |
|---|---|---|---|
| Parser | None | Read XMI files | Parse and normalize XMI input |
| Analyzer | None | Read cache | Semantic analysis of parsed models |
| Mapper | None | Read/write cache | Type mapping rules |
| Reviewer | None | Read cache | Mapping completeness review |
| Assembler | HTTPS to SDCStudio | Read cache | Execute mapping via Assembly API |
| Orchestrator | None (delegates) | None (delegates) | Coordinates other agents |

**Critical invariant**: Only the Assembler Agent makes network calls, and only to the configured SDCStudio instance.

### Credential Scoping

| Credential | Available To | Not Available To |
|---|---|---|
| SDCStudio API key | Assembler Agent | All others |
| SDCStudio base URL | Assembler Agent | All others |

The Parser, Analyzer, Mapper, and Reviewer agents have **no credentials** — they work entirely on local files and cache.

### Input Validation

- Configuration uses `${VAR}` environment variable substitution with **fail-closed** behavior — missing variables cause an immediate error
- All tool inputs are validated via Pydantic models
- No raw file paths accepted as tool input in production mode

### Audit Trail

Every tool invocation writes a structured JSON record to an append-only audit log:
- Agent name, tool name, inputs (sanitized), outputs (summarized), timestamp, duration
- Sensitive values (API keys) are never logged
- The log is append-only — agents cannot modify or delete prior entries

---

## Air-Gapped Design

XMI2SDC is designed for air-gapped deployment:
- All LLM inference runs locally via Ollama (no cloud LLM calls)
- The only outbound network call is from the Assembler Agent to a configured SDCStudio instance
- Docker image is fully self-contained
- No telemetry or phone-home behavior (all OpenTelemetry exporters disabled)

---

## Reporting a Vulnerability

### When to Report

Please report security vulnerabilities if you discover:

- **Agent isolation bypass**: An agent accessing resources outside its defined scope
- **Credential leakage**: Credentials appearing in logs, tool outputs, or agent responses
- **Input injection**: Tool inputs that can be manipulated to access unintended resources
- **Audit log tampering**: Any way to modify or delete audit log entries
- **Network policy violation**: An agent making unauthorized network calls
- **Privilege escalation**: An agent gaining capabilities beyond its defined tools

### How to Report

**Do NOT report security vulnerabilities through public GitHub issues.**

Instead, please report via email or private message to the repository maintainer.

### What to Include

1. **Description**: Clear description of the vulnerability
2. **Affected Agent(s)**: Which agent(s) are involved
3. **Impact**: What an attacker could achieve (data access, credential theft, scope bypass)
4. **Reproduction**: Steps to reproduce the issue
5. **Suggested Fix**: If you have a proposed solution (optional)

---

## Response Process

### Timeline

1. **Acknowledgment**: Within 48 hours of report
2. **Initial Assessment**: Within 5 business days
3. **Status Update**: Every 7 days until resolved

### Severity Levels

- **Critical**: Agent isolation bypass, credential leakage, unauthorized network access (24-hour response target)
- **High**: Audit log tampering, input injection vectors (1 week resolution target)
- **Medium**: Information disclosure, configuration weaknesses (2-4 weeks resolution target)
- **Low**: Documentation gaps, minor hardening improvements (addressed in next release)

---

## Disclosure Policy

We follow coordinated disclosure practices:

1. **Private Resolution**: Work privately to understand and fix the issue
2. **Patch Development**: Create and test a fix
3. **Public Disclosure**: Publish advisory after patch is available

---

## Related Security Resources

### SDC4 Ecosystem

- [SDCStudio](https://github.com/Axius-SDC/SDCStudio) — Assembly API provider
- [SDC Agents](https://github.com/SemanticDataCharter/SDC_Agents) — Runtime agent suite

---

*Last Updated: 2026-03-16*
