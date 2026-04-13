# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
- Support settings panel in GUI
- Support Basic Deadline Management Functionalities 
    - import data
    - add/edit/delete deadlines
    - deadline display in 3 views (timeline, week, month)
- Deprecated Chainlit POC frontend.

## [0.1.0] - 2025-04-01
- Project Initialization:
    - Monorepo project structure with 4 packages (core, cli, poc_frontend, gui)
    - check.sh script for local validation
    - Language check script for source code
    - CI workflow for GitHub Actions
    - Full Chinese documentation
    - Taskfile.yml for task orchestration
- POC Agent Backend:
    - ReAct agent engine using LangGraph StateGraph
    - Tool registry system with decorator-based registration
    - Calculator tools (add, subtract, multiply, divide) for POC demo
    - FastAPI REST API with SSE streaming support
- POC Frontends:
    - CLI frontend with interactive chat and server modes   
    - Chainlit POC frontend with tool call visualization (deprecate in future)
    - Vue3 + TypeScript frontend with Pinia state management and SSE, event support
    - Comprehensive test suite 
