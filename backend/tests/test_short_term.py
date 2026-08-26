# 短期记忆测试：会话创建、历史加载、消息保存（走临时测试库）

from langchain_core.messages import AIMessage, HumanMessage

from app.database.database import SessionLocal
from app.memory.short_term import (
    get_or_create_conversation,
    load_history,
    save_message,
)


def test_create_and_reuse_conversation():
    with SessionLocal() as db:
        # 新建会话
        conv = get_or_create_conversation(db, None)
        assert conv.id is not None

        # 复用同一会话（不新建）
        again = get_or_create_conversation(db, conv.id)
        assert again.id == conv.id

        # 不存在的会话报错
        try:
            get_or_create_conversation(db, 999999)
            assert False, "应抛出 ValueError"
        except ValueError:
            pass


def test_history_roundtrip():
    with SessionLocal() as db:
        conv = get_or_create_conversation(db, None)

        # 保存两轮对话
        save_message(db, conv.id, "user", "我明天有面试")
        save_message(db, conv.id, "assistant", "好的，祝顺利")
        save_message(db, conv.id, "user", "帮我安排计划")
        save_message(db, conv.id, "assistant", "已按面试安排")

        history = load_history(db, conv.id)

        # 类型与顺序正确
        assert len(history) == 4
        assert isinstance(history[0], HumanMessage)
        assert isinstance(history[1], AIMessage)
        assert history[0].content == "我明天有面试"
        assert history[-1].content == "已按面试安排"


def test_history_window_limit():
    """超过 MAX_HISTORY_MESSAGES 时只保留最近 N 条"""
    with SessionLocal() as db:
        conv = get_or_create_conversation(db, None)
        # 写入 30 条
        for i in range(30):
            save_message(db, conv.id, "user", f"消息{i}")

        history = load_history(db, conv.id)
        # 默认窗口 20 条，且是最新的（id 大的）
        assert len(history) == 20
        assert history[0].content == "消息10"
        assert history[-1].content == "消息29"
