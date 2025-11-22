"""
最適化版：汎用ウェブスクレイピング用のPythonコード
パフォーマンスとメモリ効率を改善したバージョン
"""

import asyncio
import aiohttp
from bs4 import BeautifulSoup
import csv
import json
from typing import List, Dict, Optional, AsyncGenerator, Any
import time
from functools import lru_cache
import logging
from urllib.parse import urljoin, urlparse
import re

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# パフォーマンス設定
MAX_CONCURRENT_REQUESTS = 20
CACHE_SIZE = 500
REQUEST_TIMEOUT = 30
CHUNK_SIZE = 1024 * 1024  # 1MB chunks for streaming


class OptimizedWebScraper:
    """パフォーマンス最適化版ウェブスクレイピングクラス"""
    
    def __init__(self, headers: Optional[Dict] = None, 
                 max_concurrent: int = MAX_CONCURRENT_REQUESTS):
        """
        初期化
        
        Args:
            headers: HTTPリクエストヘッダー
            max_concurrent: 最大同時接続数
        """
        self.headers = headers or {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        }
        self.max_concurrent = max_concurrent
        self.session = None
        self._url_cache = {}
        self._soup_cache = {}
        self._semaphore = None
    
    async def __aenter__(self):
        """非同期コンテキストマネージャー開始"""
        connector = aiohttp.TCPConnector(
            limit=self.max_concurrent,
            limit_per_host=self.max_concurrent,
            ttl_dns_cache=300,
            enable_cleanup_closed=True,
            force_close=False,
            keepalive_timeout=30
        )
        
        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
        self.session = aiohttp.ClientSession(
            headers=self.headers,
            connector=connector,
            timeout=timeout,
            trust_env=True,
            cookie_jar=aiohttp.CookieJar()
        )
        self._semaphore = asyncio.Semaphore(self.max_concurrent)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """非同期コンテキストマネージャー終了"""
        if self.session:
            await self.session.close()
    
    async def fetch_page(self, url: str, use_cache: bool = True) -> Optional[str]:
        """
        指定されたURLからHTMLを非同期取得
        
        Args:
            url: スクレイピング対象のURL
            use_cache: キャッシュを使用するか
        
        Returns:
            HTMLコンテンツ、エラー時はNone
        """
        if use_cache and url in self._url_cache:
            logger.debug(f"Cache hit for {url}")
            return self._url_cache[url]
        
        try:
            async with self._semaphore:
                async with self.session.get(url) as response:
                    response.raise_for_status()
                    content = await response.text()
                    
                    if use_cache:
                        self._url_cache[url] = content
                    
                    logger.info(f"Successfully fetched: {url}")
                    return content
                    
        except asyncio.TimeoutError:
            logger.error(f"Timeout fetching {url}")
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
        
        return None
    
    async def fetch_pages_parallel(self, urls: List[str]) -> Dict[str, Optional[str]]:
        """
        複数URLを並列取得
        
        Args:
            urls: URLリスト
        
        Returns:
            URL -> HTMLコンテンツの辞書
        """
        tasks = {url: asyncio.create_task(self.fetch_page(url)) for url in urls}
        results = {}
        
        for url, task in tasks.items():
            try:
                results[url] = await task
            except Exception as e:
                logger.error(f"Failed to fetch {url}: {e}")
                results[url] = None
        
        return results
    
    async def fetch_with_retry(self, url: str, max_retries: int = 3, 
                              backoff: float = 1.0) -> Optional[str]:
        """
        リトライ機能付きフェッチ
        
        Args:
            url: URL
            max_retries: 最大リトライ回数
            backoff: リトライ間隔の係数
        
        Returns:
            HTMLコンテンツ
        """
        for attempt in range(max_retries):
            content = await self.fetch_page(url, use_cache=False)
            if content:
                return content
            
            if attempt < max_retries - 1:
                wait_time = backoff * (2 ** attempt)
                logger.info(f"Retrying {url} in {wait_time} seconds...")
                await asyncio.sleep(wait_time)
        
        return None
    
    @lru_cache(maxsize=CACHE_SIZE)
    def parse_html(self, html: str, parser: str = 'lxml') -> BeautifulSoup:
        """
        HTMLをパース（キャッシュ付き）
        
        Args:
            html: HTMLコンテンツ
            parser: パーサー種別
        
        Returns:
            BeautifulSoupオブジェクト
        """
        return BeautifulSoup(html, parser)
    
    async def extract_links_async(self, url: str, base_url: str = None) -> List[str]:
        """
        ページ内のリンクを非同期抽出
        
        Args:
            url: ページURL
            base_url: 相対URLを絶対URLに変換するためのベースURL
        
        Returns:
            リンクのリスト
        """
        html = await self.fetch_page(url)
        if not html:
            return []
        
        soup = self.parse_html(html)
        links = []
        base_url = base_url or url
        
        for link in soup.find_all('a', href=True):
            href = link['href']
            absolute_url = urljoin(base_url, href)
            links.append(absolute_url)
        
        return links
    
    async def scrape_with_selector(self, url: str, selector: str) -> List[str]:
        """
        CSSセレクターを使用したスクレイピング
        
        Args:
            url: URL
            selector: CSSセレクター
        
        Returns:
            抽出されたテキストのリスト
        """
        html = await self.fetch_page(url)
        if not html:
            return []
        
        soup = self.parse_html(html)
        elements = soup.select(selector)
        return [elem.get_text(strip=True) for elem in elements]
    
    async def scrape_batch(self, urls: List[str], selectors: Dict[str, str]) -> Dict[str, Dict]:
        """
        複数URLをバッチでスクレイピング
        
        Args:
            urls: URLリスト
            selectors: セレクター辞書
        
        Returns:
            URL -> 抽出データの辞書
        """
        html_contents = await self.fetch_pages_parallel(urls)
        results = {}
        
        for url, html in html_contents.items():
            if html:
                soup = self.parse_html(html)
                data = {}
                
                for key, selector in selectors.items():
                    elements = soup.select(selector)
                    data[key] = [elem.get_text(strip=True) for elem in elements]
                
                results[url] = data
            else:
                results[url] = None
        
        return results
    
    async def stream_large_file(self, url: str, chunk_size: int = CHUNK_SIZE) -> AsyncGenerator[bytes, None]:
        """
        大きなファイルをストリーミング取得
        
        Args:
            url: ファイルURL
            chunk_size: チャンクサイズ
        
        Yields:
            バイトチャンク
        """
        async with self._semaphore:
            async with self.session.get(url) as response:
                response.raise_for_status()
                
                async for chunk in response.content.iter_chunked(chunk_size):
                    yield chunk
    
    async def download_file(self, url: str, filename: str, 
                          progress_callback: Optional[callable] = None):
        """
        ファイルをダウンロード
        
        Args:
            url: ファイルURL
            filename: 保存先ファイル名
            progress_callback: 進捗コールバック関数
        """
        total_size = 0
        
        with open(filename, 'wb') as f:
            async for chunk in self.stream_large_file(url):
                f.write(chunk)
                total_size += len(chunk)
                
                if progress_callback:
                    progress_callback(total_size)
        
        logger.info(f"Downloaded {total_size} bytes to {filename}")
    
    def save_to_csv_streaming(self, data: List[Dict], filename: str):
        """
        データをCSVにストリーミング保存
        
        Args:
            data: データリスト
            filename: ファイル名
        """
        if not data:
            logger.warning("No data to save")
            return
        
        with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=data[0].keys())
            writer.writeheader()
            
            for row in data:
                writer.writerow(row)
        
        logger.info(f"Saved {len(data)} records to {filename}")
    
    def save_to_json_streaming(self, data: Any, filename: str):
        """
        データをJSONにストリーミング保存
        
        Args:
            data: データ
            filename: ファイル名
        """
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Saved JSON to {filename}")


class SitemapCrawler:
    """サイトマップクローラー（最適化版）"""
    
    def __init__(self, scraper: OptimizedWebScraper):
        self.scraper = scraper
        self.visited_urls = set()
        self.domain = None
    
    async def crawl_site(self, start_url: str, max_pages: int = 100) -> List[str]:
        """
        サイトをクロール
        
        Args:
            start_url: 開始URL
            max_pages: 最大ページ数
        
        Returns:
            訪問したURLのリスト
        """
        self.domain = urlparse(start_url).netloc
        urls_to_visit = [start_url]
        
        while urls_to_visit and len(self.visited_urls) < max_pages:
            batch = urls_to_visit[:10]  # バッチ処理
            urls_to_visit = urls_to_visit[10:]
            
            for url in batch:
                if url in self.visited_urls:
                    continue
                
                self.visited_urls.add(url)
                links = await self.scraper.extract_links_async(url)
                
                # 同じドメインのリンクのみ追加
                for link in links:
                    if urlparse(link).netloc == self.domain and link not in self.visited_urls:
                        urls_to_visit.append(link)
        
        return list(self.visited_urls)


async def example_usage():
    """使用例（非同期版）"""
    async with OptimizedWebScraper() as scraper:
        # 単一ページの取得
        url = "https://example.com"
        html = await scraper.fetch_page(url)
        
        if html:
            soup = scraper.parse_html(html)
            title = soup.find('title')
            if title:
                print(f"ページタイトル: {title.get_text()}")
        
        # 複数ページの並列取得
        urls = [
            "https://example.com/page1",
            "https://example.com/page2",
            "https://example.com/page3"
        ]
        
        results = await scraper.fetch_pages_parallel(urls)
        for url, content in results.items():
            print(f"{url}: {'成功' if content else '失敗'}")
        
        # セレクターでデータ抽出
        data = await scraper.scrape_with_selector(url, "h1, h2, h3")
        print(f"見出し: {data[:5]}")  # 最初の5件
        
        # バッチスクレイピング
        selectors = {
            'titles': 'h1, h2, h3',
            'paragraphs': 'p',
            'links': 'a[href]'
        }
        
        batch_results = await scraper.scrape_batch(urls, selectors)
        for url, data in batch_results.items():
            if data:
                print(f"{url}: {len(data.get('links', []))} links found")


def main():
    """メイン関数"""
    import sys
    
    # Windowsイベントループの問題を回避
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    # 非同期処理を実行
    asyncio.run(example_usage())


if __name__ == "__main__":
    main()