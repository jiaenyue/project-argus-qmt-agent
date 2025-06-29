import sys
import asyncio
sys.path.append("src/xtquantai")
from xtquantai.server import main

async def test_server_connection():
    """测试服务器连接功能"""
    print("测试服务器连接...")
    try:
        print("启动服务器...")
        await main()
        print("服务器启动成功")
        return True
    except Exception as e:
        print(f"连接失败: {str(e)}")
        return False

if __name__ == "__main__":
    asyncio.run(test_server_connection())
