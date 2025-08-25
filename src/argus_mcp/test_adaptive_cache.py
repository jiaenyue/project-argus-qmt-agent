#!/usr/bin/env python3
"""
自适应缓存策略测试脚本
"""

import asyncio
import json
import time
import random
from typing import Dict, Any
from .cache_manager import CacheManager
from .adaptive_cache_strategy import AdaptationStrategy

class AdaptiveCacheTester:
    """自适应缓存策略测试器"""
    
    def __init__(self):
        self.cache_manager = None
        self.test_results = {}
        
    def setup_cache_manager(self):
        """设置缓存管理器"""
        self.cache_manager = CacheManager(
            max_size=1000,
            max_memory_mb=50,  # 50MB
            default_ttl=300,
            eviction_policy="lru"
        )
        print("缓存管理器已初始化")
        
    def generate_test_data(self, count: int = 1000) -> Dict[str, Any]:
        """生成测试数据"""
        test_data = {}
        for i in range(count):
            key = f"test_key_{i}"
            value = {
                "id": i,
                "data": f"test_data_{i}" * 10,  # 增加数据大小
                "timestamp": time.time(),
                "random": random.randint(1, 1000)
            }
            test_data[key] = value
        return test_data
        
    async def populate_cache(self, test_data: Dict[str, Any]):
        """填充缓存数据"""
        print("开始填充缓存...")
        for i, (key, value) in enumerate(test_data.items()):
            # 模拟不同的数据类型
            data_type = ["stock_data", "market_data", "user_data"][i % 3]
            await self.cache_manager.set(key, value, data_type=data_type)
        print(f"缓存填充完成，共 {len(test_data)} 条数据")
        
    async def simulate_access_patterns(self, test_data: Dict[str, Any], iterations: int = 500):
        """模拟访问模式"""
        print(f"开始模拟访问模式，共 {iterations} 次访问...")
        keys = list(test_data.keys())
        
        for i in range(iterations):
            # 80/20 规则：80% 的访问集中在 20% 的热点数据上
            if random.random() < 0.8:
                # 访问热点数据（前20%）
                key = random.choice(keys[:len(keys)//5])
            else:
                # 访问其他数据
                key = random.choice(keys)
            
            result = await self.cache_manager.get(key)
            if result is None:
                # 缓存未命中，模拟从数据源获取
                await asyncio.sleep(0.001)  # 模拟数据库查询延迟
        
        print("访问模式模拟完成")
        
    async def test_adaptive_strategy(self, strategy: str, duration: int = 30) -> Dict[str, Any]:
        """测试自适应策略"""
        print(f"\n测试策略: {strategy.value.upper()}")
        
        # 获取初始统计
        initial_stats = self.cache_manager.get_stats()
        
        # 设置策略
        self.cache_manager.adaptive_strategy.update_strategy(strategy)
        
        # 启动自适应优化
        await self.cache_manager.start_adaptive_optimization()
        
        # 运行测试负载
        start_time = time.time()
        while time.time() - start_time < duration:
            # 模拟访问模式
            test_data = self.generate_test_data(100)
            await self.simulate_access_patterns(test_data, 50)
            await asyncio.sleep(1)
        
        # 停止自适应优化
        await self.cache_manager.stop_adaptive_optimization()
        
        # 获取最终统计
        final_stats = self.cache_manager.get_stats()
        
        # 计算性能提升
        hit_rate_improvement = getattr(final_stats, 'hit_rate', final_stats.get('hit_rate', 0)) - getattr(initial_stats, 'hit_rate', initial_stats.get('hit_rate', 0))
        memory_usage_change = getattr(final_stats, 'memory_usage', final_stats.get('memory_usage', 0)) - getattr(initial_stats, 'memory_usage', initial_stats.get('memory_usage', 0))
        
        # 获取自适应调整次数
        adaptations = len(self.cache_manager.adaptive_strategy.adjustment_history)
        
        result = {
            "strategy": strategy.value,
            "duration": duration,
            "initial_stats": {
                "hits": getattr(initial_stats, 'hits', initial_stats.get('hits', 0)),
                "misses": getattr(initial_stats, 'misses', initial_stats.get('misses', 0)),
                "hit_rate": getattr(initial_stats, 'hit_rate', initial_stats.get('hit_rate', 0)),
                "memory_usage": getattr(initial_stats, 'memory_usage', initial_stats.get('memory_usage', 0))
            },
            "final_stats": {
                "hits": getattr(final_stats, 'hits', final_stats.get('hits', 0)),
                "misses": getattr(final_stats, 'misses', final_stats.get('misses', 0)),
                "hit_rate": getattr(final_stats, 'hit_rate', final_stats.get('hit_rate', 0)),
                "memory_usage": getattr(final_stats, 'memory_usage', final_stats.get('memory_usage', 0))
            },
            "performance_improvement": {
                "hit_rate_change": hit_rate_improvement,
                "memory_usage_change": memory_usage_change
            },
            "adaptations_count": adaptations,
            "adaptation_history": list(self.cache_manager.adaptive_strategy.adjustment_history)
        }
        
        print(f"策略 {strategy} 测试完成:")
        print(f"  命中率提升: {hit_rate_improvement:.2%}")
        print(f"  内存使用变化: {memory_usage_change / 1024 / 1024:.2f} MB")
        print(f"  自适应调整次数: {adaptations}")
        
        return result
        
    async def run_comprehensive_test(self):
        """运行综合测试"""
        print("开始自适应缓存策略综合测试")
        
        # 设置缓存管理器
        self.setup_cache_manager()
        
        # 生成测试数据
        test_data = self.generate_test_data(500)
        
        # 填充缓存
        await self.populate_cache(test_data)
        
        # 模拟初始访问模式
        await self.simulate_access_patterns(test_data, 200)
        
        # 测试不同的自适应策略
        strategies = [AdaptationStrategy.CONSERVATIVE, AdaptationStrategy.BALANCED, AdaptationStrategy.AGGRESSIVE]
        
        for strategy in strategies:
            result = await self.test_adaptive_strategy(strategy, 20)
            self.test_results[strategy.value] = result
            
        # 分析结果
        self.analyze_results()
        
        # 导出结果
        self.export_results()
        
    def analyze_results(self):
        """分析测试结果"""
        print("\n=== 测试结果分析 ===")
        
        for strategy_name, result in self.test_results.items():
            print(f"\n策略: {strategy_name.upper()}")
            print(f"  命中率提升: {result['performance_improvement']['hit_rate_change']:.2%}")
            print(f"  内存使用变化: {result['performance_improvement']['memory_usage_change']/1024/1024:.2f}MB")
            
            if 'adaptive_status' in result and result['adaptive_status']:
                status = result['adaptive_status']
                print(f"  自适应调整次数: {status.get('total_adjustments', 0)}")
                print(f"  成功调整次数: {status.get('successful_adjustments', 0)}")
                
    def export_results(self):
        """导出测试结果"""
        timestamp = int(time.time())
        filename = f"adaptive_cache_test_{timestamp}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.test_results, f, indent=2, ensure_ascii=False)
            
        print(f"\n测试结果已导出到: {filename}")

async def main():
    """主函数"""
    tester = AdaptiveCacheTester()
    await tester.run_comprehensive_test()

if __name__ == "__main__":
    asyncio.run(main())