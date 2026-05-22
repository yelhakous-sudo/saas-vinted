import re, time, json, asyncio
import logging
from collections import defaultdict
from statistics import mean, median
import requests
import cloudscraper
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("vinted")

app = FastAPI(title="VintedSaaS - Analyseur de Marge")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

VINTED_BASE = "https://www.vinted.fr"
VINTED_SEARCH = f"{VINTED_BASE}/api/v2/catalog/items"

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
]

scraper = cloudscraper.create_scraper()
scraper.headers.update({
    'User-Agent': USER_AGENTS[0],
    'Accept-Language': 'fr-FR,fr;q=0.9,en;q=0.5',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'DNT': '1',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
})
_session_ok = False

NOISE_WORDS = [
    'neuf', 'neuve', 'jamais porté', 'jamais porte', 'étiquette', 'etiquette',
    'très bon état', 'tres bon etat', 'bon état', 'bon etat', 'état correct', 'etat correct',
    'satisfaisant', 'occasion', 'vintage', 'authentique', 'original', 'livré', 'livre',
    'livraison', 'lot', 'pack', 'noir', 'blanc', 'rouge', 'bleu', 'vert', 'jaune',
    'rose', 'gris', 'beige', 'marron', 'violet', 'orange'
]

CATEGORIES = {
    "tops": ["t-shirt", "chemise", "polo", "pull", "sweat", "veste legere"],
    "pantalons": ["jean", "pantalon", "chino", "short", "bermuda"],
    "vestes": ["manteau", "blouson", "blazer", "doudoune", "parka"],
    "chaussures": ["basket", "sneakers", "botte", "bottine", "sandale", "escarpin"],
    "sacs": ["sac a main", "sacoche", "besace", "sport", "banane"],
    "accessoires": ["montre", "ceinture", "lunettes", "bijou", "chapeau"],
    "sport": ["running", "survetement", "fitness", "training", "sportswear", "gym"],
    "enfants": ["bebe", "enfant", "toddler", "kids"],
}

def init_session():
    global _session_ok
    _session_ok = False
    for ua in USER_AGENTS:
        try:
            scraper.headers['User-Agent'] = ua
            r = scraper.get(VINTED_BASE, timeout=25)
            if r.status_code == 200:
                token = scraper.cookies.get('access_token_web')
                if token:
                    _session_ok = True
                    logger.info(f"Session OK with UA: {ua[:50]}... token={token[:20]}...")
                    return True
                else:
                    logger.warning(f"No access_token_web cookie with UA: {ua[:50]}")
            else:
                logger.warning(f"Vinted home returned {r.status_code} with UA: {ua[:50]}")
        except Exception as e:
            logger.warning(f"init_session failed with UA {ua[:30]}: {e}")
    logger.error("All init_session attempts failed")
    return False

@app.on_event("startup")
async def startup():
    init_session()

def get_auth_header():
    token = scraper.cookies.get('access_token_web')
    return {'Authorization': f'Bearer {token}'} if token else {}

def search_vinted(search_text: str, page: int = 1, per_page: int = 30) -> Optional[dict]:
    params = {'search_text': search_text, 'page': page, 'per_page': per_page}
    for attempt in range(3):
        try:
            ua = USER_AGENTS[(attempt + page) % len(USER_AGENTS)]
            headers = {
                'Accept': 'application/json, text/plain, */*',
                'Referer': f'{VINTED_BASE}/catalog?search_text={search_text}',
                'User-Agent': ua,
                'X-Requested-With': 'XMLHttpRequest',
            }
            headers.update(get_auth_header())
            resp = scraper.get(VINTED_SEARCH, params=params, headers=headers, timeout=20)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code in (401, 403):
                logger.warning(f"Vinted API {resp.status_code}, reinitializing session...")
                if attempt == 0:
                    init_session()
                time.sleep(1)
                continue
            if resp.status_code == 429:
                wait = 3 * (attempt + 1)
                logger.warning(f"Rate limited, waiting {wait}s...")
                time.sleep(wait)
                continue
            logger.warning(f"Vinted API returned {resp.status_code}: {resp.text[:200]}")
            return None
        except requests.exceptions.Timeout:
            logger.warning(f"Timeout attempt {attempt+1}")
            time.sleep(2)
        except Exception as e:
            logger.error(f"search_vinted error attempt {attempt+1}: {e}")
            time.sleep(1)
            if attempt == 0:
                init_session()
    return None

def fetch_items(search_text: str, max_pages: int = 3) -> list:
    items = []
    for p in range(1, max_pages + 1):
        data = search_vinted(search_text, p)
        if not data or not data.get('items'):
            break
        items.extend(data['items'])
        time.sleep(0.3)
    return items

def extract_item(item: dict) -> dict:
    photo = item.get('photo') or {}
    total_price = item.get('total_item_price') or {}
    return {
        'id': item['id'],
        'title': item.get('title', ''),
        'price': float(item.get('price', {}).get('amount', 0)),
        'currency': item.get('price', {}).get('currency_code', 'EUR'),
        'total_price': float(total_price.get('amount', 0)) if total_price.get('amount') else None,
        'brand': item.get('brand_title', 'Inconnu'),
        'size': item.get('size_title', ''),
        'condition': item.get('status', ''),
        'photo': photo.get('url', ''),
        'url': f"https://www.vinted.fr/items/{item['id']}",
        'favourites': item.get('favourite_count', 0),
        'is_visible': item.get('is_visible', True),
    }

def clean_title(title: str) -> str:
    t = title.lower()
    for w in NOISE_WORDS:
        t = t.replace(w, '')
    t = re.sub(r'\b\d{2,4}\b', '', t)
    t = re.sub(r'\b(xs|s|m|l|xl|xxl|xxxl|eu|uk|us\s*\d+)\b', '', t)
    t = re.sub(r'[^\w\s-]', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t[:80] if t else title[:80]

@app.get("/api/health")
def health():
    return {"status": "ok", "vinted_connected": _session_ok}

@app.get("/api/categories")
def get_categories():
    return {"categories": list(CATEGORIES.keys()), "subcategories": CATEGORIES}

@app.get("/api/search")
def search(q: str = Query(..., min_length=1), page: int = Query(1, ge=1), per_page: int = Query(30, ge=1, le=100)):
    data = search_vinted(q, page, per_page)
    if not data:
        raise HTTPException(503, "Impossible de contacter Vinted API")
    items = [extract_item(it) for it in data.get('items', [])]
    pag = data.get('pagination', {})
    return {'items': items, 'total': pag.get('total_entries', 0), 'page': page, 'query': q}

@app.get("/api/analyze")
def analyze(category: str = Query("tops"), subcategory: str = Query(""),
    brands: str = Query("Nike,Adidas,Saucony,New Balance"), min_price: float = Query(0, ge=0),
    max_price: float = Query(500, ge=0), pages: int = Query(3, ge=1, le=10),
    sort_by: str = Query("profit")):
    brand_list = [b.strip() for b in brands.split(',') if b.strip()]
    sub_list = [subcategory] if subcategory else CATEGORIES.get(category, [category])
    all_items = []
    for brand in brand_list:
        for sub in sub_list:
            search_q = f"{brand} {sub}"
            items = fetch_items(search_q, pages)
            for it in items:
                info = extract_item(it)
                info['search_query'] = search_q
                all_items.append(info)
    if not all_items:
        raise HTTPException(404, "Aucun article trouvé")
    all_items = [i for i in all_items if min_price <= i['price'] <= max_price]
    if not all_items:
        raise HTTPException(404, "Aucun article dans cette fourchette de prix")
    groups = defaultdict(list)
    for item in all_items:
        key = clean_title(item['title'])
        if item['brand']:
            key = f"{item['brand']}###{key}"
        groups[key].append(item)
    results = []
    total_opportunities = 0
    for key, items in groups.items():
        prices = [i['price'] for i in items if i['price'] > 0]
        if len(prices) < 2:
            continue
        brand = key.split('###')[0] if '###' in key else ''
        product_name = key.split('###')[-1] if '###' in key else key
        avg_p = mean(prices)
        med_p = median(prices)
        lo, hi = min(prices), max(prices)
        opportunities = []
        for item in items:
            if item['price'] <= avg_p * 0.80:
                resale = round(avg_p * 0.93, 2)
                fees = round(resale * 0.08 + 0.50, 2)
                shipping = 2.50
                profit = round(resale - item['price'] - fees - shipping, 2)
                margin_pct = round((profit / item['price']) * 100, 1) if item['price'] > 0 else 0
                opportunities.append({
                    'id': item['id'], 'title': item['title'], 'price': item['price'],
                    'avg_price': round(avg_p, 2), 'median_price': round(med_p, 2),
                    'resale_estimation': resale, 'fees': fees, 'shipping': shipping,
                    'profit_estimation': profit, 'margin_percentage': margin_pct,
                    'size': item['size'], 'condition': item['condition'], 'url': item['url'],
                    'photo': item['photo'], 'favourites': item['favourites'],
                })
        if opportunities:
            total_opportunities += len(opportunities)
            results.append({
                'brand': brand, 'product': product_name, 'avg_price': round(avg_p, 2),
                'median_price': round(med_p, 2), 'min_price': lo, 'max_price': hi,
                'sample_size': len(prices), 'search_query': items[0].get('search_query', ''),
                'total_opportunities': len(opportunities),
                'avg_margin': round(mean([o['margin_percentage'] for o in opportunities]), 1),
                'avg_profit': round(mean([o['profit_estimation'] for o in opportunities]), 2),
                'opportunities': sorted(opportunities, key=lambda x: x['profit_estimation'], reverse=True)[:12],
            })
    if not results:
        raise HTTPException(404, "Pas assez de données pour analyser la marge")
    if sort_by == 'margin':
        results.sort(key=lambda x: x['avg_margin'], reverse=True)
    elif sort_by == 'volume':
        results.sort(key=lambda x: x['total_opportunities'], reverse=True)
    else:
        results.sort(key=lambda x: x['avg_profit'], reverse=True)
    return {
        'total_items_scanned': len(all_items), 'products_analyzed': len(results),
        'total_opportunities': total_opportunities,
        'average_margin': round(mean([r['avg_margin'] for r in results]), 1),
        'average_profit': round(mean([r['avg_profit'] for r in results]), 2),
        'results': results, 'filters': {'category': category, 'subcategory': subcategory,
            'brands': brand_list, 'min_price': min_price, 'max_price': max_price}
    }

@app.get("/api/quick-scan")
def quick_scan(search: str = Query(..., min_length=2), max_price: float = Query(100, ge=0)):
    items = fetch_items(search, 3)
    if not items:
        raise HTTPException(404, "Aucun résultat")
    items_data = [extract_item(it) for it in items]
    items_data = [i for i in items_data if i['price'] <= max_price and i['price'] > 0]
    if len(items_data) < 3:
        raise HTTPException(404, "Pas assez de données (minimum 3 articles)")
    prices = [i['price'] for i in items_data]
    avg_p, med_p = mean(prices), median(prices)
    best_deals = []
    for item in sorted(items_data, key=lambda x: x['price'])[:10]:
        if item['price'] <= avg_p * 0.80:
            resale = round(avg_p * 0.93, 2)
            fees = round(resale * 0.08 + 0.50, 2)
            shipping = 2.50
            profit = round(resale - item['price'] - fees - shipping, 2)
            margin_pct = round((profit / item['price']) * 100, 1) if item['price'] > 0 else 0
            best_deals.append({**item, 'avg_price': round(avg_p, 2), 'resale_estimation': resale,
                'fees': fees, 'shipping': shipping, 'profit_estimation': profit, 'margin_percentage': margin_pct})
    brand_stats = defaultdict(list)
    for item in items_data:
        brand_stats[item['brand']].append(item['price'])
    brand_summary = [{'brand': b, 'count': len(p), 'avg_price': round(mean(p), 2), 'lowest': min(p)}
        for b, p in brand_stats.items()]
    brand_summary.sort(key=lambda x: x['count'], reverse=True)
    return {
        'query': search, 'total_found': len(items_data), 'avg_price': round(avg_p, 2),
        'median_price': round(med_p, 2), 'min_price': min(prices), 'max_price': max(prices),
        'best_deals': best_deals, 'brands': brand_summary,
        'potential_weekly_earnings': round(len(best_deals) * 30, 2),
    }

if __name__ == '__main__':
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
else:
    from fastapi.responses import FileResponse
    from pathlib import Path
    frontend_path = Path(__file__).resolve().parent.parent / "frontend"
    if frontend_path.exists():
        @app.get("/")
        def serve_index():
            return FileResponse(frontend_path / "index.html")
        @app.get("/{file_path:path}")
        def serve_static(file_path: str):
            f = frontend_path / file_path
            if f.exists() and f.is_file():
                return FileResponse(f)
            return FileResponse(frontend_path / "index.html")
