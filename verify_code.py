"""
コードの動作検証用スクリプト
実際のHTML構造に基づいて動作を確認
"""

# 提供されたHTMLから抜粋したサンプルデータ
sample_html = """
<table>
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
<tr>
    <td><a href="/reportTop?bcode=4206">アイカ工業 4206</a></td>
    <td>2025/11/05済</td>
    <td>2025/09</td>
    <td>2Q</td>
    <td>30,000</td>
    <td>14,671 _( 2Q )_</td>
    <td>48.9</td>
    <td><a href="/discloseDetail?rid=..."></a></td>
</tr>
</table>
"""

print("=" * 60)
print("コード動作検証")
print("=" * 60)

try:
    from bs4 import BeautifulSoup
    import re
    from typing import List, Dict
    
    print("\n✓ 必要なライブラリのインポートに成功しました")
    
    # HTMLをパース
    soup = BeautifulSoup(sample_html, 'html.parser')
    print("✓ HTMLのパースに成功しました")
    
    # データ抽出のテスト
    results = []
    seen_companies = set()
    rows = soup.find_all('tr')
    
    print(f"\n✓ {len(rows)}行のデータを検出しました")
    
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
        
        company_key = f"{company_name}_{stock_code}"
        if company_key in seen_companies:
            continue
        seen_companies.add(company_key)
        
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
    
    print(f"\n✓ {len(results)}件のデータを抽出しました\n")
    
    # 結果を表示
    print("=" * 60)
    print(f"{'会社名':<30} {'銘柄コード':<10} {'進捗率':<10}")
    print("=" * 60)
    for item in results:
        print(f"{item['会社名']:<30} {item['銘柄コード']:<10} {item['進捗率']:<10}")
    
    print("\n" + "=" * 60)
    print("✓ コードの動作検証が完了しました")
    print("=" * 60)
    
except ImportError as e:
    print(f"\n✗ ライブラリのインポートエラー: {e}")
    print("以下のコマンドでインストールしてください:")
    print("  pip install beautifulsoup4")
except Exception as e:
    print(f"\n✗ エラーが発生しました: {e}")
    import traceback
    traceback.print_exc()

