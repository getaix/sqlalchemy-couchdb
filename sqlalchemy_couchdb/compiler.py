"""
SQL 编译器 - 将 SQL 语句编译为 CouchDB Mango Query

核心功能:
1. SQL AST → Mango Query JSON 转换
2. WHERE 子句解析
3. 支持 SELECT, INSERT, UPDATE, DELETE
"""

import json
from typing import Any, Dict, List

from sqlalchemy.sql import compiler
from sqlalchemy.sql import operators


class CouchDBCompiler(compiler.SQLCompiler):
    """
    CouchDB SQL 编译器

    将 SQLAlchemy SQL AST 编译为 CouchDB Mango Query JSON。
    """

    def __init__(self, *args, **kwargs):
        """初始化编译器"""
        super().__init__(*args, **kwargs)
        # 初始化 compile_state 属性以避免 AttributeError
        if not hasattr(self, 'compile_state'):
            self.compile_state = None

    # ORM 支持：定义这些属性以满足 SQLAlchemy ORM 的期望
    # 注意：不要在 __init__ 中设置它们，因为基类已经定义了 property
    @property
    def postfetch(self):
        """ORM 插入后需要获取的列（CouchDB 不支持）"""
        return []

    def visit_select(self, select_stmt, **kwargs):
        """
        编译 SELECT 语句

        SQL:
            SELECT name, age FROM users WHERE age > 25 LIMIT 10

        Mango Query:
            {
                "type": "select",
                "table": "users",
                "selector": {"type": "users", "age": {"$gt": 25}},
                "fields": ["name", "age"],
                "limit": 10
            }
        """
        # 首先调用父类方法以正确设置编译状态
        # 这确保 ORM 编译状态被正确初始化
        try:
            # 调用父类方法但忽略结果，我们生成自己的查询
            super().visit_select(select_stmt, **kwargs)
        except Exception:
            # 如果父类方法失败，继续我们的编译过程
            pass

        # 保存 ORM 编译状态（如果存在）
        if "compile_state" in kwargs:
            self.compile_state = kwargs["compile_state"]

        # 获取表名
        table_name = self._get_table_name(select_stmt)

        # 构建选择器（WHERE 子句）
        selector = {"type": table_name}  # 添加表名过滤

        if select_stmt._where_criteria:
            # _where_criteria 是一个元组，包含所有 WHERE 条件
            # 需要处理元组中的每个元素
            if len(select_stmt._where_criteria) > 0:
                if len(select_stmt._where_criteria) == 1:
                    # 单个条件
                    where_selector = self._compile_where(select_stmt._where_criteria[0])
                else:
                    # 多个条件，用 AND 连接
                    subclauses = [
                        self._compile_where(clause) for clause in select_stmt._where_criteria
                    ]
                    where_selector = {"$and": subclauses}

                # 合并选择器
                if where_selector:
                    selector.update(where_selector)

        # 获取要查询的字段
        fields = None
        is_count_query = False  # 标记是否为 COUNT 查询

        if hasattr(select_stmt, "selected_columns"):
            columns = select_stmt.selected_columns
            # 检查是否是 SELECT *
            if columns and not self._is_select_star(columns):
                # 检查是否是 COUNT 查询
                for col in columns:
                    col_str = str(col).upper()
                    if "COUNT" in col_str or "FUNC.COUNT" in col_str:
                        is_count_query = True
                        # COUNT 查询只需要 _id 字段以减少数据传输
                        fields = ["_id"]
                        break

                if not is_count_query:
                    fields = [col.name for col in columns if hasattr(col, "name")]

        # 构建查询对象
        query = {
            "type": "select",
            "table": table_name,
            "selector": selector,
        }

        # 标记 COUNT 查询
        if is_count_query:
            query["is_count"] = True

        if fields:
            query["fields"] = fields

        # LIMIT 子句
        if select_stmt._limit_clause is not None:
            query["limit"] = self._get_limit_value(select_stmt._limit_clause)
        else:
            # CouchDB默认limit是25，这对大多数查询来说太小
            if is_count_query:
                # COUNT 查询使用分段策略：每次最多查 10000 条 _id
                query["limit"] = 10000
            else:
                # 普通查询使用较大的默认值
                query["limit"] = 10000

        # OFFSET 子句
        if select_stmt._offset_clause is not None:
            query["skip"] = self._get_offset_value(select_stmt._offset_clause)

        # ORDER BY 子句
        # 注意：COUNT 查询不需要排序，跳过 ORDER BY 以避免索引要求
        if select_stmt._order_by_clauses and not is_count_query:
            query["sort"] = self._compile_order_by(select_stmt._order_by_clauses)

        # 返回 JSON 字符串
        return json.dumps(query)

    def visit_insert(self, insert_stmt, **kwargs):
        """
        编译 INSERT 语句

        SQL:
            INSERT INTO users (name, age) VALUES ('Alice', 30)

        CouchDB:
            {
                "type": "insert",
                "table": "users",
                "document": {"type": "users", "name": "Alice", "age": 30}
            }
        """
        # 获取表名
        table_name = self._get_table_name(insert_stmt)

        # 构建文档
        document = {"type": table_name}

        # 获取列和值
        if insert_stmt.select is None:
            # 从 _values 提取值（SQLAlchemy 2.0）
            has_values_attr = hasattr(insert_stmt, "_values")
            values_content = getattr(insert_stmt, "_values", None)

            # 调试：打印状态
            # print(f"[DEBUG visit_insert] Table: {table_name}, has_values: {has_values_attr}, values: {values_content}, is None: {values_content is None}")

            # 只有当_values明确存在且不为None时，才从values提取
            # 空字典{}也会进入这个分支，这是正常的（表示没有提供任何值）
            if has_values_attr and values_content is not None:
                # 有显式的 values() 调用
                for col_name, value in values_content.items():
                    # 处理 Column 对象（ORM 风格）
                    if hasattr(col_name, "name"):
                        actual_name = col_name.name
                    else:
                        actual_name = str(col_name)

                    # _id 需要包含，但 _rev 在插入时应该跳过
                    if actual_name != "_rev":
                        document[actual_name] = self._extract_value(value)
            else:
                # 没有 values() 调用 - 这是 executemany 模式
                # 为所有列生成占位符，并告诉 SQLAlchemy 需要这些参数
                from sqlalchemy.sql.elements import BindParameter

                # print(f"[DEBUG visit_insert] Generating placeholders for table: {insert_stmt.table.name}")

                for col in insert_stmt.table.columns:
                    # _rev 在插入时应该跳过，_id 允许用户指定
                    if col.name != "_rev":
                        # 创建 BindParameter 并添加到 statement
                        param = BindParameter(col.name, type_=col.type, required=False)
                        # 注册参数（添加到编译器的绑定参数列表中）
                        self.binds[param.key] = param
                        # 生成占位符
                        document[col.name] = f":{col.name}"

        query = {"type": "insert", "table": table_name, "document": document}

        return json.dumps(query)

    def _extract_value(self, value):
        """从 SQLAlchemy 表达式中提取实际值"""
        from sqlalchemy.sql.elements import BindParameter

        # 处理绑定参数
        if isinstance(value, BindParameter):
            # 检查是否有实际值（如 insert().values(name="Alice")）
            # 还是纯占位符（如 insert().values(name=bindparam('name'))）
            actual_value = None

            # BindParameter 可能携带了实际值
            if hasattr(value, "effective_value"):
                actual_value = value.effective_value
            elif hasattr(value, "value") and value.value is not None:
                actual_value = value.value

            if actual_value is not None:
                # 有实际值，序列化并嵌入
                return self._serialize_for_json(actual_value)
            else:
                # 纯占位符，注册参数并返回占位符
                self.binds[value.key] = value
                return f":{value.key}"

        # 处理字面量
        elif hasattr(value, "value"):
            return self._serialize_for_json(value.value)

        # 直接值
        else:
            return self._serialize_for_json(value)

    def _serialize_for_json(self, value):
        """将值序列化为 JSON 兼容格式"""
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
            return str(value)

    def visit_update(self, update_stmt, **kwargs):
        """
        编译 UPDATE 语句

        SQL:
            UPDATE users SET age = 31 WHERE name = 'Alice'

        CouchDB:
            {
                "type": "update",
                "table": "users",
                "selector": {"type": "users", "name": "Alice"},
                "updates": {"age": 31}
            }
        """
        # 获取表名
        table_name = self._get_table_name(update_stmt)

        # 构建选择器
        selector = {"type": table_name}

        if update_stmt._where_criteria:
            # _where_criteria 是一个元组
            if len(update_stmt._where_criteria) == 1:
                where_selector = self._compile_where(update_stmt._where_criteria[0])
            else:
                subclauses = [self._compile_where(clause) for clause in update_stmt._where_criteria]
                where_selector = {"$and": subclauses}

            if where_selector:
                selector.update(where_selector)

        # 获取更新的字段（从 _values 提取）
        updates = {}
        if hasattr(update_stmt, "_values") and update_stmt._values:
            for key, value in update_stmt._values.items():
                if key not in ("_id", "_rev", "type"):
                    updates[key] = self._extract_value(value)

        query = {
            "type": "update",
            "table": table_name,
            "selector": selector,
            "updates": updates,
        }

        return json.dumps(query)

    def visit_delete(self, delete_stmt, **kwargs):
        """
        编译 DELETE 语句

        SQL:
            DELETE FROM users WHERE age < 18

        CouchDB:
            {
                "type": "delete",
                "table": "users",
                "selector": {"type": "users", "age": {"$lt": 18}}
            }
        """
        # 获取表名
        table_name = self._get_table_name(delete_stmt)

        # 构建选择器
        selector = {"type": table_name}

        if delete_stmt._where_criteria:
            # _where_criteria 是一个元组
            if len(delete_stmt._where_criteria) == 1:
                where_selector = self._compile_where(delete_stmt._where_criteria[0])
            else:
                subclauses = [self._compile_where(clause) for clause in delete_stmt._where_criteria]
                where_selector = {"$and": subclauses}

            if where_selector:
                selector.update(where_selector)

        query = {"type": "delete", "table": table_name, "selector": selector}

        return json.dumps(query)

    def _compile_where(self, clause) -> Dict[str, Any]:
        """
        编译 WHERE 子句为 Mango Query selector

        支持的操作符:
        - 比较: =, >, >=, <, <=, !=
        - 逻辑: AND, OR
        - 其他: IN, LIKE

        示例:
            age > 25  →  {"age": {"$gt": 25}}
            name = 'Alice'  →  {"name": "Alice"}
            age > 25 AND name = 'Alice'  →  {"$and": [...]}
        """
        from sqlalchemy.sql.expression import BinaryExpression, BooleanClauseList

        if isinstance(clause, BinaryExpression):
            # 二元表达式: left op right
            left = clause.left
            right = clause.right
            op = clause.operator

            # 获取列名
            column_name = self._get_column_name(left)

            # 获取值（可能是参数或字面量）
            value = self._get_value(right)

            # 根据操作符生成 Mango Query
            if op == operators.eq:  # =
                return {column_name: value}
            elif op == operators.gt:  # >
                return {column_name: {"$gt": value}}
            elif op == operators.ge:  # >=
                return {column_name: {"$gte": value}}
            elif op == operators.lt:  # <
                return {column_name: {"$lt": value}}
            elif op == operators.le:  # <=
                return {column_name: {"$lte": value}}
            elif op == operators.ne:  # !=
                return {column_name: {"$ne": value}}
            elif op == operators.in_op:  # IN
                return {column_name: {"$in": value}}
            elif op == operators.notin_op:  # NOT IN
                return {column_name: {"$nin": value}}
            elif op == operators.like_op:  # LIKE
                # 将 SQL LIKE 转换为正则表达式
                regex = self._like_to_regex(value)
                return {column_name: {"$regex": regex}}
            else:
                # 不支持的操作符
                raise NotImplementedError(f"不支持的操作符: {op}")

        elif isinstance(clause, BooleanClauseList):
            # 逻辑表达式: AND, OR
            op = clause.operator

            # 递归编译子句
            subclauses = [self._compile_where(c) for c in clause.clauses]

            if op == operators.and_:  # AND
                # 如果所有子句都是简单的字段匹配，可以合并
                if all(isinstance(c, dict) and len(c) == 1 for c in subclauses):
                    # 合并为一个字典
                    result = {}
                    for subclause in subclauses:
                        result.update(subclause)
                    return result
                else:
                    return {"$and": subclauses}

            elif op == operators.or_:  # OR
                return {"$or": subclauses}

            else:
                raise NotImplementedError(f"不支持的逻辑操作符: {op}")

        else:
            # 其他类型的子句
            return {}

    def _compile_order_by(self, order_by_clauses) -> List[Dict[str, str]]:
        """
        编译 ORDER BY 子句

        SQL:
            ORDER BY age DESC, name ASC

        Mango:
            [{"age": "desc"}, {"name": "asc"}]
        """
        from sqlalchemy.sql.expression import UnaryExpression
        from sqlalchemy.sql import operators as sql_operators

        sort = []

        for clause in order_by_clauses:
            # 获取列名
            if isinstance(clause, UnaryExpression):
                column_name = self._get_column_name(clause.element)
                # 检查是否是降序
                if clause.modifier == sql_operators.desc_op:
                    direction = "desc"
                else:
                    direction = "asc"
            else:
                column_name = self._get_column_name(clause)
                direction = "asc"

            sort.append({column_name: direction})

        return sort

    def _get_table_name(self, stmt) -> str:
        """获取表名"""
        if hasattr(stmt, "table"):
            return stmt.table.name
        elif hasattr(stmt, "get_final_froms"):
            # SQLAlchemy 2.0: 使用 get_final_froms() 而不是 froms 属性
            froms = stmt.get_final_froms()
            if froms:
                return froms[0].name
        elif hasattr(stmt, "froms") and stmt.froms:
            # 向后兼容
            return stmt.froms[0].name
        else:
            raise ValueError("无法确定表名")

    def _get_column_name(self, column) -> str:
        """获取列名"""
        if hasattr(column, "name"):
            return column.name
        elif hasattr(column, "key"):
            return column.key
        else:
            return str(column)

    def _get_value(self, value_expr):
        """
        获取值（可能是参数或字面量）

        提取实际值而不是占位符
        """
        return self._extract_value(value_expr)

    def _get_limit_value(self, limit_clause):
        """获取 LIMIT 值"""
        if hasattr(limit_clause, "value"):
            return limit_clause.value
        return int(limit_clause)

    def _get_offset_value(self, offset_clause):
        """获取 OFFSET 值"""
        if hasattr(offset_clause, "value"):
            return offset_clause.value
        return int(offset_clause)

    def _is_select_star(self, columns) -> bool:
        """检查是否是 SELECT *"""
        # 简单检查：如果列列表为空或包含所有列，认为是 SELECT *
        return False  # 简化处理，总是返回具体字段

    def _like_to_regex(self, pattern: str) -> str:
        """
        将 SQL LIKE 模式转换为正则表达式

        SQL LIKE 语法:
        - % 匹配任意字符（0 个或多个）
        - _ 匹配单个字符

        正则表达式:
        - .* 匹配任意字符
        - . 匹配单个字符

        示例:
            'Alice%'  →  '^Alice.*$'
            '%Alice%' →  '.*Alice.*'
            'A_ice'   →  '^A.ice$'
        """
        # 转义特殊字符
        import re

        pattern = re.escape(pattern)

        # 替换 LIKE 通配符
        pattern = pattern.replace(r"\%", ".*")  # % → .*
        pattern = pattern.replace(r"\_", ".")  # _ → .

        # 添加锚点
        if not pattern.startswith(".*"):
            pattern = "^" + pattern
        if not pattern.endswith(".*"):
            pattern = pattern + "$"

        return pattern


class CouchDBTypeCompiler(compiler.GenericTypeCompiler):
    """
    CouchDB 类型编译器

    处理类型的 DDL 生成（虽然 CouchDB 不需要 DDL，但需要实现接口）
    """

    def visit_string(self, type_, **kwargs):
        """字符串类型"""
        return "STRING"

    def visit_text(self, type_, **kwargs):
        """文本类型"""
        return "TEXT"

    def visit_integer(self, type_, **kwargs):
        """整数类型"""
        return "INTEGER"

    def visit_boolean(self, type_, **kwargs):
        """布尔类型"""
        return "BOOLEAN"

    def visit_datetime(self, type_, **kwargs):
        """日期时间类型"""
        return "DATETIME"

    def visit_float(self, type_, **kwargs):
        """浮点数类型"""
        return "FLOAT"

    def visit_numeric(self, type_, **kwargs):
        """数值类型"""
        return "NUMERIC"

    def visit_JSON(self, type_, **kwargs):
        """JSON 类型"""
        return "JSON"


class CouchDBDDLCompiler(compiler.DDLCompiler):
    """
    CouchDB DDL 编译器

    CouchDB 不需要 DDL（CREATE TABLE 等），但为了兼容性提供空实现。
    """

    def visit_create_table(self, create, **kwargs):
        """CREATE TABLE - CouchDB 不需要，返回空字符串"""
        return ""

    def visit_drop_table(self, drop, **kwargs):
        """DROP TABLE - CouchDB 不需要，返回空字符串"""
        return ""

    def visit_create_index(self, create, **kwargs):
        """CREATE INDEX - 暂不支持"""
        return ""

    def visit_drop_index(self, drop, **kwargs):
        """DROP INDEX - 暂不支持"""
        return ""
