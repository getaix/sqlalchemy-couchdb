"""
高级查询支持模块

提供 DISTINCT、COUNT、聚合函数等高级查询功能。
由于 CouchDB 不直接支持这些 SQL 功能，我们通过后处理或视图来实现。
"""

from typing import Any, Dict, List, Optional, Set
from collections import defaultdict


class QueryProcessor:
    """
    查询后处理器

    用于在客户端实现 CouchDB 不直接支持的 SQL 功能。
    """

    @staticmethod
    def apply_distinct(results: List[Dict[str, Any]], fields: List[str]) -> List[Dict[str, Any]]:
        """
        应用 DISTINCT 去重

        参数:
            results: 查询结果列表
            fields: 需要去重的字段列表

        返回:
            去重后的结果列表

        示例:
            >>> results = [
            ...     {"name": "Alice", "age": 30},
            ...     {"name": "Alice", "age": 30},
            ...     {"name": "Bob", "age": 25},
            ... ]
            >>> QueryProcessor.apply_distinct(results, ["name", "age"])
            [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]
        """
        seen: Set[tuple] = set()
        unique_results = []

        for row in results:
            # 提取指定字段的值作为元组（用于哈希）
            key = tuple(row.get(field) for field in fields)

            if key not in seen:
                seen.add(key)
                unique_results.append(row)

        return unique_results

    @staticmethod
    def count(results: List[Dict[str, Any]]) -> int:
        """
        计数函数

        参数:
            results: 查询结果列表

        返回:
            结果数量
        """
        return len(results)

    @staticmethod
    def count_distinct(results: List[Dict[str, Any]], field: str) -> int:
        """
        计数不同值的数量

        参数:
            results: 查询结果列表
            field: 字段名

        返回:
            不同值的数量

        示例:
            >>> results = [
            ...     {"name": "Alice"},
            ...     {"name": "Alice"},
            ...     {"name": "Bob"},
            ... ]
            >>> QueryProcessor.count_distinct(results, "name")
            2
        """
        unique_values = set(row.get(field) for row in results if field in row)
        return len(unique_values)

    @staticmethod
    def sum(results: List[Dict[str, Any]], field: str) -> float:
        """
        求和函数

        参数:
            results: 查询结果列表
            field: 字段名

        返回:
            总和

        示例:
            >>> results = [{"age": 30}, {"age": 25}, {"age": 35}]
            >>> QueryProcessor.sum(results, "age")
            90
        """
        total = 0
        for row in results:
            value = row.get(field)
            if value is not None:
                try:
                    total += float(value)
                except (TypeError, ValueError):
                    pass  # 忽略非数值字段
        return total

    @staticmethod
    def avg(results: List[Dict[str, Any]], field: str) -> Optional[float]:
        """
        平均值函数

        参数:
            results: 查询结果列表
            field: 字段名

        返回:
            平均值，如果没有有效值则返回 None
        """
        values = []
        for row in results:
            value = row.get(field)
            if value is not None:
                try:
                    values.append(float(value))
                except (TypeError, ValueError):
                    pass

        if not values:
            return None

        return sum(values) / len(values)

    @staticmethod
    def min(results: List[Dict[str, Any]], field: str) -> Optional[Any]:
        """
        最小值函数

        参数:
            results: 查询结果列表
            field: 字段名

        返回:
            最小值，如果没有有效值则返回 None
        """
        values = [row.get(field) for row in results if field in row and row.get(field) is not None]

        if not values:
            return None

        return min(values)

    @staticmethod
    def max(results: List[Dict[str, Any]], field: str) -> Optional[Any]:
        """
        最大值函数

        参数:
            results: 查询结果列表
            field: 字段名

        返回:
            最大值，如果没有有效值则返回 None
        """
        values = [row.get(field) for row in results if field in row and row.get(field) is not None]

        if not values:
            return None

        return max(values)

    @staticmethod
    def group_by(
        results: List[Dict[str, Any]],
        group_fields: List[str],
        aggregate_func: str,
        aggregate_field: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        分组聚合函数

        参数:
            results: 查询结果列表
            group_fields: 分组字段列表
            aggregate_func: 聚合函数名（'count', 'sum', 'avg', 'min', 'max'）
            aggregate_field: 聚合字段名（count 不需要）

        返回:
            分组聚合结果

        示例:
            >>> results = [
            ...     {"city": "Beijing", "age": 30},
            ...     {"city": "Beijing", "age": 25},
            ...     {"city": "Shanghai", "age": 35},
            ... ]
            >>> QueryProcessor.group_by(results, ["city"], "avg", "age")
            [
                {"city": "Beijing", "avg_age": 27.5},
                {"city": "Shanghai", "avg_age": 35.0}
            ]
        """
        # 按分组字段分组
        groups = defaultdict(list)

        for row in results:
            # 创建分组键
            group_key = tuple(row.get(field) for field in group_fields)
            groups[group_key].append(row)

        # 应用聚合函数
        aggregated_results = []

        for group_key, group_rows in groups.items():
            result_row = {}

            # 添加分组字段
            for i, field in enumerate(group_fields):
                result_row[field] = group_key[i]

            # 计算聚合值
            if aggregate_func == "count":
                result_row["count"] = len(group_rows)
            elif aggregate_func == "sum" and aggregate_field:
                result_row[f"sum_{aggregate_field}"] = QueryProcessor.sum(
                    group_rows, aggregate_field
                )
            elif aggregate_func == "avg" and aggregate_field:
                result_row[f"avg_{aggregate_field}"] = QueryProcessor.avg(
                    group_rows, aggregate_field
                )
            elif aggregate_func == "min" and aggregate_field:
                result_row[f"min_{aggregate_field}"] = QueryProcessor.min(
                    group_rows, aggregate_field
                )
            elif aggregate_func == "max" and aggregate_field:
                result_row[f"max_{aggregate_field}"] = QueryProcessor.max(
                    group_rows, aggregate_field
                )

            aggregated_results.append(result_row)

        return aggregated_results


class AggregateQueryBuilder:
    """
    聚合查询构建器

    帮助构建使用 CouchDB 视图的聚合查询。
    """

    @staticmethod
    def create_count_view(
        design_doc: str, view_name: str, group_field: Optional[str] = None
    ) -> Dict[str, str]:
        """
        创建计数视图的 Map/Reduce 函数

        参数:
            design_doc: 设计文档名称
            view_name: 视图名称
            group_field: 分组字段（可选）

        返回:
            包含 'map' 和 'reduce' 的字典

        示例:
            >>> builder = AggregateQueryBuilder()
            >>> builder.create_count_view("stats", "count_by_city", "city")
            {
                'map': 'function(doc) { if (doc.city) emit(doc.city, 1); }',
                'reduce': '_count'
            }
        """
        if group_field:
            map_func = f"function(doc) {{ if (doc.{group_field}) emit(doc.{group_field}, 1); }}"
        else:
            map_func = "function(doc) { emit(doc._id, 1); }"

        return {
            "map": map_func,
            "reduce": "_count",
        }

    @staticmethod
    def create_sum_view(
        design_doc: str, view_name: str, sum_field: str, group_field: Optional[str] = None
    ) -> Dict[str, str]:
        """
        创建求和视图的 Map/Reduce 函数

        参数:
            design_doc: 设计文档名称
            view_name: 视图名称
            sum_field: 要求和的字段
            group_field: 分组字段（可选）

        返回:
            包含 'map' 和 'reduce' 的字典
        """
        if group_field:
            map_func = f"function(doc) {{ if (doc.{group_field} && doc.{sum_field}) emit(doc.{group_field}, doc.{sum_field}); }}"
        else:
            map_func = f"function(doc) {{ if (doc.{sum_field}) emit(doc._id, doc.{sum_field}); }}"

        return {
            "map": map_func,
            "reduce": "_sum",
        }

    @staticmethod
    def create_stats_view(
        design_doc: str, view_name: str, stats_field: str, group_field: Optional[str] = None
    ) -> Dict[str, str]:
        """
        创建统计视图的 Map/Reduce 函数

        参数:
            design_doc: 设计文档名称
            view_name: 视图名称
            stats_field: 要统计的字段
            group_field: 分组字段（可选）

        返回:
            包含 'map' 和 'reduce' 的字典

        注意:
            _stats reduce 函数提供 sum, count, min, max, sumsqr
        """
        if group_field:
            map_func = f"function(doc) {{ if (doc.{group_field} && doc.{stats_field}) emit(doc.{group_field}, doc.{stats_field}); }}"
        else:
            map_func = (
                f"function(doc) {{ if (doc.{stats_field}) emit(doc._id, doc.{stats_field}); }}"
            )

        return {
            "map": map_func,
            "reduce": "_stats",
        }
