import xtquant.xtdata as xtdata
import socket
import time

def test_miniqmt_connection():
    # 测试端口连接（增加重试机制）
    port_status = False
    for i in range(3):  # 最多重试3次
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(5)  # 增加超时时间
                s.connect(("localhost", 8000))
            print(f"✅ 端口8000连接成功 (第{i+1}次尝试)")
            port_status = True
            break
        except Exception as e:
            print(f"❌ 端口8000连接失败 (第{i+1}次尝试): {str(e)}")
            time.sleep(2)  # 等待2秒后重试

    # 测试xtdata API调用（增加重试机制）
    api_status = False
    for i in range(3):  # 最多重试3次
        try:
            trading_dates = xtdata.get_trading_dates('SH', '20250101', '20250107')
            print(f"✅ xtdata API调用成功 (第{i+1}次尝试)，返回数据: {trading_dates}")
            api_status = True
            break
        except Exception as e:
            print(f"❌ xtdata API调用失败 (第{i+1}次尝试): {str(e)}")
            time.sleep(2)  # 等待2秒后重试

    # 返回整体状态
    return port_status and api_status

if __name__ == "__main__":
    print("="*50)
    print("miniQMT连接测试 (改进版)")
    print("="*50)
    
    if test_miniqmt_connection():
        print("\n✅✅✅ 所有测试通过，miniQMT连接正常 ✅✅✅")
    else:
        print("\n❌❌❌ 测试失败，请检查miniQMT服务 ❌❌❌")