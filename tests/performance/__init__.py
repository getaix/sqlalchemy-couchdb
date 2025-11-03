"""
Performance tests for hybrid architecture

This package contains performance comparison tests between CouchDB and RDBMS.

To run performance tests:
    pytest tests/performance/ -v --benchmark-only

To generate performance report:
    pytest tests/performance/ --benchmark-only --benchmark-autosave

Requirements:
    pip install pytest-benchmark
"""
