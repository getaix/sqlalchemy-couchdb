"""
字段映射系统 - 在 CouchDB 和 RDBMS 之间进行字段映射

功能：
1. _id ↔ id 映射
2. _rev ↔ rev 映射
3. type 字段处理
4. JSON 类型映射
5. 自定义字段映射规则
"""

from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass
import logging
from datetime import datetime, date


logger = logging.getLogger(__name__)


@dataclass
class FieldMapping:
    """字段映射配置"""

    couchdb_field: str
    rdbms_field: str
    transform_to_rdbms: Optional[Callable[[Any], Any]] = None
    transform_to_couchdb: Optional[Callable[[Any], Any]] = None
    required: bool = False


class FieldMapper:
    """
    字段映射器

    处理 CouchDB 和 RDBMS 之间的字段差异：
    - CouchDB 使用 _id, _rev 等特殊字段
    - RDBMS 使用 id, rev 等标准字段
    - 处理 type 字段用于区分文档类型
    """

    # 默认字段映射规则
    DEFAULT_MAPPINGS = {
        "_id": FieldMapping("_id", "id"),
        "_rev": FieldMapping("_rev", "rev"),
        "type": FieldMapping("type", "type"),
    }

    def __init__(
        self,
        custom_mappings: Optional[Dict[str, FieldMapping]] = None,
        preserve_couchdb_fields: bool = False,
        auto_add_type_field: bool = True,
    ):
        """
        初始化字段映射器

        Args:
            custom_mappings: 自定义字段映射
            preserve_couchdb_fields: 在 RDBMS 中保留 CouchDB 特殊字段
            auto_add_type_field: 自动添加 type 字段
        """
        self.mappings = dict(self.DEFAULT_MAPPINGS)
        if custom_mappings:
            self.mappings.update(custom_mappings)

        self.preserve_couchdb_fields = preserve_couchdb_fields
        self.auto_add_type_field = auto_add_type_field

    def to_rdbms(
        self, couchdb_doc: Dict[str, Any], table_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        将 CouchDB 文档转换为 RDBMS 行

        Args:
            couchdb_doc: CouchDB 文档
            table_name: 表名（用于 type 字段）

        Returns:
            RDBMS 行数据
        """
        rdbms_row = {}

        for couchdb_field, value in couchdb_doc.items():
            # 应用字段映射
            if couchdb_field in self.mappings:
                mapping = self.mappings[couchdb_field]
                rdbms_field = mapping.rdbms_field

                # 应用转换函数
                if mapping.transform_to_rdbms:
                    value = mapping.transform_to_rdbms(value)

                rdbms_row[rdbms_field] = value

                # 如果配置了保留 CouchDB 字段，也保留原字段
                if self.preserve_couchdb_fields:
                    rdbms_row[couchdb_field] = couchdb_doc[couchdb_field]
            else:
                # 非映射字段直接复制
                rdbms_row[couchdb_field] = self._convert_value_to_rdbms(value)

        # 验证必需字段
        self._validate_required_fields(rdbms_row, "RDBMS")

        logger.debug(
            f"Mapped CouchDB doc to RDBMS row: {couchdb_doc['_id']} -> {rdbms_row.get('id')}"
        )
        return rdbms_row

    def to_couchdb(
        self, rdbms_row: Dict[str, Any], table_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        将 RDBMS 行转换为 CouchDB 文档

        Args:
            rdbms_row: RDBMS 行数据
            table_name: 表名（用于 type 字段）

        Returns:
            CouchDB 文档
        """
        couchdb_doc = {}

        # 反向映射
        reverse_mappings = {
            m.rdbms_field: (couchdb_field, m) for couchdb_field, m in self.mappings.items()
        }

        for rdbms_field, value in rdbms_row.items():
            # 应用反向映射
            if rdbms_field in reverse_mappings:
                couchdb_field, mapping = reverse_mappings[rdbms_field]

                # 应用转换函数
                if mapping.transform_to_couchdb:
                    value = mapping.transform_to_couchdb(value)

                couchdb_doc[couchdb_field] = value
            else:
                # 非映射字段直接复制
                couchdb_doc[rdbms_field] = self._convert_value_to_couchdb(value)

        # 自动添加 type 字段
        if self.auto_add_type_field and "type" not in couchdb_doc and table_name:
            couchdb_doc["type"] = table_name

        # 验证必需字段
        self._validate_required_fields(couchdb_doc, "CouchDB")

        logger.debug(
            f"Mapped RDBMS row to CouchDB doc: {rdbms_row.get('id')} -> {couchdb_doc.get('_id')}"
        )
        return couchdb_doc

    def _convert_value_to_rdbms(self, value: Any) -> Any:
        """转换值类型以适配 RDBMS"""
        if isinstance(value, (dict, list)):
            # JSON 类型保持不变（假设 RDBMS 支持 JSON）
            return value
        elif isinstance(value, datetime):
            # datetime 转换为 ISO 字符串或保持原样
            return value
        elif isinstance(value, date):
            # date 转换为字符串或保持原样
            return value
        else:
            return value

    def _convert_value_to_couchdb(self, value: Any) -> Any:
        """转换值类型以适配 CouchDB"""
        if isinstance(value, datetime):
            # datetime 转换为 ISO 8601 字符串
            return value.isoformat()
        elif isinstance(value, date):
            # date 转换为 YYYY-MM-DD 字符串
            return value.isoformat()
        else:
            return value

    def _validate_required_fields(self, doc: Dict[str, Any], target: str) -> None:
        """验证必需字段"""
        for mapping in self.mappings.values():
            if not mapping.required:
                continue

            if target == "RDBMS":
                field = mapping.rdbms_field
            else:
                field = mapping.couchdb_field

            if field not in doc:
                logger.warning(f"Required field '{field}' missing in {target} document")

    def add_mapping(
        self,
        couchdb_field: str,
        rdbms_field: str,
        transform_to_rdbms: Optional[Callable[[Any], Any]] = None,
        transform_to_couchdb: Optional[Callable[[Any], Any]] = None,
        required: bool = False,
    ) -> None:
        """添加自定义字段映射"""
        self.mappings[couchdb_field] = FieldMapping(
            couchdb_field=couchdb_field,
            rdbms_field=rdbms_field,
            transform_to_rdbms=transform_to_rdbms,
            transform_to_couchdb=transform_to_couchdb,
            required=required,
        )
        logger.info(f"Added field mapping: {couchdb_field} <-> {rdbms_field}")

    def batch_to_rdbms(
        self, couchdb_docs: List[Dict[str, Any]], table_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """批量转换 CouchDB 文档到 RDBMS 行"""
        return [self.to_rdbms(doc, table_name) for doc in couchdb_docs]

    def batch_to_couchdb(
        self, rdbms_rows: List[Dict[str, Any]], table_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """批量转换 RDBMS 行到 CouchDB 文档"""
        return [self.to_couchdb(row, table_name) for row in rdbms_rows]


class TypeFieldManager:
    """
    type 字段管理器

    在 CouchDB 中使用 type 字段来模拟 SQL 表：
    - type="users" 表示 users 表
    - type="posts" 表示 posts 表
    """

    def __init__(self, type_field_name: str = "type", table_prefix: str = ""):
        """
        初始化 type 字段管理器

        Args:
            type_field_name: type 字段名称
            table_prefix: 表名前缀
        """
        self.type_field_name = type_field_name
        self.table_prefix = table_prefix

    def get_type_value(self, table_name: str) -> str:
        """根据表名生成 type 字段值"""
        if self.table_prefix:
            return f"{self.table_prefix}_{table_name}"
        return table_name

    def get_table_name(self, type_value: str) -> str:
        """根据 type 字段值获取表名"""
        if self.table_prefix and type_value.startswith(self.table_prefix + "_"):
            return type_value[len(self.table_prefix) + 1 :]
        return type_value

    def add_type_field(self, doc: Dict[str, Any], table_name: str) -> Dict[str, Any]:
        """为文档添加 type 字段"""
        doc[self.type_field_name] = self.get_type_value(table_name)
        return doc

    def filter_by_type(self, docs: List[Dict[str, Any]], table_name: str) -> List[Dict[str, Any]]:
        """根据 type 字段过滤文档"""
        type_value = self.get_type_value(table_name)
        return [doc for doc in docs if doc.get(self.type_field_name) == type_value]


class IDGenerator:
    """
    ID 生成器

    为 CouchDB 文档生成 _id：
    - 格式：{table_name}:{uuid}
    - 例如：users:123e4567-e89b-12d3-a456-426614174000
    """

    def __init__(self, use_uuid: bool = True, separator: str = ":"):
        """
        初始化 ID 生成器

        Args:
            use_uuid: 是否使用 UUID
            separator: 表名和 ID 的分隔符
        """
        self.use_uuid = use_uuid
        self.separator = separator

    def generate_id(self, table_name: str, primary_key: Optional[Any] = None) -> str:
        """
        生成 CouchDB _id

        Args:
            table_name: 表名
            primary_key: 主键值（如果已知）

        Returns:
            _id 字符串
        """
        if primary_key is not None:
            return f"{table_name}{self.separator}{primary_key}"
        elif self.use_uuid:
            import uuid

            return f"{table_name}{self.separator}{uuid.uuid4()}"
        else:
            # 使用时间戳
            import time

            return f"{table_name}{self.separator}{int(time.time() * 1000000)}"

    def parse_id(self, doc_id: str) -> tuple[str, str]:
        """
        解析 _id 获取表名和主键

        Args:
            doc_id: _id 字符串

        Returns:
            (table_name, primary_key)
        """
        if self.separator in doc_id:
            parts = doc_id.split(self.separator, 1)
            return parts[0], parts[1]
        else:
            # 无法解析，返回空表名
            return "", doc_id
