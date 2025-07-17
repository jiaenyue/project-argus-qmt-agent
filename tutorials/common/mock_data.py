"""
模拟数据生成器 - Project Argus QMT 数据代理服务教程

提供各种API的模拟数据生成功能，用于API服务不可用时的降级处理。
确保模拟数据的真实性和一致性，支持可配置的数据生成参数。
"""

import random
import time
import datetime
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass
import math

from .config import get_config


@dataclass
class MockDataConfig:
    """模拟数据配置类"""
    # 价格相关配置
    base_price_range: tuple = (10.0, 2000.0)
    price_volatility: float = 0.05  # 价格波动率
    volume_range: tuple = (100000, 10000000)
    
    # 时间相关配置
    trading_hours_start: str = "09:30"
    trading_hours_end: str = "15:00"
    lunch_break_start: str = "11:30"
    lunch_break_end: str = "13:00"
    
    # 数据质量配置
    data_consistency_seed: int = 42  # 确保数据一致性的随机种子
    enable_realistic_patterns: bool = True  # 启用真实市场模式


class MockDataGenerator:
    """模拟数据生成器
    
    为各种QMT API提供真实的模拟数据，支持数据一致性和可重现性。
    """
    
    def __init__(self, config: Optional[MockDataConfig] = None):
        """初始化模拟数据生成器
        
        Args:
            config: 模拟数据配置，如果为None则使用默认配置
        """
        self.config = config or MockDataConfig()
        self.tutorial_config = get_config()
        self._symbol_cache = {}  # 缓存股票基础信息
        self._price_cache = {}   # 缓存价格信息
        
        # 设置随机种子以确保数据一致性
        random.seed(self.config.data_consistency_seed)
    
    def _get_symbol_base_info(self, symbol: str) -> Dict[str, Any]:
        """获取股票基础信息（缓存）
        
        Args:
            symbol: 股票代码
            
        Returns:
            Dict: 包含股票基础信息的字典
        """
        if symbol not in self._symbol_cache:
            # 基于股票代码生成一致的基础信息
            symbol_hash = hash(symbol)
            
            # 股票名称映射
            name_mapping = {
                "600519.SH": "贵州茅台",
                "000858.SZ": "五粮液", 
                "601318.SH": "中国平安",
                "000001.SZ": "平安银行",
                "600036.SH": "招商银行",
                "000002.SZ": "万科A",
                "600000.SH": "浦发银行"
            }
            
            # 生成基础价格（基于哈希值确保一致性）
            base_price = self.config.base_price_range[0] + (
                abs(symbol_hash) % 1000
            ) / 1000 * (
                self.config.base_price_range[1] - self.config.base_price_range[0]
            )
            
            self._symbol_cache[symbol] = {
                'name': name_mapping.get(symbol, f"股票{symbol[:6]}"),
                'base_price': round(base_price, 2),
                'sector': self._get_sector_by_symbol(symbol),
                'market': symbol.split('.')[1] if '.' in symbol else 'SH'
            }
        
        return self._symbol_cache[symbol]
    
    def _get_sector_by_symbol(self, symbol: str) -> str:
        """根据股票代码获取所属板块
        
        Args:
            symbol: 股票代码
            
        Returns:
            str: 板块名称
        """
        code = symbol.split('.')[0] if '.' in symbol else symbol
        
        # 简单的板块分类逻辑
        if code.startswith('60'):
            return random.choice(['银行', '保险', '证券', '白酒', '医药'])
        elif code.startswith('00'):
            return random.choice(['科技', '地产', '消费', '制造', '新能源'])
        else:
            return random.choice(['综合', '其他'])
    
    def _generate_realistic_price(self, symbol: str, base_time: Optional[int] = None) -> float:
        """生成真实的价格数据
        
        Args:
            symbol: 股票代码
            base_time: 基准时间戳
            
        Returns:
            float: 生成的价格
        """
        base_info = self._get_symbol_base_info(symbol)
        base_price = base_info['base_price']
        
        if not base_time:
            base_time = int(time.time())
        
        # 基于时间和股票代码生成价格波动
        time_factor = math.sin(base_time / 3600) * 0.02  # 时间因子
        symbol_factor = (hash(symbol + str(base_time // 300)) % 100 - 50) / 1000  # 股票因子
        
        # 应用波动
        price_change = (time_factor + symbol_factor) * base_price
        current_price = base_price + price_change
        
        return round(max(current_price, 0.01), 2)
    
    def generate_trading_dates(self, market: str, start_date: str = None, 
                             end_date: str = None, count: int = -1) -> Dict[str, Any]:
        """生成交易日历模拟数据
        
        Args:
            market: 市场代码
            start_date: 开始日期 (YYYYMMDD)
            end_date: 结束日期 (YYYYMMDD)
            count: 返回数据条数
            
        Returns:
            Dict: 交易日历数据
        """
        # 如果没有指定日期范围，使用默认范围
        if not end_date:
            end_date = datetime.datetime.now().strftime("%Y%m%d")
        
        if not start_date:
            # 默认返回最近30个交易日
            end_dt = datetime.datetime.strptime(end_date, "%Y%m%d")
            start_dt = end_dt - datetime.timedelta(days=50)  # 多取一些，过滤后得到30个交易日
            start_date = start_dt.strftime("%Y%m%d")
        
        # 生成日期范围内的交易日
        start_dt = datetime.datetime.strptime(start_date, "%Y%m%d")
        end_dt = datetime.datetime.strptime(end_date, "%Y%m%d")
        
        trading_dates = []
        current_dt = start_dt
        
        while current_dt <= end_dt:
            # 排除周末
            if current_dt.weekday() < 5:  # 0-4 是周一到周五
                # 排除一些假期（简化处理）
                date_str = current_dt.strftime("%Y%m%d")
                if not self._is_holiday(date_str):
                    trading_dates.append(date_str)
            
            current_dt += datetime.timedelta(days=1)
        
        # 如果指定了count，返回指定数量
        if count > 0:
            if len(trading_dates) > count:
                trading_dates = trading_dates[-count:]  # 取最近的count条
        
        return {
            "code": 0,
            "message": "success",
            "data": trading_dates,
            "market": market,
            "total": len(trading_dates)
        }
    
    def _is_holiday(self, date_str: str) -> bool:
        """简单的假期判断（可以扩展）
        
        Args:
            date_str: 日期字符串 (YYYYMMDD)
            
        Returns:
            bool: 是否为假期
        """
        # 简化的假期列表（实际应用中应该使用完整的假期数据）
        holidays = [
            "20250101",  # 元旦
            "20250128", "20250129", "20250130", "20250131",  # 春节
            "20250201", "20250202", "20250203", "20250204",
            "20250405", "20250406", "20250407",  # 清明节
            "20250501", "20250502", "20250503",  # 劳动节
            "20251001", "20251002", "20251003", "20251004",  # 国庆节
            "20251005", "20251006", "20251007"
        ]
        
        return date_str in holidays
    
    def generate_hist_kline(self, symbol: str, start_date: str, end_date: str, 
                           frequency: str = "1d", count: int = None) -> Dict[str, Any]:
        """生成历史K线模拟数据
        
        Args:
            symbol: 股票代码
            start_date: 开始日期 (YYYYMMDD)
            end_date: 结束日期 (YYYYMMDD)
            frequency: 频率 ('1m', '5m', '15m', '30m', '1h', '1d', '1w', '1M')
            count: 数据条数
            
        Returns:
            Dict: 历史K线数据
        """
        base_info = self._get_symbol_base_info(symbol)
        base_price = base_info['base_price']
        
        # 生成时间序列
        if frequency == '1d':
            dates = self.generate_trading_dates("SH", start_date, end_date, count or -1)['data']
        else:
            # 对于分钟级数据，简化处理
            if not count:
                count = 100  # 默认100条数据
            dates = []
            current_date = datetime.datetime.strptime(end_date, "%Y%m%d") if end_date else datetime.datetime.now()
            
            for i in range(count):
                if frequency in ['1m', '5m', '15m', '30m']:
                    # 分钟级数据
                    minutes = int(frequency[:-1])
                    time_delta = datetime.timedelta(minutes=minutes * i)
                    date_time = current_date - time_delta
                    dates.append(date_time.strftime("%Y%m%d %H:%M:%S"))
                elif frequency == '1h':
                    # 小时级数据
                    time_delta = datetime.timedelta(hours=i)
                    date_time = current_date - time_delta
                    dates.append(date_time.strftime("%Y%m%d %H:%M:%S"))
                elif frequency == '1w':
                    # 周级数据
                    time_delta = datetime.timedelta(weeks=i)
                    date_time = current_date - time_delta
                    dates.append(date_time.strftime("%Y%m%d"))
                elif frequency == '1M':
                    # 月级数据
                    time_delta = datetime.timedelta(days=30 * i)
                    date_time = current_date - time_delta
                    dates.append(date_time.strftime("%Y%m%d"))
            
            dates.reverse()  # 按时间正序排列
        
        # 生成K线数据
        kline_data = []
        current_price = base_price
        
        for i, date in enumerate(dates):
            # 生成OHLC数据
            open_price = current_price
            
            # 生成价格波动
            volatility = self.config.price_volatility
            price_change = random.uniform(-volatility, volatility)
            close_price = round(open_price * (1 + price_change), 2)
            
            # 生成最高价和最低价
            high_factor = random.uniform(0, 0.02)
            low_factor = random.uniform(0, 0.02)
            high_price = round(max(open_price, close_price) * (1 + high_factor), 2)
            low_price = round(min(open_price, close_price) * (1 - low_factor), 2)
            
            # 生成成交量和成交额
            volume = random.randint(self.config.volume_range[0], self.config.volume_range[1])
            amount = round(volume * (open_price + close_price) / 2, 2)
            
            kline_item = {
                "date": date,
                "open": open_price,
                "high": high_price,
                "low": low_price,
                "close": close_price,
                "volume": volume,
                "amount": amount,
                "symbol": symbol
            }
            
            # 添加技术指标（可选）
            if i > 0:
                prev_close = kline_data[i-1]['close']
                kline_item['change'] = round(close_price - prev_close, 2)
                kline_item['change_pct'] = round((close_price - prev_close) / prev_close * 100, 2)
            else:
                kline_item['change'] = 0
                kline_item['change_pct'] = 0
            
            kline_data.append(kline_item)
            current_price = close_price
        
        return {
            "code": 0,
            "message": "success",
            "data": kline_data,
            "symbol": symbol,
            "frequency": frequency,
            "total": len(kline_data)
        }
    
    def generate_instrument_detail(self, symbols: Union[str, List[str]]) -> Dict[str, Any]:
        """生成合约详情模拟数据
        
        Args:
            symbols: 股票代码或股票代码列表
            
        Returns:
            Dict: 合约详情数据
        """
        if isinstance(symbols, str):
            symbols = [symbols]
        
        details = {}
        for symbol in symbols:
            base_info = self._get_symbol_base_info(symbol)
            current_price = self._generate_realistic_price(symbol)
            
            # 生成合约详情
            details[symbol] = {
                "symbol": symbol,
                "name": base_info['name'],
                "market": base_info['market'],
                "sector": base_info['sector'],
                "currency": "CNY",
                "exchange": "SSE" if symbol.endswith('.SH') else "SZSE",
                "type": "stock",
                "status": "trading",
                "list_date": self._generate_list_date(symbol),
                "delist_date": None,
                "lot_size": 100,  # 每手股数
                "tick_size": 0.01,  # 最小价格变动单位
                "price_limit_up": round(current_price * 1.1, 2),  # 涨停价
                "price_limit_down": round(current_price * 0.9, 2),  # 跌停价
                "current_price": current_price,
                "pre_close": round(current_price * (1 + random.uniform(-0.02, 0.02)), 2),
                "market_cap": self._generate_market_cap(symbol, current_price),
                "pe_ratio": round(random.uniform(8.0, 50.0), 2),
                "pb_ratio": round(random.uniform(0.5, 8.0), 2),
                "dividend_yield": round(random.uniform(0.5, 5.0), 2),
                "beta": round(random.uniform(0.5, 2.0), 2),
                "volume_ratio": round(random.uniform(0.5, 3.0), 2),
                "turnover_rate": round(random.uniform(0.1, 10.0), 2)
            }
        
        return {
            "code": 0,
            "message": "success",
            "data": details if len(symbols) > 1 else details[symbols[0]]
        }
    
    def generate_stock_list(self, market: str = None, sector: str = None) -> Dict[str, Any]:
        """生成股票列表模拟数据
        
        Args:
            market: 市场代码 (SH/SZ)
            sector: 板块名称
            
        Returns:
            Dict: 股票列表数据
        """
        # 预定义的股票池
        stock_pool = {
            'SH': [
                "600519.SH", "601318.SH", "600036.SH", "600000.SH", "600276.SH",
                "600887.SH", "600585.SH", "601166.SH", "601398.SH", "601288.SH"
            ],
            'SZ': [
                "000858.SZ", "000001.SZ", "000002.SZ", "000063.SZ", "000166.SZ",
                "000338.SZ", "000568.SZ", "000625.SZ", "000651.SZ", "000725.SZ"
            ]
        }
        
        # 板块股票映射
        sector_stocks = {
            '银行': ["601318.SH", "600036.SH", "600000.SH", "000001.SZ"],
            '白酒': ["600519.SH", "000858.SZ"],
            '保险': ["601318.SH", "601601.SH"],
            '科技': ["000063.SZ", "002415.SZ", "002594.SZ"],
            '地产': ["000002.SZ", "000166.SZ"],
            '医药': ["600276.SH", "000568.SZ"],
            '新能源': ["002594.SZ", "000725.SZ"]
        }
        
        # 根据条件筛选股票
        if sector and sector in sector_stocks:
            selected_stocks = sector_stocks[sector]
        elif market:
            selected_stocks = stock_pool.get(market.upper(), [])
        else:
            # 返回所有股票
            selected_stocks = stock_pool['SH'] + stock_pool['SZ']
        
        return {
            "code": 0,
            "message": "success",
            "data": selected_stocks,
            "total": len(selected_stocks)
        }
    
    def generate_latest_market(self, symbols: Union[str, List[str]]) -> Dict[str, Any]:
        """生成最新行情模拟数据
        
        Args:
            symbols: 股票代码或股票代码列表
            
        Returns:
            Dict: 最新行情数据
        """
        if isinstance(symbols, str):
            symbols = [symbols]
        
        market_data = {}
        current_time = int(time.time())
        
        for symbol in symbols:
            base_info = self._get_symbol_base_info(symbol)
            current_price = self._generate_realistic_price(symbol, current_time)
            pre_close = round(current_price * (1 + random.uniform(-0.02, 0.02)), 2)
            
            market_data[symbol] = {
                "symbol": symbol,
                "name": base_info['name'],
                "current_price": current_price,
                "pre_close": pre_close,
                "change": round(current_price - pre_close, 2),
                "change_pct": round((current_price - pre_close) / pre_close * 100, 2),
                "high": round(current_price * (1 + random.uniform(0, 0.05)), 2),
                "low": round(current_price * (1 - random.uniform(0, 0.05)), 2),
                "open": round(pre_close * (1 + random.uniform(-0.02, 0.02)), 2),
                "volume": random.randint(1000000, 50000000),
                "turnover": round(random.uniform(100000000, 5000000000), 2),
                "timestamp": current_time
            }
        
        return {
            "code": 0,
            "message": "success",
            "data": market_data if len(symbols) > 1 else market_data[symbols[0]],
            "timestamp": current_time
        }
    
    def generate_full_market(self, market: str = None, symbols: Union[str, List[str]] = None) -> Dict[str, Any]:
        """生成完整行情模拟数据
        
        Args:
            market: 市场代码
            symbols: 股票代码列表
            
        Returns:
            Dict: 完整行情数据
        """
        if symbols:
            if isinstance(symbols, str):
                symbols = [symbols]
            target_symbols = symbols
        else:
            # 根据市场获取股票列表
            stock_list_data = self.generate_stock_list(market=market)
            target_symbols = stock_list_data['data'][:10]  # 限制数量
        
        # 生成完整行情数据
        full_data = []
        current_time = int(time.time())
        
        for symbol in target_symbols:
            latest_data = self.generate_latest_market(symbol)['data']
            
            # 扩展完整行情数据
            full_market_item = {
                **latest_data,
                "amplitude": round(random.uniform(1.0, 15.0), 2),  # 振幅
                "volume_ratio": round(random.uniform(0.5, 3.0), 2),  # 量比
                "speed": round(random.uniform(-5.0, 5.0), 2),  # 涨速
                "market_cap": self._generate_market_cap(symbol, latest_data['current_price']),
                "pe_ratio": round(random.uniform(8.0, 50.0), 2),
                "pb_ratio": round(random.uniform(0.5, 8.0), 2)
            }
            full_data.append(full_market_item)
        
        return {
            "code": 0,
            "message": "success",
            "data": full_data,
            "total": len(full_data),
            "timestamp": current_time
        }
    
    def _generate_list_date(self, symbol: str) -> str:
        """生成上市日期
        
        Args:
            symbol: 股票代码
            
        Returns:
            str: 上市日期 (YYYYMMDD)
        """
        # 基于股票代码生成一致的上市日期
        symbol_hash = abs(hash(symbol))
        
        # 大部分股票在2000-2020年间上市
        base_year = 2000 + (symbol_hash % 20)
        base_month = 1 + (symbol_hash // 20 % 12)
        base_day = 1 + (symbol_hash // 240 % 28)
        
        return f"{base_year:04d}{base_month:02d}{base_day:02d}"
    
    def _generate_market_cap(self, symbol: str, current_price: float, ratio: float = 1.0) -> float:
        """生成市值数据
        
        Args:
            symbol: 股票代码
            current_price: 当前价格
            ratio: 流通比例（用于计算流通市值）
            
        Returns:
            float: 市值（亿元）
        """
        # 基于股票代码和价格生成一致的股本数据
        symbol_hash = abs(hash(symbol))
        
        # 总股本在1-100亿股之间
        total_shares = (1 + symbol_hash % 99) * 100000000  # 股
        
        # 计算市值
        market_cap = current_price * total_shares * ratio / 100000000  # 转换为亿元
        
        return round(market_cap, 2)


if __name__ == "__main__":
    """模拟数据生成器演示"""
    from .utils import print_section_header, print_subsection_header, print_api_result
    
    print_section_header("模拟数据生成器演示")
    
    # 创建模拟数据生成器实例
    mock_generator = MockDataGenerator()
    
    # 测试交易日历数据生成
    print_subsection_header("交易日历数据生成")
    trading_dates = mock_generator.generate_trading_dates("SH", count=10)
    print_api_result(trading_dates, "交易日历")
    
    # 测试历史K线数据生成
    print_subsection_header("历史K线数据生成")
    end_date = datetime.datetime.now().strftime("%Y%m%d")
    start_date = (datetime.datetime.now() - datetime.timedelta(days=10)).strftime("%Y%m%d")
    hist_kline = mock_generator.generate_hist_kline("600519.SH", start_date, end_date)
    print_api_result(hist_kline, "历史K线")
    
    # 测试合约详情数据生成
    print_subsection_header("合约详情数据生成")
    instrument_detail = mock_generator.generate_instrument_detail("600519.SH")
    print_api_result(instrument_detail, "合约详情")
    
    # 测试股票列表数据生成
    print_subsection_header("股票列表数据生成")
    stock_list = mock_generator.generate_stock_list("SH")
    print_api_result(stock_list, "股票列表")
    
    # 测试最新行情数据生成
    print_subsection_header("最新行情数据生成")
    latest_market = mock_generator.generate_latest_market("600519.SH")
    print_api_result(latest_market, "最新行情")
    
    # 测试完整行情数据生成
    print_subsection_header("完整行情数据生成")
    full_market = mock_generator.generate_full_market(symbols=["600519.SH", "000858.SZ"])
    print_api_result(full_market, "完整行情")
    
    print("\n模拟数据生成器演示完成")