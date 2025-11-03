"""
CouchDB 复制功能

实现 CouchDB 的复制功能，支持数据库间的数据同步。

主要功能：
- 单次复制 (one-shot replication)
- 连续复制 (continuous replication)
- 双向复制 (bidirectional replication)
- 冲突检测和解决
- 复制监控和统计
"""

import time
import threading
from typing import Optional, Dict, Any, Callable, List
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy_couchdb.exceptions import OperationalError, IntegrityError


class ReplicationState(Enum):
    """复制状态"""

    IDLE = "idle"  # 空闲
    RUNNING = "running"  # 运行中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"  # 失败
    CANCELLED = "cancelled"  # 已取消


class ConflictStrategy(Enum):
    """冲突解决策略"""

    SOURCE_WINS = "source_wins"  # 源优先
    TARGET_WINS = "target_wins"  # 目标优先
    LATEST_WINS = "latest_wins"  # 最新优先
    MANUAL = "manual"  # 手动解决


@dataclass
class ReplicationStats:
    """复制统计信息"""

    docs_read: int = 0  # 读取文档数
    docs_written: int = 0  # 写入文档数
    doc_write_failures: int = 0  # 写入失败数
    missing_checked: int = 0  # 检查缺失数
    missing_found: int = 0  # 发现缺失数
    revisions_checked: int = 0  # 检查版本数
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    @property
    def duration(self) -> Optional[float]:
        """复制持续时间（秒）"""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None

    @property
    def docs_per_second(self) -> Optional[float]:
        """每秒处理文档数"""
        duration = self.duration
        if duration and duration > 0:
            return self.docs_written / duration
        return None


@dataclass
class ReplicationResult:
    """复制结果"""

    ok: bool  # 是否成功
    session_id: str  # 会话 ID
    source_last_seq: str  # 源最后序列号
    replication_id_version: int = 4  # 复制 ID 版本
    history: List[Dict[str, Any]] = field(default_factory=list)
    stats: ReplicationStats = field(default_factory=ReplicationStats)


class Replicator:
    """
    复制器

    处理两个数据库之间的复制。

    示例:
        >>> replicator = Replicator(source_client, target_client)
        >>> result = replicator.replicate()
        >>> print(f"Replicated {result.stats.docs_written} documents")
    """

    def __init__(
        self,
        source_client,
        target_client,
        continuous: bool = False,
        create_target: bool = False,
        doc_ids: Optional[List[str]] = None,
        filter_function: Optional[Callable[[Dict[str, Any]], bool]] = None,
        conflict_strategy: ConflictStrategy = ConflictStrategy.SOURCE_WINS,
        batch_size: int = 100,
        checkpoint_interval: int = 5000,  # 检查点间隔（文档数）
    ):
        """
        初始化复制器

        参数:
            source_client: 源数据库客户端
            target_client: 目标数据库客户端
            continuous: 是否连续复制
            create_target: 是否创建目标数据库
            doc_ids: 要复制的文档 ID 列表（None 表示全部）
            filter_function: 文档过滤函数
            conflict_strategy: 冲突解决策略
            batch_size: 批处理大小
            checkpoint_interval: 检查点间隔
        """
        self.source_client = source_client
        self.target_client = target_client
        self.continuous = continuous
        self.create_target = create_target
        self.doc_ids = doc_ids
        self.filter_function = filter_function
        self.conflict_strategy = conflict_strategy
        self.batch_size = batch_size
        self.checkpoint_interval = checkpoint_interval

        self.state = ReplicationState.IDLE
        self.stats = ReplicationStats()
        self._stop_flag = False
        self._thread = None
        self._last_seq = "0"
        self._session_id = self._generate_session_id()

    def replicate(self) -> ReplicationResult:
        """
        执行复制

        返回:
            ReplicationResult 对象
        """
        if self.state == ReplicationState.RUNNING:
            raise RuntimeError("Replication already running")

        self.state = ReplicationState.RUNNING
        self.stats.start_time = datetime.now()
        self._stop_flag = False

        try:
            if self.continuous:
                self._replicate_continuous()
            else:
                self._replicate_once()

            self.state = ReplicationState.COMPLETED
            self.stats.end_time = datetime.now()

            return ReplicationResult(
                ok=True,
                session_id=self._session_id,
                source_last_seq=self._last_seq,
                stats=self.stats,
            )

        except Exception as e:
            self.state = ReplicationState.FAILED
            self.stats.end_time = datetime.now()
            raise OperationalError(f"Replication failed: {e}")

    def start_continuous(self):
        """启动连续复制（异步）"""
        if not self.continuous:
            raise ValueError("Replicator not configured for continuous replication")

        if self._thread and self._thread.is_alive():
            raise RuntimeError("Continuous replication already running")

        self._stop_flag = False
        self._thread = threading.Thread(target=self._replicate_continuous_thread, daemon=True)
        self._thread.start()

    def stop(self):
        """停止连续复制"""
        if not self.continuous:
            raise ValueError("Not a continuous replication")

        self._stop_flag = True
        if self._thread:
            self._thread.join(timeout=10)
            self._thread = None

        self.state = ReplicationState.CANCELLED

    def _replicate_once(self):
        """执行单次复制"""
        # 1. 获取源数据库的所有文档
        if self.doc_ids:
            doc_ids = self.doc_ids
        else:
            # 获取所有文档 ID
            doc_ids = self._get_all_doc_ids()

        # 2. 按批次复制
        for i in range(0, len(doc_ids), self.batch_size):
            batch_ids = doc_ids[i : i + self.batch_size]
            self._replicate_batch(batch_ids)

            # 检查点
            if (i + len(batch_ids)) % self.checkpoint_interval == 0:
                self._save_checkpoint()

    def _replicate_continuous(self):
        """执行连续复制"""
        # 使用 _changes API 监听变更
        from sqlalchemy_couchdb.changes import ChangesListener

        listener = ChangesListener(
            self.source_client, on_change=self._handle_change, include_docs=True
        )

        listener.start(since=self._last_seq)

        # 等待停止信号
        while not self._stop_flag:
            time.sleep(1)

        listener.stop()

    def _replicate_continuous_thread(self):
        """连续复制线程"""
        try:
            self._replicate_continuous()
        except Exception as e:
            print(f"Continuous replication error: {e}")
            self.state = ReplicationState.FAILED

    def _handle_change(self, change):
        """处理变更（连续复制）"""
        try:
            # 应用过滤器
            if self.filter_function and change.doc:
                if not self.filter_function(change.doc):
                    return

            # 复制文档
            if change.deleted:
                self._replicate_deletion(change.id, change.changes[0]["rev"])
            elif change.doc:
                self._replicate_document(change.doc)

            self._last_seq = change.seq

        except Exception as e:
            print(f"Error replicating change {change.id}: {e}")
            self.stats.doc_write_failures += 1

    def _replicate_batch(self, doc_ids: List[str]):
        """复制一批文档"""
        for doc_id in doc_ids:
            try:
                # 从源读取
                doc = self.source_client.get_document(doc_id)
                self.stats.docs_read += 1

                # 应用过滤器
                if self.filter_function and not self.filter_function(doc):
                    continue

                # 写入目标
                self._replicate_document(doc)

            except Exception as e:
                print(f"Error replicating document {doc_id}: {e}")
                self.stats.doc_write_failures += 1

    def _replicate_document(self, doc: Dict[str, Any]):
        """复制单个文档"""
        doc_id = doc["_id"]
        source_rev = doc["_rev"]

        try:
            # 检查目标是否存在
            target_doc = self.target_client.get_document(doc_id)
            target_rev = target_doc["_rev"]

            # 检查冲突
            if self._has_conflict(source_rev, target_rev):
                doc = self._resolve_conflict(doc, target_doc)

            # 更新文档
            # 移除 _rev 以便 CouchDB 自动处理
            doc_copy = {k: v for k, v in doc.items() if k != "_rev"}
            self.target_client.update_document(doc_id, doc_copy, target_rev)
            self.stats.docs_written += 1

        except Exception as e:
            # 目标不存在，创建新文档
            if "not found" in str(e).lower() or "404" in str(e):
                doc_copy = {k: v for k, v in doc.items() if k != "_rev"}
                self.target_client.create_document(doc_copy)
                self.stats.docs_written += 1
            else:
                raise

    def _replicate_deletion(self, doc_id: str, rev: str):
        """复制删除操作"""
        try:
            target_doc = self.target_client.get_document(doc_id)
            self.target_client.delete_document(doc_id, target_doc["_rev"])
            self.stats.docs_written += 1
        except Exception:
            # 目标已删除或不存在，忽略
            pass

    def _has_conflict(self, source_rev: str, target_rev: str) -> bool:
        """检查是否有冲突"""
        # 简单的版本比较
        return source_rev != target_rev

    def _resolve_conflict(
        self, source_doc: Dict[str, Any], target_doc: Dict[str, Any]
    ) -> Dict[str, Any]:
        """解决冲突"""
        if self.conflict_strategy == ConflictStrategy.SOURCE_WINS:
            return source_doc
        elif self.conflict_strategy == ConflictStrategy.TARGET_WINS:
            return target_doc
        elif self.conflict_strategy == ConflictStrategy.LATEST_WINS:
            # 比较版本号（简单实现）
            source_rev_num = int(source_doc["_rev"].split("-")[0])
            target_rev_num = int(target_doc["_rev"].split("-")[0])
            return source_doc if source_rev_num > target_rev_num else target_doc
        else:
            # 手动解决（抛出异常）
            raise IntegrityError(
                f"Conflict detected for document {source_doc['_id']}: "
                f"source rev {source_doc['_rev']} vs target rev {target_doc['_rev']}"
            )

    def _get_all_doc_ids(self) -> List[str]:
        """获取所有文档 ID"""
        # 使用 _all_docs 视图
        url = self.source_client._build_db_url("_all_docs")
        response = self.source_client.client.get(url)
        data = response.json()

        doc_ids = [row["id"] for row in data.get("rows", [])]
        self.stats.missing_checked = len(doc_ids)

        return doc_ids

    def _save_checkpoint(self):
        """保存检查点"""
        # 在实际实现中，应该将检查点保存到特殊文档中
        # 这里简化处理
        pass

    def _generate_session_id(self) -> str:
        """生成会话 ID"""
        import uuid

        return str(uuid.uuid4())


class BidirectionalReplicator:
    """
    双向复制器

    在两个数据库之间建立双向复制。

    示例:
        >>> replicator = BidirectionalReplicator(client_a, client_b)
        >>> replicator.start()
        >>> # ... 数据将在两个数据库间同步 ...
        >>> replicator.stop()
    """

    def __init__(self, client_a, client_b, continuous: bool = True, **kwargs):
        """
        初始化双向复制器

        参数:
            client_a: 数据库 A 客户端
            client_b: 数据库 B 客户端
            continuous: 是否连续复制
            **kwargs: 传递给 Replicator 的其他参数
        """
        self.client_a = client_a
        self.client_b = client_b
        self.continuous = continuous

        # 创建两个复制器
        self.replicator_a_to_b = Replicator(client_a, client_b, continuous=continuous, **kwargs)
        self.replicator_b_to_a = Replicator(client_b, client_a, continuous=continuous, **kwargs)

    def start(self):
        """启动双向复制"""
        if not self.continuous:
            # 单次复制
            result_a_to_b = self.replicator_a_to_b.replicate()
            result_b_to_a = self.replicator_b_to_a.replicate()
            return {"a_to_b": result_a_to_b, "b_to_a": result_b_to_a}
        else:
            # 连续复制
            self.replicator_a_to_b.start_continuous()
            self.replicator_b_to_a.start_continuous()

    def stop(self):
        """停止双向复制"""
        if self.continuous:
            self.replicator_a_to_b.stop()
            self.replicator_b_to_a.stop()

    def get_stats(self) -> Dict[str, ReplicationStats]:
        """获取统计信息"""
        return {"a_to_b": self.replicator_a_to_b.stats, "b_to_a": self.replicator_b_to_a.stats}


# 添加到 SyncCouchDBClient
def create_replicator(self, target_client, **kwargs) -> Replicator:
    """
    创建复制器

    参数:
        target_client: 目标数据库客户端
        **kwargs: 传递给 Replicator 的参数

    返回:
        Replicator 实例
    """
    return Replicator(self, target_client, **kwargs)


def replicate_to(self, target_client, **kwargs) -> ReplicationResult:
    """
    复制到目标数据库

    参数:
        target_client: 目标数据库客户端
        **kwargs: 传递给 Replicator 的参数

    返回:
        ReplicationResult 对象
    """
    replicator = Replicator(self, target_client, **kwargs)
    return replicator.replicate()
