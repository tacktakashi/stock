"""
決算カレンダーから会社名と進捗率を抽出するスクリプト
https://kabuyoho.jp/calender の決算発表予定表からデータを取得
"""

import requests
from bs4 import BeautifulSoup
import csv
import json
import re
from typing import List, Dict, Optional
from urllib.parse import urljoin


class EarningsScheduleScraper:
    """決算カレンダー用のスクレイパー"""
    
    def __init__(self):
        """初期化"""
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ja,en-US;q=0.9,en;q=0.8',
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
    
    def fetch_page(self, url: str) -> Optional[BeautifulSoup]:
        """
        ページを取得
        
        Args:
            url: スクレイピング対象のURL
        
        Returns:
            BeautifulSoupオブジェクト、エラー時はNone
        """
        try:
            print(f"ページを取得中: {url}")
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            # エンコーディングを自動検出
            response.encoding = response.apparent_encoding or 'utf-8'
            soup = BeautifulSoup(response.text, 'html.parser')
            print("ページの取得に成功しました")
            return soup
        except requests.exceptions.RequestException as e:
            print(f"エラーが発生しました: {e}")
            return None
    
    def extract_earnings_data(self, soup: BeautifulSoup) -> List[Dict]:
        """
        決算表から会社名と進捗率を抽出
        
        Args:
            soup: BeautifulSoupオブジェクト
        
        Returns:
            会社名と進捗率のリスト
        """
        results = []
        seen_companies = set()  # 重複チェック用
        
        # すべてのtr要素を探す
        rows = soup.find_all('tr')
        
        for row in rows:
            # 会社名と銘柄コードを取得（リンクから）
            company_link = row.find('a', href=re.compile(r'/reportTop\?bcode='))
            if not company_link:
                continue
            
            # 会社名と銘柄コードを抽出
            full_text = company_link.get_text(strip=True)
            href = company_link.get('href', '')
            
            # 銘柄コードをhrefから取得
            stock_code_match = re.search(r'bcode=(\d+)', href)
            stock_code = stock_code_match.group(1) if stock_code_match else ''
            
            # 会社名を抽出（テキストから銘柄コードを除去）
            # パターン1: "会社名 1234" の形式
            parts = full_text.split()
            if len(parts) >= 2 and parts[-1].isdigit():
                company_name = ' '.join(parts[:-1])
                if not stock_code:
                    stock_code = parts[-1]
            else:
                company_name = full_text
            
            # 重複チェック
            company_key = f"{company_name}_{stock_code}"
            if company_key in seen_companies:
                continue
            seen_companies.add(company_key)
            
            # 進捗率を探す（行内のすべてのtd要素を確認）
            cells = row.find_all('td')
            progress_rate = None
            
            # 各セルから進捗率を探す（右から左へ、最後の数値.数値パターンを優先）
            for i in range(len(cells) - 1, -1, -1):  # 右から左へ検索
                cell = cells[i]
                cell_text = cell.get_text(strip=True)
                
                # パターン1: "59.4" のような数値のみ（進捗率の可能性が高い）
                if re.match(r'^\d+\.\d+$', cell_text):
                    try:
                        rate = float(cell_text)
                        # 進捗率の妥当な範囲（0-200%）
                        if 0 <= rate <= 200:
                            progress_rate = rate
                            break
                    except ValueError:
                        continue
                
                # パターン2: "59.4%" のようなパーセンテージ
                elif re.match(r'^\d+\.\d+%$', cell_text):
                    try:
                        rate = float(cell_text.replace('%', ''))
                        if 0 <= rate <= 200:
                            progress_rate = rate
                            break
                    except ValueError:
                        continue
            
            # 右から検索で見つからなかった場合、左から検索
            if progress_rate is None:
                for cell in cells:
                    cell_text = cell.get_text(strip=True)
                    # テキスト内に数値.数値のパターンを含む場合
                    match = re.search(r'(\d+\.\d+)\s*%?', cell_text)
                    if match:
                        try:
                            rate = float(match.group(1))
                            # 進捗率の妥当な範囲（0-200%）
                            if 0 <= rate <= 200:
                                # より右側のセルにある進捗率を優先
                                if progress_rate is None:
                                    progress_rate = rate
                                elif cells.index(cell) > [i for i, c in enumerate(cells) if progress_rate and str(progress_rate) in c.get_text()][0] if any(progress_rate and str(progress_rate) in c.get_text() for c in cells) else -1:
                                    progress_rate = rate
                        except (ValueError, IndexError):
                            continue
            
            # データを追加（詳細ページのURLも保存）
            if company_name:
                # 詳細ページのURLを構築
                detail_url = None
                if href:
                    if href.startswith('/'):
                        detail_url = f"https://kabuyoho.jp{href}"
                    elif href.startswith('http'):
                        detail_url = href
                    else:
                        detail_url = f"https://kabuyoho.jp/{href}"
                
                result = {
                    '会社名': company_name,
                    '銘柄コード': stock_code,
                    '進捗率': f"{progress_rate:.1f}%" if progress_rate is not None else "N/A",
                    '詳細ページURL': detail_url or ''
                }
                results.append(result)
        
        return results
    
    def fetch_page_silent(self, url: str) -> Optional[BeautifulSoup]:
        """
        ページを取得（メッセージを表示しない）
        
        Args:
            url: スクレイピング対象のURL
        
        Returns:
            BeautifulSoupオブジェクト、エラー時はNone
        """
        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or 'utf-8'
            soup = BeautifulSoup(response.text, 'html.parser')
            return soup
        except requests.exceptions.RequestException:
            return None
    
    def extract_company_details(self, detail_url: str) -> Dict[str, str]:
        """
        会社の詳細ページからPER、PBR、配当利回りを抽出
        
        Args:
            detail_url: 会社の詳細ページURL
        
        Returns:
            PER、PBR、配当利回りの辞書
        """
        result = {
            'PER': 'N/A',
            'PBR': 'N/A',
            '配当利回り': 'N/A'
        }
        
        if not detail_url:
            return result
        
        try:
            soup = self.fetch_page_silent(detail_url)
            if not soup:
                return result
            
            # <dl>要素からPER、PBR、配当利回りを抽出
            # 構造: <dl><dt><p>PER</p></dt><dd><p>14.1<span>倍</span></p></dd></dl>
            dl_elements = soup.find_all('dl')
            for dl in dl_elements:
                dt = dl.find('dt')
                dd = dl.find('dd')
                
                if dt and dd:
                    label_text = dt.get_text(strip=True)
                    value_elem = dd.find('p')
                    
                    if value_elem:
                        value_text = value_elem.get_text(strip=True)
                        # 数値を抽出（「倍」「%」などの単位を除去）
                        value_match = re.search(r'([0-9,]+\.?\d*)', value_text.replace(',', ''))
                        
                        if value_match:
                            try:
                                num_value = float(value_match.group(1))
                                
                                # PERを探す
                                if 'PER' in label_text and result['PER'] == 'N/A':
                                    result['PER'] = str(num_value)
                                
                                # PBRを探す
                                if 'PBR' in label_text and result['PBR'] == 'N/A':
                                    result['PBR'] = str(num_value)
                                
                                # 配当利回りを探す
                                if ('配当利回り' in label_text or '利回り' in label_text) and result['配当利回り'] == 'N/A':
                                    result['配当利回り'] = f"{num_value}%"
                            except ValueError:
                                pass
            
            # <dl>要素で見つからなかった場合、テーブルから探す
            if result['PER'] == 'N/A' or result['PBR'] == 'N/A' or result['配当利回り'] == 'N/A':
                tables = soup.find_all('table')
                for table in tables:
                    rows = table.find_all('tr')
                    for row in rows:
                        cells = row.find_all(['td', 'th'])
                        if len(cells) >= 2:
                            label = cells[0].get_text(strip=True)
                            value = cells[1].get_text(strip=True)
                            
                            # PERを探す
                            if ('PER' in label or '株価収益率' in label) and result['PER'] == 'N/A':
                                value_clean = re.search(r'([0-9,]+\.?\d*)', value.replace(',', ''))
                                if value_clean:
                                    try:
                                        per_val = float(value_clean.group(1))
                                        if per_val > 0:
                                            result['PER'] = str(per_val)
                                    except ValueError:
                                        pass
                            
                            # PBRを探す
                            if ('PBR' in label or '株価純資産倍率' in label) and result['PBR'] == 'N/A':
                                value_clean = re.search(r'([0-9,]+\.?\d*)', value.replace(',', ''))
                                if value_clean:
                                    try:
                                        pbr_val = float(value_clean.group(1))
                                        if pbr_val > 0:
                                            result['PBR'] = str(pbr_val)
                                    except ValueError:
                                        pass
                            
                            # 配当利回りを探す
                            if ('配当利回り' in label or '利回り' in label) and result['配当利回り'] == 'N/A':
                                value_clean = re.search(r'([0-9,]+\.?\d*)', value.replace(',', ''))
                                if value_clean:
                                    try:
                                        div_val = float(value_clean.group(1))
                                        if div_val >= 0:
                                            result['配当利回り'] = f"{div_val}%"
                                    except ValueError:
                                        pass
            
            # それでも見つからなかった場合、テキストから探す
            if result['PER'] == 'N/A' or result['PBR'] == 'N/A' or result['配当利回り'] == 'N/A':
                page_text = soup.get_text()
                
                # PERを探す
                if result['PER'] == 'N/A':
                    per_patterns = [
                        r'PER[：:]\s*([0-9,]+\.?\d*)',
                        r'株価収益率[：:]\s*([0-9,]+\.?\d*)',
                    ]
                    for pattern in per_patterns:
                        match = re.search(pattern, page_text)
                        if match:
                            per_value = match.group(1).replace(',', '')
                            try:
                                per_val = float(per_value)
                                if per_val > 0:
                                    result['PER'] = str(per_val)
                                    break
                            except ValueError:
                                continue
                
                # PBRを探す
                if result['PBR'] == 'N/A':
                    pbr_patterns = [
                        r'PBR[：:]\s*([0-9,]+\.?\d*)',
                        r'株価純資産倍率[：:]\s*([0-9,]+\.?\d*)',
                    ]
                    for pattern in pbr_patterns:
                        match = re.search(pattern, page_text)
                        if match:
                            pbr_value = match.group(1).replace(',', '')
                            try:
                                pbr_val = float(pbr_value)
                                if pbr_val > 0:
                                    result['PBR'] = str(pbr_val)
                                    break
                            except ValueError:
                                continue
                
                # 配当利回りを探す
                if result['配当利回り'] == 'N/A':
                    dividend_patterns = [
                        r'配当利回り[：:]\s*([0-9,]+\.?\d*)\s*%',
                        r'利回り[：:]\s*([0-9,]+\.?\d*)\s*%',
                    ]
                    for pattern in dividend_patterns:
                        match = re.search(pattern, page_text)
                        if match:
                            div_value = match.group(1).replace(',', '')
                            try:
                                div_val = float(div_value)
                                if div_val >= 0:
                                    result['配当利回り'] = f"{div_val}%"
                                    break
                            except ValueError:
                                continue
            
        except Exception as e:
            print(f"  詳細ページの取得エラー ({detail_url}): {e}")
        
        return result
    
    def extract_52week_prices(self, stock_code: str) -> Dict[str, str]:
        """
        チャートページから52週高値・安値・現在値を抽出
        
        Args:
            stock_code: 銘柄コード
        
        Returns:
            52週高値・安値・現在値の辞書
        """
        result = {
            '52週高値': 'N/A',
            '52週安値': 'N/A',
            '現在値': 'N/A'
        }
        
        if not stock_code:
            return result
        
        try:
            chart_url = f"https://kabuyoho.jp/reportChart?bcode={stock_code}"
            soup = self.fetch_page_silent(chart_url)
            if not soup:
                return result
            
            # テーブルから52週高値・安値を探す
            tables = soup.find_all('table')
            for table in tables:
                rows = table.find_all('tr')
                for row in rows:
                    # th要素でラベルを探す
                    th = row.find('th')
                    if not th:
                        continue
                    
                    label = th.get_text(strip=True)
                    td = row.find('td')
                    
                    # 52週高値を探す
                    if '52週高値' in label and result['52週高値'] == 'N/A':
                        if td:
                            # span要素のクラス名で探す（week52_high）
                            high_span = td.find('span', class_=re.compile(r'week52_high'))
                            if high_span:
                                value_text = high_span.get_text(strip=True)
                                # カンマを除去して数値に変換
                                value_clean = value_text.replace(',', '')
                                try:
                                    high_val = float(value_clean)
                                    if high_val > 0:
                                        result['52週高値'] = str(high_val)
                                except ValueError:
                                    pass
                            else:
                                # span要素が見つからない場合、tdのテキストから抽出
                                value_text = td.get_text(strip=True)
                                value_clean = re.search(r'([0-9,]+\.?\d*)', value_text.replace(',', ''))
                                if value_clean:
                                    try:
                                        high_val = float(value_clean.group(1))
                                        if high_val > 0:
                                            result['52週高値'] = str(high_val)
                                    except ValueError:
                                        pass
                    
                    # 52週安値を探す
                    if '52週安値' in label and result['52週安値'] == 'N/A':
                        if td:
                            # span要素のクラス名で探す（week52_low）
                            low_span = td.find('span', class_=re.compile(r'week52_low'))
                            if low_span:
                                value_text = low_span.get_text(strip=True)
                                # カンマを除去して数値に変換
                                value_clean = value_text.replace(',', '')
                                try:
                                    low_val = float(value_clean)
                                    if low_val > 0:
                                        result['52週安値'] = str(low_val)
                                except ValueError:
                                    pass
                            else:
                                # span要素が見つからない場合、tdのテキストから抽出
                                value_text = td.get_text(strip=True)
                                value_clean = re.search(r'([0-9,]+\.?\d*)', value_text.replace(',', ''))
                                if value_clean:
                                    try:
                                        low_val = float(value_clean.group(1))
                                        if low_val > 0:
                                            result['52週安値'] = str(low_val)
                                    except ValueError:
                                        pass
                    
                    # 現在値を探す
                    if '現在値' in label and result['現在値'] == 'N/A':
                        if td:
                            # span要素のクラス名で探す（close_price）
                            current_span = td.find('span', class_=re.compile(r'close_price'))
                            if current_span:
                                value_text = current_span.get_text(strip=True)
                                # カンマを除去して数値に変換
                                value_clean = value_text.replace(',', '')
                                try:
                                    current_val = float(value_clean)
                                    if current_val > 0:
                                        result['現在値'] = str(current_val)
                                except ValueError:
                                    pass
                            else:
                                # span要素が見つからない場合、tdのテキストから抽出
                                value_text = td.get_text(strip=True)
                                value_clean = re.search(r'([0-9,]+\.?\d*)', value_text.replace(',', ''))
                                if value_clean:
                                    try:
                                        current_val = float(value_clean.group(1))
                                        if current_val > 0:
                                            result['現在値'] = str(current_val)
                                    except ValueError:
                                        pass
            
            # テーブルで見つからなかった場合、テキストから探す
            if result['52週高値'] == 'N/A' or result['52週安値'] == 'N/A' or result['現在値'] == 'N/A':
                page_text = soup.get_text()
                
                # 52週高値を探す
                if result['52週高値'] == 'N/A':
                    high_patterns = [
                        r'52週高値[：:\s]*([0-9,]+\.?\d*)',
                        r'52週.*高値[：:\s]*([0-9,]+\.?\d*)',
                    ]
                    for pattern in high_patterns:
                        match = re.search(pattern, page_text)
                        if match:
                            high_value = match.group(1).replace(',', '')
                            try:
                                high_val = float(high_value)
                                if high_val > 0:
                                    result['52週高値'] = str(high_val)
                                    break
                            except ValueError:
                                continue
                
                # 52週安値を探す
                if result['52週安値'] == 'N/A':
                    low_patterns = [
                        r'52週安値[：:\s]*([0-9,]+\.?\d*)',
                        r'52週.*安値[：:\s]*([0-9,]+\.?\d*)',
                    ]
                    for pattern in low_patterns:
                        match = re.search(pattern, page_text)
                        if match:
                            low_value = match.group(1).replace(',', '')
                            try:
                                low_val = float(low_value)
                                if low_val > 0:
                                    result['52週安値'] = str(low_val)
                                    break
                            except ValueError:
                                continue
                
                # 現在値を探す
                if result['現在値'] == 'N/A':
                    current_patterns = [
                        r'現在値[：:\s]*([0-9,]+\.?\d*)',
                    ]
                    for pattern in current_patterns:
                        match = re.search(pattern, page_text)
                        if match:
                            current_value = match.group(1).replace(',', '')
                            try:
                                current_val = float(current_value)
                                if current_val > 0:
                                    result['現在値'] = str(current_val)
                                    break
                            except ValueError:
                                continue
            
        except Exception as e:
            print(f"  52週高値・安値の取得エラー (銘柄コード: {stock_code}): {e}")
        
        return result
    
    def save_to_csv(self, data: List[Dict], filename: str):
        """CSVファイルに保存"""
        if not data:
            print("保存するデータがありません")
            return
        
        with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)
        print(f"データを {filename} に保存しました")
    
    def save_to_json(self, data: List[Dict], filename: str):
        """JSONファイルに保存"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"データを {filename} に保存しました")
    
    def get_all_page_urls(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """
        ページネーションリンクからすべてのページURLを取得
        
        Args:
            soup: BeautifulSoupオブジェクト
            base_url: ベースURL
        
        Returns:
            すべてのページURLのリスト
        """
        page_urls = [base_url]  # 最初のページを含める
        
        # ページネーションリンクを探す（/calender?lst=...&page=数字#stocklist の形式）
        # リンクのテキストが数字のものを探す
        page_links = soup.find_all('a', href=re.compile(r'/calender\?.*page=\d+'))
        
        # ページ番号を抽出（hrefとテキストの両方から）
        page_numbers = set()
        base_domain = "https://kabuyoho.jp"
        
        for link in page_links:
            href = link.get('href', '')
            link_text = link.get_text(strip=True)
            
            # hrefからページ番号を抽出
            page_match = re.search(r'page=(\d+)', href)
            if page_match:
                page_num = int(page_match.group(1))
                page_numbers.add(page_num)
            # テキストが数字の場合も確認
            elif link_text.isdigit():
                page_num = int(link_text)
                # hrefにpageパラメータがあるか確認
                if 'page=' in href:
                    page_numbers.add(page_num)
        
        # ベースURLからページ番号を抽出
        base_match = re.search(r'page=(\d+)', base_url)
        if base_match:
            base_page = int(base_match.group(1))
        else:
            base_page = 1
            page_numbers.add(1)  # 最初のページも含める
        
        if page_numbers:
            max_page = max(page_numbers)
            print(f"最大ページ数: {max_page}")
            
            # すべてのページのURLを生成
            for page_num in range(1, max_page + 1):
                if page_num == 1:
                    # 1ページ目はベースURLを使用（pageパラメータなし）
                    if base_url not in page_urls:
                        page_urls.append(base_url)
                    continue
                
                # 2ページ目以降はpageパラメータを追加
                # ベースURLにpageパラメータを追加
                separator = '&' if '?' in base_url else '?'
                # #stocklistの前にpageパラメータを挿入
                if '#stocklist' in base_url:
                    page_url = base_url.replace('#stocklist', f'{separator}page={page_num}#stocklist')
                else:
                    page_url = f"{base_url}{separator}page={page_num}"
                
                # 相対URLの場合は絶対URLに変換
                if page_url.startswith('/'):
                    page_url = base_domain + page_url
                
                if page_url not in page_urls:
                    page_urls.append(page_url)
        
        # ページ番号でソート
        def get_page_number(url):
            match = re.search(r'page=(\d+)', url)
            return int(match.group(1)) if match else 0
        
        return sorted(set(page_urls), key=get_page_number)


def main():
    """メイン処理"""
    import sys
    import time
    
    try:
        print("=" * 60)
        print("決算カレンダー データ抽出スクリプト（複数ページ対応）")
        print("=" * 60)
        
        base_url = "https://kabuyoho.jp/calender?lst=20251125&ym=202511&sett=&publ=off#stocklist"
        
        scraper = EarningsScheduleScraper()
        
        # 最初のページを取得
        print(f"\n最初のページを取得中...")
        soup = scraper.fetch_page(base_url)
        
        if not soup:
            print("ページの取得に失敗しました")
            return
        
        # すべてのページURLを取得
        print("\nページネーションを確認中...")
        page_urls = scraper.get_all_page_urls(soup, base_url)
        print(f"合計 {len(page_urls)} ページを処理します")
        
        # すべてのページからデータを抽出
        all_data = []
        seen_companies = set()  # 全ページを通して重複チェック
        
        for page_num, url in enumerate(page_urls, 1):
            print(f"\n--- ページ {page_num}/{len(page_urls)} を処理中 ---")
            
            if page_num == 1:
                # 最初のページは既に取得済み
                page_soup = soup
            else:
                # 他のページを取得
                page_soup = scraper.fetch_page(url)
                if not page_soup:
                    print(f"ページ {page_num} の取得に失敗しました。スキップします。")
                    continue
                # サーバー負荷を考慮して少し待機
                time.sleep(1)
            
            # データを抽出
            page_data = scraper.extract_earnings_data(page_soup)
            
            # 新規データ数を計算（追加前に）
            new_count = 0
            for item in page_data:
                company_key = f"{item['会社名']}_{item['銘柄コード']}"
                if company_key not in seen_companies:
                    all_data.append(item)
                    seen_companies.add(company_key)
                    new_count += 1
            
            print(f"ページ {page_num} から {len(page_data)} 件のデータを抽出しました（新規: {new_count} 件）")
        
        if not all_data:
            print("\nデータが見つかりませんでした。HTMLの構造を確認します...")
            # デバッグ用：HTMLの一部を表示
            print("\n=== デバッグ情報 ===")
            table = soup.find('table')
            if table:
                print("テーブルが見つかりました")
                rows = table.find_all('tr')[:5]
                for i, row in enumerate(rows):
                    print(f"\n行 {i+1}:")
                    cells = row.find_all(['td', 'th'])
                    for j, cell in enumerate(cells):
                        print(f"  セル {j+1}: {cell.get_text(strip=True)[:50]}")
            else:
                print("テーブルが見つかりませんでした")
                links = soup.find_all('a', href=re.compile(r'/reportTop\?bcode='))[:5]
                print(f"\n会社リンクを {len(links)} 個見つけました（最初の5個）:")
                for link in links:
                    print(f"  - {link.get_text(strip=True)}")
        else:
            print(f"\n{'=' * 60}")
            print(f"全ページから合計 {len(all_data)} 件のデータを抽出しました")
            print(f"{'=' * 60}\n")
            
            # 各会社の詳細ページからPER、PBR、配当利回り、52週高値・安値を取得
            print("各会社の詳細情報を取得中...")
            print("=" * 60)
            for i, item in enumerate(all_data, 1):
                detail_url = item.get('詳細ページURL', '')
                stock_code = item.get('銘柄コード', '')
                
                if detail_url:
                    print(f"[{i}/{len(all_data)}] {item['会社名']} の詳細情報を取得中...", end=' ')
                    details = scraper.extract_company_details(detail_url)
                    item['PER'] = details['PER']
                    item['PBR'] = details['PBR']
                    item['配当利回り'] = details['配当利回り']
                    
                    # 52週高値・安値・現在値を取得
                    if stock_code:
                        week52_prices = scraper.extract_52week_prices(stock_code)
                        item['52週高値'] = week52_prices['52週高値']
                        item['52週安値'] = week52_prices['52週安値']
                        item['現在値'] = week52_prices['現在値']
                        
                        # 指標を計算: (現在値 - 52週安値) ÷ (52週高値 - 52週安値)
                        try:
                            current_val = float(item['現在値']) if item['現在値'] != 'N/A' else None
                            high_val = float(item['52週高値']) if item['52週高値'] != 'N/A' else None
                            low_val = float(item['52週安値']) if item['52週安値'] != 'N/A' else None
                            
                            if current_val is not None and high_val is not None and low_val is not None:
                                if high_val > low_val:  # ゼロ除算を防ぐ
                                    indicator = (current_val - low_val) / (high_val - low_val)
                                    item['指標'] = f"{indicator:.4f}"
                                else:
                                    item['指標'] = 'N/A'
                            else:
                                item['指標'] = 'N/A'
                        except (ValueError, TypeError):
                            item['指標'] = 'N/A'
                    else:
                        item['52週高値'] = 'N/A'
                        item['52週安値'] = 'N/A'
                        item['現在値'] = 'N/A'
                        item['指標'] = 'N/A'
                    
                    print(f"PER: {item['PER']}, PBR: {item['PBR']}, 配当利回り: {item['配当利回り']}, 現在値: {item['現在値']}, 52週高値: {item['52週高値']}, 52週安値: {item['52週安値']}, 指標: {item.get('指標', 'N/A')}")
                    # サーバー負荷を考慮して少し待機
                    time.sleep(0.5)
                else:
                    # 詳細ページURLがない場合
                    item['PER'] = 'N/A'
                    item['PBR'] = 'N/A'
                    item['配当利回り'] = 'N/A'
                    item['52週高値'] = 'N/A'
                    item['52週安値'] = 'N/A'
                    item['現在値'] = 'N/A'
                    item['指標'] = 'N/A'
            
            print("=" * 60)
            
            # 配当利回りの高い順にソート
            def get_dividend_yield(item):
                """配当利回りから数値を抽出してソート用の値を返す"""
                div_yield = item.get('配当利回り', 'N/A')
                if div_yield == 'N/A':
                    return -1  # N/Aは最後に
                # 「2.75%」から「2.75」を抽出
                match = re.search(r'([0-9,]+\.?\d*)', str(div_yield).replace(',', ''))
                if match:
                    try:
                        return float(match.group(1))
                    except ValueError:
                        return -1
                return -1
            
            sorted_data = sorted(all_data, key=get_dividend_yield, reverse=True)
            
            # 結果を表示（最初の20件のみ）
            print("\n" + "=" * 150)
            print("配当利回りの高い順に並び替えました")
            print("=" * 150)
            print(f"{'会社名':<25} {'銘柄コード':<10} {'進捗率':<10} {'PER':<10} {'PBR':<10} {'配当利回り':<12} {'現在値':<12} {'52週高値':<12} {'52週安値':<12} {'指標':<10}")
            print("=" * 150)
            display_count = min(20, len(sorted_data))
            for item in sorted_data[:display_count]:
                print(f"{item['会社名']:<25} {item['銘柄コード']:<10} {item['進捗率']:<10} {item.get('PER', 'N/A'):<10} {item.get('PBR', 'N/A'):<10} {item.get('配当利回り', 'N/A'):<12} {item.get('現在値', 'N/A'):<12} {item.get('52週高値', 'N/A'):<12} {item.get('52週安値', 'N/A'):<12} {item.get('指標', 'N/A'):<10}")
            
            if len(sorted_data) > display_count:
                print(f"... 他 {len(sorted_data) - display_count} 件")
            
            # ファイルに保存（ソート済みデータ）
            output_dir = r"C:\999"
            scraper.save_to_csv(sorted_data, f"{output_dir}\\earnings_schedule.csv")
            scraper.save_to_json(sorted_data, f"{output_dir}\\earnings_schedule.json")
            print(f"\nデータを {output_dir} に保存しました")
            print("=" * 60)
            print("処理が完了しました")
            print("=" * 60)
            
    except Exception as e:
        print(f"\nエラーが発生しました: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

