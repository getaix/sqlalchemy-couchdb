"""
CouchDB 变更 Feed 功能

实现 CouchDB 的 _changes API，支持实时数据同步和变更监听。

主要功能：
- 轮询变更 (poll)
- 长轮询变更 (longpoll)
- 连续变更监听 (continuous)
- 变更过滤
- 变更序列号跟踪
"""

import time
import json
import threading
from typing import Optional, Callable, Dict, Any, List
from enum import Enum
from dataclasses import dataclass



class FeedType(Enum):
    """变更 Feed 类型"""

    NORMAL = "normal"  # 一次性返回所有变更
    LONGPOLL = "longpoll"  # 长轮询，等待新变更
    CONTINUOUS = "continuous"  # 连续流式返回变更


class FilterType(Enum):
    """过滤器类型"""

    NONE = None  # 无过滤
    DOC_IDS = "_doc_ids"  # 按文档 ID 过滤
    SELECTOR = "_selector"  # 按 Mango 选择器过滤
    VIEW = "_view"  # 按视图过滤
    DESIGN = "_design"  # 仅设计文档


@dataclass
class Change:
    """单个变更记录"""

    seq: str  # 序列号
    id: str  # 文档 ID
    changes: List[Dict[str, str]]  # 变更列表 (包含 rev)
    deleted: bool = False  # 是否删除
    doc: Optional[Dict[str, Any]] = None  # 文档内容（如果 include_docs=True）


@dataclass
class ChangesFeedResult:
    """变更 Feed 结果"""

    results: List[Change]  # 变更列表
    last_seq: str  # 最后序列号
    pending: int = 0  # 待处理变更数量


class ChangesListener:
    """
    变更监听器

    用于监听 CouchDB 数据库的变更，支持回调函数处理。

    示例:
        >>> listener = ChangesListener(client, on_change=handle_change)
        >>> listener.start()
        >>> # ... 处理变更 ...
        >>> listener.stop()
    """

    def __init__(
        self,
        client,
        on_change: Optional[Callable[[Change], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
        feed_type: FeedType = FeedType.CONTINUOUS,
        include_docs: bool = True,
        filter_type: Optional[FilterType] = None,
        filter_params: Optional[Dict[str, Any]] = None,
        heartbeat: int = 60000,  # 心跳间隔（毫秒）
        timeout: int = 60000,  # 超时时间（毫秒）
    ):
        """
        初始化变更监听器

        参数:
            client: SyncCouchDBClient 实例
            on_change: 变更回调函数
            on_error: 错误回调函数
            feed_type: Feed 类型
            include_docs: 是否包含文档内容
            filter_type: 过滤器类型
            filter_params: 过滤器参数
            heartbeat: 心跳间隔（毫秒）
            timeout: 超时时间（毫秒）
        """
        self.client = client
        self.on_change = on_change
        self.on_error = on_error
        self.feed_type = feed_type
        self.include_docs = include_docs
        self.filter_type = filter_type
        self.filter_params = filter_params or {}
        self.heartbeat = heartbeat
        self.timeout = timeout

        self._running = False
        self._thread = None
        self._last_seq = "now"  # 从当前位置开始

    def start(self, since: Optional[str] = None):
        """
        启动监听器

        参数:
            since: 起始序列号（None 表示从最新位置开始）
        """
        if self._running:
            raise RuntimeError("Listener is already running")

        if since is not None:
            self._last_seq = since

        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """停止监听器"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None

    def _listen_loop(self):
        """监听循环（在后台线程中运行）"""
        while self._running:
            try:
                if self.feed_type == FeedType.CONTINUOUS:
                    self._listen_continuous()
                else:
                    self._listen_poll()
                    time.sleep(1)  # 轮询间隔
            except Exception as e:
                if self.on_error:
                    self.on_error(e)
                else:
                    # 默认行为：打印错误并继续
                    print(f"Error in changes listener: {e}")
                time.sleep(5)  # 错误后等待

    def _listen_continuous(self):
        """连续监听模式"""
        # 构建 URL
        url = self.client._build_db_url("_changes")
        params = self._build_params()
        params["feed"] = "continuous"

        # 流式请求
        with self.client.client.stream("GET", url, params=params, timeout=None) as response:
            response.raise_for_status()

            for line in response.iter_lines():
                if not self._running:
                    break

                line = line.strip()
                if not line:
                    continue  # 跳过空行（心跳）

                try:
                    change_data = json.loads(line)
                    change = self._parse_change(change_data)

                    if change:
                        self._last_seq = change.seq
                        if self.on_change:
                            self.on_change(change)
                except json.JSONDecodeError:
                    continue  # 跳过无效 JSON

    def _listen_poll(self):
        """轮询监听模式"""
        result = self.get_changes(since=self._last_seq)

        for change in result.results:
            if self.on_change:
                self.on_change(change)

        self._last_seq = result.last_seq

    def get_changes(
        self, since: Optional[str] = None, limit: Optional[int] = None
    ) -> ChangesFeedResult:
        """
        获取变更（同步方法）

        参数:
            since: 起始序列号
            limit: 限制返回数量

        返回:
            ChangesFeedResult 对象
        """
        url = self.client._build_db_url("_changes")
        params = self._build_params()

        if since:
            params["since"] = since
        if limit:
            params["limit"] = limit

        response = self.client.client.get(url, params=params)
        self.client._handle_response(response)

        data = response.json()
        return self._parse_changes_result(data)

    def _build_params(self) -> Dict[str, Any]:
        """构建请求参数"""
        params = {
            "include_docs": "true" if self.include_docs else "false",
            "heartbeat": self.heartbeat,
            "timeout": self.timeout,
            "since": self._last_seq,
        }

        # 添加过滤器
        if self.filter_type:
            if self.filter_type == FilterType.DOC_IDS:
                params["filter"] = "_doc_ids"
                # doc_ids 通过 POST 发送
            elif self.filter_type == FilterType.SELECTOR:
                params["filter"] = "_selector"
                # selector 通过 POST 发送
            elif self.filter_type == FilterType.VIEW:
                params["filter"] = "_view"
                # 需要指定 ddoc 和 view
            elif self.filter_type == FilterType.DESIGN:
                params["filter"] = "_design"

        # 添加自定义过滤参数
        params.update(self.filter_params)

        return params

    def _parse_change(self, data: Dict[str, Any]) -> Optional[Change]:
        """解析单个变更"""
        if "last_seq" in data:
            # 这是结束标记，不是变更
            return None

        return Change(
            seq=data["seq"],
            id=data["id"],
            changes=data["changes"],
            deleted=data.get("deleted", False),
            doc=data.get("doc"),
        )

    def _parse_changes_result(self, data: Dict[str, Any]) -> ChangesFeedResult:
        """解析变更结果"""
        results = [
            Change(
                seq=item["seq"],
                id=item["id"],
                changes=item["changes"],
                deleted=item.get("deleted", False),
                doc=item.get("doc"),
            )
            for item in data.get("results", [])
        ]

        return ChangesFeedResult(
            results=results, last_seq=data.get("last_seq", "0"), pending=data.get("pending", 0)
        )


class ChangesFeed:
    """
    变更 Feed 管理器

    提供更高级的变更 Feed 功能，包括：
    - 自动重连
    - 变更缓冲
    - 序列号持久化

    示例:
        >>> feed = ChangesFeed(client)
        >>> feed.on_change(lambda change: print(f"Changed: {change.id}"))
        >>> feed.start()
    """

    def __init__(
        self,
        client,
        buffer_size: int = 100,
        auto_reconnect: bool = True,
        max_reconnect_attempts: int = 5,
    ):
        """
        初始化变更 Feed

        参数:
            client: SyncCouchDBClient 实例
            buffer_size: 变更缓冲区大小
            auto_reconnect: 是否自动重连
            max_reconnect_attempts: 最大重连次数
        """
        self.client = client
        self.buffer_size = buffer_size
        self.auto_reconnect = auto_reconnect
        self.max_reconnect_attempts = max_reconnect_attempts

        self._listeners: List[ChangesListener] = []
        self._handlers: List[Callable[[Change], None]] = []
        self._buffer: List[Change] = []
        self._reconnect_count = 0

    def on_change(self, handler: Callable[[Change], None]):
        """注册变更处理函数"""
        self._handlers.append(handler)

    def start(self, **kwargs):
        """启动 Feed"""
        listener = ChangesListener(
            self.client, on_change=self._handle_change, on_error=self._handle_error, **kwargs
        )

        self._listeners.append(listener)
        listener.start()

    def stop(self):
        """停止所有监听器"""
        for listener in self._listeners:
            listener.stop()
        self._listeners.clear()

    def _handle_change(self, change: Change):
        """处理变更"""
        # 添加到缓冲区
        self._buffer.append(change)
        if len(self._buffer) > self.buffer_size:
            self._buffer.pop(0)

        # 调用所有处理函数
        for handler in self._handlers:
            try:
                handler(change)
            except Exception as e:
                print(f"Error in change handler: {e}")

    def _handle_error(self, error: Exception):
        """处理错误"""
        print(f"Changes feed error: {error}")

        if self.auto_reconnect and self._reconnect_count < self.max_reconnect_attempts:
            self._reconnect_count += 1
            print(f"Reconnecting... (attempt {self._reconnect_count})")
            time.sleep(2**self._reconnect_count)  # 指数退避
            # 重启监听器会由监听循环自动处理
        else:
            print("Max reconnect attempts reached")

    def get_buffer(self) -> List[Change]:
        """获取缓冲的变更"""
        return self._buffer.copy()

    def clear_buffer(self):
        """清空缓冲区"""
        self._buffer.clear()


# 添加到 SyncCouchDBClient
def create_changes_listener(
    self, on_change: Optional[Callable[[Change], None]] = None, **kwargs
) -> ChangesListener:
    """
    创建变更监听器

    参数:
        on_change: 变更回调函数
        **kwargs: 传递给 ChangesListener 的其他参数

    返回:
        ChangesListener 实例
    """
    return ChangesListener(self, on_change=on_change, **kwargs)


def create_changes_feed(self, **kwargs) -> ChangesFeed:
    """
    创建变更 Feed

    参数:
        **kwargs: 传递给 ChangesFeed 的参数

    返回:
        ChangesFeed 实例
    """
    return ChangesFeed(self, **kwargs)
