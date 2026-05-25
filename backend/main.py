import re, time, json, random, os
import logging
from collections import defaultdict
from statistics import mean, median
from datetime import datetime
from contextlib import asynccontextmanager
from pathlib import Path

import requests
import cloudscraper
from fastapi import FastAPI, Query, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from sqlalchemy import func as sa_func, desc
from .database import init_db, get_db, DB_DIR
from .models import User, Scan, Opportunity
from .auth import hash_password, verify_password, create_access_token, get_current_user, require_user
from .schemas import UserRegister, UserLogin, TokenResponse, UserResponse, StatsResponse, ScanHistoryItem

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("vinted")

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    init_session()
    yield

app = FastAPI(title="VintedPro SaaS", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

COUNTRIES = {
    "fr": {"domain": "www.vinted.fr", "name": "France", "currency": "EUR"},
    "be": {"domain": "www.vinted.be", "name": "Belgique", "currency": "EUR"},
    "nl": {"domain": "www.vinted.nl", "name": "Pays-Bas", "currency": "EUR"},
    "de": {"domain": "www.vinted.de", "name": "Allemagne", "currency": "EUR"},
    "it": {"domain": "www.vinted.it", "name": "Italie", "currency": "EUR"},
    "es": {"domain": "www.vinted.es", "name": "Espagne", "currency": "EUR"},
    "pt": {"domain": "www.vinted.pt", "name": "Portugal", "currency": "EUR"},
    "at": {"domain": "www.vinted.at", "name": "Autriche", "currency": "EUR"},
    "pl": {"domain": "www.vinted.pl", "name": "Pologne", "currency": "PLN"},
    "lt": {"domain": "www.vinted.lt", "name": "Lituanie", "currency": "EUR"},
    "cz": {"domain": "www.vinted.cz", "name": "Republique Tcheque", "currency": "CZK"},
    "lu": {"domain": "www.vinted.lu", "name": "Luxembourg", "currency": "EUR"},
}
DEFAULT_COUNTRY = "fr"

def get_vinted_urls(country: str = DEFAULT_COUNTRY) -> tuple:
    domain = COUNTRIES.get(country, COUNTRIES[DEFAULT_COUNTRY])["domain"]
    return f"https://{domain}", f"https://{domain}/api/v2/catalog/items"

VINTED_BASE, VINTED_SEARCH = get_vinted_urls()

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:126.0) Gecko/20100101 Firefox/126.0',
]

PROXIES = os.getenv("VINTED_PROXIES", "").split(",") if os.getenv("VINTED_PROXIES") else []
PROXY_INDEX = 0

scraper = cloudscraper.create_scraper()
scraper.headers.update({
    'Accept-Language': 'fr-FR,fr;q=0.9,en;q=0.5',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'DNT': '1',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
})
_session_ok = False

NOISE_WORDS = [
    'neuf', 'neuve', 'jamais porte', 'jamais porté', 'etiquette', 'étiquette',
    'très bon etat', 'tres bon etat', 'très bon état', 'bon etat', 'bon état',
    'etat correct', 'état correct', 'satisfaisant', 'occasion', 'vintage',
    'authentique', 'original', 'livré', 'livre', 'livraison', 'lot', 'pack',
    'noir', 'blanc', 'rouge', 'bleu', 'vert', 'jaune', 'rose', 'gris',
    'beige', 'marron', 'violet', 'orange'
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

def get_proxy() -> dict | None:
    if not PROXIES:
        return None
    global PROXY_INDEX
    proxy = PROXIES[PROXY_INDEX % len(PROXIES)].strip()
    PROXY_INDEX += 1
    return {"http": proxy, "https": proxy} if proxy else None

def init_session(country: str = DEFAULT_COUNTRY) -> bool:
    global _session_ok
    _session_ok = False
    vinted_base, _ = get_vinted_urls(country)
    for ua in USER_AGENTS:
        try:
            scraper.headers["User-Agent"] = ua
            r = scraper.get(vinted_base, timeout=25, proxies=get_proxy())
            if r.status_code == 200:
                token = scraper.cookies.get("access_token_web")
                if token:
                    _session_ok = True
                    logger.info(f"Session OK - UA: {ua[:40]}... token: {token[:16]}...")
                    return True
                logger.warning(f"No access_token_web for UA: {ua[:40]}")
            else:
                logger.warning(f"Vinted {r.status_code} for UA: {ua[:40]}")
        except Exception as e:
            logger.warning(f"init_session UA {ua[:20]}: {e}")
    return False

def get_auth_header() -> dict:
    token = scraper.cookies.get("access_token_web")
    return {"Authorization": f"Bearer {token}"} if token else {}

def search_vinted(search_text: str, page: int = 1, per_page: int = 30) -> dict | None:
    params = {"search_text": search_text, "page": page, "per_page": per_page}
    for attempt in range(3):
        try:
            ua = USER_AGENTS[(attempt + page) % len(USER_AGENTS)]
            headers = {
                "Accept": "application/json, text/plain, */*",
                "Referer": f"{VINTED_BASE}/catalog?search_text={search_text}",
                "User-Agent": ua,
                "X-Requested-With": "XMLHttpRequest",
            }
            headers.update(get_auth_header())
            resp = scraper.get(
                VINTED_SEARCH, params=params, headers=headers,
                timeout=20, proxies=get_proxy()
            )
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code in (401, 403):
                if attempt == 0:
                    init_session()
                time.sleep(1)
                continue
            if resp.status_code == 429:
                wait = 3 * (attempt + 1)
                time.sleep(wait)
                continue
            logger.warning(f"Vinted API {resp.status_code}")
            return None
        except requests.exceptions.Timeout:
            time.sleep(2)
        except Exception as e:
            logger.error(f"search error attempt {attempt+1}: {e}")
            time.sleep(1)
            if attempt == 0:
                init_session()
    return None

def fetch_items(search_text: str, max_pages: int = 3) -> list:
    items = []
    for p in range(1, max_pages + 1):
        data = search_vinted(search_text, p)
        if not data or not data.get("items"):
            break
        items.extend(data["items"])
        time.sleep(0.3 + random.random() * 0.2)
    return items

def extract_item(item: dict) -> dict:
    photo = item.get("photo") or {}
    total_price = item.get("total_item_price") or {}
    return {
        "id": item["id"],
        "title": item.get("title", ""),
        "price": float(item.get("price", {}).get("amount", 0)),
        "currency": item.get("price", {}).get("currency_code", "EUR"),
        "total_price": float(total_price.get("amount", 0)) if total_price.get("amount") else None,
        "brand": item.get("brand_title", "Inconnu"),
        "size": item.get("size_title", ""),
        "condition": item.get("status", ""),
        "photo": photo.get("url", ""),
        "url": f"https://www.vinted.fr/items/{item['id']}",
        "favourites": item.get("favourite_count", 0),
        "is_visible": item.get("is_visible", True),
    }

def clean_title(title: str) -> str:
    t = title.lower()
    for w in NOISE_WORDS:
        t = t.replace(w, "")
    t = re.sub(r"\b\d{2,4}\b", "", t)
    t = re.sub(r"\b(xs|s|m|l|xl|xxl|xxxl|eu|uk|us\s*\d+)\b", "", t)
    t = re.sub(r"[^\w\s-]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t[:80] if t else title[:80]

# ─── Auth Routes ───

@app.post("/api/auth/register")
def register(body: UserRegister, db: Session = Depends(get_db)):
    if db.query(User).filter((User.email == body.email) | (User.username == body.username)).first():
        raise HTTPException(400, "Email ou nom d'utilisateur deja pris")
    if len(body.password) < 6:
        raise HTTPException(400, "Mot de passe trop court (min 6 caracteres)")
    user = User(
        email=body.email,
        username=body.username,
        hashed_password=hash_password(body.password),
        credits=10,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token({"sub": str(user.id)})
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )

@app.post("/api/auth/login")
def login(body: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(401, "Email ou mot de passe incorrect")
    token = create_access_token({"sub": str(user.id)})
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )

@app.get("/api/auth/me")
def me(user: User = Depends(require_user)):
    return UserResponse.model_validate(user)

# ─── API Routes ───

@app.get("/api/health")
def health():
    return {"status": "ok", "vinted_connected": _session_ok}

@app.get("/api/categories")
def get_categories():
    return {"categories": list(CATEGORIES.keys()), "subcategories": CATEGORIES}

@app.get("/api/search")
def search(
    q: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    per_page: int = Query(30, ge=1, le=100),
):
    data = search_vinted(q, page, per_page)
    if not data:
        raise HTTPException(503, "Impossible de contacter Vinted API")
    items = [extract_item(it) for it in data.get("items", [])]
    pag = data.get("pagination", {})
    return {"items": items, "total": pag.get("total_entries", 0), "page": page, "query": q}

@app.get("/api/analyze")
def analyze(
    category: str = Query("tops"),
    subcategory: str = Query(""),
    brands: str = Query("Nike,Adidas,Saucony,New Balance"),
    min_price: float = Query(0, ge=0),
    max_price: float = Query(500, ge=0),
    pages: int = Query(3, ge=1, le=10),
    sort_by: str = Query("profit"),
    model: str = Query(""),
    sizes: str = Query(""),
    conditions: str = Query(""),
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    brand_list = [b.strip() for b in brands.split(",") if b.strip()]
    sub_list = [subcategory] if subcategory else CATEGORIES.get(category, [category])
    all_items = []
    for brand in brand_list:
        for sub in sub_list:
            search_q = f"{brand} {model}" if model else f"{brand} {sub}"
            items = fetch_items(search_q, pages)
            for it in items:
                info = extract_item(it)
                info["search_query"] = search_q
                all_items.append(info)

    if not all_items:
        raise HTTPException(404, "Aucun article trouve")
    all_items = [i for i in all_items if min_price <= i["price"] <= max_price]
    if model:
        all_items = [i for i in all_items if model.lower() in i["title"].lower()]
    if sizes:
        sz_list = [s.strip().lower() for s in sizes.split(",") if s.strip()]
        if sz_list:
            all_items = [i for i in all_items if i["size"] and any(sz in i["size"].lower() for sz in sz_list)]
    if conditions:
        c_list = [c.strip().lower() for c in conditions.split(",") if c.strip()]
        if c_list:
            all_items = [i for i in all_items if i["condition"] and any(c in i["condition"].lower() for c in c_list)]
    if not all_items:
        raise HTTPException(404, "Aucun article dans cette fourchette de prix")

    groups = defaultdict(list)
    for item in all_items:
        key = clean_title(item["title"])
        if item["brand"]:
            key = f"{item['brand']}###{key}"
        groups[key].append(item)

    results = []
    total_opportunities = 0
    for key, items in groups.items():
        prices = [i["price"] for i in items if i["price"] > 0]
        if len(prices) < 2:
            continue
        brand = key.split("###")[0] if "###" in key else ""
        product_name = key.split("###")[-1] if "###" in key else key
        avg_p = mean(prices)
        med_p = median(prices)
        lo, hi = min(prices), max(prices)
        opportunities = []
        for item in items:
            if item["price"] <= avg_p * 0.80:
                resale = round(avg_p * 0.93, 2)
                fees = round(resale * 0.08 + 0.50, 2)
                shipping = 2.50
                profit = round(resale - item["price"] - fees - shipping, 2)
                margin_pct = round((profit / item["price"]) * 100, 1) if item["price"] > 0 else 0
                opportunities.append({
                    "id": item["id"], "title": item["title"], "price": item["price"],
                    "avg_price": round(avg_p, 2), "median_price": round(med_p, 2),
                    "resale_estimation": resale, "fees": fees, "shipping": shipping,
                    "profit_estimation": profit, "margin_percentage": margin_pct,
                    "size": item["size"], "condition": item["condition"], "url": item["url"],
                    "photo": item["photo"], "favourites": item["favourites"],
                })
        if opportunities:
            total_opportunities += len(opportunities)
            results.append({
                "brand": brand, "product": product_name, "avg_price": round(avg_p, 2),
                "median_price": round(med_p, 2), "min_price": lo, "max_price": hi,
                "sample_size": len(prices), "search_query": items[0].get("search_query", ""),
                "total_opportunities": len(opportunities),
                "avg_margin": round(mean([o["margin_percentage"] for o in opportunities]), 1),
                "avg_profit": round(mean([o["profit_estimation"] for o in opportunities]), 2),
                "opportunities": sorted(opportunities, key=lambda x: x["profit_estimation"], reverse=True)[:12],
            })

    if not results:
        raise HTTPException(404, "Pas assez de donnees pour analyser la marge")

    if sort_by == "margin":
        results.sort(key=lambda x: x["avg_margin"], reverse=True)
    elif sort_by == "volume":
        results.sort(key=lambda x: x["total_opportunities"], reverse=True)
    else:
        results.sort(key=lambda x: x["avg_profit"], reverse=True)

    avg_margin = round(mean([r["avg_margin"] for r in results]), 1)
    avg_profit = round(mean([r["avg_profit"] for r in results]), 2)

    # Save scan to DB
    if user:
        scan = Scan(
            user_id=user.id,
            category=category,
            brands=brands,
            model=model,
            min_price=min_price,
            max_price=max_price,
            sizes=sizes,
            conditions=conditions,
            total_items=len(all_items),
            opportunities_found=total_opportunities,
            avg_margin=avg_margin,
            avg_profit=avg_profit,
        )
        db.add(scan)
        db.flush()
        for r in results:
            for o in r["opportunities"]:
                opp = Opportunity(
                    scan_id=scan.id,
                    vinted_item_id=o["id"],
                    title=o["title"],
                    brand=r["brand"],
                    product=r["product"],
                    price=o["price"],
                    avg_price=o["avg_price"],
                    resale_estimation=o["resale_estimation"],
                    profit_estimation=o["profit_estimation"],
                    margin_percentage=o["margin_percentage"],
                    size=o["size"],
                    condition=o["condition"],
                    url=o["url"],
                    photo=o["photo"],
                    favourites=o["favourites"],
                )
                db.add(opp)
        db.commit()

    return {
        "total_items_scanned": len(all_items),
        "products_analyzed": len(results),
        "total_opportunities": total_opportunities,
        "average_margin": avg_margin,
        "average_profit": avg_profit,
        "results": results,
        "filters": {"category": category, "subcategory": subcategory,
                     "brands": brand_list, "min_price": min_price, "max_price": max_price},
    }

@app.get("/api/quick-scan")
def quick_scan(
    search: str = Query(..., min_length=2),
    max_price: float = Query(100, ge=0),
):
    items = fetch_items(search, 3)
    if not items:
        raise HTTPException(404, "Aucun resultat")
    items_data = [extract_item(it) for it in items]
    items_data = [i for i in items_data if i["price"] <= max_price and i["price"] > 0]
    if len(items_data) < 3:
        raise HTTPException(404, "Pas assez de donnees (minimum 3 articles)")
    prices = [i["price"] for i in items_data]
    avg_p, med_p = mean(prices), median(prices)
    best_deals = []
    for item in sorted(items_data, key=lambda x: x["price"])[:10]:
        if item["price"] <= avg_p * 0.80:
            resale = round(avg_p * 0.93, 2)
            fees = round(resale * 0.08 + 0.50, 2)
            shipping = 2.50
            profit = round(resale - item["price"] - fees - shipping, 2)
            margin_pct = round((profit / item["price"]) * 100, 1) if item["price"] > 0 else 0
            best_deals.append({**item, "avg_price": round(avg_p, 2), "resale_estimation": resale,
                "fees": fees, "shipping": shipping, "profit_estimation": profit, "margin_percentage": margin_pct})
    brand_stats = defaultdict(list)
    for item in items_data:
        brand_stats[item["brand"]].append(item["price"])
    brand_summary = [{"brand": b, "count": len(p), "avg_price": round(mean(p), 2), "lowest": min(p)}
        for b, p in brand_stats.items()]
    brand_summary.sort(key=lambda x: x["count"], reverse=True)
    return {
        "query": search, "total_found": len(items_data), "avg_price": round(avg_p, 2),
        "median_price": round(med_p, 2), "min_price": min(prices), "max_price": max(prices),
        "best_deals": best_deals, "brands": brand_summary,
        "potential_weekly_earnings": round(len(best_deals) * 30, 2),
    }

# ─── Stats / History Routes ───

@app.get("/api/stats")
def get_stats(user: User = Depends(require_user), db: Session = Depends(get_db)):
    scans = db.query(Scan).filter(Scan.user_id == user.id).order_by(desc(Scan.created_at)).limit(50).all()
    total_scans = db.query(Scan).filter(Scan.user_id == user.id).count()
    total_opps = db.query(Opportunity).join(Scan).filter(Scan.user_id == user.id).count()
    avg_m = db.query(Scan.avg_margin).filter(Scan.user_id == user.id, Scan.avg_margin > 0).all()
    avg_p = db.query(Scan.avg_profit).filter(Scan.user_id == user.id, Scan.avg_profit > 0).all()

    top_cats = db.query(Scan.category, sa_func.count(Scan.id).label("count")) \
        .filter(Scan.user_id == user.id) \
        .group_by(Scan.category) \
        .order_by(desc("count")) \
        .limit(5).all()

    return StatsResponse(
        total_scans=total_scans,
        total_opportunities=total_opps,
        avg_margin_all=round(mean([m[0] for m in avg_m]), 1) if avg_m else 0,
        avg_profit_all=round(mean([p[0] for p in avg_p]), 2) if avg_p else 0,
        top_categories=[{"category": c, "count": n} for c, n in top_cats],
        scan_history=[
            ScanHistoryItem(
                id=s.id, category=s.category, brands=s.brands,
                total_items=s.total_items, opportunities_found=s.opportunities_found,
                avg_margin=s.avg_margin, avg_profit=s.avg_profit,
                created_at=s.created_at.isoformat() if s.created_at else "",
            ) for s in scans
        ],
    )

if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
