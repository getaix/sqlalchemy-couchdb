"""
智能查询路由器 - 根据查询复杂度决定使用 CouchDB 还是 RDBMS

功能：
1. 分析 SQL 查询的复杂度
2. 根据能力对比决策路由目标
3. 支持自定义路由规则
"""

from typing import Any, Dict, List, Optional, Set
from enum import Enum
from dataclasses import dataclass
import logging

from sqlalchemy.sql import Select, Insert, Update, Delete
from sqlalchemy.sql.elements import ClauseElement


logger = logging.getLogger(__name__)


class DatabaseType(Enum):
    """数据库类型"""

    COUCHDB = "couchdb"
    RDBMS = "rdbms"


class QueryComplexity(Enum):
    """查询复杂度级别"""

    SIMPLE = 1  # 简单查询（CouchDB 可处理）
    MODERATE = 2  # 中等复杂度（CouchDB 有限支持）
    COMPLEX = 3  # 复杂查询（需要 RDBMS）


@dataclass
class QueryAnalysis:
    """查询分析结果"""

    complexity: QueryComplexity
    features: Set[str]
    recommended_db: DatabaseType
    reason: str
    confidence: float  # 0.0 - 1.0


class QueryRouter:
    """
    智能查询路由器

    根据 SQL 查询的复杂度和特性，决定使用 CouchDB 还是 RDBMS。

    CouchDB 支持的特性：
    - 简单 SELECT（WHERE, ORDER BY, LIMIT, OFFSET）
    - INSERT（单条/批量）
    - UPDATE（需要 _rev）
    - DELETE（需要 _rev）
    - 基础聚合（通过视图）

    RDBMS 才支持的特性：
    - JOIN（多表关联）
    - 复杂聚合（GROUP BY + HAVING + 多个聚合函数）
    - 子查询
    - UNION/INTERSECT/EXCEPT
    - 窗口函数
    - 事务（ACID）
    """

    # CouchDB 不支持的 SQL 特性
    COUCHDB_UNSUPPORTED = {
        "JOIN",
        "SUBQUERY",
        "UNION",
        "INTERSECT",
        "EXCEPT",
        "WINDOW_FUNCTION",
        "HAVING",
        "RECURSIVE_CTE",
        "TRANSACTION",
    }

    # CouchDB 有限支持的特性
    COUCHDB_LIMITED = {
        "GROUP_BY",  # 需要通过视图实现
        "AGGREGATE",  # 需要通过视图实现
        "DISTINCT",  # 需要客户端处理
    }

    def __init__(self, prefer_couchdb: bool = True, custom_rules: Optional[Dict[str, Any]] = None):
        """
        初始化查询路由器

        Args:
            prefer_couchdb: 当不确定时是否优先使用 CouchDB
            custom_rules: 自定义路由规则
        """
        self.prefer_couchdb = prefer_couchdb
        self.custom_rules = custom_rules or {}

    def route_query(self, statement: ClauseElement) -> QueryAnalysis:
        """
        路由查询到合适的数据库

        Args:
            statement: SQLAlchemy 查询语句

        Returns:
            QueryAnalysis: 查询分析结果
        """
        # 分析查询特性
        features = self._analyze_features(statement)

        # 计算复杂度
        complexity = self._calculate_complexity(features)

        # 决策数据库类型
        recommended_db, reason, confidence = self._decide_database(complexity, features)

        logger.info(
            f"Query routed to {recommended_db.value}: "
            f"complexity={complexity.name}, "
            f"features={features}, "
            f"confidence={confidence:.2f}"
        )

        return QueryAnalysis(
            complexity=complexity,
            features=features,
            recommended_db=recommended_db,
            reason=reason,
            confidence=confidence,
        )

    def _analyze_features(self, statement: ClauseElement) -> Set[str]:
        """分析查询使用的 SQL 特性"""
        features = set()

        if isinstance(statement, Select):
            features.add("SELECT")

            # 检查 JOIN（使用 SQLAlchemy 2.0 兼容的 API）
            try:
                from sqlalchemy.sql.selectable import Join

                # SQLAlchemy 2.0+ 使用 get_final_froms()
                if hasattr(statement, "get_final_froms"):
                    froms = statement.get_final_froms()
                else:
                    # 兼容旧版本
                    froms = statement.froms if hasattr(statement, "froms") else []

                # 检查是否有 Join 对象（表示有 JOIN 操作）
                for from_clause in froms:
                    if isinstance(from_clause, Join):
                        features.add("JOIN")
                        break
            except Exception:
                # 如果无法检测 JOIN，保守起见不添加
                pass

            # 检查 WHERE
            if statement.whereclause is not None:
                features.add("WHERE")

            # 检查 ORDER BY
            if statement._order_by_clauses:
                features.add("ORDER_BY")

            # 检查 LIMIT/OFFSET
            if statement._limit_clause is not None:
                features.add("LIMIT")
            if statement._offset_clause is not None:
                features.add("OFFSET")

            # 检查 GROUP BY
            if statement._group_by_clauses:
                features.add("GROUP_BY")

            # 检查 HAVING
            if statement._having_criteria:
                features.add("HAVING")

            # 检查 DISTINCT
            if statement._distinct:
                features.add("DISTINCT")

            # 检查聚合函数（通过列表达式）
            if hasattr(statement, "selected_columns"):
                for col in statement.selected_columns:
                    col_str = str(col).upper()
                    if any(agg in col_str for agg in ["COUNT", "SUM", "AVG", "MIN", "MAX"]):
                        features.add("AGGREGATE")
                        break

        elif isinstance(statement, Insert):
            features.add("INSERT")

        elif isinstance(statement, Update):
            features.add("UPDATE")
            if statement.whereclause is not None:
                features.add("WHERE")

        elif isinstance(statement, Delete):
            features.add("DELETE")
            if statement.whereclause is not None:
                features.add("WHERE")

        return features

    def _calculate_complexity(self, features: Set[str]) -> QueryComplexity:
        """计算查询复杂度"""
        # 如果有 CouchDB 不支持的特性，直接判定为复杂查询
        if features & self.COUCHDB_UNSUPPORTED:
            return QueryComplexity.COMPLEX

        # 如果有 CouchDB 有限支持的特性，判定为中等复杂度
        if features & self.COUCHDB_LIMITED:
            return QueryComplexity.MODERATE

        # 否则是简单查询
        return QueryComplexity.SIMPLE

    def _decide_database(
        self, complexity: QueryComplexity, features: Set[str]
    ) -> tuple[DatabaseType, str, float]:
        """
        决策使用哪个数据库

        Returns:
            (database_type, reason, confidence)
        """
        # 检查自定义规则
        if self.custom_rules:
            custom_result = self._apply_custom_rules(features)
            if custom_result:
                return custom_result

        # 复杂查询必须使用 RDBMS
        if complexity == QueryComplexity.COMPLEX:
            unsupported = features & self.COUCHDB_UNSUPPORTED
            return (
                DatabaseType.RDBMS,
                f"Query uses CouchDB-unsupported features: {unsupported}",
                1.0,
            )

        # 中等复杂度查询
        if complexity == QueryComplexity.MODERATE:
            limited = features & self.COUCHDB_LIMITED
            if self.prefer_couchdb:
                return (
                    DatabaseType.COUCHDB,
                    f"Query uses limited-support features: {limited}, but prefer_couchdb=True",
                    0.6,
                )
            else:
                return (
                    DatabaseType.RDBMS,
                    f"Query uses limited-support features: {limited}, prefer RDBMS for reliability",
                    0.7,
                )

        # 简单查询优先使用 CouchDB
        return (DatabaseType.COUCHDB, "Simple query, CouchDB is sufficient", 0.9)

    def _apply_custom_rules(self, features: Set[str]) -> Optional[tuple[DatabaseType, str, float]]:
        """应用自定义路由规则"""
        # 示例：自定义规则可以基于表名、特性组合等
        # 这里提供扩展点供用户自定义

        # 例如：强制某些表总是使用 RDBMS
        if "force_rdbms_tables" in self.custom_rules:
            force_tables = self.custom_rules["force_rdbms_tables"]
            # 这里需要从 statement 中提取表名，简化起见暂不实现
            pass

        return None

    def add_custom_rule(self, rule_name: str, rule_config: Any) -> None:
        """添加自定义路由规则"""
        self.custom_rules[rule_name] = rule_config
        logger.info(f"Added custom routing rule: {rule_name}")


class RoutingStrategy:
    """路由策略配置"""

    def __init__(
        self,
        strategy: str = "auto",
        fallback_to_rdbms: bool = True,
        couchdb_only_tables: Optional[List[str]] = None,
        rdbms_only_tables: Optional[List[str]] = None,
    ):
        """
        初始化路由策略

        Args:
            strategy: 路由策略 ('auto', 'couchdb_first', 'rdbms_first')
            fallback_to_rdbms: CouchDB 失败时是否回退到 RDBMS
            couchdb_only_tables: 只使用 CouchDB 的表
            rdbms_only_tables: 只使用 RDBMS 的表
        """
        self.strategy = strategy
        self.fallback_to_rdbms = fallback_to_rdbms
        self.couchdb_only_tables = set(couchdb_only_tables or [])
        self.rdbms_only_tables = set(rdbms_only_tables or [])

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "strategy": self.strategy,
            "fallback_to_rdbms": self.fallback_to_rdbms,
            "couchdb_only_tables": list(self.couchdb_only_tables),
            "rdbms_only_tables": list(self.rdbms_only_tables),
        }
