import asyncio  
from typing import Optional, List, Dict, Any  
import json  
import sys  
import os  
import traceback  
import time  
import re
import logging
from datetime import datetime, timedelta
import pandas as pd
from contextvars import ContextVar

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 项目已移除复杂的异常处理机制，使用简单的异常抛出
# from data_agent_service.exception_handler import (...)
# 异常处理函数已移除，直接使用标准异常

# 配置日志
logger = logging.getLogger(__name__)

# 请求追踪ID上下文变量
request_id_context: ContextVar[str] = ContextVar('request_id', default='unknown')

def get_request_id() -> str:
    """获取当前请求的追踪ID"""
    return request_id_context.get('unknown')

def set_request_id(request_id: str):
    """设置当前请求的追踪ID"""
    request_id_context.set(request_id)  

from mcp.server.models import InitializationOptions  
import mcp.types as types  
from mcp.server import NotificationOptions, Server  
  
from fastapi import APIRouter, Query  
from pydantic import AnyUrl, BaseModel, Field, ValidationError  
# from xtquant import xtdata # 延迟导入或包装导入
# from xtquant import xttrader # 延迟导入或包装导入

# 尝试导入xtquant，如果失败则使用模拟对象
try:
    from xtquant import xtdata
    from xtquant import xttrader
except ImportError as e:
    # 项目已移除所有模拟数据和回退机制
    # 必须连接真实的miniQMT客户端才能运行
    raise ImportError(
        "无法导入xtquant库，项目必须连接miniQMT客户端才能运行。\n"
        "请确保：\n"
        "1. miniQMT客户端已正确安装并运行\n"
        "2. xtquant包已正确安装\n"
        "3. Python路径配置正确\n"
        f"原始错误: {str(e)}"
    ) from e

def ensure_xtdc_initialized():  
    # ... 保持不变 ...  
    pass  

class XTQuantAIHandler:  
    @staticmethod
    def _get_xtdata():
        """获取xtdata模块"""
        try:
            return xtdata
        except NameError:
            return None
    
    @staticmethod
    def get_trading_dates(market: str, start_date: str = "", end_date: str = "") -> Dict[str, Any]:
        """
        获取交易日期列表
        
        Args:
            market: 市场代码，如 'SH' 或 'SZ'
            start_date: 开始日期，格式为 'YYYYMMDD'，默认为空
            end_date: 结束日期，格式为 'YYYYMMDD'，默认为空
            
        Returns:
            Dict: 包含交易日期列表的响应
        """
        try:
            # 参数验证
            if not market:
                raise ValueError("市场代码不能为空")
            
            # 如果日期为空，使用默认值
            if not start_date:
                start_date = ""
            if not end_date:
                end_date = ""
            
            # 导入datetime模块
            from datetime import datetime, timedelta
            
            # 验证日期格式（如果提供了日期）
            if start_date and start_date.strip():
                try:
                    datetime.strptime(start_date, '%Y%m%d')
                except ValueError as e:
                    raise ValueError(f"开始日期格式错误，应为YYYYMMDD格式: {str(e)}")
            
            if end_date and end_date.strip():
                try:
                    datetime.strptime(end_date, '%Y%m%d')
                except ValueError as e:
                    raise ValueError(f"结束日期格式错误，应为YYYYMMDD格式: {str(e)}")
            
            # 导入xtquant库
            xtdata = XTQuantAIHandler._get_xtdata()
            if not xtdata:
                raise ImportError("xtquant库未正确加载，项目必须连接miniQMT客户端")
            
            # 获取交易日期 - xtdata.get_trading_dates 只需要开始和结束日期
            if start_date and end_date and start_date.strip() and end_date.strip():
                trading_dates = xtdata.get_trading_dates(start_date, end_date)
            else:
                # 如果没有提供日期范围，获取最近的交易日期
                end_dt = datetime.now()
                start_dt = end_dt - timedelta(days=30)  # 默认获取最近30天
                start_date = start_dt.strftime('%Y%m%d')
                end_date = end_dt.strftime('%Y%m%d')
                trading_dates = xtdata.get_trading_dates(start_date, end_date)
            
            if trading_dates is None or len(trading_dates) == 0:
                raise ValueError(f"未找到指定日期范围内的交易日期: {start_date} 到 {end_date}")
            
            # 转换为字符串列表 - 处理不同的返回类型
            date_list = []
            for date in trading_dates:
                if isinstance(date, str):
                    date_list.append(date)
                elif hasattr(date, 'strftime'):
                    date_list.append(date.strftime('%Y%m%d'))
                else:
                    date_list.append(str(date))
            
            logger.info(
                f"成功获取交易日期: {len(date_list)}个交易日",
                extra={
                    "request_id": get_request_id(),
                    "market": market,
                    "start_date": start_date,
                    "end_date": end_date,
                    "count": len(date_list)
                }
            )
            
            return {
                "success": True,
                "message": "获取交易日期成功",
                "data": {
                    "trading_dates": date_list,
                    "count": len(date_list),
                    "start_date": start_date,
                    "end_date": end_date
                },
                "code": 200
            }
            
        except Exception as e:
            # 如果是我们自定义的异常，直接抛出
            if hasattr(e, 'code'):
                raise
            
            # 其他未预期的异常
            logger.error(
                f"获取交易日期时发生未预期错误: {str(e)}", 
                extra={
                    "request_id": get_request_id(),
                    "market": market,
                    "start_date": start_date,
                    "end_date": end_date,
                    "error_type": type(e).__name__
                },
                exc_info=True
            )
            raise ImportError(f"获取交易日期失败: {str(e)}，项目必须连接miniQMT客户端")  

    @staticmethod  
    async def get_hist_kline(symbol: str = None, start_date: str = None, end_date: str = None, frequency: str = None, 
                      enhanced: bool = Query(False, description="是否使用增强API"), 
                      include_quality: bool = Query(False, description="是否包含质量指标"), 
                      normalize: bool = Query(True, description="是否标准化数据")):  
        ensure_xtdc_initialized()  
        try:  
            # 参数验证  
            if symbol is None:  
                return {"success": False, "message": "symbol is required", "status": 400}  
            if start_date is None:  
                return {"success": False, "message": "start_date is required", "status": 400}  
            if end_date is None:  
                return {"success": False, "message": "end_date is required", "status": 400}  
            if frequency is None:  
                return {"success": False, "message": "frequency is required", "status": 400}  

            # 验证日期格式  
            date_pattern = re.compile(r"^\d{8}$")  
            if not date_pattern.match(start_date):  
                return {"success": False, "message": "start_date must be in YYYYMMDD format", "status": 400}  
            if not date_pattern.match(end_date):  
                return {"success": False, "message": "end_date must be in YYYYMMDD format", "status": 400}  

            # 如果使用增强API
            if enhanced:
                try:
                    # 修复导入路径 - 使用正确的相对路径
                    import sys
                    import os
                    
                    # 添加src目录到路径
                    src_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'src')
                    if src_path not in sys.path:
                        sys.path.insert(0, src_path)
                    
                    from argus_mcp.api.enhanced_historical_api import EnhancedHistoricalDataAPI, HistoricalDataRequest
                    from argus_mcp.data_models.historical_data import SupportedPeriod
                    
                    # 频率映射
                    frequency_map = {
                        '1m': SupportedPeriod.MINUTE_1,
                        '5m': SupportedPeriod.MINUTE_5,
                        '15m': SupportedPeriod.MINUTE_15,
                        '30m': SupportedPeriod.MINUTE_30,
                        '1h': SupportedPeriod.HOUR_1,
                        '1d': SupportedPeriod.DAY_1,
                        '1w': SupportedPeriod.WEEK_1,
                        '1M': SupportedPeriod.MONTH_1
                    }
                    
                    api = EnhancedHistoricalDataAPI()
                    
                    # 转换日期格式
                    formatted_start = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:8]}"
                    formatted_end = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:8]}"
                    
                    # 创建请求
                    request = HistoricalDataRequest(
                        symbol=symbol,
                        start_date=formatted_start,
                        end_date=formatted_end,
                        period=frequency_map.get(frequency, SupportedPeriod.DAY_1),
                        include_quality_metrics=include_quality,
                        normalize_data=normalize,
                        use_cache=True
                    )
                    
                    # 获取增强数据
                    response = await api.get_historical_data(request)
                    
                    logger.info(
                        f"增强API成功获取历史数据: {symbol}, {frequency}, {len(response.data)}条记录",
                        extra={
                            "request_id": get_request_id(),
                            "symbol": symbol,
                            "frequency": frequency,
                            "enhanced": True,
                            "records": len(response.data) if response.data else 0
                        }
                    )
                    
                    return {
                        "success": response.success,
                        "data": response.data,
                        "quality_report": response.quality_report,
                        "metadata": response.metadata,
                        "status": 200 if response.success else 500
                    }
                    
                except ImportError as ie:
                    # 如果增强API不可用，回退到原始方法
                    logger.warning(
                        f"增强API不可用，使用原始方法: {str(ie)}",
                        extra={
                            "request_id": get_request_id(),
                            "symbol": symbol,
                            "enhanced": False
                        }
                    )
                except Exception as e:
                    # 增强API调用失败，记录错误并回退
                    logger.error(
                        f"增强API调用失败，回退到原始方法: {str(e)}",
                        extra={
                            "request_id": get_request_id(),
                            "symbol": symbol,
                            "error_type": type(e).__name__
                        },
                        exc_info=True
                    )
                    # 继续执行原始方法

            # 原始方法 - 调用xtquant接口获取K线数据
            logger.info(
                f"调用原始xtquant接口获取K线数据",
                extra={
                    "request_id": get_request_id(),
                    "symbol": symbol,
                    "frequency": frequency,
                    "start_date": start_date,
                    "end_date": end_date,
                    "enhanced": enhanced
                }
            )
            
            # 验证xtdata可用性
            if not xtdata:
                raise ImportError("xtquant库未正确加载，项目必须连接miniQMT客户端")
            
            df = xtdata.get_history_market_data(symbol, frequency, start_date, end_date)
            
            if df is None or df.empty:
                logger.warning(
                    f"未获取到K线数据",
                    extra={
                        "request_id": get_request_id(),
                        "symbol": symbol,
                        "frequency": frequency
                    }
                )
                return {
                    "success": False,
                    "message": f"No data available for {symbol} in period {start_date} to {end_date}",
                    "status": 404
                }
            
            logger.info(
                f"成功获取K线数据: {len(df)}条记录",
                extra={
                    "request_id": get_request_id(),
                    "symbol": symbol,
                    "records": len(df)
                }
            )

            # 转换为标准格式
            data = []
            for index, row in df.iterrows():
                try:
                    data.append({
                        "time": str(index),
                        "open": float(row['open']) if pd.notna(row['open']) else None,
                        "high": float(row['high']) if pd.notna(row['high']) else None,
                        "low": float(row['low']) if pd.notna(row['low']) else None,
                        "close": float(row['close']) if pd.notna(row['close']) else None,
                        "volume": int(row['volume']) if pd.notna(row['volume']) else 0
                    })
                except (ValueError, TypeError) as e:
                    logger.warning(
                        f"数据转换警告: {str(e)}",
                        extra={
                            "request_id": get_request_id(),
                            "symbol": symbol,
                            "index": str(index)
                        }
                    )
                    continue

            return {
                "success": True,
                "data": data,
                "metadata": {
                    "symbol": symbol,
                    "frequency": frequency,
                    "start_date": start_date,
                    "end_date": end_date,
                    "total_records": len(data),
                    "enhanced": enhanced
                },
                "status": 200
            }  
        except Exception as e:
            logger.error(
                f"获取历史K线数据失败: {str(e)}",
                extra={
                    "request_id": get_request_id(),
                    "symbol": symbol,
                    "frequency": frequency,
                    "start_date": start_date,
                    "end_date": end_date,
                    "enhanced": enhanced,
                    "error_type": type(e).__name__
                },
                exc_info=True
            )
            
            return {
                "success": False,
                "message": f"Failed to fetch historical kline data: {str(e)}",
                "error_type": type(e).__name__,
                "status": 500
            }  

    @staticmethod
    def get_instrument_detail(symbol: str = None) -> Dict[str, Any]:
        """
        获取股票详情
        
        Args:
            symbol: 股票代码
            
        Returns:
            Dict: 包含股票详情的响应
        """
        try:
            # 参数验证
            if not symbol or not symbol.strip():
                raise ValueError("股票代码不能为空")
            
            symbol = symbol.strip()
            
            # 验证股票代码格式
            if not re.match(r'^\d{6}\.(SH|SZ)$', symbol):
                raise ValueError("股票代码格式错误，应为6位数字.SH或6位数字.SZ格式")
            
            # 导入xtquant库
            xtdata_module = XTQuantAIHandler._get_xtdata()
            if not xtdata_module:
                raise ImportError("xtquant库未正确加载，项目必须连接miniQMT客户端")
            
            # 获取股票详情
            instrument_detail = xtdata.get_instrument_detail(symbol)
            
            if not instrument_detail:
                raise ValueError(f"未找到股票代码 {symbol} 的详情信息")
            
            logger.info(
                f"成功获取股票详情: {symbol}",
                extra={
                    "request_id": get_request_id(),
                    "symbol": symbol
                }
            )
            
            return {
                "success": True,
                "message": "获取股票详情成功",
                "data": {
                    "symbol": instrument_detail.get("symbol", ""),
                    "name": instrument_detail.get("name", ""),
                    "exchange": instrument_detail.get("exchange", ""),
                    "type": instrument_detail.get("type", ""),
                    "list_date": instrument_detail.get("list_date", ""),
                    "delist_date": instrument_detail.get("delist_date", ""),
                    # 包含其他原始字段
                    **instrument_detail
                },
                "code": 200
            }
            
        except Exception as e:
            # 如果是我们自定义的异常，直接抛出
            if hasattr(e, 'code'):
                raise
            
            # 其他未预期的异常
            logger.error(
                f"获取股票详情时发生未预期错误: {str(e)}",
                extra={
                    "request_id": get_request_id(),
                    "symbol": symbol,
                    "error_type": type(e).__name__
                },
                exc_info=True
            )
            raise ImportError(f"获取股票详情失败: {str(e)}，项目必须连接miniQMT客户端")

    @staticmethod
    def get_stock_list(sector: str = Query(..., description="板块名称")) -> Dict[str, Any]:
        """
        获取板块股票列表
        
        Args:
            sector: 板块代码
            
        Returns:
            Dict: 包含股票列表的响应
        """
        try:
            # 参数验证
            if not sector or not sector.strip():
                raise ValueError("板块代码不能为空")
            
            sector = sector.strip()
            
            # 导入xtquant库
            xtdata_module = XTQuantAIHandler._get_xtdata()
            if not xtdata_module:
                raise ImportError("xtquant库未正确加载，项目必须连接miniQMT客户端")
            
            # 获取板块股票列表
            stock_list = xtdata.get_stock_list_in_sector(sector)
            
            # 处理空列表情况（返回空数组而非错误）
            if stock_list is None:
                stock_list = []
            
            if len(stock_list) == 0:
                logger.warning(
                    f"板块 {sector} 的股票列表为空",
                    extra={
                        "request_id": get_request_id(),
                        "sector": sector
                    }
                )
            
            logger.info(
                f"成功获取板块股票列表: {sector}, 共{len(stock_list)}只股票",
                extra={
                    "request_id": get_request_id(),
                    "sector": sector,
                    "count": len(stock_list)
                }
            )
            
            return {
                "success": True,
                "message": "获取板块股票列表成功",
                "data": {
                    "sector": sector,
                    "stocks": stock_list,
                    "count": len(stock_list)
                },
                "code": 200
            }
            
        except Exception as e:
            # 如果是我们自定义的异常，直接抛出
            if hasattr(e, 'code'):
                raise
            
            # 其他未预期的异常
            logger.error(
                f"获取板块股票列表时发生未预期错误: {str(e)}",
                extra={
                    "request_id": get_request_id(),
                    "sector": sector,
                    "error_type": type(e).__name__
                },
                exc_info=True
            )
            raise ImportError(f"获取板块股票列表失败: {str(e)}，项目必须连接miniQMT客户端")
    @staticmethod
    def get_latest_market(symbols: str = Query(..., description="股票代码列表，逗号分隔")) -> Dict[str, Any]:
        """
        获取最新行情数据
        
        Args:
            symbols: 股票代码列表，逗号分隔
            
        Returns:
            Dict: 包含最新行情数据的响应
        """
        try:
            # 参数验证
            if not symbols or not symbols.strip():
                raise ValueError("股票代码列表不能为空")
            
            # 解析股票代码列表
            symbol_list = [s.strip() for s in symbols.split(',') if s.strip()]
            
            if not symbol_list:
                raise ValueError("未提供有效的股票代码")
            
            # 验证股票代码格式
            invalid_symbols = []
            for symbol in symbol_list:
                if not re.match(r'^\d{6}\.(SH|SZ)$', symbol):
                    invalid_symbols.append(symbol)
            
            if invalid_symbols:
                raise ValueError(f"股票代码格式错误，应为6位数字.SH或6位数字.SZ格式，无效代码: {','.join(invalid_symbols)}")
            
            # 导入xtquant库
            xtdata_module = XTQuantAIHandler._get_xtdata()
            if not xtdata_module:
                raise ImportError("xtquant库未正确加载，项目必须连接miniQMT客户端")
            
            # 获取最新行情数据
            market_data = xtdata.get_latest_market_data(symbol_list)
            
            if market_data is None:
                raise ValueError(f"未找到股票代码 {symbols} 的行情数据")
            
            # 转换数据结构
            result_data = {}
            for symbol in symbol_list:
                data_item = market_data.get(symbol)
                if data_item:
                    # 提取所需字段（根据XTQuant返回的字段名）
                    result_data[symbol] = {
                        "price": data_item.get("lastPrice"),      # 最新价
                        "volume": data_item.get("volume"),        # 成交量
                        "amount": data_item.get("amount"),        # 成交额
                        "open": data_item.get("openPrice"),       # 开盘价
                        "high": data_item.get("highPrice"),       # 最高价
                        "low": data_item.get("lowPrice"),         # 最低价
                        "prevClose": data_item.get("prevClosePrice")  # 前收盘价
                    }
                else:
                    # 处理部分股票查询失败
                    result_data[symbol] = {"error": "No data available"}
            
            logger.info(
                f"成功获取最新行情数据: {len(symbol_list)}只股票",
                extra={
                    "request_id": get_request_id(),
                    "symbols": symbol_list,
                    "count": len(symbol_list)
                }
            )
            
            return {
                "success": True,
                "message": "获取最新行情数据成功",
                "data": result_data,
                "code": 200
            }
            
        except Exception as e:
            # 如果是我们自定义的异常，直接抛出
            if hasattr(e, 'code'):
                raise
            
            # 其他未预期的异常
            logger.error(
                f"获取最新行情数据时发生未预期错误: {str(e)}",
                extra={
                    "request_id": get_request_id(),
                    "symbols": symbols,
                    "error_type": type(e).__name__
                },
                exc_info=True
            )
            raise ImportError(f"获取最新行情数据失败: {str(e)}，项目必须连接miniQMT客户端")

    @staticmethod
    def get_full_market(
        symbol: str = Query(..., description="股票代码"),
        fields: str = Query(None, description="可选字段列表，逗号分隔")
    ):
        ensure_xtdc_initialized()
        try:
            # 参数验证
            if not symbol:
                logger.error(
                    "获取全市场数据失败: 股票代码不能为空",
                    extra={
                        "request_id": get_request_id(),
                        "symbol": symbol or "None"
                    }
                )
                return {"success": False, "message": "symbol is required", "status": 400}

            # 调用xtquant接口获取全市场数据
            full_market_data = xtdata.get_full_market_data(symbol)
            if full_market_data is None:
                logger.warning(
                    f"未找到股票代码 {symbol} 的全市场数据",
                    extra={
                        "request_id": get_request_id(),
                        "symbol": symbol
                    }
                )
                return {"success": False, "message": f"No full market data for symbol: {symbol}", "status": 404}

            # 如果指定了fields，则过滤字段
            if fields:
                field_list = [f.strip() for f in fields.split(',') if f.strip()]
                # 创建过滤后的数据字典
                filtered_data = {}
                for field in field_list:
                    if field in full_market_data:
                        filtered_data[field] = full_market_data[field]
                full_market_data = filtered_data

            return {
                "success": True,
                "data": full_market_data,
                "status": 200
            }

        except Exception as e:
            traceback.print_exc()
            return {
                "success": False,
                "message": f"Failed to fetch full market data: {str(e)}",
                "status": 500
            }

    @staticmethod
    async def get_multi_period_data(
        symbol: str = Query(..., description="股票代码"),
        start_date: str = Query(..., description="开始日期，格式YYYYMMDD"),
        end_date: str = Query(..., description="结束日期，格式YYYYMMDD"),
        periods: str = Query(..., description="周期列表，逗号分隔，如 1d,1w,1M"),
        include_quality: bool = Query(True, description="是否包含质量指标"),
        normalize: bool = Query(True, description="是否标准化数据")
    ):
        """
        获取多周期历史数据（增强API）
        
        Args:
            symbol: 股票代码
            start_date: 开始日期，格式YYYYMMDD
            end_date: 结束日期，格式YYYYMMDD
            periods: 周期列表，逗号分隔
            include_quality: 是否包含质量指标
            normalize: 是否标准化数据
            
        Returns:
            Dict: 多周期数据响应
        """
        try:
            # 修复导入路径
            import sys
            import os
            
            # 添加src目录到路径
            src_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'src')
            if src_path not in sys.path:
                sys.path.insert(0, src_path)
            
            from argus_mcp.api.enhanced_historical_api import EnhancedHistoricalDataAPI, MultiPeriodRequest
            from argus_mcp.data_models.historical_data import SupportedPeriod
            
            # 参数验证
            if not symbol:
                return {"success": False, "message": "symbol is required", "status": 400}
            
            # 验证日期格式
            date_pattern = re.compile(r"^\d{8}$")
            if not date_pattern.match(start_date):
                return {"success": False, "message": "start_date must be in YYYYMMDD format", "status": 400}
            if not date_pattern.match(end_date):
                return {"success": False, "message": "end_date must be in YYYYMMDD format", "status": 400}
            
            # 频率映射
            frequency_map = {
                '1m': SupportedPeriod.MINUTE_1,
                '5m': SupportedPeriod.MINUTE_5,
                '15m': SupportedPeriod.MINUTE_15,
                '30m': SupportedPeriod.MINUTE_30,
                '1h': SupportedPeriod.HOUR_1,
                '1d': SupportedPeriod.DAY_1,
                '1w': SupportedPeriod.WEEK_1,
                '1M': SupportedPeriod.MONTH_1
            }
            
            # 解析周期
            period_list = []
            for p in periods.split(','):
                p = p.strip()
                if p in frequency_map:
                    period_list.append(frequency_map[p])
            
            if not period_list:
                return {"success": False, "message": "无效的周期列表", "status": 400}
            
            # 转换日期格式
            formatted_start = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:8]}"
            formatted_end = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:8]}"
            
            # 创建API实例并获取数据
            api = EnhancedHistoricalDataAPI()
            request = MultiPeriodRequest(
                symbol=symbol,
                start_date=formatted_start,
                end_date=formatted_end,
                periods=period_list,
                include_quality_metrics=include_quality
            )
            
            response = await api.get_multi_period_data(request)
            
            return {
                "success": response.success,
                "data": response.data,
                "quality_reports": response.quality_reports,
                "metadata": response.metadata,
                "status": 200 if response.success else 500
            }
            
        except ImportError as e:
            return {
                "success": False,
                "message": f"增强API不可用: {str(e)}",
                "status": 503
            }
        except Exception as e:
            traceback.print_exc()
            return {
                "success": False,
                "message": f"获取多周期数据失败: {str(e)}",
                "status": 500
            }

# 注册API路由
router = APIRouter()
router.get("/trading_dates")(XTQuantAIHandler.get_trading_dates)
router.get("/hist_kline")(XTQuantAIHandler.get_hist_kline)
router.get("/instrument_detail")(XTQuantAIHandler.get_instrument_detail)
router.get("/stock_list")(XTQuantAIHandler.get_stock_list)
router.get("/latest_market")(XTQuantAIHandler.get_latest_market)
router.get("/full_market")(XTQuantAIHandler.get_full_market)
router.get("/multi_period_data")(XTQuantAIHandler.get_multi_period_data)

# (文件末尾空行)
