"""
同步 DBAPI 2.0 实现

提供符合 DB-API 2.0 规范的同步连接和游标对象。
"""

import json
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy_couchdb.client import SyncCouchDBClient
from sqlalchemy_couchdb.exceptions import ProgrammingError


class Connection:
    """
    DBAPI 2.0 连接对象（同步）

    代表与 CouchDB 数据库的连接。
    """

    def __init__(self, client: SyncCouchDBClient):
        """
        初始化连接

        参数:
            client: SyncCouchDBClient 实例
        """
        self.client = client
        self._closed = False

    def cursor(self) -> "Cursor":
        """
        创建游标对象

        返回:
            Cursor 实例
        """
        if self._closed:
            raise ProgrammingError("无法在已关闭的连接上创建游标")

        return Cursor(self)

    def commit(self):
        """
        提交事务

        注意: CouchDB 自动提交每个操作，此方法为空操作。
        """
        # CouchDB 没有事务概念，自动提交
        pass

    def rollback(self):
        """
        回滚事务

        注意: CouchDB 不支持事务回滚，此方法为空操作。
        """
        # CouchDB 自动提交，不支持回滚
        # 为了兼容性，不抛出异常
        pass

    def close(self):
        """关闭连接"""
        if not self._closed:
            self.client.close()
            self._closed = True

    def __enter__(self):
        """上下文管理器入口"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器退出"""
        self.close()


class Cursor:
    """
    DBAPI 2.0 游标对象（同步）

    用于执行查询和获取结果。
    """

    def __init__(self, connection: Connection):
        """
        初始化游标

        参数:
            connection: Connection 实例
        """
        self.connection = connection
        self.client = connection.client

        # 查询结果
        self._rows: List[Tuple] = []
        self._row_index = 0

        # 游标属性
        self.description: Optional[List[Tuple]] = None  # 列描述
        self.rowcount: int = -1  # 受影响的行数
        self.arraysize: int = 1  # fetchmany 默认大小

        self._closed = False

    def execute(self, operation: str, parameters: Optional[Dict[str, Any]] = None):
        """
        执行数据库操作

        参数:
            operation: 操作字符串（JSON 格式的 Mango Query 或操作描述）
            parameters: 参数字典（可选）

        返回:
            self（支持链式调用）

        注意:
            operation 应该是由 Compiler 生成的 JSON 字符串，包含：
            {
                "type": "select|insert|update|delete",
                "table": "表名",
                "query": {...},  # Mango Query 或操作数据
                ...
            }
        """
        if self._closed:
            raise ProgrammingError("无法在已关闭的游标上执行操作")

        # 重置状态
        self._rows = []
        self._row_index = 0
        self.description = None
        self.rowcount = -1

        try:
            # 解析操作
            if operation == "PING":
                # 特殊命令：检查连接
                result = self.client.ping()
                self._rows = [(result,)]
                self.rowcount = 1
                return self

            # 解析 JSON 操作
            op_data = json.loads(operation)
            op_type = op_data.get("type")
            table = op_data.get("table")

            if op_type == "select":
                # SELECT 查询
                self._execute_select(op_data, parameters)

            elif op_type == "insert":
                # INSERT 操作
                self._execute_insert(op_data, parameters)

            elif op_type == "update":
                # UPDATE 操作
                self._execute_update(op_data, parameters)

            elif op_type == "delete":
                # DELETE 操作
                self._execute_delete(op_data, parameters)

            else:
                raise ProgrammingError(f"不支持的操作类型: {op_type}")

        except json.JSONDecodeError as e:
            raise ProgrammingError(f"无法解析操作: {e}")

        return self

    def _execute_select(self, op_data: Dict, parameters: Optional[Dict]):
        """执行 SELECT 查询"""
        selector = op_data.get("selector", {})
        fields = op_data.get("fields")
        limit = op_data.get("limit")
        skip = op_data.get("skip")
        sort = op_data.get("sort")

        # 应用参数
        if parameters:
            selector = self._apply_parameters(selector, parameters)

        # 执行查询
        docs = self.client.find(selector=selector, fields=fields, limit=limit, skip=skip, sort=sort)

        # 转换为行
        if docs:
            # 构建列描述
            if fields:
                columns = fields
            else:
                # 使用第一个文档的键作为列名
                columns = list(docs[0].keys())

            self.description = [(col, None, None, None, None, None, None) for col in columns]

            # 转换文档为元组
            self._rows = [tuple(doc.get(col) for col in columns) for doc in docs]
            self.rowcount = len(self._rows)
        else:
            # 即使没有结果，也需要设置 description
            if fields:
                columns = fields
            else:
                # 默认列
                columns = ["_id", "_rev"]

            self.description = [(col, None, None, None, None, None, None) for col in columns]
            self._rows = []
            self.rowcount = 0

    def _execute_insert(self, op_data: Dict, parameters: Optional[Dict]):
        """执行 INSERT 操作"""
        doc = op_data.get("document", {})

        # 应用参数
        if parameters:
            doc = self._apply_parameters(doc, parameters)

        # 执行插入
        result = self.client.create_document(doc)
        self.rowcount = 1

        # 返回插入的 ID 和 REV
        self._rows = [(result["id"], result["rev"])]
        self.description = [
            ("id", None, None, None, None, None, None),
            ("rev", None, None, None, None, None, None),
        ]

    def _execute_update(self, op_data: Dict, parameters: Optional[Dict]):
        """执行 UPDATE 操作"""
        selector = op_data.get("selector", {})
        updates = op_data.get("updates", {})

        # 应用参数
        if parameters:
            selector = self._apply_parameters(selector, parameters)
            updates = self._apply_parameters(updates, parameters)

        # 先查找要更新的文档
        docs = self.client.find(selector=selector)

        # 更新每个文档
        updated_count = 0
        for doc in docs:
            doc_id = doc["_id"]
            doc_rev = doc["_rev"]

            # 应用更新
            updated_doc = {**doc, **updates}

            # 执行更新
            self.client.update_document(doc_id, updated_doc, doc_rev)
            updated_count += 1

        self.rowcount = updated_count

    def _execute_delete(self, op_data: Dict, parameters: Optional[Dict]):
        """执行 DELETE 操作"""
        selector = op_data.get("selector", {})

        # 应用参数
        if parameters:
            selector = self._apply_parameters(selector, parameters)

        # 先查找要删除的文档
        docs = self.client.find(selector=selector)

        # 删除每个文档
        deleted_count = 0
        for doc in docs:
            doc_id = doc["_id"]
            doc_rev = doc["_rev"]

            # 执行删除
            self.client.delete_document(doc_id, doc_rev)
            deleted_count += 1

        self.rowcount = deleted_count

    def _apply_parameters(self, data: Any, parameters: Dict) -> Any:
        """
        递归应用参数到数据结构

        参数:
            data: 数据（可以是字典、列表或标量值）
            parameters: 参数字典

        返回:
            应用参数后的数据
        """
        if isinstance(data, dict):
            return {k: self._apply_parameters(v, parameters) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._apply_parameters(item, parameters) for item in data]
        elif isinstance(data, str) and data.startswith(":"):
            # 参数占位符，例如 :name
            param_name = data[1:]
            value = parameters.get(param_name, data)
            # 序列化值
            return self._serialize_value(value)
        else:
            return data

    def _serialize_value(self, value: Any) -> Any:
        """序列化值为 JSON 兼容格式"""
        from datetime import datetime, date

        if value is None:
            return None
        elif isinstance(value, datetime):
            return value.isoformat()
        elif isinstance(value, date):
            return value.isoformat()
        elif isinstance(value, (dict, list, str, int, float, bool)):
            return value
        else:
            # 其他类型转为字符串
            return str(value)

    def executemany(self, operation: str, seq_of_parameters: List[Dict[str, Any]]):
        """
        执行批量操作

        对于 INSERT 操作，使用 CouchDB 的 _bulk_docs API 进行批量插入。
        对于其他操作类型，回退到逐条执行。

        参数:
            operation: 操作字符串（JSON格式）
            seq_of_parameters: 参数字典列表

        返回:
            self（支持链式调用）
        """
        if self._closed:
            raise ProgrammingError("无法在已关闭的游标上执行操作")

        if not seq_of_parameters:
            # 空参数列表，直接返回
            return self

        # 重置状态
        self._rows = []
        self._row_index = 0
        self.description = None
        self.rowcount = -1

        try:
            # 解析操作
            op_data = json.loads(operation)
            op_type = op_data.get("type")

            if op_type == "insert":
                # INSERT 批量操作 - 使用 _bulk_docs
                self._execute_bulk_insert(op_data, seq_of_parameters)
            else:
                # 其他操作 - 回退到循环执行
                for parameters in seq_of_parameters:
                    self.execute(operation, parameters)

        except json.JSONDecodeError as e:
            raise ProgrammingError(f"无法解析操作: {e}")

        return self

    def _execute_bulk_insert(self, op_data: Dict, seq_of_parameters: List[Dict]):
        """
        执行批量 INSERT 操作

        使用 CouchDB 的 _bulk_docs API 一次性插入多条文档。

        参数:
            op_data: 操作数据（包含表名和文档模板）
            seq_of_parameters: 参数字典列表
        """
        table = op_data.get("table")
        doc_template = op_data.get("document", {})

        # 构建批量文档列表
        documents = []
        for parameters in seq_of_parameters:
            # 复制文档模板
            doc = doc_template.copy()

            # 应用参数
            if parameters:
                doc = self._apply_parameters(doc, parameters)

            documents.append(doc)

        # 调用 bulk_docs API
        from sqlalchemy_couchdb.exceptions import IntegrityError

        results = self.client.bulk_docs(documents)

        # 处理结果
        success_count = 0
        errors = []

        for idx, result in enumerate(results):
            if result.get("error"):
                # 记录错误
                errors.append(
                    {
                        "index": idx,
                        "error": result.get("error"),
                        "reason": result.get("reason"),
                        "id": result.get("id"),
                    }
                )
            else:
                success_count += 1

        # 如果有错误，抛出异常
        if errors:
            error_summary = f"批量插入部分失败: {len(errors)}/{len(results)} 失败"
            error_details = "\n".join(
                [
                    f"  [{e['index']}] {e['error']}: {e['reason']} (id={e.get('id', 'N/A')})"
                    for e in errors[:5]  # 最多显示5个错误
                ]
            )
            if len(errors) > 5:
                error_details += f"\n  ... 以及其他 {len(errors) - 5} 个错误"

            raise IntegrityError(f"{error_summary}\n{error_details}")

        # 设置返回结果
        self.rowcount = success_count

        # 构建返回的行（_id, _rev）
        self._rows = [
            (result.get("id"), result.get("rev")) for result in results if not result.get("error")
        ]

        # 设置列描述
        self.description = [
            ("id", None, None, None, None, None, None),
            ("rev", None, None, None, None, None, None),
        ]

    def fetchone(self) -> Optional[Tuple]:
        """
        获取下一行

        返回:
            元组或 None（如果没有更多行）
        """
        if self._row_index < len(self._rows):
            row = self._rows[self._row_index]
            self._row_index += 1
            return row
        return None

    def fetchmany(self, size: Optional[int] = None) -> List[Tuple]:
        """
        获取多行

        参数:
            size: 要获取的行数（默认为 arraysize）

        返回:
            行列表
        """
        if size is None:
            size = self.arraysize

        rows = self._rows[self._row_index : self._row_index + size]
        self._row_index += len(rows)
        return rows

    def fetchall(self) -> List[Tuple]:
        """
        获取所有剩余行

        返回:
            行列表
        """
        rows = self._rows[self._row_index :]
        self._row_index = len(self._rows)
        return rows

    def close(self):
        """关闭游标"""
        self._closed = True
        self._rows = []

    def __iter__(self):
        """迭代器接口"""
        return self

    def __next__(self):
        """获取下一行（迭代器）"""
        row = self.fetchone()
        if row is None:
            raise StopIteration
        return row
