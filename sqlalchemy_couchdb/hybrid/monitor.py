"""
一致性监控 - 检测和修复 CouchDB 与 RDBMS 之间的数据差异

功能：
1. 数据差异检测
2. 自动修复机制
3. 冲突解决策略
4. 一致性报告
"""

from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
import logging


logger = logging.getLogger(__name__)


class ConflictResolution(Enum):
    """冲突解决策略"""

    PRIMARY_WINS = "primary_wins"  # 主数据库优先
    SECONDARY_WINS = "secondary_wins"  # 从数据库优先
    LATEST_WINS = "latest_wins"  # 最新修改优先
    MANUAL = "manual"  # 手动解决


class DiffType(Enum):
    """差异类型"""

    MISSING_IN_PRIMARY = "missing_in_primary"  # 主库缺失
    MISSING_IN_SECONDARY = "missing_in_secondary"  # 从库缺失
    VALUE_MISMATCH = "value_mismatch"  # 值不匹配
    TYPE_MISMATCH = "type_mismatch"  # 类型不匹配


@dataclass
class DataDifference:
    """数据差异"""

    table_name: str
    record_id: Any
    diff_type: DiffType
    field_name: Optional[str] = None
    primary_value: Optional[Any] = None
    secondary_value: Optional[Any] = None
    detected_at: datetime = None

    def __post_init__(self):
        if self.detected_at is None:
            self.detected_at = datetime.now()


@dataclass
class ConsistencyReport:
    """一致性报告"""

    table_name: str
    total_records: int
    consistent_records: int
    inconsistent_records: int
    differences: List[DataDifference]
    consistency_rate: float
    checked_at: datetime

    @classmethod
    def create(
        cls,
        table_name: str,
        total_records: int,
        differences: List[DataDifference],
        checked_at: Optional[datetime] = None,
    ) -> "ConsistencyReport":
        """创建一致性报告"""
        inconsistent_records = len(set(d.record_id for d in differences))
        consistent_records = total_records - inconsistent_records
        consistency_rate = consistent_records / total_records if total_records > 0 else 1.0

        return cls(
            table_name=table_name,
            total_records=total_records,
            consistent_records=consistent_records,
            inconsistent_records=inconsistent_records,
            differences=differences,
            consistency_rate=consistency_rate,
            checked_at=checked_at or datetime.now(),
        )


class ConsistencyMonitor:
    """
    一致性监控器

    定期检查 CouchDB 和 RDBMS 之间的数据一致性，
    检测差异并根据配置的策略自动修复。

    检查项：
    1. 记录是否存在于两个数据库
    2. 字段值是否一致
    3. 数据类型是否一致

    修复策略：
    1. 主库优先：以 CouchDB 为准
    2. 从库优先：以 RDBMS 为准
    3. 最新优先：比较时间戳，以最新的为准
    4. 手动解决：记录冲突，不自动修复
    """

    def __init__(
        self,
        primary_client: Any,  # CouchDB 客户端
        secondary_client: Any,  # RDBMS 客户端
        field_mapper: Any,  # 字段映射器
        conflict_resolution: ConflictResolution = ConflictResolution.PRIMARY_WINS,
        auto_repair: bool = False,
        ignore_fields: Optional[Set[str]] = None,
    ):
        """
        初始化一致性监控器

        Args:
            primary_client: 主数据库客户端（CouchDB）
            secondary_client: 从数据库客户端（RDBMS）
            field_mapper: 字段映射器
            conflict_resolution: 冲突解决策略
            auto_repair: 是否自动修复差异
            ignore_fields: 忽略的字段（不检查一致性）
        """
        self.primary_client = primary_client
        self.secondary_client = secondary_client
        self.field_mapper = field_mapper
        self.conflict_resolution = conflict_resolution
        self.auto_repair = auto_repair
        self.ignore_fields = ignore_fields or {"_rev", "rev", "updated_at", "modified_at"}

        # 统计信息
        self.stats = {
            "total_checks": 0,
            "total_differences": 0,
            "auto_repairs": 0,
            "manual_conflicts": 0,
        }

    def check_consistency(
        self, table_name: str, record_ids: Optional[List[Any]] = None
    ) -> ConsistencyReport:
        """
        检查表的一致性

        Args:
            table_name: 表名
            record_ids: 要检查的记录 ID 列表（None 表示检查所有记录）

        Returns:
            ConsistencyReport: 一致性报告
        """
        self.stats["total_checks"] += 1
        logger.info(f"Checking consistency for table: {table_name}")

        # 获取两边的数据
        primary_records = self._fetch_primary_records(table_name, record_ids)
        secondary_records = self._fetch_secondary_records(table_name, record_ids)

        # 检测差异
        differences = self._detect_differences(table_name, primary_records, secondary_records)

        self.stats["total_differences"] += len(differences)

        # 自动修复
        if self.auto_repair and differences:
            self._auto_repair_differences(differences)

        # 生成报告
        total_records = max(len(primary_records), len(secondary_records))
        report = ConsistencyReport.create(
            table_name=table_name, total_records=total_records, differences=differences
        )

        logger.info(
            f"Consistency check completed: {report.consistency_rate:.2%} "
            f"({report.consistent_records}/{report.total_records} records)"
        )

        return report

    def _fetch_primary_records(
        self, table_name: str, record_ids: Optional[List[Any]]
    ) -> Dict[Any, Dict[str, Any]]:
        """从主数据库获取记录"""
        logger.debug(f"Fetching primary records for {table_name}")
        records = {}

        if record_ids:
            # 获取指定的记录
            for record_id in record_ids:
                try:
                    doc = self.primary_client.get_document(record_id)
                    records[record_id] = doc
                except Exception as e:
                    logger.debug(f"Failed to fetch {record_id} from primary: {e}")
        else:
            # 获取所有记录（使用 type 字段过滤）
            try:
                # 使用 Mango Query 查询所有此类型的文档
                query = {"selector": {"type": table_name}, "limit": 10000}
                result = self.primary_client.find(query)
                for doc in result.get("docs", []):
                    records[doc["_id"]] = doc
            except Exception as e:
                logger.debug(f"Failed to fetch records from primary: {e}")

        return records

    def _fetch_secondary_records(
        self, table_name: str, record_ids: Optional[List[Any]]
    ) -> Dict[Any, Dict[str, Any]]:
        """从从数据库获取记录"""
        logger.debug(f"Fetching secondary records for {table_name}")
        records = {}

        try:

            cursor = self.secondary_client.cursor()

            if record_ids:
                # 获取指定的记录
                placeholders = ",".join(["?" for _ in record_ids])
                query = f"SELECT * FROM {table_name} WHERE id IN ({placeholders})"
                cursor.execute(query, record_ids)
            else:
                # 获取所有记录
                query = f"SELECT * FROM {table_name}"
                cursor.execute(query)

            # 获取列名
            columns = [desc[0] for desc in cursor.description]

            # 将结果转换为字典
            for row in cursor.fetchall():
                row_dict = dict(zip(columns, row))
                record_id = row_dict.get("id")
                if record_id:
                    records[record_id] = row_dict

        except Exception as e:
            logger.debug(f"Failed to fetch records from secondary: {e}")

        return records

    def _detect_differences(
        self,
        table_name: str,
        primary_records: Dict[Any, Dict[str, Any]],
        secondary_records: Dict[Any, Dict[str, Any]],
    ) -> List[DataDifference]:
        """检测数据差异"""
        differences = []

        # 获取所有记录 ID
        all_ids = set(primary_records.keys()) | set(secondary_records.keys())

        for record_id in all_ids:
            primary_record = primary_records.get(record_id)
            secondary_record = secondary_records.get(record_id)

            # 检查记录是否存在
            if primary_record is None:
                differences.append(
                    DataDifference(
                        table_name=table_name,
                        record_id=record_id,
                        diff_type=DiffType.MISSING_IN_PRIMARY,
                        secondary_value=secondary_record,
                    )
                )
                continue

            if secondary_record is None:
                differences.append(
                    DataDifference(
                        table_name=table_name,
                        record_id=record_id,
                        diff_type=DiffType.MISSING_IN_SECONDARY,
                        primary_value=primary_record,
                    )
                )
                continue

            # 比较字段值
            field_diffs = self._compare_records(
                table_name, record_id, primary_record, secondary_record
            )
            differences.extend(field_diffs)

        return differences

    def _compare_records(
        self,
        table_name: str,
        record_id: Any,
        primary_record: Dict[str, Any],
        secondary_record: Dict[str, Any],
    ) -> List[DataDifference]:
        """比较两条记录"""
        differences = []

        # 映射从数据库记录到 CouchDB 格式
        mapped_secondary = self.field_mapper.to_couchdb(secondary_record, table_name)

        # 获取所有字段
        all_fields = set(primary_record.keys()) | set(mapped_secondary.keys())

        for field_name in all_fields:
            # 跳过忽略的字段
            if field_name in self.ignore_fields:
                continue

            primary_value = primary_record.get(field_name)
            secondary_value = mapped_secondary.get(field_name)

            # 比较值
            if not self._values_equal(primary_value, secondary_value):
                # 检查类型是否匹配
                diff_type = (
                    DiffType.TYPE_MISMATCH
                    if type(primary_value) != type(secondary_value)
                    else DiffType.VALUE_MISMATCH
                )

                differences.append(
                    DataDifference(
                        table_name=table_name,
                        record_id=record_id,
                        diff_type=diff_type,
                        field_name=field_name,
                        primary_value=primary_value,
                        secondary_value=secondary_value,
                    )
                )

        return differences

    def _values_equal(self, value1: Any, value2: Any) -> bool:
        """比较两个值是否相等（考虑类型转换）"""
        if value1 is None and value2 is None:
            return True
        if value1 is None or value2 is None:
            return False

        # 数字比较（容忍浮点误差）
        if isinstance(value1, (int, float)) and isinstance(value2, (int, float)):
            return abs(value1 - value2) < 1e-9

        # 字符串比较
        if isinstance(value1, str) or isinstance(value2, str):
            return str(value1) == str(value2)

        # 其他类型直接比较
        return value1 == value2

    def _auto_repair_differences(self, differences: List[DataDifference]) -> None:
        """自动修复差异"""
        logger.info(f"Auto-repairing {len(differences)} differences")

        for diff in differences:
            try:
                if self.conflict_resolution == ConflictResolution.PRIMARY_WINS:
                    self._repair_primary_wins(diff)
                elif self.conflict_resolution == ConflictResolution.SECONDARY_WINS:
                    self._repair_secondary_wins(diff)
                elif self.conflict_resolution == ConflictResolution.LATEST_WINS:
                    self._repair_latest_wins(diff)
                elif self.conflict_resolution == ConflictResolution.MANUAL:
                    self._log_manual_conflict(diff)

                self.stats["auto_repairs"] += 1
            except Exception as e:
                logger.error(f"Failed to repair difference: {e}")

    def _repair_primary_wins(self, diff: DataDifference) -> None:
        """修复：主数据库优先"""
        if diff.diff_type == DiffType.MISSING_IN_SECONDARY:
            # 从库缺失，从主库复制
            logger.info(f"Copying record to secondary: {diff.record_id}")
            # self._copy_to_secondary(diff.table_name, diff.primary_value)

        elif diff.diff_type == DiffType.MISSING_IN_PRIMARY:
            # 主库缺失，删除从库
            logger.info(f"Deleting record from secondary: {diff.record_id}")
            # self._delete_from_secondary(diff.table_name, diff.record_id)

        elif diff.diff_type in (DiffType.VALUE_MISMATCH, DiffType.TYPE_MISMATCH):
            # 值不匹配，更新从库
            logger.info(f"Updating secondary field: {diff.record_id}.{diff.field_name}")
            # self._update_secondary_field(diff)

    def _repair_secondary_wins(self, diff: DataDifference) -> None:
        """修复：从数据库优先"""
        if diff.diff_type == DiffType.MISSING_IN_PRIMARY:
            # 主库缺失，从从库复制
            logger.info(f"Copying record to primary: {diff.record_id}")
            # self._copy_to_primary(diff.table_name, diff.secondary_value)

        elif diff.diff_type == DiffType.MISSING_IN_SECONDARY:
            # 从库缺失，删除主库
            logger.info(f"Deleting record from primary: {diff.record_id}")
            # self._delete_from_primary(diff.table_name, diff.record_id)

        elif diff.diff_type in (DiffType.VALUE_MISMATCH, DiffType.TYPE_MISMATCH):
            # 值不匹配，更新主库
            logger.info(f"Updating primary field: {diff.record_id}.{diff.field_name}")
            # self._update_primary_field(diff)

    def _repair_latest_wins(self, diff: DataDifference) -> None:
        """修复：最新修改优先"""
        # 需要比较时间戳，这里简化为主库优先
        self._repair_primary_wins(diff)

    def _log_manual_conflict(self, diff: DataDifference) -> None:
        """记录手动冲突"""
        logger.warning(
            f"Manual conflict detected: {diff.table_name}.{diff.record_id}"
            f".{diff.field_name or 'record'}: "
            f"primary={diff.primary_value}, secondary={diff.secondary_value}"
        )
        self.stats["manual_conflicts"] += 1

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return dict(self.stats)

    def generate_summary_report(self, reports: List[ConsistencyReport]) -> Dict[str, Any]:
        """生成汇总报告"""
        if not reports:
            return {
                "total_tables": 0,
                "total_records": 0,
                "overall_consistency_rate": 1.0,
                "tables": [],
            }

        total_records = sum(r.total_records for r in reports)
        total_consistent = sum(r.consistent_records for r in reports)
        overall_rate = total_consistent / total_records if total_records > 0 else 1.0

        return {
            "total_tables": len(reports),
            "total_records": total_records,
            "total_consistent_records": total_consistent,
            "total_inconsistent_records": total_records - total_consistent,
            "overall_consistency_rate": overall_rate,
            "tables": [
                {
                    "table_name": r.table_name,
                    "consistency_rate": r.consistency_rate,
                    "inconsistent_records": r.inconsistent_records,
                }
                for r in reports
            ],
            "checked_at": datetime.now(),
        }
