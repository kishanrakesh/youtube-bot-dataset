# Copilot Instructions for youtube-bot-dataset

## Project Overview
This repository analyzes YouTube channels and comments, focusing on bot detection and ranking. The architecture is modular, with pipelines for data fetching, processing, and analysis. Most logic is in the `app/` directory, organized by function (e.g., `pipeline/`, `models/`, `utils/`).

## Key Workflows
- **Data Fetching:**
  - Use `make fetch-trending` to fetch trending videos.
  - Use `make fetch-comments` to fetch comments for trending videos.
  - Use `make load-trending` to load trending results into the system.
- **Commenter Registration & Screenshots:**
  - Use `make register-commenters` to register channels from comments.
  - Use `make capture-screenshots` to capture channel screenshots.
- **Review:**
  - Use `make review` to launch the manual review UI.
- **End-to-End:**
  - Use `make trending-to-comments` for trending-to-comments workflow.
  - Use `make annotate` for full annotation workflow.

## Directory Structure & Patterns
- `app/` contains all core logic, split into submodules:
  - `pipeline/`: Main entry points for data workflows (invoked via Makefile).
  - `models/`: ML models and related utilities.
  - `analysis/`, `labelling/`, `parser/`: Specialized data processing.
  - `utils/`: Shared helpers.
- `env/`: Python virtual environment (do not edit).
- `raw/`: Raw data and images (input/output files).
- `screenshots/`: Output screenshots from workflows.
- `test/`: Reserved for tests (structure may be incomplete).

## Conventions & Integration
- **Makefile** is the canonical source for running workflows. Always prefer `make` targets over direct script invocation.
- **Python modules** are invoked with `python -m app.pipeline.<module>` and use CLI arguments for configuration.
- **Configurable defaults** (region, category, limits) are set in the Makefile and passed as environment variables/CLI args.
- **Data files** (CSV, PKL) are used for intermediate and final results. Paths are hardcoded in scripts or passed via CLI.
- **No explicit test runner** is present; add tests in `test/` and document how to run them if implemented.

## External Dependencies
- Python packages listed in `requirements.txt`.
- ML models loaded from `.pkl` files in the root directory.
- No cloud integration detected; local file and CLI workflows dominate.

## Example: Adding a New Pipeline Step
1. Create a new module in `app/pipeline/`.
2. Add a corresponding target in the Makefile, following the CLI pattern.
3. Document CLI arguments and expected input/output files.

## Tips for AI Agents
- Always check the Makefile for canonical workflow commands and argument patterns.
- Follow the directory structure for placing new logic.
- Use existing CLI argument conventions for new scripts.
- Reference existing modules in `app/pipeline/` for implementation examples.

---

*If any section is unclear or missing, please provide feedback to improve these instructions.*
