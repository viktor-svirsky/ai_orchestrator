# AI Orchestrator

AI Orchestrator is a modular Python CLI tool that unifies multiple AI providers (Ollama, Claude, Gemini) into a single interface. It enables intelligent workflows, from simple parallel queries to complex autonomous development pipelines with checkpoint/resume capabilities.

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Features

- **Multi-Provider Support:** Seamlessly integrates Ollama (local), Claude, and Gemini with intelligent fallback
- **Async & Parallel:** Queries multiple models simultaneously for optimal performance
- **Smart Mode:** Uses a second model (Claude) to verify the output of a local model (Ollama)
- **Panel Mode:** Aggregates drafts from all models and uses a "Curator" to synthesize the best final answer
- **Workflow Mode:** An autonomous "Plan -> Code -> Test -> Review -> Refine -> Document" pipeline where models are assigned specialized roles (Architect, Developer, QA, Reviewer)
- **Checkpoint/Resume:** Workflow state is saved at each step, allowing continuation after interruptions
- **Configurable:** YAML-based configuration for providers, timeouts, and workflow behavior
- **Type-Safe:** Comprehensive type hints for better code reliability
- **Tested:** Unit and integration tests with continuous testing support

## Prerequisites

- **Python 3.8+**
- **At least one AI provider CLI tool** installed and authenticated:
  - `ollama` - For local models (recommended for fast mode)
  - `claude` - Anthropic CLI
  - `gemini` - Google Gemini CLI
- **Optional:** `make` for using the Makefile commands

## Installation

### Quick Install

1.  Clone the repository:

    ```bash
    git clone <repository_url>
    cd ai_orchestrator
    ```

2.  Install dependencies:

    ```bash
    pip install -r requirements.txt
    # OR using make
    make install
    ```

3.  Ensure at least one AI provider CLI tool is in your system PATH:
    ```bash
    make check-providers  # Check which providers are available
    ```

### Development Install

For development with testing and linting tools:

```bash
make install-dev
# OR
pip install -e ".[dev]"
```

### Package Install

Install as a package:

```bash
python setup.py install
# Then use as:
ai-orchestrator "Your prompt here"
```

## Configuration

The tool can be configured via `config.yaml` or environment variables:

```yaml
# config.yaml example
providers:
  ollama:
    model: "qwen3-coder:480b-cloud"
    timeout: 300

workflow:
  enable_checkpoints: true
  checkpoint_dir: "./checkpoints"
```

Environment variables:

- `OLLAMA_MODEL` - Override default Ollama model
- `AI_ORCHESTRATOR_TIMEOUT` - Override default timeout
- `AI_ORCHESTRATOR_MODE` - Override default mode

## Usage

Run the script using `python3`:

```bash
python3 ai_orchestrator.py [PROMPT] --mode [MODE] [OPTIONS]
```

### Options

- `--mode` - Operation mode: `fast`, `smart`, `all`, `panel`, `workflow` (default: `workflow`)
- `--fast` - Shortcut for `--mode fast`
- `--timeout` - Timeout per provider in seconds (default: 300)
- `--curator` - Curator model for panel mode (default: `claude`)
- `--output-dir` - Directory to save workflow results
- `--quiet`, `-q` - Disable progress logging

### Modes

#### 1. Workflow Mode (Default)

Assigns roles (Planner, Coder, Tester, Reviewer, Documenter) to create a robust end-to-end solution.

- **Plan:** Architect creates a step-by-step plan.
- **Code:** Developer writes the implementation.
- **Test:** QA Engineer generates a unit test suite.
- **Review:** Lead Dev reviews code and tests.
- **Refine:** Developer fixes issues based on feedback.
- **Document:** Writer creates a README snippet.

```bash
python3 ai_orchestrator.py "Create a Python script to parse CSV files"
# Optional: Save results to a folder
python3 ai_orchestrator.py "..." --output-dir ./my_project
```

#### 2. Fast Mode

Uses **Ollama** (or first available provider) for a quick response.

```bash
python3 ai_orchestrator.py "Why is the sky blue?" --fast
# Equivalent to: --mode fast
```

#### 3. Smart Mode

Asks **Ollama** first, then asks **Claude** to verify and correct the answer.

```bash
python3 ai_orchestrator.py "Explain quantum entanglement" --mode smart
```

#### 4. Parallel Mode (`all`)

Queries **Ollama**, **Claude**, and **Gemini** simultaneously.

```bash
python3 ai_orchestrator.py "Write a haiku about coding" --mode all
```

#### 5. Panel Mode

Gather drafts from all "worker" models, then a "Curator" synthesizes the best final answer.

```bash
python3 ai_orchestrator.py "Best practices for Microservices" --mode panel --curator claude
```

## Project Structure

```
ai_orchestrator/
├── ai_orchestrator.py           # Main script and Orchestrator logic
├── checkpoint_manager.py        # Checkpoint/resume functionality
├── config.yaml                  # Configuration file
├── setup.py                     # Package setup
├── requirements.txt             # Python dependencies
├── Makefile                     # Build and test automation
├── .gitignore                   # Git ignore rules
├── tests/
│   ├── test_ai_orchestrator.py # Unit tests
│   └── test_workflow.py        # Workflow tests
├── logs/
│   └── checkpoint_log.json     # Improvement tracking log
└── README.md                   # This documentation
```

## Running Tests

### Using Make (Recommended)

```bash
# Run all tests
make test

# Run specific test suites
make test-unit
make test-workflow

# Run tests with coverage
make test-cov

# Run CI checks (format check + lint + tests)
make ci_unit_lint
```

### Using Python Directly

```bash
# Run all tests
python3 tests/test_ai_orchestrator.py
python3 tests/test_workflow.py

# Run with pytest (if installed)
pytest tests/ -v
```

## Code Quality

### Formatting

```bash
# Format code
make format

# Check formatting
make format-check
```

### Linting

```bash
# Run all linters
make lint

# Run specific linters
make lint-flake8
make lint-pylint
make lint-mypy
```

### Cleanup

```bash
# Clean all artifacts
make clean

# Clean specific artifacts
make clean-pyc
make clean-test
```

## Checkpoint and Resume

Workflow mode automatically saves checkpoints at each step. If interrupted, you can resume:

```bash
# Checkpoints are saved in ./checkpoints/ by default
# Resume is automatic when running the same workflow again
python3 ai_orchestrator.py "Your prompt" --mode workflow --output-dir ./my_project
```

The checkpoint system tracks:

- Planning phase results
- Generated code
- Test suites
- Review feedback
- Refined implementations
- Documentation

## Advanced Features

### Multiple Provider Fallback

If a provider is unavailable, the orchestrator automatically falls back to available providers while maintaining workflow quality.

### Role-Based Provider Assignment

Each workflow role (Planner, Coder, Tester, Reviewer, Documenter) can be assigned to specific providers based on their strengths:

- **Planning**: Claude (strategic), Gemini (creative), Ollama (fast)
- **Coding**: Gemini (code generation), Claude (quality), Ollama (speed)
- **Testing**: Gemini (comprehensive), Claude (edge cases), Ollama (quick)
- **Review**: Claude (thorough), Ollama (fast feedback), Gemini (alternative view)
- **Documentation**: Ollama (clear), Gemini (detailed), Claude (professional)

### Error Recovery

The tool includes robust error handling:

- Automatic retries with exponential backoff
- Graceful degradation when providers fail
- Non-blocking failures for non-critical steps (tests, documentation)
- Detailed error logging

## Troubleshooting

### No providers available

```bash
make check-providers  # Check which providers are installed
```

Install missing providers:

- **Ollama**: https://ollama.ai/
- **Claude**: Anthropic CLI
- **Gemini**: Google AI CLI

### Workflow timeout

Increase timeout for long-running workflows:

```bash
python3 ai_orchestrator.py "Complex prompt" --timeout 600
```

### Tests failing

```bash
# Clean and reinstall
make clean
make install-dev
make test
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `make ci_unit_lint`
5. Submit a pull request

## License

MIT License - see LICENSE file for details

## Acknowledgments

- Ollama for local AI inference
- Anthropic for Claude API
- Google for Gemini API
