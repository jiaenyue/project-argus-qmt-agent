import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

import sys
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

# 在所有其他导入和fixture设置之前，尝试全局模拟xtquant
# 这确保了当其他模块（如data_agent_service.main）尝试导入xtquant时，
# 它们会得到这个模拟版本。
MOCK_XTQUANT_PACKAGE = MagicMock()
MOCK_XTQUANT_XTDATA = MagicMock()
MOCK_XTQUANT_XTTRADER = MagicMock() # 这个可以保留为私有的，如果只通过MOCK_XTQUANT_PACKAGE访问

# MOCK_XTQUANT_XTDATA 现在是全局可访问的，以便测试可以直接配置它
# 为xtdata的特定方法预先定义为MagicMock实例，并可以设置默认返回值
MOCK_XTQUANT_XTDATA.get_stock_list_in_sector = MagicMock(return_value=[])
MOCK_XTQUANT_XTDATA.get_instrument_detail = MagicMock(return_value=None)
MOCK_XTQUANT_XTDATA.get_latest_market_data = MagicMock(return_value={})
MOCK_XTQUANT_XTDATA.get_full_market_data = MagicMock(return_value={})
# 其他xtdata方法如果被API使用，也应在此处添加

MOCK_XTQUANT_PACKAGE.xtdata = MOCK_XTQUANT_XTDATA # MOCK_XTQUANT_PACKAGE.xtdata 指向 MOCK_XTQUANT_XTDATA
MOCK_XTQUANT_PACKAGE.xttrader = MOCK_XTQUANT_XTTRADER

sys.modules['xtquant'] = MOCK_XTQUANT_PACKAGE
sys.modules['xtquant.xtdata'] = MOCK_XTQUANT_XTDATA
sys.modules['xtquant.xttrader'] = MOCK_XTQUANT_XTTRADER


@pytest.fixture(scope="session")
def client():
    """
    Provides a TestClient instance for API testing.
    xtquant and its submodules (xtdata, xttrader) are globally mocked via sys.modules
    before this fixture is even called, so data_agent_service.main should import
    the mocked versions.
    """
    # 现在 data_agent_service.main 在导入时应该会使用上面 sys.modules 中的模拟 xtquant
    # 这也意味着 src.xtquantai.server 中的 try-except 导入也会成功导入模拟对象
    from data_agent_service.main import app

    test_client = TestClient(app)
    yield test_client
