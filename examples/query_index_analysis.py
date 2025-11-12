#!/usr/bin/env python3
"""
Query Index Analysis Example

Demonstrates how to use the query analyzer to identify missing indexes
and generate index creation statements for CouchDB.
"""

import json
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker
from sqlalchemy_couchdb.client import SyncCouchDBClient
from sqlalchemy_couchdb.query_analyzer import QueryAnalyzer, IndexAnalysisReport


def example_1_basic_analysis():
    """
    Example 1: Analyze a simple query with filters and sorting.
    """
    print("=" * 80)
    print("Example 1: Basic Query Analysis")
    print("=" * 80)
    print()

    # Simulated compiled query (normally this comes from the compiler)
    query_json = json.dumps({
        "type": "select",
        "table": "audit_logs",
        "selector": {
            "type": "audit_logs",
            "$and": [
                {"log_type": "operation"},
                {"tenant_id": "019976df-0628-7c46-a896-81d3f290a7df"}
            ]
        },
        "sort": [{"create_time": "desc"}],
        "limit": 20
    })

    # Analyze the query
    analyzer = QueryAnalyzer()
    analysis, recommendation = analyzer.analyze_and_recommend(query_json)

    # Print analysis results
    print("Query Analysis:")
    print(f"  Table: {analysis.table}")
    print(f"  Filter fields: {', '.join(sorted(analysis.selector_fields))}")
    print(f"  Sort fields: {', '.join(analysis.sort_fields)}")
    print()

    # Generate and print report
    report = IndexAnalysisReport()
    if recommendation:
        report.add_recommendation(recommendation)
        print(report.generate_report(format="text"))


def example_2_using_client():
    """
    Example 2: Use the client's built-in analysis method.
    """
    print("\n" + "=" * 80)
    print("Example 2: Using Client API")
    print("=" * 80)
    print()

    # Create a CouchDB client
    client = SyncCouchDBClient(
        host="localhost",
        port=5984,
        username="admin",
        password="password",
        database="audit_logs"
    )

    # Simulated compiled query
    query_json = json.dumps({
        "type": "select",
        "table": "users",
        "selector": {
            "type": "users",
            "age": {"$gt": 25},
            "status": "active"
        },
        "sort": [{"created_at": "desc"}, {"name": "asc"}],
        "limit": 50
    })

    # Generate analysis report
    print("Text Format:")
    print(client.analyze_query_index_needs(query_json, format="text"))

    print("\nMarkdown Format:")
    print(client.analyze_query_index_needs(query_json, format="markdown"))

    print("\nJSON Format:")
    print(client.analyze_query_index_needs(query_json, format="json"))


def example_3_intercepting_errors():
    """
    Example 3: Intercept `no_usable_index` errors and generate recommendations.
    """
    print("\n" + "=" * 80)
    print("Example 3: Error-Driven Analysis")
    print("=" * 80)
    print()

    # Simulated error scenario
    error_message = """
    Bad request: HTTP 400: {"error":"no_usable_index",
    "reason":"No index exists for this sort, try indexing by the sort fields."}
    """

    # The query that caused the error
    failing_query = json.dumps({
        "type": "select",
        "table": "audit_logs",
        "selector": {
            "type": "audit_logs",
            "$and": [
                {"log_type": "operation"},
                {"tenant_id": "019976df-0628-7c46-a896-81d3f290a7df"}
            ]
        },
        "fields": ["_id", "log_type", "tenant_id", "create_time"],
        "limit": 20,
        "sort": [{"create_time": "desc"}]
    })

    print("Error occurred:")
    print(error_message)
    print()

    # Analyze the failing query
    analyzer = QueryAnalyzer()
    analysis, recommendation = analyzer.analyze_and_recommend(failing_query)

    report = IndexAnalysisReport()
    if recommendation:
        report.add_recommendation(recommendation)
        print("Recommended Fix:")
        print(report.generate_report(format="text"))


def example_4_batch_analysis():
    """
    Example 4: Analyze multiple queries and prioritize recommendations.
    """
    print("\n" + "=" * 80)
    print("Example 4: Batch Query Analysis")
    print("=" * 80)
    print()

    # Multiple queries to analyze
    queries = [
        json.dumps({
            "type": "select",
            "table": "orders",
            "selector": {"type": "orders", "status": "pending", "customer_id": "12345"},
            "sort": [{"order_date": "desc"}]
        }),
        json.dumps({
            "type": "select",
            "table": "products",
            "selector": {"type": "products", "category": "electronics", "in_stock": True},
            "sort": [{"price": "asc"}, {"rating": "desc"}]
        }),
        json.dumps({
            "type": "select",
            "table": "users",
            "selector": {"type": "users", "last_login": {"$gt": "2025-01-01"}}
        })
    ]

    analyzer = QueryAnalyzer()
    report = IndexAnalysisReport()

    # Analyze all queries
    for i, query in enumerate(queries, 1):
        analysis, recommendation = analyzer.analyze_and_recommend(query)
        if recommendation:
            report.add_recommendation(recommendation)

    # Generate consolidated report (sorted by priority)
    print("Consolidated Index Recommendations:")
    print(report.generate_report(format="markdown"))


def example_5_custom_analysis():
    """
    Example 5: Custom analysis logic for advanced scenarios.
    """
    print("\n" + "=" * 80)
    print("Example 5: Custom Analysis")
    print("=" * 80)
    print()

    query_json = json.dumps({
        "type": "select",
        "table": "events",
        "selector": {
            "type": "events",
            "$and": [
                {"event_type": "click"},
                {"user_id": {"$in": ["user1", "user2", "user3"]}},
                {"timestamp": {"$gte": "2025-01-01", "$lte": "2025-01-31"}}
            ]
        },
        "sort": [{"timestamp": "desc"}]
    })

    analyzer = QueryAnalyzer()
    analysis = analyzer.analyze_query(query_json)

    print("Detailed Analysis:")
    print(f"  Table: {analysis.table}")
    print(f"  Query Type: {analysis.query_type}")
    print(f"  Filter Fields: {sorted(analysis.selector_fields)}")
    print(f"  Sort Fields: {analysis.sort_fields}")
    print()
    print("Raw Selector:")
    print(json.dumps(analysis.selector, indent=2))
    print()

    # Generate recommendation
    recommendation = analyzer.recommend_index(analysis)
    if recommendation:
        print(f"Recommended Index Fields: {recommendation.fields}")
        print(f"Priority: {recommendation.priority}/10")
        print(f"Reason: {recommendation.reason}")
        print()
        print("Index DDL:")
        print(json.dumps(recommendation.ddl, indent=2))


if __name__ == "__main__":
    # Run all examples
    example_1_basic_analysis()
    example_2_using_client()
    example_3_intercepting_errors()
    example_4_batch_analysis()
    example_5_custom_analysis()

    print("\n" + "=" * 80)
    print("All examples completed!")
    print("=" * 80)
