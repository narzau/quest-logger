# QuestLogger Tests

This directory contains comprehensive tests for the QuestLogger backend application. The test suite focuses on ensuring the reliability and correctness of critical features such as note management and subscription handling.

## Test Structure

The tests are organized into the following directories:

- `api/`: API integration tests for endpoints
- `unit/`: Unit tests for individual components and services
- `conftest.py`: Shared test fixtures and configuration

## Running Tests

### Using the test script

The easiest way to run all tests is using the provided script:

```bash
./scripts/run_tests.sh
```

This script:

1. Activates the virtual environment (if exists)
2. Installs test dependencies
3. Sets up testing environment variables
4. Runs all tests with coverage reporting

### Running specific tests

To run specific test categories:

```bash
# Run only API tests
./scripts/run_tests.sh -m api

# Run only unit tests
./scripts/run_tests.sh -m unit

# Run a specific test file
./scripts/run_tests.sh tests/api/test_notes.py

# Run a specific test class or function
./scripts/run_tests.sh tests/api/test_notes.py::TestNotesAPI::test_create_note_success
```

## Testing Philosophy

### Critical Features

We prioritize thorough testing of mission-critical features:

1. **Notes API**: As the core feature of QuestLogger
2. **Subscription Management**: Due to its sensitive nature (handling payments)
3. **Voice Processing**: Ensuring consistent and high-quality note generation

### Mock vs. Integration

- **Unit Tests**: Use mocking for external services (Stripe, OpenAI, Deepgram)
- **API Tests**: Test the full request lifecycle, but still mock external services
- Webhooks and third-party integrations require special testing approaches

## Adding New Tests

When adding new tests, follow these guidelines:

1. **Categorize properly**: Add unit tests for isolated components, API tests for endpoints
2. **Handle external dependencies**: Always mock external services
3. **Test edge cases**: Include tests for error conditions and edge cases
4. **Subscription features**: Always test with both Free and Pro subscription tiers

## Test Coverage

We aim for high test coverage of critical paths:

- Run `./scripts/run_tests.sh` to generate a coverage report
- Review the HTML report in `coverage_report/index.html`
- Focus on improving coverage for subscription and payment-related code
