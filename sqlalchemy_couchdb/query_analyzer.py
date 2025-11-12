"""Query Analyzer Module

Analyzes Mango queries to extract field requirements and generate
index recommendations for CouchDB.
"""

import json
from typing import Any, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field


@dataclass
class QueryAnalysis:
    """
    Query analysis result containing extracted fields and metadata.
    """

    # Fields used in selector (filter conditions)
    selector_fields: Set[str] = field(default_factory=set)

    # Fields used in sorting
    sort_fields: List[str] = field(default_factory=list)

    # The table name
    table: Optional[str] = None

    # Query type (select, update, delete, etc.)
    query_type: Optional[str] = None

    # Raw selector JSON
    selector: Dict[str, Any] = field(default_factory=dict)

    # Raw sort array
    sort: Optional[List[Dict[str, str]]] = None


@dataclass
class IndexRecommendation:
    """
    Index recommendation with DDL statement.
    """

    # Fields to include in the index (in order)
    fields: List[str]

    # The table this index is for
    table: str

    # Reason for recommending this index
    reason: str

    # CouchDB index creation JSON
    ddl: Dict[str, Any]

    # Priority: higher means more important (1-10)
    priority: int = 5


class QueryAnalyzer:
    """
    Analyzes compiled Mango queries to extract field usage and generate
    index recommendations.
    """

    # System fields that should not be indexed explicitly
    SYSTEM_FIELDS = {"_id", "_rev", "type"}

    def __init__(self):
        """Initialize the query analyzer."""
        pass

    def analyze_query(self, compiled_query: str) -> QueryAnalysis:
        """
        Analyze a compiled Mango query to extract field usage.

        Args:
            compiled_query: JSON string containing the compiled query

        Returns:
            QueryAnalysis object with extracted information
        """
        try:
            query_data = json.loads(compiled_query)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid query JSON: {e}")

        analysis = QueryAnalysis(
            query_type=query_data.get("type"),
            table=query_data.get("table"),
            selector=query_data.get("selector", {}),
            sort=query_data.get("sort")
        )

        # Extract selector fields
        if analysis.selector:
            analysis.selector_fields = self._extract_selector_fields(analysis.selector)

        # Extract sort fields
        if analysis.sort:
            analysis.sort_fields = self._extract_sort_fields(analysis.sort)

        return analysis

    def _extract_selector_fields(self, selector: Dict[str, Any]) -> Set[str]:
        """
        Recursively extract all fields used in a Mango selector.

        Args:
            selector: Mango query selector dictionary

        Returns:
            Set of field names used in the selector
        """
        fields = set()

        for key, value in selector.items():
            # Skip Mango operators
            if key.startswith("$"):
                # Logical operators: $and, $or, $not, etc.
                if isinstance(value, list):
                    # $and, $or: list of sub-selectors
                    for sub_selector in value:
                        if isinstance(sub_selector, dict):
                            fields.update(self._extract_selector_fields(sub_selector))
                elif isinstance(value, dict):
                    # $not: single sub-selector
                    fields.update(self._extract_selector_fields(value))
            else:
                # Regular field
                if key not in self.SYSTEM_FIELDS:
                    fields.add(key)

                # Recursively check nested conditions
                if isinstance(value, dict):
                    # Check for nested operators like {"age": {"$gt": 25, "$lt": 50}}
                    # We've already captured the field name, don't recurse into operator values
                    pass

        return fields

    def _extract_sort_fields(self, sort: List[Dict[str, str]]) -> List[str]:
        """
        Extract fields used in sorting.

        Args:
            sort: Mango sort array, e.g., [{"age": "desc"}, {"name": "asc"}]

        Returns:
            List of field names in sort order
        """
        fields = []

        for sort_item in sort:
            if isinstance(sort_item, dict):
                for field_name in sort_item.keys():
                    if field_name not in self.SYSTEM_FIELDS:
                        fields.append(field_name)

        return fields

    def recommend_index(self, analysis: QueryAnalysis) -> Optional[IndexRecommendation]:
        """
        Generate index recommendation based on query analysis.

        CouchDB index requirements:
        1. Equality filters should come first in the index
        2. Range/comparison filters should come next
        3. Sort fields must be at the end
        4. All sort fields must be in the index

        Args:
            analysis: QueryAnalysis object

        Returns:
            IndexRecommendation or None if no index needed
        """
        if not analysis.table:
            return None

        # Determine which fields need indexing
        index_fields = []

        # Start with selector fields (filters)
        # Note: In a more sophisticated implementation, we would:
        # - Distinguish between equality and range filters
        # - Order equality filters first, then range filters
        # For now, we'll use the selector fields in a deterministic order
        selector_fields_list = sorted(analysis.selector_fields)
        index_fields.extend(selector_fields_list)

        # Add sort fields (must come after filters)
        for sort_field in analysis.sort_fields:
            if sort_field not in index_fields:
                index_fields.append(sort_field)

        # If no fields to index, no recommendation
        if not index_fields:
            return None

        # Build reason string
        reason_parts = []
        if selector_fields_list:
            reason_parts.append(f"Filters on: {', '.join(selector_fields_list)}")
        if analysis.sort_fields:
            reason_parts.append(f"Sorts by: {', '.join(analysis.sort_fields)}")
        reason = "; ".join(reason_parts)

        # Generate CouchDB index DDL
        ddl = self._generate_index_ddl(
            database=analysis.table,
            fields=index_fields
        )

        # Calculate priority
        # Higher priority if:
        # - Has sorting (sorting requires index)
        # - Has multiple filter fields
        priority = 5
        if analysis.sort_fields:
            priority += 3
        if len(selector_fields_list) > 1:
            priority += 2

        return IndexRecommendation(
            fields=index_fields,
            table=analysis.table,
            reason=reason,
            ddl=ddl,
            priority=min(10, priority)
        )

    def _generate_index_ddl(self, database: str, fields: List[str]) -> Dict[str, Any]:
        """
        Generate CouchDB index creation JSON.

        Args:
            database: Database name
            fields: List of fields to index (in order)

        Returns:
            Index creation JSON for CouchDB _index API
        """
        # Generate a descriptive index name
        index_name = f"idx_{database}_{'_'.join(fields)}"

        # Build the index definition
        index_def = {
            "index": {
                "fields": fields
            },
            "name": index_name,
            "type": "json",
            "ddoc": f"_design/{index_name}"
        }

        return index_def

    def analyze_and_recommend(self, compiled_query: str) -> Tuple[QueryAnalysis, Optional[IndexRecommendation]]:
        """
        Convenience method: analyze query and generate recommendation in one call.

        Args:
            compiled_query: JSON string containing the compiled query

        Returns:
            Tuple of (QueryAnalysis, IndexRecommendation or None)
        """
        analysis = self.analyze_query(compiled_query)
        recommendation = self.recommend_index(analysis)
        return analysis, recommendation


class IndexAnalysisReport:
    """
    Generate formatted reports for index recommendations.
    """

    def __init__(self):
        """Initialize the report generator."""
        self.recommendations: List[IndexRecommendation] = []

    def add_recommendation(self, recommendation: IndexRecommendation) -> None:
        """Add a recommendation to the report."""
        if recommendation:
            self.recommendations.append(recommendation)

    def generate_report(self, format: str = "text") -> str:
        """
        Generate a formatted report.

        Args:
            format: Output format ("text", "json", "markdown")

        Returns:
            Formatted report string
        """
        if format == "json":
            return self._generate_json_report()
        elif format == "markdown":
            return self._generate_markdown_report()
        else:
            return self._generate_text_report()

    def _generate_text_report(self) -> str:
        """Generate plain text report."""
        if not self.recommendations:
            return "No index recommendations.\n"

        lines = []
        lines.append("=" * 80)
        lines.append("CouchDB Index Recommendations")
        lines.append("=" * 80)
        lines.append("")

        # Sort by priority (highest first)
        sorted_recs = sorted(self.recommendations, key=lambda r: r.priority, reverse=True)

        for i, rec in enumerate(sorted_recs, 1):
            lines.append(f"Recommendation #{i} (Priority: {rec.priority}/10)")
            lines.append("-" * 80)
            lines.append(f"Table: {rec.table}")
            lines.append(f"Fields: {', '.join(rec.fields)}")
            lines.append(f"Reason: {rec.reason}")
            lines.append("")
            lines.append("Index creation JSON:")
            lines.append(json.dumps(rec.ddl, indent=2))
            lines.append("")
            lines.append("To create this index, POST the above JSON to:")
            lines.append(f"  http://<couchdb-host>:5984/{rec.table}/_index")
            lines.append("")
            lines.append("Example using curl:")
            curl_cmd = (
                f"curl -X POST http://localhost:5984/{rec.table}/_index \\"
                f"\n  -H 'Content-Type: application/json' \\"
                f"\n  -d '{json.dumps(rec.ddl)}'"
            )
            lines.append(curl_cmd)
            lines.append("")
            if i < len(sorted_recs):
                lines.append("=" * 80)
                lines.append("")

        return "\n".join(lines)

    def _generate_markdown_report(self) -> str:
        """Generate Markdown report."""
        if not self.recommendations:
            return "## No index recommendations\n"

        lines = []
        lines.append("# CouchDB Index Recommendations\n")

        sorted_recs = sorted(self.recommendations, key=lambda r: r.priority, reverse=True)

        for i, rec in enumerate(sorted_recs, 1):
            lines.append(f"## Recommendation #{i} (Priority: {rec.priority}/10)\n")
            lines.append(f"**Table:** `{rec.table}`\n")
            lines.append(f"**Fields:** `{', '.join(rec.fields)}`\n")
            lines.append(f"**Reason:** {rec.reason}\n")
            lines.append("### Index Creation JSON\n")
            lines.append("```json")
            lines.append(json.dumps(rec.ddl, indent=2))
            lines.append("```\n")
            lines.append("### How to Apply\n")
            lines.append(f"POST the above JSON to: `http://<couchdb-host>:5984/{rec.table}/_index`\n")
            lines.append("#### Example (curl):\n")
            lines.append("```bash")
            curl_cmd = (
                f"curl -X POST http://localhost:5984/{rec.table}/_index \\"
                f"\n  -H 'Content-Type: application/json' \\"
                f"\n  -d '{json.dumps(rec.ddl)}'"
            )
            lines.append(curl_cmd)
            lines.append("```\n")
            lines.append("---\n")

        return "\n".join(lines)

    def _generate_json_report(self) -> str:
        """Generate JSON report."""
        data = {
            "recommendations": [
                {
                    "table": rec.table,
                    "fields": rec.fields,
                    "reason": rec.reason,
                    "priority": rec.priority,
                    "ddl": rec.ddl
                }
                for rec in sorted(self.recommendations, key=lambda r: r.priority, reverse=True)
            ]
        }
        return json.dumps(data, indent=2)
