#!/bin/bash
set -e

# Activate virtual environment if needed
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Install test dependencies
pip install -r tests/requirements-test.txt

# Use test environment file
export ENV_FILE="tests/.env.test"

# Run the tests with coverage
python -m pytest tests/ \
    --cov=app \
    --cov-report=term \
    --cov-report=html:coverage_report \
    $@

# Display test coverage summary
echo "Test coverage summary:"
python -m coverage report 