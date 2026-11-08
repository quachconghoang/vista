# Copilot instructions

Read `AGENTS.md` before making changes. This repository uses Python for idea drafting and experiments, and C++ for performance-sensitive implementations.

- Preserve behavioral parity between Python prototypes and C++ implementations.
- Follow existing project structure, formatters, linters, build settings, and test conventions.
- Prefer small, testable changes and avoid speculative abstractions.
- For optimization, establish a baseline and measure the proposed change.
- Do not add generated files, IDE metadata, build artifacts, or secrets.
- Summarize validation and any benchmark results in the final response.
