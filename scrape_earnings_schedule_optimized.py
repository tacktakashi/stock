"""
最適化版：決算カレンダーから会社名と進捗率を抽出するスクリプト
パフォーマンスを大幅に改善したバージョン
"""

import asyncio
import aiohttp
from bs4 import BeautifulSoup
import csv
import json
import re
from typing import List, Dict, Optional, Generator, Tuple
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from functools import lru_cache, partial
from dataclasses import dataclass
import logging
from collections import defaultdict
from itertools import islice

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 正規表現パターンをプリコンパイル（キャッシュ効果）
COMPANY_LINK_PATTERN = re.compile(r'/reportTop\?bcode=')
STOCK_CODE_PATTERN = re.compile(r'bcode=(\d+)')
PAGE_LINK_PATTERN = re.compile(r'/calender\?.*page=\d+')
PAGE_NUMBER_PATTERN = re.compile(r'page=(\d+)')
PROGRESS_RATE_PATTERN = re.compile(r'^\d+\.\d+$')
PERCENT_PATTERN = re.compile(r'^\d+\.\d+%$')
NUMBER_EXTRACT_PATTERN = re.compile(r'(\d+\.\d+)\s*%?')
NUMBER_CLEAN_PATTERN = re.compile(r'([0-9,]+\.?\d*)')

# パフォーマンス設定
MAX_CONCURRENT_REQUESTS = 10  # 同時リクエスト数
BATCH_SIZE = 50  # バッチ処理サイズ
CACHE_SIZE = 1000  # LRUキャッシュサイズ
REQUEST_TIMEOUT = 30  # タイムアウト（秒）
RATE_LIMIT_DELAY = 0.1  # レート制限用の最小遅延（秒）


@dataclass
class CompanyData:
    """会社データを表すデータクラス（メモリ効率向上）"""
    name: str
    stock_code: str
    progress_rate: Optional[float]
    detail_url: str
    per: str = 'N/A'
    pbr: str = 'N/A'
    dividend_yield: str = 'N/A'
    
    def to_dict(self) -> Dict:
        """辞書形式に変換"""
        return {
            '会社名': self.name,
            '銘柄コード': self.stock_code,
            '進捗率': f"{self.progress_rate:.1f}%" if self.progress_rate is not None else "N/A",
            '詳細ページURL': self.detail_url,
            'PER': self.per,
            'PBR': self.pbr,
            '配当利回り': self.dividend_yield
        }


class OptimizedEarningsScheduleScraper:
    """パフォーマンス最適化版の決算カレンダースクレイパー"""
    
    def __init__(self):
        """初期化"""
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'ja,en-US;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',  # 圧縮サポート
            'Connection': 'keep-alive',  # 接続の再利用
        }
        self.session = None
        self._cache = {}  # URLごとのキャッシュ
        self._detail_cache = {}  # 詳細ページのキャッシュ
    
    async def __aenter__(self):
        """非同期コンテキストマネージャーの開始"""
        connector = aiohttp.TCPConnector(
            limit=MAX_CONCURRENT_REQUESTS,
            limit_per_host=MAX_CONCURRENT_REQUESTS,
            ttl_dns_cache=300,  # DNSキャッシュ
            enable_cleanup_closed=True
        )
        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
        self.session = aiohttp.ClientSession(
            headers=self.headers,
            connector=connector,
            timeout=timeout,
            trust_env=True
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """非同期コンテキストマネージャーの終了"""
        if self.session:
            await self.session.close()
    
    @lru_cache(maxsize=CACHE_SIZE)
    def _parse_progress_rate(self, cell_text: str) -> Optional[float]:
        """進捗率のパース（キャッシュ付き）"""
        if PROGRESS_RATE_PATTERN.match(cell_text):
            try:
                rate = float(cell_text)
                if 0 <= rate <= 200:
                    return rate
            except ValueError:
                pass
        elif PERCENT_PATTERN.match(cell_text):
            try:
                rate = float(cell_text.replace('%', ''))
                if 0 <= rate <= 200:
                    return rate
            except ValueError:
                pass
        return None
    
    async def fetch_page_async(self, url: str) -> Optional[str]:
        """非同期でページを取得"""
        if url in self._cache:
            return self._cache[url]
        
        try:
            async with self.session.get(url) as response:
                response.raise_for_status()
                content = await response.text()
                self._cache[url] = content
                return content
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None
    
    def parse_company_row(self, row) -> Optional[CompanyData]:
        """行から会社データを高速パース"""
        company_link = row.find('a', href=COMPANY_LINK_PATTERN)
        if not company_link:
            return None
        
        # 会社名と銘柄コードの抽出
        full_text = company_link.get_text(strip=True)
        href = company_link.get('href', '')
        
        stock_code_match = STOCK_CODE_PATTERN.search(href)
        stock_code = stock_code_match.group(1) if stock_code_match else ''
        
        # 会社名の抽出（最適化済み）
        parts = full_text.split()
        if len(parts) >= 2 and parts[-1].isdigit():
            company_name = ' '.join(parts[:-1])
            if not stock_code:
                stock_code = parts[-1]
        else:
            company_name = full_text
        
        # 進捗率の抽出（最適化済み）
        cells = row.find_all('td')
        progress_rate = None
        
        # 右から左へ効率的に検索
        for cell in reversed(cells):
            cell_text = cell.get_text(strip=True)
            rate = self._parse_progress_rate(cell_text)
            if rate is not None:
                progress_rate = rate
                break
        
        # 詳細ページURLの構築
        detail_url = None
        if href:
            if href.startswith('/'):
                detail_url = f"https://kabuyoho.jp{href}"
            elif href.startswith('http'):
                detail_url = href
            else:
                detail_url = f"https://kabuyoho.jp/{href}"
        
        if company_name:
            return CompanyData(
                name=company_name,
                stock_code=stock_code,
                progress_rate=progress_rate,
                detail_url=detail_url or ''
            )
        return None
    
    def extract_earnings_data_batch(self, html_content: str) -> Generator[CompanyData, None, None]:
        """HTMLコンテンツからデータをバッチ抽出（ジェネレータ使用でメモリ効率向上）"""
        soup = BeautifulSoup(html_content, 'lxml')  # lxmlパーサーで高速化
        seen_companies = set()
        
        for row in soup.find_all('tr'):
            company = self.parse_company_row(row)
            if company:
                company_key = f"{company.name}_{company.stock_code}"
                if company_key not in seen_companies:
                    seen_companies.add(company_key)
                    yield company
    
    async def fetch_company_details_async(self, company: CompanyData) -> CompanyData:
        """会社の詳細情報を非同期で取得"""
        if not company.detail_url or company.detail_url in self._detail_cache:
            if company.detail_url in self._detail_cache:
                cached = self._detail_cache[company.detail_url]
                company.per = cached['PER']
                company.pbr = cached['PBR']
                company.dividend_yield = cached['配当利回り']
            return company
        
        try:
            html_content = await self.fetch_page_async(company.detail_url)
            if html_content:
                details = self._extract_details_from_html(html_content)
                self._detail_cache[company.detail_url] = details
                company.per = details['PER']
                company.pbr = details['PBR']
                company.dividend_yield = details['配当利回り']
        except Exception as e:
            logger.error(f"Error fetching details for {company.name}: {e}")
        
        return company
    
    @lru_cache(maxsize=CACHE_SIZE)
    def _extract_details_from_html(self, html_content: str) -> Dict[str, str]:
        """HTMLから詳細情報を抽出（キャッシュ付き）"""
        result = {'PER': 'N/A', 'PBR': 'N/A', '配当利回り': 'N/A'}
        soup = BeautifulSoup(html_content, 'lxml')
        
        # DL要素から抽出（最適化済み）
        for dl in soup.find_all('dl'):
            dt = dl.find('dt')
            dd = dl.find('dd')
            
            if dt and dd:
                label_text = dt.get_text(strip=True)
                value_elem = dd.find('p')
                
                if value_elem:
                    value_text = value_elem.get_text(strip=True)
                    value_match = NUMBER_CLEAN_PATTERN.search(value_text.replace(',', ''))
                    
                    if value_match:
                        try:
                            num_value = float(value_match.group(1))
                            
                            if 'PER' in label_text and result['PER'] == 'N/A':
                                result['PER'] = str(num_value)
                            elif 'PBR' in label_text and result['PBR'] == 'N/A':
                                result['PBR'] = str(num_value)
                            elif ('配当利回り' in label_text or '利回り' in label_text) and result['配当利回り'] == 'N/A':
                                result['配当利回り'] = f"{num_value}%"
                        except ValueError:
                            pass
        
        return result
    
    async def process_pages_parallel(self, page_urls: List[str]) -> List[CompanyData]:
        """複数ページを並列処理"""
        tasks = []
        for url in page_urls:
            task = asyncio.create_task(self.fetch_page_async(url))
            tasks.append((url, task))
        
        all_companies = []
        seen_companies = set()
        
        # 非同期でページを取得
        for url, task in tasks:
            html_content = await task
            if html_content:
                for company in self.extract_earnings_data_batch(html_content):
                    company_key = f"{company.name}_{company.stock_code}"
                    if company_key not in seen_companies:
                        seen_companies.add(company_key)
                        all_companies.append(company)
                        
        logger.info(f"Extracted {len(all_companies)} companies from {len(page_urls)} pages")
        return all_companies
    
    async def fetch_all_details_parallel(self, companies: List[CompanyData], batch_size: int = BATCH_SIZE):
        """会社詳細情報をバッチで並列取得"""
        total = len(companies)
        
        # バッチ処理で負荷を制御
        for i in range(0, total, batch_size):
            batch = companies[i:i+batch_size]
            tasks = [self.fetch_company_details_async(company) for company in batch]
            
            # セマフォで同時実行数を制限
            async with asyncio.Semaphore(MAX_CONCURRENT_REQUESTS):
                await asyncio.gather(*tasks, return_exceptions=True)
            
            logger.info(f"Processed {min(i+batch_size, total)}/{total} company details")
            
            # レート制限
            if i + batch_size < total:
                await asyncio.sleep(RATE_LIMIT_DELAY)
    
    def get_all_page_urls(self, first_page_html: str, base_url: str) -> List[str]:
        """ページネーションURLを効率的に生成"""
        soup = BeautifulSoup(first_page_html, 'lxml')
        page_urls = [base_url]
        
        page_links = soup.find_all('a', href=PAGE_LINK_PATTERN)
        page_numbers = set()
        
        for link in page_links:
            href = link.get('href', '')
            page_match = PAGE_NUMBER_PATTERN.search(href)
            if page_match:
                page_numbers.add(int(page_match.group(1)))
        
        if page_numbers:
            max_page = max(page_numbers)
            logger.info(f"Found {max_page} pages to process")
            
            for page_num in range(2, max_page + 1):
                separator = '&' if '?' in base_url else '?'
                if '#stocklist' in base_url:
                    page_url = base_url.replace('#stocklist', f'{separator}page={page_num}#stocklist')
                else:
                    page_url = f"{base_url}{separator}page={page_num}"
                
                if page_url.startswith('/'):
                    page_url = f"https://kabuyoho.jp{page_url}"
                
                page_urls.append(page_url)
        
        return page_urls


def save_data_streaming(data: List[CompanyData], csv_file: str, json_file: str):
    """データをストリーミング形式で保存（メモリ効率向上）"""
    # CSV保存（ストリーミング）
    with open(csv_file, 'w', newline='', encoding='utf-8-sig') as f:
        if data:
            fieldnames = data[0].to_dict().keys()
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for company in data:
                writer.writerow(company.to_dict())
    
    logger.info(f"Saved CSV to {csv_file}")
    
    # JSON保存（ストリーミング）
    with open(json_file, 'w', encoding='utf-8') as f:
        json_data = [company.to_dict() for company in data]
        json.dump(json_data, f, ensure_ascii=False, indent=2)
    
    logger.info(f"Saved JSON to {json_file}")


async def main():
    """メイン処理（非同期版）"""
    start_time = time.time()
    
    print("=" * 60)
    print("最適化版：決算カレンダー データ抽出スクリプト")
    print("=" * 60)
    
    base_url = "https://kabuyoho.jp/calender?lst=20251119&ym=202511&sett=&publ=off#stocklist"
    
    async with OptimizedEarningsScheduleScraper() as scraper:
        # 最初のページを取得
        print("\n最初のページを取得中...")
        first_page_html = await scraper.fetch_page_async(base_url)
        
        if not first_page_html:
            print("ページの取得に失敗しました")
            return
        
        # すべてのページURLを取得
        print("\nページネーションを確認中...")
        page_urls = scraper.get_all_page_urls(first_page_html, base_url)
        print(f"合計 {len(page_urls)} ページを並列処理します")
        
        # すべてのページからデータを並列抽出
        companies = await scraper.process_pages_parallel(page_urls)
        
        if not companies:
            print("\nデータが見つかりませんでした")
            return
        
        print(f"\n全ページから合計 {len(companies)} 件のデータを抽出しました")
        
        # 詳細情報を並列取得
        print("\n各会社の詳細情報を並列取得中...")
        await scraper.fetch_all_details_parallel(companies)
        
        # 配当利回りでソート
        def get_dividend_yield(company: CompanyData) -> float:
            if company.dividend_yield == 'N/A':
                return -1
            match = NUMBER_CLEAN_PATTERN.search(str(company.dividend_yield).replace(',', ''))
            if match:
                try:
                    return float(match.group(1))
                except ValueError:
                    return -1
            return -1
        
        companies.sort(key=get_dividend_yield, reverse=True)
        
        # 結果を表示
        print("\n" + "=" * 80)
        print("配当利回りの高い順（上位20件）")
        print("=" * 80)
        print(f"{'会社名':<25} {'銘柄コード':<10} {'進捗率':<10} {'PER':<10} {'PBR':<10} {'配当利回り':<10}")
        print("=" * 80)
        
        for company in companies[:20]:
            data = company.to_dict()
            print(f"{data['会社名']:<25} {data['銘柄コード']:<10} {data['進捗率']:<10} "
                  f"{data['PER']:<10} {data['PBR']:<10} {data['配当利回り']:<10}")
        
        if len(companies) > 20:
            print(f"... 他 {len(companies) - 20} 件")
        
        # ファイルに保存
        save_data_streaming(companies, "earnings_schedule.csv", "earnings_schedule.json")
        
    # 実行時間の表示
    elapsed_time = time.time() - start_time
    print(f"\n{'=' * 60}")
    print(f"処理完了 - 実行時間: {elapsed_time:.2f}秒")
    print(f"パフォーマンス: {len(companies) / elapsed_time:.1f} 件/秒")
    print("=" * 60)


if __name__ == "__main__":
    # Windowsイベントループの問題を回避
    import sys
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    # 非同期メイン関数を実行
    asyncio.run(main())