# Performance Test Suite

This directory contains comprehensive performance tests for the MongoDB backend, specifically designed to validate the performance improvements from replacing deprecated PyMongo 2.x methods with modern PyMongo 3.x equivalents.

## Overview

The performance test suite (`test_performance.py`) measures:

1. **Single Write Performance**: Individual record write operations
2. **Bulk Write Performance**: Batch write operations with multiple records
3. **Sequential Write Consistency**: Validates that writes don't have random delays
4. **Sustained Write Throughput**: Tests performance over extended periods
5. **Delete Operation Performance**: Both single and bulk delete operations
6. **Functional Regression Tests**: Ensures correctness after performance changes

## Running Tests

### In GitHub Actions (Recommended)

Performance tests automatically run in GitHub Actions when:
- A PR is labeled with `performance` or `to be merged`
- Manually triggered via workflow dispatch

The tests run across multiple MongoDB versions (3.0, 5.0, 8.0) to ensure consistent performance improvements.

### Locally (Tests Will Skip)

Performance tests are designed to run only in GitHub Actions CI environment. When run locally, they will be skipped with the message:

```
Performance tests only run in GitHub Actions (GITHUB_ACTIONS env var not set)
```

To force local execution (not recommended for accurate measurements):
```bash
export GITHUB_ACTIONS=true
python -m pytest tests/test_performance.py -v
```

## Test Reports

### Console Output

Tests generate detailed console reports showing:
- Summary statistics (average improvement, speedup factors)
- Detailed comparisons between test runs
- Per-operation metrics (mean, median, min/max, standard deviation)
- Throughput measurements (operations per second)

### JSON Reports

A `performance_report.json` file is generated containing:
- Test run metadata (timestamp, environment, Python version)
- Summary statistics
- Detailed metrics for each operation
- Performance comparisons
- Statistical analysis (mean, median, stdev, etc.)

### GitHub Actions Integration

Performance reports are:
1. Uploaded as workflow artifacts (retained for 30 days)
2. Displayed in the workflow summary page
3. Published as test result comments on PRs

## Performance Metrics

### Key Metrics Measured

1. **Duration**: Time taken for each operation
2. **Throughput**: Operations per second
3. **Consistency**: Standard deviation and coefficient of variation
4. **Improvement**: Percentage improvement over baseline
5. **Speedup**: Factor of performance improvement

### Expected Results

After replacing deprecated methods with modern equivalents:
- ✅ Single writes should complete in < 100ms
- ✅ Bulk writes (100 records) should complete in < 1 second
- ✅ Sequential writes should have CV < 50% (consistent performance)
- ✅ No extreme outliers (max time < 5x mean time)
- ✅ Sustained throughput should remain stable across batches

## Test Architecture

### PerformanceTestModel

A simple test model with basic fields:
- `name`: Character field
- `value`: Integer field  
- `description`: Text field
- `active`: Boolean field with default

### PerformanceMetrics Class

Handles:
- Recording individual operation timings
- Calculating statistics (mean, median, stdev, etc.)
- Generating comparisons between implementations
- Creating formatted reports (console and JSON)
- Artifact generation for CI

### Test Classes

1. **TestWritePerformance**: Core performance measurements
2. **TestPerformanceRegression**: Functional correctness validation

## Interpreting Results

### Good Performance Indicators

- Low mean duration
- Low standard deviation (consistent timing)
- High throughput (ops/sec)
- Positive improvement percentages
- Speedup factors > 1.0

### Warning Signs

- High coefficient of variation (> 50%)
- Extreme outliers (max >> mean)
- Decreasing throughput over time
- Negative improvement percentages

## Contributing

When adding new performance tests:

1. Use the `@unittest.skipIf(SKIP_IF_NOT_CI, SKIP_REASON)` decorator
2. Record metrics using `PerformanceMetrics.record_operation()`
3. Add meaningful assertions with descriptive failure messages
4. Include the test in the performance report generation
5. Update this README with new test descriptions

## Continuous Monitoring

Performance tests run automatically on every PR with the `to be merged` label, ensuring:
- No performance regressions are introduced
- Improvements are validated across MongoDB versions
- Historical performance data is tracked
- Performance issues are caught early

## Environment Variables

Required for GitHub Actions:
- `GITHUB_ACTIONS`: Set to "true" to enable tests
- `PYTHON_VERSION`: Python version being tested
- `MONGO_VERSION`: MongoDB version being tested
- Standard ERP environment variables (see workflow files)

## References

- [PyMongo 3.x Migration Guide](https://pymongo.readthedocs.io/en/stable/migrate-to-pymongo3.html)
- [MongoDB Performance Best Practices](https://docs.mongodb.com/manual/administration/analyzing-mongodb-performance/)
