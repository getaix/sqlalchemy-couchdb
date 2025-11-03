"""
混合数据库架构 - 同时使用 CouchDB 和 RDBMS

核心组件：
1. QueryRouter - 智能查询路由
2. FieldMapper - 字段映射
3. DualWriteManager - 双写同步
4. ConsistencyMonitor - 一致性监控

URL 格式：
    couchdb+hybrid://admin:password@localhost:5984/mydb?secondary_db=postgresql://...
"""

from .router import QueryRouter, QueryAnalysis, QueryComplexity, DatabaseType, RoutingStrategy
from .mapper import FieldMapper, FieldMapping, TypeFieldManager, IDGenerator
from .dual_write import DualWriteManager, WriteMode, WriteResult, DatabaseRole
from .monitor import (
    ConsistencyMonitor,
    ConsistencyReport,
    DataDifference,
    ConflictResolution,
    DiffType,
)


__all__ = [
    # Router
    "QueryRouter",
    "QueryAnalysis",
    "QueryComplexity",
    "DatabaseType",
    "RoutingStrategy",
    # Mapper
    "FieldMapper",
    "FieldMapping",
    "TypeFieldManager",
    "IDGenerator",
    # Dual Write
    "DualWriteManager",
    "WriteMode",
    "WriteResult",
    "DatabaseRole",
    # Monitor
    "ConsistencyMonitor",
    "ConsistencyReport",
    "DataDifference",
    "ConflictResolution",
    "DiffType",
]
