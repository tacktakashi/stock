"""
パフォーマンスベンチマークスクリプト
オリジナル版と最適化版の性能を比較
"""

import time
import asyncio
import sys
import tracemalloc
import psutil
import os
from typing import Dict, Any
import json


class PerformanceBenchmark:
    """パフォーマンス測定クラス"""
    
    def __init__(self):
        self.results = {}
        self.process = psutil.Process(os.getpid())
    
    def measure_memory(self) -> Dict[str, float]:
        """メモリ使用量を測定"""
        mem_info = self.process.memory_info()
        return {
            'rss_mb': mem_info.rss / 1024 / 1024,  # Resident Set Size (MB)
            'vms_mb': mem_info.vms / 1024 / 1024,  # Virtual Memory Size (MB)
        }
    
    def run_test(self, test_name: str, test_func: callable, *args, **kwargs) -> Dict[str, Any]:
        """テストを実行して測定"""
        print(f"\n{'=' * 60}")
        print(f"テスト: {test_name}")
        print('=' * 60)
        
        # メモリ測定開始
        tracemalloc.start()
        mem_before = self.measure_memory()
        
        # 実行時間測定
        start_time = time.time()
        
        try:
            result = test_func(*args, **kwargs)
            success = True
            error = None
        except Exception as e:
            result = None
            success = False
            error = str(e)
            print(f"エラー: {error}")
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # メモリ測定終了
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        mem_after = self.measure_memory()
        
        # 結果をまとめる
        test_result = {
            'name': test_name,
            'success': success,
            'execution_time': execution_time,
            'memory': {
                'peak_mb': peak / 1024 / 1024,
                'current_mb': current / 1024 / 1024,
                'rss_before_mb': mem_before['rss_mb'],
                'rss_after_mb': mem_after['rss_mb'],
                'rss_increase_mb': mem_after['rss_mb'] - mem_before['rss_mb']
            },
            'error': error
        }
        
        self.results[test_name] = test_result
        
        # 結果を表示
        if success:
            print(f"✓ 成功")
            print(f"  実行時間: {execution_time:.2f}秒")
            print(f"  メモリ使用量（ピーク）: {test_result['memory']['peak_mb']:.2f} MB")
            print(f"  メモリ増加量: {test_result['memory']['rss_increase_mb']:.2f} MB")
        else:
            print(f"✗ 失敗: {error}")
        
        return test_result
    
    def compare_results(self):
        """結果を比較"""
        print(f"\n{'=' * 80}")
        print("パフォーマンス比較結果")
        print('=' * 80)
        
        if len(self.results) < 2:
            print("比較するには2つ以上のテストが必要です")
            return
        
        # オリジナルと最適化版を比較
        original_key = None
        optimized_key = None
        
        for key in self.results:
            if 'オリジナル' in key:
                original_key = key
            elif '最適化' in key:
                optimized_key = key
        
        if original_key and optimized_key:
            original = self.results[original_key]
            optimized = self.results[optimized_key]
            
            if original['success'] and optimized['success']:
                time_improvement = (original['execution_time'] - optimized['execution_time']) / original['execution_time'] * 100
                memory_improvement = (original['memory']['peak_mb'] - optimized['memory']['peak_mb']) / original['memory']['peak_mb'] * 100
                
                print(f"\n実行時間:")
                print(f"  オリジナル版: {original['execution_time']:.2f}秒")
                print(f"  最適化版: {optimized['execution_time']:.2f}秒")
                print(f"  改善率: {time_improvement:.1f}% {'高速化' if time_improvement > 0 else '低下'}")
                print(f"  速度比: {original['execution_time'] / optimized['execution_time']:.2f}倍")
                
                print(f"\nメモリ使用量（ピーク）:")
                print(f"  オリジナル版: {original['memory']['peak_mb']:.2f} MB")
                print(f"  最適化版: {optimized['memory']['peak_mb']:.2f} MB")
                print(f"  改善率: {memory_improvement:.1f}% {'削減' if memory_improvement > 0 else '増加'}")
                
                # パフォーマンススコア計算
                performance_score = (time_improvement + memory_improvement) / 2
                print(f"\n総合パフォーマンススコア: {performance_score:.1f}%")
                
                # 改善の詳細
                print(f"\n改善の詳細:")
                if time_improvement > 50:
                    print(f"  ⚡ 大幅な速度向上を達成しました！")
                elif time_improvement > 20:
                    print(f"  ✓ 良好な速度改善が見られます")
                
                if memory_improvement > 30:
                    print(f"  💾 メモリ効率が大幅に改善しました！")
                elif memory_improvement > 10:
                    print(f"  ✓ メモリ使用量が削減されました")
        
        # 結果をJSONで保存
        with open('benchmark_results.json', 'w', encoding='utf-8') as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)
        print(f"\n結果を benchmark_results.json に保存しました")
    
    def print_summary(self):
        """サマリーを表示"""
        print(f"\n{'=' * 80}")
        print("ベンチマークサマリー")
        print('=' * 80)
        
        print(f"\n{'テスト名':<30} {'状態':<10} {'実行時間':<15} {'メモリ(MB)':<15}")
        print('-' * 80)
        
        for name, result in self.results.items():
            status = '✓ 成功' if result['success'] else '✗ 失敗'
            time_str = f"{result['execution_time']:.2f}秒" if result['success'] else 'N/A'
            mem_str = f"{result['memory']['peak_mb']:.2f}" if result['success'] else 'N/A'
            print(f"{name:<30} {status:<10} {time_str:<15} {mem_str:<15}")


def test_original_scraper():
    """オリジナル版のテスト（シンプル化）"""
    from scrape_earnings_schedule import EarningsScheduleScraper
    
    scraper = EarningsScheduleScraper()
    
    # テスト用の小規模なスクレイピング
    test_url = "https://kabuyoho.jp/calender?lst=20251119&ym=202511&sett=&publ=off#stocklist"
    soup = scraper.fetch_page(test_url)
    
    if soup:
        data = scraper.extract_earnings_data(soup)
        # 最初の10件の詳細を取得（全件は時間がかかるため）
        for item in data[:10]:
            if item.get('詳細ページURL'):
                details = scraper.extract_company_details(item['詳細ページURL'])
                item.update(details)
                time.sleep(0.5)  # オリジナル版の遅延
        
        return len(data)
    
    return 0


async def test_optimized_scraper():
    """最適化版のテスト"""
    from scrape_earnings_schedule_optimized import OptimizedEarningsScheduleScraper
    
    async with OptimizedEarningsScheduleScraper() as scraper:
        # テスト用の小規模なスクレイピング
        test_url = "https://kabuyoho.jp/calender?lst=20251119&ym=202511&sett=&publ=off#stocklist"
        html = await scraper.fetch_page_async(test_url)
        
        if html:
            companies = list(scraper.extract_earnings_data_batch(html))
            # 最初の10件の詳細を並列取得
            await scraper.fetch_all_details_parallel(companies[:10], batch_size=10)
            return len(companies)
    
    return 0


def test_web_scraping_original():
    """オリジナル版ウェブスクレイパーのテスト"""
    from web_scraping import WebScraper
    
    scraper = WebScraper()
    
    # 複数URLのテスト
    urls = [
        "https://example.com",
        "https://www.google.com",
        "https://www.github.com"
    ]
    
    results = []
    for url in urls:
        soup = scraper.fetch_page(url)
        if soup:
            links = scraper.extract_links(soup, url)
            results.append(len(links))
            time.sleep(0.5)  # 遅延
    
    return sum(results)


async def test_web_scraping_optimized():
    """最適化版ウェブスクレイパーのテスト"""
    from web_scraping_optimized import OptimizedWebScraper
    
    async with OptimizedWebScraper() as scraper:
        # 複数URLの並列テスト
        urls = [
            "https://example.com",
            "https://www.google.com",
            "https://www.github.com"
        ]
        
        # 並列でリンクを抽出
        tasks = [scraper.extract_links_async(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        total_links = 0
        for result in results:
            if isinstance(result, list):
                total_links += len(result)
        
        return total_links


def main():
    """メイン処理"""
    print("=" * 80)
    print("パフォーマンスベンチマーク開始")
    print("=" * 80)
    
    # Windowsイベントループの問題を回避
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    benchmark = PerformanceBenchmark()
    
    # テスト1: 決算カレンダースクレイパー
    print("\n📊 決算カレンダースクレイパーのテスト")
    
    # オリジナル版
    benchmark.run_test(
        "決算スクレイパー（オリジナル）",
        test_original_scraper
    )
    
    # 最適化版
    benchmark.run_test(
        "決算スクレイパー（最適化版）",
        lambda: asyncio.run(test_optimized_scraper())
    )
    
    # テスト2: 汎用ウェブスクレイパー
    print("\n🌐 汎用ウェブスクレイパーのテスト")
    
    # オリジナル版
    benchmark.run_test(
        "ウェブスクレイパー（オリジナル）",
        test_web_scraping_original
    )
    
    # 最適化版
    benchmark.run_test(
        "ウェブスクレイパー（最適化版）",
        lambda: asyncio.run(test_web_scraping_optimized())
    )
    
    # 結果の比較とサマリー
    benchmark.compare_results()
    benchmark.print_summary()
    
    print(f"\n{'=' * 80}")
    print("ベンチマーク完了")
    print('=' * 80)
    
    # 最適化の要約
    print("\n📈 実装された最適化:")
    print("  1. ⚡ 非同期処理（asyncio/aiohttp）による並列化")
    print("  2. 🔄 接続プーリングとキープアライブ")
    print("  3. 📦 Gzip/Deflate圧縮サポート")
    print("  4. 💾 LRUキャッシュによるメモリ効率化")
    print("  5. 🎯 正規表現のプリコンパイル")
    print("  6. 🚀 バッチ処理とストリーミング")
    print("  7. 🔒 セマフォによる同時実行制御")
    print("  8. 📊 ジェネレータによるメモリ使用量削減")


if __name__ == "__main__":
    main()