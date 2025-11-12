# Query Index Analysis Feature

## Overview

The Query Index Analysis feature analyzes Mango queries to identify missing indexes and generates index creation statements for CouchDB. This helps optimize query performance by ensuring proper indexes exist.

## Key Features

- **Automatic Field Extraction**: Analyzes `selector` and `sort` clauses to identify required fields
- **Index Recommendations**: Generates CouchDB-compatible index creation JSON
- **Multiple Report Formats**: Outputs in text, Markdown, or JSON format
- **Priority Scoring**: Ranks recommendations by importance
- **Batch Analysis**: Process multiple queries to find common indexing needs

## Installation

This feature is included in the `sqlalchemy-couchdb` package:

```bash
pip install sqlalchemy-couchdb
```

## Quick Start

### Using the Client API

```python
from sqlalchemy_couchdb.client import SyncCouchDBClient
import json

# Create client
client = SyncCouchDBClient(
    host="localhost",
    port=5984,
    username="admin",
    password="password",
    database="mydb"
)

# Your compiled query (from the SQL compiler)
query = json.dumps({
    "type": "select",
    "table": "audit_logs",
    "selector": {
        "type": "audit_logs",
        "log_type": "operation",
        "tenant_id": "12345"
    },
    "sort": [{"create_time": "desc"}]
})

# Generate analysis report
report = client.analyze_query_index_needs(query, format="text")
print(report)
```

### Using the QueryAnalyzer Directly

```python
from sqlalchemy_couchdb.query_analyzer import QueryAnalyzer, IndexAnalysisReport

analyzer = QueryAnalyzer()
analysis, recommendation = analyzer.analyze_and_recommend(query)

if recommendation:
    report = IndexAnalysisReport()
    report.add_recommendation(recommendation)
    print(report.generate_report(format="markdown"))
```

## How It Works

### 1. Query Analysis

The analyzer extracts fields from two sources:

**Selector Fields** (from WHERE clauses):
```json
{
  "selector": {
    "log_type": "operation",  // ← extracted
    "tenant_id": "12345",     // ← extracted
    "age": {"$gt": 25}         // ← extracted
  }
}
```

**Sort Fields** (from ORDER BY clauses):
```json
{
  "sort": [
    {"create_time": "desc"},  // ← extracted
    {"name": "asc"}            // ← extracted
  ]
}
```

### 2. Index Recommendation Logic

CouchDB requires indexes to follow specific rules:

1. **Filter fields come first**: Fields used in `selector`
2. **Sort fields come last**: Fields used in `sort`
3. **Order matters**: The index field order must match query patterns

Example:
```python
# Query filters by log_type and tenant_id, sorts by create_time
# Recommended index: ["log_type", "tenant_id", "create_time"]
```

### 3. DDL Generation

The analyzer generates CouchDB-compatible index JSON:

```json
{
  "index": {
    "fields": ["log_type", "tenant_id", "create_time"]
  },
  "name": "idx_audit_logs_log_type_tenant_id_create_time",
  "type": "json",
  "ddoc": "_design/idx_audit_logs_log_type_tenant_id_create_time"
}
```

## Report Formats

### Text Format

```
================================================================================
CouchDB Index Recommendations
================================================================================

Recommendation #1 (Priority: 8/10)
--------------------------------------------------------------------------------
Table: audit_logs
Fields: log_type, tenant_id, create_time
Reason: Filters on: log_type, tenant_id; Sorts by: create_time

Index creation JSON:
{
  "index": {
    "fields": ["log_type", "tenant_id", "create_time"]
  },
  "name": "idx_audit_logs_log_type_tenant_id_create_time",
  "type": "json"
}

To create this index, POST the above JSON to:
  http://<couchdb-host>:5984/audit_logs/_index

Example using curl:
curl -X POST http://localhost:5984/audit_logs/_index \
  -H 'Content-Type: application/json' \
  -d '{...}'
```

### Markdown Format

Perfect for documentation or GitHub issues:

```markdown
# CouchDB Index Recommendations

## Recommendation #1 (Priority: 8/10)

**Table:** `audit_logs`
**Fields:** `log_type, tenant_id, create_time`
**Reason:** Filters on: log_type, tenant_id; Sorts by: create_time

### Index Creation JSON
```json
{...}
```

### How to Apply
POST the above JSON to: `http://<couchdb-host>:5984/audit_logs/_index`
```

### JSON Format

Machine-readable for automation:

```json
{
  "recommendations": [
    {
      "table": "audit_logs",
      "fields": ["log_type", "tenant_id", "create_time"],
      "reason": "Filters on: log_type, tenant_id; Sorts by: create_time",
      "priority": 8,
      "ddl": {...}
    }
  ]
}
```

## Common Use Cases

### 1. Debugging "no_usable_index" Errors

When CouchDB throws a `no_usable_index` error:

```python
try:
    result = session.execute(query)
except OperationalError as e:
    if "no_usable_index" in str(e):
        # Get the compiled query from the error or re-compile
        report = client.analyze_query_index_needs(compiled_query)
        print("Fix the error by creating this index:")
        print(report)
```

### 2. Preventive Index Analysis

Before deploying new queries:

```python
# Analyze all queries in your application
queries = [
    compile_query("SELECT * FROM users WHERE age > 25 ORDER BY name"),
    compile_query("SELECT * FROM orders WHERE status = 'pending'"),
    # ... more queries
]

report = IndexAnalysisReport()
analyzer = QueryAnalyzer()

for query in queries:
    _, recommendation = analyzer.analyze_and_recommend(query)
    if recommendation:
        report.add_recommendation(recommendation)

# Get prioritized list of all needed indexes
print(report.generate_report(format="markdown"))
```

### 3. CI/CD Integration

Automatically check for missing indexes in your CI pipeline:

```python
import sys

analyzer = QueryAnalyzer()
problems = []

for query_file in query_files:
    query = read_query(query_file)
    _, recommendation = analyzer.analyze_and_recommend(query)

    if recommendation:
        # Check if index exists in CouchDB
        if not index_exists(recommendation.ddl):
            problems.append(f"{query_file}: Missing index {recommendation.fields}")

if problems:
    print("\n".join(problems))
    sys.exit(1)  # Fail the build
```

## API Reference

### QueryAnalyzer

#### `analyze_query(compiled_query: str) -> QueryAnalysis`

Analyzes a compiled query and extracts field usage.

**Parameters:**
- `compiled_query`: JSON string containing the Mango query

**Returns:** `QueryAnalysis` object with:
- `selector_fields`: Set of fields used in filters
- `sort_fields`: List of fields used in sorting
- `table`: Table name
- `query_type`: Query type (select, update, etc.)

#### `recommend_index(analysis: QueryAnalysis) -> Optional[IndexRecommendation]`

Generates index recommendation based on analysis.

**Returns:** `IndexRecommendation` object with:
- `fields`: List of index fields in order
- `table`: Table name
- `reason`: Explanation of why this index is needed
- `ddl`: CouchDB index creation JSON
- `priority`: Score from 1-10

#### `analyze_and_recommend(compiled_query: str) -> Tuple[QueryAnalysis, Optional[IndexRecommendation]]`

Convenience method combining both operations.

### Client Methods

#### `client.analyze_query_index_needs(compiled_query: str, format: str = "text") -> str`

High-level API for generating reports.

**Parameters:**
- `compiled_query`: JSON string of the Mango query
- `format`: Output format ("text", "json", or "markdown")

**Returns:** Formatted report string

### IndexAnalysisReport

#### `add_recommendation(recommendation: IndexRecommendation) -> None`

Adds a recommendation to the report.

#### `generate_report(format: str = "text") -> str`

Generates formatted report.

## Advanced Topics

### Complex Selectors

The analyzer handles nested logical operators:

```json
{
  "selector": {
    "$and": [
      {"field1": "value1"},
      {"$or": [
        {"field2": "value2"},
        {"field3": "value3"}
      ]}
    ]
  }
}
```

Extracted fields: `field1`, `field2`, `field3`

### Priority Scoring

Priority is calculated based on:

- **Base priority**: 5
- **+3 if has sorting**: Sorting requires indexes
- **+2 if multiple filters**: Complex queries benefit more
- **Max priority**: 10

### System Fields

The following fields are automatically excluded from index recommendations:
- `_id`
- `_rev`
- `type`

These are CouchDB system fields that don't need explicit indexing.

## Limitations

1. **Static Analysis**: Analyzes query structure, not runtime performance
2. **No Cardinality Info**: Cannot determine optimal field order based on data distribution
3. **CouchDB Specific**: Recommendations are for Mango Query indexes only
4. **No Existing Index Check**: Doesn't query CouchDB to see if indexes already exist

## Examples

See `examples/query_index_analysis.py` for comprehensive examples covering:

1. Basic query analysis
2. Using client API
3. Error-driven analysis
4. Batch analysis
5. Custom analysis logic

Run the examples:

```bash
python examples/query_index_analysis.py
```

## Best Practices

### 1. Analyze Before Deploying

Always analyze new queries before deploying to production:

```python
# Development
report = client.analyze_query_index_needs(new_query)
if "No index recommendations" not in report:
    print("⚠️  Warning: This query needs an index!")
    print(report)
```

### 2. Batch Similar Queries

Group queries by table to find common indexing patterns:

```python
from collections import defaultdict

by_table = defaultdict(list)
for query in all_queries:
    analysis, rec = analyzer.analyze_and_recommend(query)
    if rec:
        by_table[rec.table].append(rec)

# Create composite indexes covering multiple queries
for table, recs in by_table.items():
    # Find common field patterns
    common_fields = find_common_fields(recs)
    print(f"{table}: Consider index on {common_fields}")
```

### 3. Document Index Rationale

Use the generated Markdown reports in your documentation:

```python
report = analyzer.generate_report(format="markdown")
with open("docs/indexes.md", "a") as f:
    f.write(report)
```

### 4. Monitor Performance

After creating indexes, verify they're being used:

```bash
# Check CouchDB's explain endpoint
curl -X POST http://localhost:5984/mydb/_explain \
  -H 'Content-Type: application/json' \
  -d '{"selector": {...}}'
```

## Troubleshooting

### "No index recommendations"

This means:
- Query has no filters or sorting, OR
- All fields are system fields (`_id`, `_rev`, `type`)

### Recommended index doesn't solve the error

Possible causes:
1. **Field order**: CouchDB is sensitive to field order in indexes
2. **Partial index**: Query uses more fields than detected
3. **Type conflicts**: Field types don't match index types

Solution: Check CouchDB's `_explain` endpoint to see what indexes it expects.

### Priority seems wrong

Priority is a heuristic based on query structure. You can:
1. Manually adjust priorities in your application
2. Use domain knowledge to override recommendations
3. Focus on queries causing actual errors first

## Contributing

To improve the analysis feature:

1. **Add test cases**: See `tests/test_query_analyzer.py`
2. **Improve heuristics**: Update priority calculation in `QueryAnalyzer.recommend_index()`
3. **Support more operators**: Extend `_extract_selector_fields()` for new Mango operators

## License

This feature is part of sqlalchemy-couchdb and follows the same license.
