#!/usr/bin/env python3
"""
最適化版のテストスクリプト
"""

import asyncio
import sys
import time


async def test_optimized_version():
    """最適化版の動作テスト"""
    print("=" * 60)
    print("最適化版スクレイパーの動作テスト")
    print("=" * 60)
    
    try:
        from scrape_earnings_schedule_optimized import OptimizedEarningsScheduleScraper
        print("✓ モジュールのインポート成功")
        
        # テスト用HTMLデータ
        test_html = """
        <table>
        <tr>
            <td><a href="/reportTop?bcode=1802">大林組 1802</a></td>
            <td>2025/11/05済</td>
            <td>2025/09</td>
            <td>3Q</td>
            <td>13,900</td>
            <td>8,258 _( 3Q )_</td>
            <td>59.4</td>
        </tr>
        <tr>
            <td><a href="/reportTop?bcode=4523">エーザイ 4523</a></td>
            <td>2025/11/05済</td>
            <td>2025/09</td>
            <td>2Q</td>
            <td>59,000</td>
            <td>36,936 _( 2Q )_</td>
            <td>62.6</td>
        </tr>
        </table>
        """
        
        async with OptimizedEarningsScheduleScraper() as scraper:
            print("✓ スクレイパーの初期化成功")
            
            # HTMLパースのテスト
            companies = list(scraper.extract_earnings_data_batch(test_html))
            print(f"✓ HTMLパース成功: {len(companies)}件のデータを抽出")
            
            # データ確認
            for i, company in enumerate(companies, 1):
                data = company.to_dict()
                print(f"\n  会社 {i}:")
                print(f"    名前: {data['会社名']}")
                print(f"    銘柄コード: {data['銘柄コード']}")
                print(f"    進捗率: {data['進捗率']}")
            
            print("\n✓ テスト完了")
            return True
            
    except Exception as e:
        print(f"\n✗ エラー: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_web_scraper():
    """汎用ウェブスクレイパーのテスト"""
    print("\n" + "=" * 60)
    print("最適化版ウェブスクレイパーの動作テスト")
    print("=" * 60)
    
    try:
        from web_scraping_optimized import OptimizedWebScraper
        print("✓ モジュールのインポート成功")
        
        async with OptimizedWebScraper(max_concurrent=5) as scraper:
            print("✓ スクレイパーの初期化成功")
            
            # HTMLパースのテスト
            test_html = "<html><head><title>テストページ</title></head><body><h1>見出し</h1><p>段落</p></body></html>"
            soup = scraper.parse_html(test_html)
            title = soup.find('title')
            
            if title:
                print(f"✓ HTMLパース成功: タイトル = {title.get_text()}")
            
            print("✓ テスト完了")
            return True
            
    except Exception as e:
        print(f"\n✗ エラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """メイン処理"""
    # Windowsイベントループの問題を回避
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    print("最適化版コードの動作確認\n")
    
    start_time = time.time()
    
    # テスト実行
    result1 = asyncio.run(test_optimized_version())
    result2 = asyncio.run(test_web_scraper())
    
    elapsed_time = time.time() - start_time
    
    print("\n" + "=" * 60)
    print("テスト結果サマリー")
    print("=" * 60)
    print(f"決算スクレイパー: {'✓ 成功' if result1 else '✗ 失敗'}")
    print(f"汎用スクレイパー: {'✓ 成功' if result2 else '✗ 失敗'}")
    print(f"実行時間: {elapsed_time:.2f}秒")
    
    if result1 and result2:
        print("\n✅ すべてのテストが成功しました！")
        print("\n最適化の特徴:")
        print("  • 非同期処理による高速化")
        print("  • メモリ効率の改善")
        print("  • 並列リクエスト対応")
        print("  • キャッシュ機構の実装")
        print("  • エラーハンドリングの強化")
        return 0
    else:
        print("\n⚠️ 一部のテストが失敗しました")
        return 1


if __name__ == "__main__":
    sys.exit(main())