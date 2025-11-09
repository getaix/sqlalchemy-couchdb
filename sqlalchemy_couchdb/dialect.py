"""
CouchDB Dialect - SQLAlchemy 方言实现

提供完整的 SQLAlchemy Dialect 接口，连接所有模块:
- 编译器 (Compiler)
- 类型系统 (Types)
- DBAPI 接口
"""

from typing import Dict, List, Tuple
from sqlalchemy.engine import default

from sqlalchemy_couchdb.compiler import (
    CouchDBCompiler,
    CouchDBDDLCompiler,
    CouchDBTypeCompiler,
)
from sqlalchemy_couchdb.types import colspecs


class CouchDBDialect(default.DefaultDialect):
    """
    CouchDB 方言（同步模式）

    实现 SQLAlchemy DefaultDialect 接口，提供:
    1. 连接管理
    2. SQL 编译
    3. 类型映射
    4. 元数据反射（部分支持）

    使用示例:
        engine = create_engine('couchdb://admin:password@localhost:5984/mydb')
        with engine.connect() as conn:
            result = conn.execute(text("SELECT * FROM users"))
    """

    # ==================== 基本属性 ====================

    name = "couchdb"  # 方言名称
    driver = "httpx"  # 驱动名称
    default_schema_name = None  # CouchDB 没有 schema 概念

    # 编译器
    statement_compiler = CouchDBCompiler
    ddl_compiler = CouchDBDDLCompiler
    type_compiler = CouchDBTypeCompiler

    # 类型映射
    colspecs = colspecs

    # ==================== 功能支持 ====================

    # 事务和隔离级别
    supports_transactions = False  # CouchDB 不支持传统事务
    supports_sane_rowcount = True  # 支持 rowcount
    supports_sane_multi_rowcount = False  # 不支持批量操作的 rowcount

    # DDL 和 schema
    supports_alter = False  # 不支持 ALTER TABLE
    supports_schemas = False  # 不支持 schema
    supports_views = False  # 暂不支持视图
    supports_sequences = False  # 不支持序列

    # 查询功能
    supports_native_boolean = True  # 支持原生布尔类型
    supports_native_decimal = False  # JSON 不支持原生 Decimal
    supports_default_values = True  # 支持默认值
    supports_empty_insert = True  # 支持空 INSERT

    # 其他
    # 禁用语句缓存以避免绑定参数值被缓存导致的错误
    # 因为我们的编译器将值直接嵌入到 JSON 中，缓存会导致不同的查询使用相同的值
    supports_statement_cache = False

    # 批量插入支持（使用 CouchDB _bulk_docs API）
    # 注意：我们使用 executemany 而不是 insertmanyvalues，因为 CouchDB 使用 _bulk_docs API
    supports_multivalues_insert = False  # 禁用以强制使用 executemany
    insert_executemany_returning = False  # CouchDB 不支持 RETURNING 但 bulk_docs 返回结果
    use_insertmanyvalues = False  # 明确禁用 insertmanyvalues 特性

    # ==================== 初始化 ====================

    def __init__(self, use_ssl=False, json_serializer=None, json_deserializer=None, **kwargs):
        """
        初始化方言

        参数:
            use_ssl: 是否使用 SSL/TLS
            json_serializer: 自定义 JSON 序列化器
            json_deserializer: 自定义 JSON 反序列化器
            **kwargs: 其他参数
        """
        super().__init__(**kwargs)
        self.use_ssl = use_ssl
        self.json_serializer = json_serializer
        self.json_deserializer = json_deserializer

    # ==================== 连接管理 ====================

    @classmethod
    def import_dbapi(cls):
        """
        导入 DBAPI 模块

        返回符合 DB-API 2.0 规范的模块。

        返回:
            dbapi 模块
        """
        import sqlalchemy_couchdb.dbapi as dbapi

        return dbapi

    def create_connect_args(self, url) -> Tuple[List, Dict]:
        """
        从 URL 创建连接参数

        URL 格式:
            couchdb://username:password@host:port/database
            couchdb+httpx://username:password@host:port/database

        参数:
            url: SQLAlchemy URL 对象

        返回:
            (args, kwargs) 元组，传递给 connect() 函数

        示例:
            url = make_url('couchdb://admin:pass@localhost:5984/mydb')
            args, kwargs = dialect.create_connect_args(url)
            # kwargs = {
            #     'host': 'localhost',
            #     'port': 5984,
            #     'username': 'admin',
            #     'password': 'pass',
            #     'database': 'mydb'
            # }
        """
        # 基础连接参数
        opts = {
            "host": url.host or "localhost",
            "port": url.port or 5984,
            "username": url.username,
            "password": url.password,
            "database": url.database,
            "use_ssl": self.use_ssl,
        }

        # 添加查询参数
        opts.update(url.query)

        return ([], opts)

    def do_ping(self, dbapi_connection) -> bool:
        """
        检查连接是否有效

        参数:
            dbapi_connection: DBAPI Connection 对象

        返回:
            True 表示连接有效，False 表示连接失败
        """
        try:
            cursor = dbapi_connection.cursor()
            cursor.execute("PING")
            cursor.close()
            return True
        except Exception:
            return False

    def do_close(self, dbapi_connection):
        """
        关闭连接

        参数:
            dbapi_connection: DBAPI Connection 对象
        """
        dbapi_connection.close()

    # ==================== 执行方法 ====================

    def do_execute(self, cursor, statement, parameters, context=None):
        """
        执行语句

        参数:
            cursor: DBAPI Cursor 对象
            statement: 编译后的 SQL 语句（实际上是 JSON 字符串）
            parameters: 参数字典
            context: 执行上下文
        """
        # 从 context 获取参数（如果可用）
        if context and hasattr(context, "compiled_parameters"):
            params_list = context.compiled_parameters
            if params_list and len(params_list) > 0:
                # 使用第一组参数
                parameters = params_list[0] if params_list[0] else parameters

        if parameters:
            cursor.execute(statement, parameters)
        else:
            cursor.execute(statement)

    def do_executemany(self, cursor, statement, parameters, context=None):
        """
        批量执行语句

        对于 INSERT 语句，使用 CouchDB 的 _bulk_docs API 进行批量插入。
        对于其他语句类型，回退到逐条执行。

        参数:
            cursor: DBAPI Cursor 对象
            statement: 编译后的 SQL 语句（实际上是 JSON 字符串）
            parameters: 参数列表，每个元素是一个字典
            context: 执行上下文

        注意:
            由于SQLAlchemy 2.0的参数绑定机制不适用于非标准SQL（JSON），
            建议使用 bulk_insert() 辅助函数进行批量插入。
            直接使用 execute(insert(table), params_list) 可能会导致参数传递问题。
        """
        cursor.executemany(statement, parameters)

    # ==================== 元数据反射 ====================

    def has_table(self, connection, table_name, schema=None, **kw) -> bool:
        """
        检查表是否存在

        在 CouchDB 中，"表" 对应于 type 字段的值。
        我们通过查询是否存在该 type 的文档来判断。

        参数:
            connection: 数据库连接
            table_name: 表名
            schema: Schema 名（忽略）

        返回:
            True 表示表存在，False 表示不存在
        """
        try:
            # 尝试查询该 type 的文档
            cursor = connection.cursor()
            import json

            query = json.dumps(
                {
                    "type": "select",
                    "table": table_name,
                    "selector": {"type": table_name},
                    "limit": 1,
                }
            )
            cursor.execute(query)
            result = cursor.fetchone()
            cursor.close()
            return result is not None
        except Exception:
            return False

    def get_table_names(self, connection, schema=None, **kw) -> List[str]:
        """
        获取所有表名

        在 CouchDB 中，我们返回所有不同的 type 值。

        参数:
            connection: 数据库连接
            schema: Schema 名（忽略）

        返回:
            表名列表
        """
        # CouchDB 没有直接的方式获取所有 type
        # 这需要遍历所有文档或使用视图
        # 暂时返回空列表
        return []

    def get_columns(self, connection, table_name, schema=None, **kw) -> List[Dict]:
        """
        获取表的列信息

        在 CouchDB 中，我们通过查询文档来推断字段。

        参数:
            connection: 数据库连接
            table_name: 表名
            schema: Schema 名（忽略）

        返回:
            列信息列表，每个元素是一个字典:
            {
                'name': 列名,
                'type': 类型,
                'nullable': 是否可空,
                'default': 默认值
            }
        """
        # 查询一个文档，推断字段
        try:
            cursor = connection.cursor()
            import json

            query = json.dumps(
                {
                    "type": "select",
                    "table": table_name,
                    "selector": {"type": table_name},
                    "limit": 1,
                }
            )
            cursor.execute(query)
            row = cursor.fetchone()
            cursor.close()

            if not row:
                return []

            # 从 description 获取列名
            columns = []
            if cursor.description:
                for col_desc in cursor.description:
                    col_name = col_desc[0]
                    # 简单推断类型（实际应该更智能）
                    columns.append(
                        {
                            "name": col_name,
                            "type": self._infer_column_type(row),
                            "nullable": True,
                            "default": None,
                        }
                    )

            return columns
        except Exception:
            return []

    def _infer_column_type(self, value):
        """
        推断列类型

        参数:
            value: 列值

        返回:
            SQLAlchemy 类型对象
        """
        from sqlalchemy import types as sa_types

        if value is None:
            return sa_types.String()
        elif isinstance(value, bool):
            return sa_types.Boolean()
        elif isinstance(value, int):
            return sa_types.Integer()
        elif isinstance(value, float):
            return sa_types.Float()
        elif isinstance(value, str):
            return sa_types.String()
        elif isinstance(value, (dict, list)):
            return sa_types.JSON()
        else:
            return sa_types.String()

    def get_pk_constraint(self, connection, table_name, schema=None, **kw) -> Dict:
        """
        获取主键约束

        在 CouchDB 中，_id 是主键。

        参数:
            connection: 数据库连接
            table_name: 表名
            schema: Schema 名（忽略）

        返回:
            主键约束字典: {'constrained_columns': ['_id'], 'name': None}
        """
        return {"constrained_columns": ["_id"], "name": None}

    def get_foreign_keys(self, connection, table_name, schema=None, **kw) -> List:
        """
        获取外键约束

        CouchDB 不支持外键，返回空列表。

        参数:
            connection: 数据库连接
            table_name: 表名
            schema: Schema 名（忽略）

        返回:
            空列表
        """
        return []

    def get_indexes(self, connection, table_name, schema=None, **kw) -> List:
        """
        获取索引信息

        CouchDB 的索引通过 Mango Index 管理，暂不支持反射。

        参数:
            connection: 数据库连接
            table_name: 表名
            schema: Schema 名（忽略）

        返回:
            空列表
        """
        return []


class AsyncCouchDBDialect(CouchDBDialect):
    """
    CouchDB 异步方言

    与 CouchDBDialect 相同，但使用异步 DBAPI。

    使用示例:
        engine = create_async_engine(
            'couchdb+async://admin:password@localhost:5984/mydb'
        )
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT * FROM users"))
    """

    # 标记为异步方言
    is_async = True
    supports_server_side_cursors = False

    # 禁用语句缓存（与基类相同，显式声明以确保生效）
    supports_statement_cache = False

    @classmethod
    def import_dbapi(cls):
        """
        导入异步 DBAPI 模块

        返回:
            异步 dbapi 模块（带有 __asyncio__ 标记）
        """
        import sqlalchemy_couchdb.dbapi as dbapi

        # 标记为异步 DBAPI（SQLAlchemy 会检查这个属性）
        if not hasattr(dbapi, "__asyncio__"):
            dbapi.__asyncio__ = True

        return dbapi

    def connect(self, *cargs, **cparams):
        """
        创建异步数据库连接

        使用 await_only() 在同步方法中调用 async_connect()。
        SQLAlchemy 在 greenlet 上下文中调用此方法。

        参数:
            *cargs: 位置参数（通常为空）
            **cparams: 连接参数（由 create_connect_args 生成）

        返回:
            AsyncConnection 实例
        """
        from sqlalchemy.util import await_only

        # 调用异步 connect 函数
        return await_only(self.dbapi.async_connect(*cargs, **cparams))

    def do_ping(self, dbapi_connection) -> bool:
        """
        检查连接是否有效（异步）

        使用 await_only() 在同步方法中调用异步操作。
        SQLAlchemy 通过 greenlet_spawn() 调用此方法。

        参数:
            dbapi_connection: 异步 DBAPI Connection 对象

        返回:
            True 表示连接有效，False 表示连接失败
        """
        from sqlalchemy.util import await_only

        try:
            cursor = dbapi_connection.cursor()
            await_only(cursor.execute("PING"))
            await_only(cursor.close())
            return True
        except Exception:
            return False

    def do_close(self, dbapi_connection):
        """
        关闭连接（异步）

        使用 await_only() 在同步方法中调用异步操作。
        SQLAlchemy 通过 greenlet_spawn() 调用此方法。

        参数:
            dbapi_connection: 异步 DBAPI Connection 对象
        """
        from sqlalchemy.util import await_only

        await_only(dbapi_connection.close())

    def do_execute(self, cursor, statement, parameters, context=None):
        """
        执行语句（异步）

        使用 await_only() 在同步方法中调用异步操作。
        SQLAlchemy 通过 greenlet_spawn() 调用此方法。

        参数:
            cursor: 异步 DBAPI Cursor 对象
            statement: 编译后的 SQL 语句（实际上是 JSON 字符串）
            parameters: 参数字典
            context: 执行上下文（包含 ORM 需要的 compile_state）
        """
        from sqlalchemy.util import await_only

        # 保存 context 到 cursor，供结果处理使用
        if hasattr(cursor, '_sqlalchemy_context'):
            cursor._sqlalchemy_context = context

        if parameters:
            await_only(cursor.execute(statement, parameters))
        else:
            await_only(cursor.execute(statement))

    def do_executemany(self, cursor, statement, parameters, context=None):
        """
        批量执行语句（异步）

        使用 await_only() 在同步方法中调用异步操作。
        SQLAlchemy 通过 greenlet_spawn() 调用此方法。

        对于 INSERT 语句，使用 CouchDB 的 _bulk_docs API 进行批量插入。
        对于其他语句类型，回退到逐条执行。

        参数:
            cursor: 异步 DBAPI Cursor 对象
            statement: 编译后的 SQL 语句（实际上是 JSON 字符串）
            parameters: 参数列表，每个元素是一个字典
            context: 执行上下文
        """
        from sqlalchemy.util import await_only

        await_only(cursor.executemany(statement, parameters))
