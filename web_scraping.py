"""
ウェブスクレイピング用のPythonコード
requests と BeautifulSoup を使用してウェブページからデータを取得します
"""

import requests
from bs4 import BeautifulSoup
import csv
import json
from typing import List, Dict, Optional
import time


class WebScraper:
    """ウェブスクレイピング用のクラス"""
    
    def __init__(self, headers: Optional[Dict] = None):
        """
        初期化
        
        Args:
            headers: HTTPリクエストヘッダー（デフォルトでは一般的なブラウザヘッダーを使用）
        """
        self.headers = headers or {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
    
    def fetch_page(self, url: str, timeout: int = 10) -> Optional[BeautifulSoup]:
        """
        指定されたURLからHTMLを取得してBeautifulSoupオブジェクトを返す
        
        Args:
            url: スクレイピング対象のURL
            timeout: リクエストのタイムアウト時間（秒）
        
        Returns:
            BeautifulSoupオブジェクト、エラー時はNone
        """
        try:
            print(f"ページを取得中: {url}")
            response = self.session.get(url, timeout=timeout)
            response.raise_for_status()
            response.encoding = response.apparent_encoding
            soup = BeautifulSoup(response.text, 'html.parser')
            print("ページの取得に成功しました")
            return soup
        except requests.exceptions.RequestException as e:
            print(f"エラーが発生しました: {e}")
            return None
    
    def extract_links(self, soup: BeautifulSoup, base_url: str = "") -> List[str]:
        """
        ページ内のすべてのリンクを抽出
        
        Args:
            soup: BeautifulSoupオブジェクト
            base_url: 相対URLを絶対URLに変換するためのベースURL
        
        Returns:
            リンクのリスト
        """
        links = []
        for link in soup.find_all('a', href=True):
            href = link['href']
            if href.startswith('http'):
                links.append(href)
            elif base_url:
                links.append(f"{base_url.rstrip('/')}/{href.lstrip('/')}")
        return links
    
    def extract_text(self, soup: BeautifulSoup, selector: str = None) -> str:
        """
        ページのテキストを抽出
        
        Args:
            soup: BeautifulSoupオブジェクト
            selector: CSSセレクター（指定された場合、その要素のテキストのみ抽出）
        
        Returns:
            抽出されたテキスト
        """
        if selector:
            elements = soup.select(selector)
            return ' '.join([elem.get_text(strip=True) for elem in elements])
        return soup.get_text(strip=True)
    
    def extract_data(self, soup: BeautifulSoup, selectors: Dict[str, str]) -> Dict:
        """
        指定されたセレクターに基づいてデータを抽出
        
        Args:
            soup: BeautifulSoupオブジェクト
            selectors: データ名とCSSセレクターの辞書
        
        Returns:
            抽出されたデータの辞書
        """
        data = {}
        for key, selector in selectors.items():
            elements = soup.select(selector)
            if elements:
                data[key] = [elem.get_text(strip=True) for elem in elements]
            else:
                data[key] = []
        return data
    
    def save_to_csv(self, data: List[Dict], filename: str):
        """
        データをCSVファイルに保存
        
        Args:
            data: 保存するデータのリスト（辞書のリスト）
            filename: 保存先のファイル名
        """
        if not data:
            print("保存するデータがありません")
            return
        
        with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)
        print(f"データを {filename} に保存しました")
    
    def save_to_json(self, data: any, filename: str):
        """
        データをJSONファイルに保存
        
        Args:
            data: 保存するデータ
            filename: 保存先のファイル名
        """
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"データを {filename} に保存しました")


def example_usage():
    """使用例"""
    scraper = WebScraper()
    
    # 例: ニュースサイトからタイトルを取得
    url = "https://example.com"
    soup = scraper.fetch_page(url)
    
    if soup:
        # タイトルを取得
        title = soup.find('title')
        if title:
            print(f"ページタイトル: {title.get_text()}")
        
        # すべてのリンクを取得
        links = scraper.extract_links(soup, url)
        print(f"見つかったリンク数: {len(links)}")
        
        # 特定のセレクターでデータを抽出（例）
        # selectors = {
        #     'titles': 'h1, h2, h3',
        #     'paragraphs': 'p'
        # }
        # data = scraper.extract_data(soup, selectors)
        # print(data)
        
        # データを保存
        # scraper.save_to_json({'title': title.get_text(), 'links': links}, 'output.json')


if __name__ == "__main__":
    # 使用例を実行
    example_usage()
    
    # カスタムスクレイピングの例
    print("\n=== カスタムスクレイピング例 ===")
    scraper = WebScraper()
    
    # ここにスクレイピングしたいURLを指定してください
    target_url = input("スクレイピングしたいURLを入力してください（Enterキーでスキップ）: ").strip()
    
    if target_url:
        soup = scraper.fetch_page(target_url)
        if soup:
            # ページの基本情報を表示
            title_tag = soup.find('title')
            if title_tag:
                print(f"\nページタイトル: {title_tag.get_text()}")
            
            # メタディスクリプションを取得
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            if meta_desc:
                print(f"説明: {meta_desc.get('content', '')}")
            
            # 見出しを取得
            headings = soup.find_all(['h1', 'h2', 'h3'])
            if headings:
                print(f"\n見出し ({len(headings)}個):")
                for heading in headings[:10]:  # 最初の10個を表示
                    print(f"  - {heading.get_text(strip=True)}")
            
            # リンクを取得
            links = scraper.extract_links(soup, target_url)
            print(f"\nリンク数: {len(links)}")
            if links:
                print("最初の5つのリンク:")
                for link in links[:5]:
                    print(f"  - {link}")

