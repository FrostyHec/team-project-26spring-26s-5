# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Monorepo project structure with 4 packages (core, cli, poc_frontend, gui)
- ReAct agent engine using LangGraph StateGraph
- Tool registry system with decorator-based registration
- Calculator tools (add, subtract, multiply, divide) for POC demo
- FastAPI REST API with SSE streaming support
- CLI frontend with interactive chat and server modes
- Chainlit POC frontend with tool call visualization
- Vue3 + TypeScript frontend with Pinia state management
- Comprehensive test suite (38 Python + 15 Vue tests)
- Taskfile.yml for task orchestration
- check.sh and ci-local.sh scripts for local validation
- Language check script for source code
- CI workflow for GitHub Actions
- Full Chinese documentation
