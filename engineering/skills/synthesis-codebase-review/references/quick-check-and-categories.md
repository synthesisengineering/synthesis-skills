# Codebase review: quick check and category overview

The 15-minute check for any project, then a map of the 16 review categories. The full checks are in [detailed-checklist.md](detailed-checklist.md).

## Minimum Viable Review (15-Minute Quick Check)

Use this for a rapid health assessment. These are the absolute essentials that apply to ANY project.

### Security Essentials (5 minutes)
- No secrets in code: run `git log -p | grep -i "password\|secret\|api_key\|token"` — should return nothing
- Dependencies not ancient: check for critical vulnerabilities (`npm audit`, `pip-audit`, etc.)
- HTTPS only for all external communication
- Input validated before use
- Auth exists if there are users

### Code Health (5 minutes)
- It builds: clean build with no errors
- Tests exist and pass
- No obvious duplication (no copy-pasted files or massive repeated blocks)
- Readable: a new developer could understand the main flow

### Operations Essentials (5 minutes)
- README exists with instructions on how to run it
- Documented or automated deployment process
- Application produces logs
- Errors logged or sent somewhere visible
- Config externalized (no hardcoded environment-specific values)

**Quick Score: ___ / 15.** If you score <12, address the gaps before proceeding.

---

## Review Categories

The full detailed checklist is in `references/detailed-checklist.md`. Here is an overview of all 16 review categories:

### 1. Architecture & System Design
Architectural foundation, API design and contracts, service communication, data architecture. Evaluate whether the chosen patterns are appropriate for scale and team size.

### 2. Secrets, Credentials & Sensitive Data
Active secret scanning, secret type inventory, AI tool configuration files, comment-aware credential scanning, secret management, preventive controls. This section is CRITICAL for all tiers.

### 3. Code Duplication & Reusability
Duplication analysis, shared code and libraries, abstraction quality.

### 4. Code Quality, Efficiency & Optimization
Basic code quality, algorithmic efficiency, database efficiency, memory and resource efficiency, concurrency and thread safety.

### 5. Clean Code & Software Engineering Principles
Naming and readability, function design, SOLID principles, error handling, defensive programming.

### 6. Code Readability & AI/Human Maintainability
Human readability, documentation, AI and automation friendliness.

### 7. Testing
Test existence, coverage, test types (unit, integration, API, E2E, performance, security), test quality (verify tests actually test behavior, not just imports).

### 8. Security
Authentication, authorization, input validation, data protection, dependency security.

### 9. Multi-Tenancy (Tier 3+)
Tenant isolation, configuration, lifecycle.

### 10. Identity & SSO (Tier 3+)
SSO support, session management.

### 11. Scalability & Performance (Tier 2+)
Horizontal scaling, auto-scaling, response times, caching, CDN.

### 12. Reliability (Tier 2+)
Fault tolerance, data durability, backups, disaster recovery.

### 13. Observability (Tier 2+)
Logging, monitoring, alerting, distributed tracing.

### 14. Deployment & Operations
Build and deploy documentation and automation, deployment strategy, configuration management.

### 15. Licensing & Legal
Dependency licenses, intellectual property, attribution.

### 16. Developer Experience
Getting started documentation, development workflow, CI speed.

### Addenda
- **Open Source Software Addendum** — License, community docs, security policy, versioning, distribution, contribution workflow, project health, testing, documentation
- **Closed-Source Software Addendum** — Trade secret protection, vendor management, customer data protection
- **Industry-Specific Addenda** — Financial services, healthcare, e-commerce, government/public sector
