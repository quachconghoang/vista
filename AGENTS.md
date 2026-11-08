# AGENTS.md

## Project overview

`vista` is a research workspace with two implementation layers:

- **Python** for drafting ideas, experiments, data preparation, and reference implementations.
- **C++** for performance-critical implementations and production-quality optimization.

## Working rules

1. Inspect the repository and existing conventions before editing.
2. Keep Python prototypes easy to read and reproducible.
3. Move code to C++ only after the algorithm and behavior are understood.
4. Preserve equivalent behavior between Python and C++ implementations.
5. Prefer small, focused changes. Do not introduce dependencies without justification.
6. Add or update tests for behavior changes.
7. Run the narrowest relevant formatter, linter, build, and test commands before finishing.
8. Never commit secrets, local IDE metadata, build output, or generated files.

## Python conventions

- Use Python 3.11+ features only when the project configuration supports them.
- Prefer type hints, clear function boundaries, and deterministic experiments.
- Keep notebooks or exploratory scripts separate from reusable modules.

## C++ conventions

- Follow the C++ standard and compiler settings already used by the project.
- Prefer RAII, value semantics, const-correctness, and explicit ownership.
- Measure before optimizing; document non-obvious performance decisions.
- Keep platform-specific code isolated.

## Commit and review guidance

Explain the problem, the approach, and validation performed. For performance work, include the benchmark method and representative results when available.
