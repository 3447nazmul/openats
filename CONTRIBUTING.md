# Contributing to OpenATS ⚡

Thank you for your interest in contributing to **OpenATS**! We welcome bug fixes, taxonomy expansions, feature requests, documentation improvements, and UI enhancements.

## Code of Conduct & Principles
- **Privacy First**: OpenATS is 100% local and client-side. Contributions must never add external trackers, telemetry, analytics, or unsolicited network calls.
- **Zero Required Dependencies**: The core Python engine, CLI, and document extractors must remain functional with the Python 3.8+ standard library alone.

## Commit Message Conventions
To maintain a clean and readable git history, please do **not** rewrite shared commit history. Instead, commit in small, atomic steps using standard [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` A new user-facing feature or enhancement (e.g. `feat: add Rust frameworks to taxonomy`)
- `fix:` A bug fix in scoring, parsing, CLI, or UI (e.g. `fix: prevent duplicate keyword counts in longest-match extraction`)
- `docs:` Documentation changes, README updates, or changelog entries (e.g. `docs: update CLI usage examples`)
- `test:` Adding or updating unit tests and quality control checks (e.g. `test: add unit tests for multi-column PDF audit`)
- `refactor:` Code refactoring with no behavior or scoring changes
- `chore:` Maintenance, packaging, or release configuration

## Development Workflow
1. Fork the repository and create your feature branch:
   ```bash
   git checkout -b feat/my-new-feature
   ```
2. Make your improvements in `openats/` or `scripts/`.
3. If taxonomy skills, aliases, or action verbs were modified, regenerate the web bundle:
   ```bash
   python3 scripts/build_web_data.py
   node scripts/parity_check.js
   ```
4. Run the Quality Control test suite:
   ```bash
   python3 run_qc_suite.py
   ```
   *All tests must pass with 0 errors or failures before submitting a Pull Request.*
5. Commit your changes with a conventional commit message:
   ```bash
   git commit -m "feat: add support for custom keyword thresholds"
   ```
6. Push to your branch and open a Pull Request on GitHub!
