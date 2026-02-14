"""
Amazon Renewed/Refurbished Laptop Scraper — Multi-Market
Scrapes UAE, Singapore, Australia, India
"""
import requests
from bs4 import BeautifulSoup
import time, random, re, json, sys
from datetime import datetime

# ── Market configurations ──────────────────────────────────
MARKETS = {
    'UAE': {
        'domain': 'www.amazon.ae',
        'currency': 'AED',
        'usd_rate': 3.6725,   # AED per USD
    },
    'SG': {
        'domain': 'www.amazon.sg',
        'currency': 'SGD',
        'usd_rate': 1.3450,   # SGD per USD
    },
    'AU': {
        'domain': 'www.amazon.com.au',
        'currency': 'AUD',
        'usd_rate': 1.5700,   # AUD per USD
    },
    'IN': {
        'domain': 'www.amazon.in',
        'currency': 'INR',
        'usd_rate': 83.50,    # INR per USD
    },
}

QUERIES = {
    'Dell':   ['Dell+laptop+renewed', 'Dell+Latitude+renewed+laptop', 'Dell+XPS+renewed'],
    'HP':     ['HP+laptop+renewed', 'HP+EliteBook+renewed+laptop', 'HP+ProBook+renewed'],
    'Apple':  ['MacBook+renewed', 'MacBook+Air+renewed', 'MacBook+Pro+renewed'],
    'Lenovo': ['Lenovo+laptop+renewed', 'Lenovo+ThinkPad+renewed', 'Lenovo+IdeaPad+renewed'],
}

UAS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0',
]

SKIP = ['case','charger','adapter','stand','sleeve','bag','mouse','keyboard',
        'protector','cable','dock','cover','skin','memory stick','hard drive',
        'backpack','cooling','battery','screen ']

LAPTOPS = ['laptop','macbook','notebook','elitebook','thinkpad','latitude',
           'probook','xps','inspiron','ideapad','yoga','pavilion','zbook',
           'chromebook','precision','vostro','spectre','envy']


def get_year(title):
    m = re.search(r'\b(20[1-2][0-9])\b', title)
    if m: return int(m.group(1))
    g = re.search(r'i[3579]-(\d{1,2})\d{2,3}', title)
    if g:
        gen = int(g.group(1))
        mp = {4:2013,5:2015,6:2016,7:2017,8:2018,9:2019,10:2020,11:2020,12:2022,13:2023,14:2024}
        return mp.get(gen)
    g2 = re.search(r'(\d{1,2})(?:th|st|nd|rd)\s*Gen', title, re.I)
    if g2:
        gen = int(g2.group(1))
        mp = {4:2013,5:2015,6:2016,7:2017,8:2018,9:2019,10:2020,11:2020,12:2022,13:2023,14:2024}
        return mp.get(gen)
    mc = re.search(r'\bM([1-4])\b', title)
    if mc: return {1:2020,2:2022,3:2023,4:2024}.get(int(mc.group(1)))
    return None


def get_specs(title):
    s = {}
    ram = re.search(r'(\d+)\s*GB\s*(?:DDR|RAM)', title, re.I) or re.search(r'(\d+)GB\s*RAM', title, re.I)
    s['ram'] = int(ram.group(1)) if ram else None
    stor = re.search(r'(\d+)\s*(?:GB|TB)\s*(?:SSD|HDD|eMMC|NVMe|Solid|Storage)', title, re.I)
    if stor:
        v = int(stor.group(1))
        s['storage'] = v * 1000 if 'TB' in stor.group(0).upper() else v
        s['stype'] = 'SSD' if any(x in stor.group(0).upper() for x in ['SSD','NVM','SOL']) else 'HDD'
    else:
        s['storage'] = None
        s['stype'] = None
    for pat in [r'(Core\s+i[3579]-?\w+)', r'(Ryzen\s+\d\s*\w*)', r'(M[1-4](?:\s+Pro|\s+Max)?)',
                r'(Celeron\s*\w*)', r'(Pentium\s*\w*)']:
        p = re.search(pat, title, re.I)
        if p:
            s['proc'] = p.group(1).strip()
            break
    else:
        s['proc'] = None
    scr = re.search(r'(\d{2}(?:\.\d)?)\s*[\"\']?\s*(?:inch|in\b|\"|Fhd|FHD|HD|display)', title, re.I)
    s['screen'] = float(scr.group(1)) if scr else None
    return s


def get_model(title, brand):
    pats = {
        'Dell':   [r'(Latitude\s*\w+)', r'(Inspiron\s*\w+)', r'(XPS\s*\d+)', r'(Precision\s*\w+)', r'(Vostro\s*\w+)'],
        'HP':     [r'(EliteBook\s*\w+)', r'(ProBook\s*\w+)', r'(Pavilion\s*\w+)', r'(ZBook\s*\w+)', r'(Spectre\s*\w+)', r'(Envy\s*\w+)'],
        'Apple':  [r'(MacBook\s+Air)', r'(MacBook\s+Pro)'],
        'Lenovo': [r'(ThinkPad\s*\w+)', r'(IdeaPad\s*\w+)', r'(Yoga\s*\w+)'],
    }
    for pat in pats.get(brand, []):
        m = re.search(pat, title, re.I)
        if m: return m.group(1).strip()
    return None


def pprice(t):
    if not t: return None
    c = re.sub(r'[^\d.]', '', t.replace(',', ''))
    try: return float(c)
    except: return None


def scrape_market(market_code):
    cfg = MARKETS[market_code]
    domain = cfg['domain']
    currency = cfg['currency']
    usd_rate = cfg['usd_rate']

    all_prods = []
    seen = set()
    session = requests.Session()

    for brand, qs in QUERIES.items():
        print(f'\n  --- {brand} ---')
        for query in qs:
            qname = query.replace('+', ' ')
            for page in range(1, 4):
                time.sleep(random.uniform(2.5, 5.5))
                url = f'https://{domain}/s?k={query}&page={page}'
                try:
                    r = session.get(url, headers={
                        'User-Agent': random.choice(UAS),
                        'Accept': 'text/html,application/xhtml+xml',
                        'Accept-Language': 'en-US,en;q=0.9',
                    }, timeout=15)
                    if r.status_code != 200:
                        print(f'    {qname} p{page}: HTTP {r.status_code}')
                        break
                except Exception as e:
                    print(f'    {qname} p{page}: {e}')
                    break

                if 'captcha' in r.text[:5000].lower():
                    print(f'    {qname} p{page}: CAPTCHA - stopping this market')
                    return all_prods

                soup = BeautifulSoup(r.text, 'lxml')
                divs = soup.select('div[data-component-type="s-search-result"]')
                new_count = 0

                for div in divs:
                    asin = div.get('data-asin', '')
                    if not asin or asin in seen:
                        continue

                    te = div.select_one('h2 a span') or div.select_one('h2 span')
                    if not te:
                        continue
                    title = te.get_text(strip=True)
                    tl = title.lower()

                    if any(k in tl for k in SKIP):
                        continue
                    if not any(k in tl for k in LAPTOPS):
                        continue

                    pe = div.select_one('.a-price span.a-offscreen')
                    price = pprice(pe.get_text(strip=True)) if pe else None
                    if not price or price < (200 * usd_rate / 3.6725) or price > (20000 * usd_rate / 3.6725):
                        continue

                    oe = div.select_one('.a-price.a-text-price span.a-offscreen')
                    orig = pprice(oe.get_text(strip=True)) if oe else None

                    rat_el = div.select_one('span.a-icon-alt')
                    rating = None
                    if rat_el:
                        rm = re.search(r'([\d.]+)', rat_el.get_text())
                        if rm:
                            rating = float(rm.group(1))

                    rev_el = div.select_one('span.a-size-base.s-underline-text')
                    review_count = None
                    if rev_el:
                        rc = re.sub(r'[^\d]', '', rev_el.get_text())
                        if rc:
                            review_count = int(rc)

                    le = div.select_one('h2 a')
                    purl = (f'https://{domain}' + le['href']) if le and le.get('href') else None

                    specs = get_specs(title)
                    my = get_year(title)

                    seen.add(asin)
                    disc = round((1 - price / orig) * 100, 1) if orig and orig > price else None

                    all_prods.append({
                        'asin': asin,
                        'brand': brand,
                        'model_series': get_model(title, brand),
                        'title': title,
                        'price_local': price,
                        'price_usd': round(price / usd_rate, 2),
                        'original_price_local': orig,
                        'original_price_usd': round(orig / usd_rate, 2) if orig else None,
                        'discount_pct': disc,
                        'condition': 'Renewed',
                        'model_year': my,
                        'age_months': (2026 - my) * 12 if my else None,
                        'processor': specs['proc'],
                        'ram_gb': specs['ram'],
                        'storage_gb': specs['storage'],
                        'storage_type': specs['stype'],
                        'screen_size': specs['screen'],
                        'rating': rating,
                        'review_count': review_count,
                        'country': market_code,
                        'currency': currency,
                        'product_url': purl,
                        'scraped_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    })
                    new_count += 1

                print(f'    {qname} p{page}: {len(divs)} results, {new_count} new laptops -> total {len(all_prods)}')
                if len(divs) < 10:
                    break
            time.sleep(random.uniform(3, 7))

    return all_prods


if __name__ == '__main__':
    markets_to_scrape = sys.argv[1:] if len(sys.argv) > 1 else list(MARKETS.keys())

    print('=' * 60)
    print('  Amazon Renewed Laptop Scraper — Multi-Market')
    print(f'  {datetime.now().strftime("%Y-%m-%d %H:%M")}')
    print(f'  Markets: {", ".join(markets_to_scrape)}')
    print('=' * 60)

    all_data = {}
    grand_total = 0

    for mkt in markets_to_scrape:
        if mkt not in MARKETS:
            print(f'\n  Unknown market: {mkt}, skipping')
            continue
        cfg = MARKETS[mkt]
        print(f'\n{"=" * 60}')
        print(f'  SCRAPING: {mkt} ({cfg["domain"]}) — {cfg["currency"]}')
        print(f'{"=" * 60}')

        products = scrape_market(mkt)
        all_data[mkt] = products
        grand_total += len(products)

        # Save per-market file
        outfile = f'/home/user/RV/data/amazon_{mkt.lower()}_renewed.json'
        with open(outfile, 'w') as f:
            json.dump(products, f, indent=2)
        print(f'\n  {mkt}: {len(products)} listings saved -> {outfile}')

        # Brand breakdown
        bc = {}
        for p in products:
            bc[p['brand']] = bc.get(p['brand'], 0) + 1
        for b in sorted(bc):
            print(f'    {b}: {bc[b]}')
        wy = sum(1 for p in products if p['model_year'])
        wr = sum(1 for p in products if p['rating'])
        print(f'    With model year: {wy}/{len(products)}')
        print(f'    With rating: {wr}/{len(products)}')

        # Pause between markets
        if mkt != markets_to_scrape[-1]:
            wait = random.uniform(10, 20)
            print(f'\n  Waiting {wait:.0f}s before next market...')
            time.sleep(wait)

    # Combined summary
    print(f'\n{"=" * 60}')
    print(f'  GRAND TOTAL: {grand_total} listings across {len(all_data)} markets')
    print(f'{"=" * 60}')
    for mkt, prods in all_data.items():
        avg_usd = sum(p['price_usd'] for p in prods) / len(prods) if prods else 0
        avg_rat = sum(p['rating'] for p in prods if p['rating']) / max(1, sum(1 for p in prods if p['rating']))
        print(f'  {mkt:4s}: {len(prods):4d} listings | avg ${avg_usd:,.0f} USD | avg rating {avg_rat:.1f}')

    # Save combined file
    combined = []
    for prods in all_data.values():
        combined.extend(prods)
    with open('/home/user/RV/data/amazon_all_markets_renewed.json', 'w') as f:
        json.dump(combined, f, indent=2)
    print(f'\n  Combined JSON: /home/user/RV/data/amazon_all_markets_renewed.json')
