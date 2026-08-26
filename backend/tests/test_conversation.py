# 会话管理接口测试（列表/历史消息/删除/自动标题）

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_conversation_flow():
    # 1. 发一条消息 → 创建会话并自动标题
    resp = client.post("/api/chat", json={"message": "帮我记住明天的面试"})
    assert resp.status_code == 200
    conv_id = resp.json()["conversation_id"]
    assert conv_id is not None

    # 2. 会话列表应包含它，标题为首条消息前 20 字
    lst = client.get("/api/conversations").json()
    conv = next(c for c in lst if c["id"] == conv_id)
    assert conv["title"].startswith("帮我记住明天的面试")
    assert conv["message_count"] >= 2  # user + assistant
    assert conv["last_message"] is not None

    # 3. 历史消息按时间正序
    msgs = client.get(f"/api/conversations/{conv_id}/messages").json()
    assert msgs[0]["role"] == "user"
    assert msgs[0]["content"] == "帮我记住明天的面试"
    assert msgs[-1]["role"] == "assistant"

    # 4. 删除会话（级联删消息）
    resp = client.delete(f"/api/conversations/{conv_id}")
    assert resp.status_code == 204

    # 5. 删除后再查：列表无此项、消息 404
    lst2 = client.get("/api/conversations").json()
    assert all(c["id"] != conv_id for c in lst2)
    assert client.get(f"/api/conversations/{conv_id}/messages").status_code == 404


def test_conversation_404():
    assert client.get("/api/conversations/999999/messages").status_code == 404
    assert client.delete("/api/conversations/999999").status_code == 404
