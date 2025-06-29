import pytest
from fastapi.testclient import TestClient
# from data_agent_service.main import app # client fixture 会处理 app 的导入和 patching

# client fixture 由 conftest.py 自动提供

def test_root_endpoint(client): # client fixture注入
    """
    测试根端点 /
    """
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Welcome to Data Agent Service"}

# 可以考虑在这里添加其他不特定于某个API功能模块的通用测试，
# 例如通用的HTTP头检查、全局异常处理程序行为等（如果适用）。
# 目前，我们只测试根路径。

# 旧的 test_error_handling 依赖于 /instrument_detail，并且其逻辑已部分
# 被各个端点的特定错误测试所覆盖。如果需要一个通用的错误格式测试，
# 它应该使用一个保证会出错的、可能是专门为此目的设置的端点，
# 或者更深入地测试FastAPI的异常处理机制。

# 旧的 test_rate_limiting 已被跳过，如果将来实现，它也应该有自己的测试文件或部分。
