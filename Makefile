# AI Orchestrator Makefile
# Provides commands for testing, linting, formatting, and building

PYTHON := python3
PIP := $(PYTHON) -m pip
PYTEST := $(PYTHON) -m pytest
BLACK := $(PYTHON) -m black
ISORT := $(PYTHON) -m isort
FLAKE8 := $(PYTHON) -m flake8
MYPY := $(PYTHON) -m mypy
PYLINT := $(PYTHON) -m pylint

# Source directories
SRC_DIR := .
TEST_DIR := tests
EXCLUDE_DIRS := __pycache__,*.pyc,*.pyo,*.egg-info,.git,.pytest_cache,.mypy_cache

# Colors for output
COLOR_RESET := \033[0m
COLOR_GREEN := \033[32m
COLOR_YELLOW := \033[33m
COLOR_BLUE := \033[34m

.PHONY: help
help:
	@echo "$(COLOR_BLUE)AI Orchestrator - Available Commands$(COLOR_RESET)"
	@echo ""
	@echo "$(COLOR_GREEN)Setup:$(COLOR_RESET)"
	@echo "  make install          - Install dependencies"
	@echo "  make install-dev      - Install dev dependencies"
	@echo ""
	@echo "$(COLOR_GREEN)Testing:$(COLOR_RESET)"
	@echo "  make test             - Run all tests"
	@echo "  make test-unit        - Run unit tests only"
	@echo "  make test-workflow    - Run workflow tests only"
	@echo "  make test-cov         - Run tests with coverage report"
	@echo "  make ci_unit_lint     - Run tests and linting (CI mode)"
	@echo ""
	@echo "$(COLOR_GREEN)Code Quality:$(COLOR_RESET)"
	@echo "  make lint             - Run all linters"
	@echo "  make lint-flake8      - Run flake8"
	@echo "  make lint-pylint      - Run pylint"
	@echo "  make lint-mypy        - Run mypy type checking"
	@echo "  make format           - Format code with black and isort"
	@echo "  make format-check     - Check formatting without changes"
	@echo ""
	@echo "$(COLOR_GREEN)Cleanup:$(COLOR_RESET)"
	@echo "  make clean            - Remove build artifacts and cache"
	@echo "  make clean-pyc        - Remove Python file artifacts"
	@echo "  make clean-test       - Remove test and coverage artifacts"
	@echo ""
	@echo "$(COLOR_GREEN)API:$(COLOR_RESET)"
	@echo "  make apispec          - Generate swagger spec (if applicable)"

.PHONY: install
install:
	@echo "$(COLOR_BLUE)Installing dependencies...$(COLOR_RESET)"
	$(PIP) install -r requirements.txt

.PHONY: install-dev
install-dev: install
	@echo "$(COLOR_BLUE)Installing dev dependencies...$(COLOR_RESET)"
	$(PIP) install -r requirements.txt

.PHONY: test
test:
	@echo "$(COLOR_BLUE)Running all tests...$(COLOR_RESET)"
	$(PYTEST) $(TEST_DIR) -v

.PHONY: test-unit
test-unit:
	@echo "$(COLOR_BLUE)Running unit tests...$(COLOR_RESET)"
	$(PYTEST) $(TEST_DIR)/test_ai_orchestrator.py -v

.PHONY: test-workflow
test-workflow:
	@echo "$(COLOR_BLUE)Running workflow tests...$(COLOR_RESET)"
	$(PYTEST) $(TEST_DIR)/test_workflow.py -v

.PHONY: test-cov
test-cov:
	@echo "$(COLOR_BLUE)Running tests with coverage...$(COLOR_RESET)"
	$(PYTEST) $(TEST_DIR) --cov=$(SRC_DIR) --cov-report=html --cov-report=term-missing -v
	@echo "$(COLOR_GREEN)Coverage report generated in htmlcov/index.html$(COLOR_RESET)"

.PHONY: ci_unit_lint
ci_unit_lint: format-check lint test
	@echo "$(COLOR_GREEN)CI checks passed!$(COLOR_RESET)"

.PHONY: lint
lint: lint-flake8 lint-pylint lint-mypy
	@echo "$(COLOR_GREEN)All linting passed!$(COLOR_RESET)"

.PHONY: lint-flake8
lint-flake8:
	@echo "$(COLOR_BLUE)Running flake8...$(COLOR_RESET)"
	$(FLAKE8) $(SRC_DIR) --exclude=$(EXCLUDE_DIRS) --max-line-length=120 --extend-ignore=E203,W503

.PHONY: lint-pylint
lint-pylint:
	@echo "$(COLOR_BLUE)Running pylint...$(COLOR_RESET)"
	$(PYLINT) ai_orchestrator.py --max-line-length=120 --disable=C0103,C0114,C0115,C0116,R0913,R0914,R0915 || true

.PHONY: lint-mypy
lint-mypy:
	@echo "$(COLOR_BLUE)Running mypy...$(COLOR_RESET)"
	$(MYPY) $(SRC_DIR) --ignore-missing-imports --check-untyped-defs || true

.PHONY: format
format:
	@echo "$(COLOR_BLUE)Formatting code with black...$(COLOR_RESET)"
	$(BLACK) $(SRC_DIR) --exclude '/(\.git|\.mypy_cache|\.pytest_cache|__pycache__|\.venv)/'
	@echo "$(COLOR_BLUE)Sorting imports with isort...$(COLOR_RESET)"
	$(ISORT) $(SRC_DIR) --skip-glob='*/.git/*' --skip-glob='*/__pycache__/*'
	@echo "$(COLOR_GREEN)Code formatted!$(COLOR_RESET)"

.PHONY: format-check
format-check:
	@echo "$(COLOR_BLUE)Checking code formatting...$(COLOR_RESET)"
	$(BLACK) $(SRC_DIR) --check --exclude '/(\.git|\.mypy_cache|\.pytest_cache|__pycache__|\.venv)/'
	$(ISORT) $(SRC_DIR) --check-only --skip-glob='*/.git/*' --skip-glob='*/__pycache__/*'

.PHONY: clean
clean: clean-pyc clean-test
	@echo "$(COLOR_BLUE)Cleaning build artifacts...$(COLOR_RESET)"
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf .eggs/
	find . -name '.DS_Store' -delete
	@echo "$(COLOR_GREEN)Clean complete!$(COLOR_RESET)"

.PHONY: clean-pyc
clean-pyc:
	@echo "$(COLOR_BLUE)Removing Python file artifacts...$(COLOR_RESET)"
	find . -type f -name '*.pyc' -delete
	find . -type f -name '*.pyo' -delete
	find . -type f -name '*~' -delete
	find . -type d -name '__pycache__' -exec rm -rf {} +

.PHONY: clean-test
clean-test:
	@echo "$(COLOR_BLUE)Removing test and coverage artifacts...$(COLOR_RESET)"
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf coverage.xml

.PHONY: apispec
apispec:
	@echo "$(COLOR_YELLOW)API spec generation not implemented yet$(COLOR_RESET)"
	@echo "$(COLOR_YELLOW)This project is a CLI tool without REST API$(COLOR_RESET)"

.PHONY: run-fast
run-fast:
	@echo "$(COLOR_BLUE)Running in fast mode...$(COLOR_RESET)"
	$(PYTHON) ai_orchestrator.py "$(PROMPT)" --fast

.PHONY: run-workflow
run-workflow:
	@echo "$(COLOR_BLUE)Running workflow mode...$(COLOR_RESET)"
	$(PYTHON) ai_orchestrator.py "$(PROMPT)" --mode workflow

.PHONY: check-providers
check-providers:
	@echo "$(COLOR_BLUE)Checking provider availability...$(COLOR_RESET)"
	@which ollama > /dev/null && echo "$(COLOR_GREEN)✓ ollama found$(COLOR_RESET)" || echo "$(COLOR_YELLOW)✗ ollama not found$(COLOR_RESET)"
	@which claude > /dev/null && echo "$(COLOR_GREEN)✓ claude found$(COLOR_RESET)" || echo "$(COLOR_YELLOW)✗ claude not found$(COLOR_RESET)"
	@which gemini > /dev/null && echo "$(COLOR_GREEN)✓ gemini found$(COLOR_RESET)" || echo "$(COLOR_YELLOW)✗ gemini not found$(COLOR_RESET)"
