# Trinsic Test Suite Guide

Trinsic includes a comprehensive test suite to validate the financial pipeline, Excel formula exporting, and Monte Carlo simulations.

## Running Tests

### 1. Pytest Test Suite (Fast & Clean)
We use `pytest` for regular test execution. The testing configurations are defined in `pytest.ini`.

To run the core test suite (which includes 90+ validation cases verifying simple corp models, leveraged manufacturing scenarios, and stress tests):

```bash
# Run pytest quietly (configured via pytest.ini)
python -m pytest

# Run pytest with verbose details
python -m pytest -v
```

All script-style tests (`test_cross_check.py`, `test_v5_cross_check.py`, `test_monte_carlo_e2e.py`) are automatically skipped during the pytest collection phase to avoid executing slow calculations or calling `sys.exit` in the test runner.

### 2. Standalone Verification Scripts (Slow & Deep)
If you want to run the full cross-checks or deep Monte Carlo simulations directly, you can execute them as standalone Python scripts:

```bash
# Run comprehensive Excel-to-Python cross-check (V4 inputs)
python tests/test_cross_check.py

# Run comprehensive Excel-to-Python cross-check (V5 odd inputs)
python tests/test_v5_cross_check.py

# Run Monte Carlo end-to-end simulation validation
python tests/test_monte_carlo_e2e.py

# Run quick Monte Carlo seed/update checks
python tests/test_mc_update.py
```
