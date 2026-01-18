# AI Orchestrator - Quick Reference Card

⚡ Fast access to common commands and workflows

---

## 🚀 Quick Start

```bash
# Install dependencies
make install

# Check which AI providers are available
make check-providers

# Run a quick test
python3 ai_orchestrator.py "Hello world" --fast
```

---

## 📦 Installation

```bash
# Standard install
pip install -r requirements.txt

# Development install (with testing tools)
make install-dev

# Package install
python3 setup.py install
```

---

## 🎯 Common Usage Patterns

### Fast Mode (Quick Answers)
```bash
python3 ai_orchestrator.py "Why is the sky blue?" --fast
```

### Smart Mode (Verified Answers)
```bash
python3 ai_orchestrator.py "Explain quantum computing" --mode smart
```

### Workflow Mode (Full Development Pipeline)
```bash
python3 ai_orchestrator.py "Create a CSV parser" --mode workflow --output-dir ./my_project
```

### Panel Mode (Multiple Perspectives)
```bash
python3 ai_orchestrator.py "Best practices for APIs" --mode panel --curator claude
```

### Parallel Mode (All Providers)
```bash
python3 ai_orchestrator.py "Write a haiku" --mode all
```

---

## 🧪 Testing Commands

```bash
# Run all tests
make test

# Run with coverage
make test-cov

# Run specific test suite
make test-unit
make test-workflow

# CI mode (tests + linting)
make ci_unit_lint
```

---

## 🔧 Code Quality

```bash
# Format code (black + isort)
make format

# Check formatting without changes
make format-check

# Run all linters
make lint

# Run specific linter
make lint-flake8
make lint-pylint
make lint-mypy
```

---

## 🧹 Cleanup

```bash
# Clean all artifacts
make clean

# Clean only Python cache
make clean-pyc

# Clean only test artifacts
make clean-test
```

---

## ⚙️ Configuration

### Environment Variables
```bash
export OLLAMA_MODEL="qwen3-coder:480b-cloud"
export AI_ORCHESTRATOR_TIMEOUT=600
export AI_ORCHESTRATOR_MODE=workflow
```

### Config File
Edit `config.yaml`:
```yaml
providers:
  ollama:
    model: "your-model-here"
    timeout: 300

workflow:
  enable_checkpoints: true
```

---

## 🔄 Checkpoint/Resume

### Automatic Resume
```bash
# Run workflow (creates checkpoints)
python3 ai_orchestrator.py "Complex task" --output-dir ./project

# If interrupted, rerun same command to resume
python3 ai_orchestrator.py "Complex task" --output-dir ./project
```

### Checkpoint Files
- Location: `./checkpoints/checkpoint_*.json`
- Contains: All workflow step results
- Resume: Automatic on rerun

---

## 📊 Workflow Steps

1. **Planning** - Architect creates implementation plan
2. **Coding** - Developer writes the code
3. **Testing** - QA generates test suite
4. **Reviewing** - Lead developer reviews quality
5. **Refining** - Developer fixes issues (if needed)
6. **Documenting** - Writer creates documentation

All steps save output to `--output-dir` if specified.

---

## 🛠️ Troubleshooting

### No Providers Available
```bash
make check-providers  # See what's installed
```

Install missing providers:
- **Ollama**: https://ollama.ai/
- **Claude**: Anthropic CLI
- **Gemini**: Google AI CLI

### Timeout Issues
```bash
# Increase timeout to 10 minutes
python3 ai_orchestrator.py "Task" --timeout 600
```

### Test Failures
```bash
make clean
make install-dev
make test
```

---

## 📁 Project Structure

```
ai_orchestrator/
├── ai_orchestrator.py       # Main CLI tool
├── checkpoint_manager.py    # Checkpoint system
├── config.yaml              # Configuration
├── requirements.txt         # Dependencies
├── Makefile                 # Build commands
├── setup.py                 # Package setup
├── tests/                   # Test suite
├── logs/                    # Progress logs
└── README.md                # Full documentation
```

---

## 🎓 Examples

### Example 1: Create a Python Module
```bash
python3 ai_orchestrator.py \
  "Create a Python module for JSON validation with tests" \
  --mode workflow \
  --output-dir ./json_validator
```

Output files:
- `1_plan.txt` - Implementation plan
- `2_code.txt` - Python code
- `3_tests.txt` - Test suite
- `4_review.txt` - Code review
- `5_final_code.txt` - Refined code
- `6_README.md` - Documentation

### Example 2: Get Multiple Opinions
```bash
python3 ai_orchestrator.py \
  "What are the best practices for REST API design?" \
  --mode panel \
  --curator claude
```

### Example 3: Quick Answer
```bash
python3 ai_orchestrator.py \
  "How do I reverse a string in Python?" \
  --fast
```

---

## 📚 Further Reading

- **Full Documentation**: `README.md`
- **Improvements Summary**: `logs/IMPROVEMENTS_SUMMARY.md`
- **Completion Report**: `logs/COMPLETION_REPORT.txt`
- **Checkpoint Log**: `logs/checkpoint_log.json`

---

## 🆘 Help

```bash
# Show all available options
python3 ai_orchestrator.py --help

# Show Makefile commands
make help
```

---

## 📝 Notes

- **Default Mode**: workflow
- **Default Timeout**: 300 seconds
- **Checkpoint Auto-Save**: Enabled in workflow mode
- **Provider Fallback**: Automatic if provider unavailable
- **Non-Critical Failures**: Tests and docs are non-blocking

---

**Version**: 1.0.0
**Last Updated**: 2025-01-22
**License**: MIT
