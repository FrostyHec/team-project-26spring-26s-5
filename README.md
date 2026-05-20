[![Review Assignment Due Date](https://classroom.github.com/assets/deadline-readme-button-22041afd0340ce965d47ae6ef1cefeee28c7c493a6346c4f15d667ab976d596c.svg)](https://classroom.github.com/a/py413vYq)

# SUSTech Campus Assistant

A SUSTech campus academic assistant for deadlines, course support, policy search, course recommendation, and campus news, built on a ReAct/LangGraph agent architecture.

## Architecture

```
packages/
├── core/           # ReAct engine (LangGraph + FastAPI)
├── cli/            # Command-line interface
└── gui/            # Vue3 + TypeScript frontend
```

## Quick Start

### Prerequisites

- Python ≥3.12
- Node.js ≥20
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- [pnpm](https://pnpm.io/) (Node.js package manager)
- [Task](https://taskfile.dev/) (task runner)

### Setup

```bash
# Install all dependencies
task init

# Configure environment
cp .env.example .env
# Edit .env with your OpenAI API key

# Run tests
task test
```

### Development

```bash
# Start backend API server
task dev:server

# Start Vue frontend (separate terminal)
task dev:gui
```

### Testing

```bash
# Run all checks with auto-format (development mode)
bash scripts/check.sh

# Run checks without auto-format (CI mode - for pre-commit verification)
bash scripts/check.sh --check-only

# Run only tests
task test
```

## Tech Stack

| Component | Technology |
|-----------|------------|
| Agent Engine | LangChain + LangGraph |
| Web API | FastAPI + Uvicorn |
| CLI | argparse |
| GUI Frontend | Vue3 + TypeScript + Pinia |
| Python Tooling | uv, Ruff, pytest |
| Node Tooling | pnpm, Vite, Vitest |
| Task Runner | Taskfile (go-task) |

## Documentation

See [docs/zh-CN/](docs/zh-CN/index.md) for full documentation (Chinese).
