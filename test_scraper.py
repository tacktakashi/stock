"""
テスト用スクリプト - 実際のHTML構造に基づいたテスト
"""

# テスト用のHTMLサンプル（提供されたHTMLから抜粋）
test_html = """
<tr>
    <td><a href="/reportTop?bcode=1802">大林組 1802</a></td>
    <td>2025/11/05済</td>
    <td>2025/09</td>
    <td>3Q</td>
    <td>13,900</td>
    <td>8,258 _( 3Q )_</td>
    <td>59.4</td>
    <td><a href="/discloseDetail?rid=..."></a></td>
</tr>
<tr>
    <td><a href="/reportTop?bcode=4523">エーザイ 4523</a></td>
    <td>2025/11/05済</td>
    <td>2025/09</td>
    <td>2Q</td>
    <td>59,000</td>
    <td>36,936 _( 2Q )_</td>
    <td>62.6</td>
    <td><a href="/discloseDetail?rid=..."></a></td>
</tr>
"""

from bs4 import BeautifulSoup
import re
from typing import List, Dict

def extract_test_data(html: str) -> List[Dict]:
    """テスト用の抽出関数"""
    soup = BeautifulSoup(html, 'html.parser')
    results = []
    rows = soup.find_all('tr')
    
    for row in rows:
        company_link = row.find('a', href=re.compile(r'/reportTop\?bcode='))
        if not company_link:
            continue
        
        full_text = company_link.get_text(strip=True)
        href = company_link.get('href', '')
        
        stock_code_match = re.search(r'bcode=(\d+)', href)
        stock_code = stock_code_match.group(1) if stock_code_match else ''
        
        parts = full_text.split()
        if len(parts) >= 2 and parts[-1].isdigit():
            company_name = ' '.join(parts[:-1])
            if not stock_code:
                stock_code = parts[-1]
        else:
            company_name = full_text
        
        cells = row.find_all('td')
        progress_rate = None
        
        # 右から左へ検索
        for i in range(len(cells) - 1, -1, -1):
            cell = cells[i]
            cell_text = cell.get_text(strip=True)
            
            if re.match(r'^\d+\.\d+$', cell_text):
                try:
                    rate = float(cell_text)
                    if 0 <= rate <= 200:
                        progress_rate = rate
                        break
                except ValueError:
                    continue
        
        if company_name:
            results.append({
                '会社名': company_name,
                '銘柄コード': stock_code,
                '進捗率': f"{progress_rate:.1f}%" if progress_rate is not None else "N/A"
            })
    
    return results

# テスト実行
if __name__ == "__main__":
    print("テストHTMLからデータを抽出中...")
    data = extract_test_data(test_html)
    
    print(f"\n{len(data)}件のデータを抽出しました\n")
    print("=" * 60)
    print(f"{'会社名':<30} {'銘柄コード':<10} {'進捗率':<10}")
    print("=" * 60)
    for item in data:
        print(f"{item['会社名']:<30} {item['銘柄コード']:<10} {item['進捗率']:<10}")

