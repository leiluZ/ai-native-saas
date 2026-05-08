"""FastAPI 应用测试"""
import pytest
from fastapi.testclient import TestClient
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.main import app

client = TestClient(app)


def test_health_check():
    """测试健康检查接口"""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert data["message"] == "success"
    assert "request_id" in data


def test_chat_message():
    """测试聊天消息接口"""
    response = client.post(
        "/api/v1/chat/message",
        json={"content": "Hello, World!"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert "request_id" in data
    assert "data" in data


def test_chat_history():
    """测试聊天历史接口"""
    response = client.get("/api/v1/chat/history/test-session")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert "request_id" in data


def test_agent_endpoint_exists():
    """测试 Agent 端点是否存在"""
    response = client.post(
        "/api/v1/chat/agent",
        json={"prompt": "Hello"}
    )
    # 由于没有配置 LLM，应该返回错误但端点应该存在
    assert response.status_code in [200, 500]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
