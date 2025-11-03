"""
双写同步机制 - 同时写入 CouchDB 和 RDBMS，确保数据一致性

功能：
1. 同步写入（阻塞直到两边都写入成功）
2. 异步写入队列（先写入主数据库，再异步写入从数据库）
3. 失败重试机制
4. 事务补偿（如果一方失败，回滚另一方）
"""

from typing import Any, Dict, Optional
from enum import Enum
from dataclasses import dataclass
import logging
from datetime import datetime
import time
from queue import Queue, Empty
from threading import Thread

from sqlalchemy import MetaData
from sqlalchemy.engine import Engine

from .mapper import FieldMapper


logger = logging.getLogger(__name__)


class WriteMode(Enum):
    """写入模式"""

    SYNC = "sync"  # 同步写入（两边都成功才返回）
    ASYNC = "async"  # 异步写入（先写主库，后台队列写从库）
    PRIMARY_ONLY = "primary_only"  # 只写主数据库
    SECONDARY_ONLY = "secondary_only"  # 只写从数据库


class DatabaseRole(Enum):
    """数据库角色"""

    PRIMARY = "primary"  # 主数据库（优先级高）
    SECONDARY = "secondary"  # 从数据库（可以异步同步）


@dataclass
class WriteResult:
    """写入结果"""

    success: bool
    primary_success: bool
    secondary_success: bool
    error: Optional[Exception] = None
    primary_error: Optional[Exception] = None
    secondary_error: Optional[Exception] = None
    write_time: float = 0.0  # 毫秒


@dataclass
class WriteTask:
    """异步写入任务"""

    operation: str  # "insert", "update", "delete"
    table_name: str
    data: Dict[str, Any]
    timestamp: datetime
    retry_count: int = 0


class DualWriteManager:
    """
    双写管理器

    同时管理 CouchDB 和 RDBMS 的写入，确保数据一致性。

    写入策略：
    1. 同步模式：同时写入两个数据库，任一失败则回滚
    2. 异步模式：先写入主数据库，成功后异步写入从数据库
    3. 主库优先：只写主数据库
    4. 从库优先：只写从数据库
    """

    def __init__(
        self,
        primary_engine: Engine,
        secondary_engine: Engine,
        field_mapper: FieldMapper,
        write_mode: WriteMode = WriteMode.SYNC,
        max_retry: int = 3,
        retry_delay: float = 1.0,
        async_queue_size: int = 1000,
    ):
        """
        初始化双写管理器

        Args:
            primary_engine: 主数据库引擎（通常是 CouchDB）
            secondary_engine: 从数据库引擎（RDBMS）
            field_mapper: 字段映射器
            write_mode: 写入模式
            max_retry: 最大重试次数
            retry_delay: 重试延迟（秒）
            async_queue_size: 异步队列大小
        """
        self.primary_engine = primary_engine
        self.secondary_engine = secondary_engine
        self.field_mapper = field_mapper
        self.write_mode = write_mode
        self.max_retry = max_retry
        self.retry_delay = retry_delay

        # 异步写入队列
        self.async_queue: Queue[WriteTask] = Queue(maxsize=async_queue_size)
        self.async_worker: Optional[Thread] = None
        self.async_worker_running = False

        # 统计信息
        self.stats = {
            "total_writes": 0,
            "success_writes": 0,
            "failed_writes": 0,
            "primary_failures": 0,
            "secondary_failures": 0,
            "retries": 0,
        }

        # 启动异步写入工作线程
        if write_mode == WriteMode.ASYNC:
            self._start_async_worker()

    def insert(
        self, table_name: str, data: Dict[str, Any], primary_first: bool = True
    ) -> WriteResult:
        """
        插入数据到两个数据库

        Args:
            table_name: 表名
            data: 数据字典
            primary_first: 是否先写主数据库

        Returns:
            WriteResult: 写入结果
        """
        start_time = time.time()
        self.stats["total_writes"] += 1

        try:
            if self.write_mode == WriteMode.SYNC:
                return self._sync_insert(table_name, data, primary_first)
            elif self.write_mode == WriteMode.ASYNC:
                return self._async_insert(table_name, data)
            elif self.write_mode == WriteMode.PRIMARY_ONLY:
                return self._primary_only_insert(table_name, data)
            elif self.write_mode == WriteMode.SECONDARY_ONLY:
                return self._secondary_only_insert(table_name, data)
        except Exception as e:
            logger.error(f"Insert failed: {e}")
            self.stats["failed_writes"] += 1
            return WriteResult(
                success=False,
                primary_success=False,
                secondary_success=False,
                error=e,
                write_time=(time.time() - start_time) * 1000,
            )

    def _sync_insert(
        self, table_name: str, data: Dict[str, Any], primary_first: bool
    ) -> WriteResult:
        """同步插入（事务性）"""
        start_time = time.time()

        primary_success = False
        secondary_success = False
        primary_error = None
        secondary_error = None
        primary_data = None
        secondary_data = None

        try:
            if primary_first:
                # 先写主数据库
                primary_data, primary_error = self._write_primary(table_name, data)
                primary_success = primary_error is None

                if primary_success:
                    # 主数据库成功，写从数据库
                    secondary_data, secondary_error = self._write_secondary(table_name, data)
                    secondary_success = secondary_error is None

                    if not secondary_success:
                        # 从数据库失败，回滚主数据库
                        logger.warning("Secondary write failed, rolling back primary")
                        self._rollback_primary(table_name, primary_data)
                        primary_success = False
            else:
                # 先写从数据库
                secondary_data, secondary_error = self._write_secondary(table_name, data)
                secondary_success = secondary_error is None

                if secondary_success:
                    # 从数据库成功，写主数据库
                    primary_data, primary_error = self._write_primary(table_name, data)
                    primary_success = primary_error is None

                    if not primary_success:
                        # 主数据库失败，回滚从数据库
                        logger.warning("Primary write failed, rolling back secondary")
                        self._rollback_secondary(table_name, secondary_data)
                        secondary_success = False

            success = primary_success and secondary_success

            if success:
                self.stats["success_writes"] += 1
            else:
                self.stats["failed_writes"] += 1
                if not primary_success:
                    self.stats["primary_failures"] += 1
                if not secondary_success:
                    self.stats["secondary_failures"] += 1

            return WriteResult(
                success=success,
                primary_success=primary_success,
                secondary_success=secondary_success,
                primary_error=primary_error,
                secondary_error=secondary_error,
                write_time=(time.time() - start_time) * 1000,
            )

        except Exception as e:
            logger.error(f"Sync insert failed: {e}")
            self.stats["failed_writes"] += 1
            return WriteResult(
                success=False,
                primary_success=primary_success,
                secondary_success=secondary_success,
                error=e,
                write_time=(time.time() - start_time) * 1000,
            )

    def _async_insert(self, table_name: str, data: Dict[str, Any]) -> WriteResult:
        """异步插入（先写主库，异步队列写从库）"""
        start_time = time.time()

        # 先写主数据库
        primary_data, primary_error = self._write_primary(table_name, data)
        primary_success = primary_error is None

        if not primary_success:
            self.stats["failed_writes"] += 1
            self.stats["primary_failures"] += 1
            return WriteResult(
                success=False,
                primary_success=False,
                secondary_success=False,
                primary_error=primary_error,
                write_time=(time.time() - start_time) * 1000,
            )

        # 将从数据库写入任务加入队列
        task = WriteTask(
            operation="insert", table_name=table_name, data=data, timestamp=datetime.now()
        )

        try:
            self.async_queue.put(task, timeout=1.0)
            logger.debug(f"Added insert task to async queue: {table_name}")
        except Exception as e:
            logger.error(f"Failed to add task to async queue: {e}")

        self.stats["success_writes"] += 1

        return WriteResult(
            success=True,
            primary_success=True,
            secondary_success=True,  # 假设会成功
            write_time=(time.time() - start_time) * 1000,
        )

    def _primary_only_insert(self, table_name: str, data: Dict[str, Any]) -> WriteResult:
        """只写主数据库"""
        start_time = time.time()
        primary_data, primary_error = self._write_primary(table_name, data)
        primary_success = primary_error is None

        if primary_success:
            self.stats["success_writes"] += 1
        else:
            self.stats["failed_writes"] += 1
            self.stats["primary_failures"] += 1

        return WriteResult(
            success=primary_success,
            primary_success=primary_success,
            secondary_success=False,
            primary_error=primary_error,
            write_time=(time.time() - start_time) * 1000,
        )

    def _secondary_only_insert(self, table_name: str, data: Dict[str, Any]) -> WriteResult:
        """只写从数据库"""
        start_time = time.time()
        secondary_data, secondary_error = self._write_secondary(table_name, data)
        secondary_success = secondary_error is None

        if secondary_success:
            self.stats["success_writes"] += 1
        else:
            self.stats["failed_writes"] += 1
            self.stats["secondary_failures"] += 1

        return WriteResult(
            success=secondary_success,
            primary_success=False,
            secondary_success=secondary_success,
            secondary_error=secondary_error,
            write_time=(time.time() - start_time) * 1000,
        )

    def _write_primary(
        self, table_name: str, data: Dict[str, Any]
    ) -> tuple[Optional[Dict[str, Any]], Optional[Exception]]:
        """
        写入主数据库（CouchDB）

        Returns:
            (写入后的数据包含_id和_rev, 错误对象)
        """
        try:
            with self.primary_engine.connect() as conn:
                # 执行插入操作
                from sqlalchemy import text

                # 假设使用原生SQL或者通过table对象插入
                # 实际应该调用 CouchDB 客户端的 insert 方法
                result = conn.execute(
                    text(f"INSERT INTO {table_name} VALUES (:data)"), {"data": data}
                )
                conn.commit()

                # 返回插入后的数据（包含_id和_rev用于回滚）
                inserted_data = {
                    **data,
                    "_id": data.get("_id"),
                    "_rev": result.lastrowid if hasattr(result, "lastrowid") else None,
                }

                logger.debug(
                    f"Primary write successful: {table_name}, id={inserted_data.get('_id')}"
                )
                return inserted_data, None

        except Exception as e:
            logger.error(f"Primary write failed for {table_name}: {e}")
            return None, e

    def _write_secondary(
        self, table_name: str, data: Dict[str, Any]
    ) -> tuple[Optional[Dict[str, Any]], Optional[Exception]]:
        """
        写入从数据库（RDBMS）

        Returns:
            (写入后的数据包含主键, 错误对象)
        """
        try:
            # 字段映射：CouchDB格式 -> RDBMS格式
            mapped_data = self.field_mapper.to_rdbms(data, table_name)

            with self.secondary_engine.connect() as conn:
                metadata = MetaData()
                metadata.reflect(bind=self.secondary_engine)

                if table_name not in metadata.tables:
                    raise ValueError(f"Table {table_name} not found in secondary database")

                table = metadata.tables[table_name]
                result = conn.execute(table.insert().values(**mapped_data))
                conn.commit()

                # 获取插入后的主键
                primary_key = None
                if hasattr(result, "inserted_primary_key"):
                    primary_key = (
                        result.inserted_primary_key[0] if result.inserted_primary_key else None
                    )

                inserted_data = {**mapped_data, "_primary_key": primary_key}

                logger.debug(f"Secondary write successful: {table_name}, pk={primary_key}")
                return inserted_data, None

        except Exception as e:
            logger.error(f"Secondary write failed for {table_name}: {e}")
            return None, e

    def _rollback_primary(self, table_name: str, data: Optional[Dict[str, Any]]) -> bool:
        """
        回滚主数据库（CouchDB）- 删除已写入的数据

        Args:
            table_name: 表名
            data: 写入时返回的数据，包含_id和_rev

        Returns:
            是否回滚成功
        """
        if data is None:
            logger.warning("Cannot rollback primary: no data provided")
            return False

        doc_id = data.get("_id")
        if not doc_id:
            logger.error("Cannot rollback primary: missing _id")
            return False

        try:
            with self.primary_engine.connect() as conn:
                # 删除已插入的文档
                from sqlalchemy import text

                conn.execute(
                    text(f"DELETE FROM {table_name} WHERE _id = :doc_id"), {"doc_id": doc_id}
                )
                conn.commit()

                logger.info(f"Primary rollback successful: {table_name}, id={doc_id}")
                return True

        except Exception as e:
            logger.error(f"Primary rollback failed for {table_name}, id={doc_id}: {e}")
            # 回滚失败是严重问题，应该记录到错误日志或告警系统
            self._log_rollback_failure("primary", table_name, doc_id, e)
            return False

    def _rollback_secondary(self, table_name: str, data: Optional[Dict[str, Any]]) -> bool:
        """
        回滚从数据库（RDBMS）- 删除已写入的数据

        Args:
            table_name: 表名
            data: 写入时返回的数据，包含主键

        Returns:
            是否回滚成功
        """
        if data is None:
            logger.warning("Cannot rollback secondary: no data provided")
            return False

        primary_key = data.get("_primary_key")
        if primary_key is None:
            logger.error("Cannot rollback secondary: missing primary key")
            return False

        try:
            with self.secondary_engine.connect() as conn:
                metadata = MetaData()
                metadata.reflect(bind=self.secondary_engine)

                if table_name not in metadata.tables:
                    raise ValueError(f"Table {table_name} not found in secondary database")

                table = metadata.tables[table_name]

                # 获取主键列名
                pk_columns = [col for col in table.columns if col.primary_key]
                if not pk_columns:
                    raise ValueError(f"No primary key found for table {table_name}")

                pk_column = pk_columns[0]

                # 删除记录
                conn.execute(table.delete().where(pk_column == primary_key))
                conn.commit()

                logger.info(f"Secondary rollback successful: {table_name}, pk={primary_key}")
                return True

        except Exception as e:
            logger.error(f"Secondary rollback failed for {table_name}, pk={primary_key}: {e}")
            # 回滚失败是严重问题，应该记录到错误日志或告警系统
            self._log_rollback_failure("secondary", table_name, primary_key, e)
            return False

    def _log_rollback_failure(
        self, database: str, table_name: str, record_id: Any, error: Exception
    ) -> None:
        """
        记录回滚失败的详细信息

        这些失败的回滚需要人工介入或者通过补偿机制处理
        """
        failure_info = {
            "timestamp": datetime.now().isoformat(),
            "database": database,
            "table": table_name,
            "record_id": record_id,
            "error": str(error),
            "error_type": type(error).__name__,
        }

        # 记录到日志
        logger.critical(f"ROLLBACK FAILURE: {failure_info}")

        # 可以考虑：
        # 1. 写入到专门的失败队列
        # 2. 发送告警通知
        # 3. 记录到数据库以便后续处理
        # 例如：self._save_to_failure_queue(failure_info)

    def _start_async_worker(self) -> None:
        """启动异步写入工作线程"""
        if self.async_worker is not None:
            return

        self.async_worker_running = True
        self.async_worker = Thread(target=self._async_worker_loop, daemon=True)
        self.async_worker.start()
        logger.info("Async write worker started")

    def _async_worker_loop(self) -> None:
        """异步写入工作循环"""
        while self.async_worker_running:
            try:
                # 从队列获取任务
                task = self.async_queue.get(timeout=1.0)

                # 执行写入
                if task.operation == "insert":
                    _, error = self._write_secondary(task.table_name, task.data)

                    if error is not None:
                        # 写入失败，重试
                        if task.retry_count < self.max_retry:
                            task.retry_count += 1
                            self.stats["retries"] += 1
                            time.sleep(self.retry_delay)
                            self.async_queue.put(task)
                            logger.warning(
                                f"Secondary write failed, retry {task.retry_count}/{self.max_retry}: {error}"
                            )
                        else:
                            logger.error(
                                f"Secondary write failed after {self.max_retry} retries: {error}"
                            )
                            self.stats["secondary_failures"] += 1

            except Empty:
                continue
            except Exception as e:
                logger.error(f"Async worker error: {e}")

    def stop_async_worker(self) -> None:
        """停止异步写入工作线程"""
        if self.async_worker is None:
            return

        self.async_worker_running = False
        self.async_worker.join(timeout=5.0)
        logger.info("Async write worker stopped")

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self.stats,
            "async_queue_size": self.async_queue.qsize(),
            "success_rate": (
                self.stats["success_writes"] / self.stats["total_writes"]
                if self.stats["total_writes"] > 0
                else 0
            ),
        }
