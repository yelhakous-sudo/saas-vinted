const API_BASE = typeof API_URL !== 'undefined' ? API_URL : 'http://localhost:8001';

let credits = 0;
let isAnalyzing = false;

const $ = (s) => document.querySelector(s);
const $$ = (s) => document.querySelectorAll(s);

const categoryGrid = $('#categoryGrid');
const subSelect = $('#subcategorySelect');
const minPrice = $('#minPrice');
const maxPrice = $('#maxPrice');
const rangeFill = $('#rangeFill');
const priceLabel = $('#priceRangeLabel');
const brandInput = $('#brandInput');
const analyzeBtn = $('#analyzeBtn');
const loadingState = $('#loadingState');
const emptyState = $('#emptyState');
const resultsList = $('#resultsList');
const scanCount = $('#scanCount');
const oppCount = $('#oppCount');
const avgMargin = $('#avgMargin');
const avgProfit = $('#avgProfit');
const resultCount = $('#resultCount');
const creditsDisplay = $('#creditsDisplay');
const clearBtn = $('#clearBtn');
const toastContainer = $('#toastContainer');
const statsScanned = $('#statsScanned');
const statsDeals = $('#statsDeals');
const statsMargin = $('#statsMargin');

const subcategories = {};

// ─── Animated Background ───
function initBackground() {
    const canvas = document.getElementById('bgCanvas');
    const ctx = canvas.getContext('2d');
    let w, h, particles = [];
    const COUNT = 80;

    function resize() {
        w = canvas.width = window.innerWidth;
        h = canvas.height = window.innerHeight;
    }

    class Particle {
        constructor() { this.reset(); }
        reset() {
            this.x = Math.random() * w;
            this.y = Math.random() * h;
            this.size = Math.random() * 3 + 1;
            this.speedX = (Math.random() - 0.5) * 0.3;
            this.speedY = (Math.random() - 0.5) * 0.3;
            this.opacity = Math.random() * 0.6 + 0.3;
            this.color = ['#6C5CE7', '#A29BFE', '#fd79a8', '#4a3fbf'][Math.floor(Math.random() * 4)];
        }
        update() {
            this.x += this.speedX;
            this.y += this.speedY;
            if (this.x < 0 || this.x > w) this.speedX *= -1;
            if (this.y < 0 || this.y > h) this.speedY *= -1;
        }
        draw() {
            ctx.beginPath();
            ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
            ctx.fillStyle = this.color;
            ctx.globalAlpha = this.opacity;
            ctx.fill();
            // glow
            ctx.shadowColor = this.color;
            ctx.shadowBlur = 8;
            ctx.fill();
            ctx.shadowBlur = 0;
            ctx.globalAlpha = 1;
        }
    }

    function connect() {
        for (let i = 0; i < particles.length; i++) {
            for (let j = i + 1; j < particles.length; j++) {
                const dx = particles[i].x - particles[j].x;
                const dy = particles[i].y - particles[j].y;
                const dist = Math.sqrt(dx * dx + dy * dy);
                if (dist < 160) {
                    const op = (1 - dist / 160) * 0.35;
                    ctx.beginPath();
                    ctx.moveTo(particles[i].x, particles[i].y);
                    ctx.lineTo(particles[j].x, particles[j].y);
                    ctx.strokeStyle = `rgba(108, 92, 231, ${op})`;
                    ctx.lineWidth = 1;
                    ctx.stroke();
                }
            }
        }
    }

    function animate() {
        ctx.clearRect(0, 0, w, h);
        particles.forEach(p => { p.update(); p.draw(); });
        connect();
        requestAnimationFrame(animate);
    }

    resize();
    for (let i = 0; i < COUNT; i++) particles.push(new Particle());
    animate();
    window.addEventListener('resize', resize);
}

// ─── Toast ───
function showToast(msg, type = 'info') {
    const t = document.createElement('div');
    t.className = 'toast';
    t.innerHTML = msg;
    toastContainer.appendChild(t);
    setTimeout(() => { t.classList.add('toast-out'); setTimeout(() => t.remove(), 300); }, 3000);
}

// ─── Counter Animation ───
function animateCounter(el, target, suffix = '') {
    const span = el.querySelector('.counter');
    if (!span) {
        // parse number from start
        const startVal = parseFloat(el.textContent) || 0;
        animateValue(el, startVal, target, 800, suffix);
        return;
    }
    animateValue(span, 0, target, 800, '');
}

function animateValue(el, start, end, duration, suffix = '') {
    const startTime = performance.now();
    const isFloat = end % 1 !== 0;

    function tick(now) {
        const elapsed = now - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const eased = 1 - Math.pow(1 - progress, 3);
        const val = start + (end - start) * eased;
        el.textContent = (isFloat ? val.toFixed(1) : Math.round(val)) + suffix;
        if (progress < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
}

// ─── Categories ───
async function initCategories() {
    try {
        const resp = await fetch(`${API_BASE}/api/categories`);
        const data = await resp.json();
        Object.entries(data.subcategories).forEach(([cat, subs]) => { subcategories[cat] = subs; });
        updateSubcategories('chaussures');
    } catch (e) {
        subcategories['tops'] = ['t-shirt', 'chemise', 'polo', 'pull', 'sweat'];
        subcategories['pantalons'] = ['jean', 'pantalon', 'chino', 'short'];
        subcategories['vestes'] = ['manteau', 'blouson', 'blazer', 'doudoune'];
        subcategories['chaussures'] = ['basket', 'sneakers', 'botte', 'sandale'];
        subcategories['sacs'] = ['sac a main', 'sacoche', 'besace'];
        subcategories['accessoires'] = ['montre', 'ceinture', 'lunettes', 'bijou'];
        subcategories['sport'] = ['running', 'survetement', 'fitness', 'gym', 'training'];
        subcategories['enfants'] = ['bebe', 'enfant', 'kids'];
        updateSubcategories('chaussures');
    }

    $$('.cat-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            $$('.cat-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            updateSubcategories(btn.dataset.cat);
        });
    });
}

function updateSubcategories(category) {
    subSelect.innerHTML = '<option value="">Tous les types</option>';
    const subs = subcategories[category] || [];
    subs.forEach(sub => {
        const opt = document.createElement('option');
        opt.value = sub;
        opt.textContent = sub.charAt(0).toUpperCase() + sub.slice(1);
        subSelect.appendChild(opt);
    });
}

// ─── Price Range ───
function updateRange() {
    let vmin = parseFloat(minPrice.value);
    let vmax = parseFloat(maxPrice.value);
    if (vmin >= vmax) {
        if (minPrice === document.activeElement) { vmax = Math.min(vmin + 1, 500); maxPrice.value = vmax; }
        else { vmin = Math.max(vmax - 1, 0); minPrice.value = vmin; }
    }
    const pctMin = (vmin / 500) * 100;
    const pctMax = (vmax / 500) * 100;
    rangeFill.style.left = pctMin + '%';
    rangeFill.style.width = (pctMax - pctMin) + '%';
    priceLabel.textContent = `${vmin} € — ${vmax} €`;
}

minPrice.addEventListener('input', updateRange);
maxPrice.addEventListener('input', updateRange);

// ─── Clear ───
clearBtn.addEventListener('click', () => {
    resultsList.classList.add('hidden');
    emptyState.classList.remove('hidden');
    $('#summaryCards').classList.add('hidden');
    clearBtn.classList.remove('visible');
    resultCount.textContent = '';
});

// ─── Analyze ───
analyzeBtn.addEventListener('click', doAnalyze);

let loadingPhaseInterval = null;

async function doAnalyze() {
    if (isAnalyzing) return;
    isAnalyzing = true;

    const activeCat = $('.cat-btn.active');
    const category = activeCat ? activeCat.dataset.cat : 'chaussures';
    const subcategory = subSelect.value;
    const brands = brandInput.value || 'Nike,Adidas,Saucony';
    const minP = parseFloat(minPrice.value);
    const maxP = parseFloat(maxPrice.value);

    analyzeBtn.disabled = true;
    analyzeBtn.querySelector('.btn-text').textContent = 'Analyse...';
    loadingState.classList.remove('hidden');
    emptyState.classList.add('hidden');
    resultsList.classList.add('hidden');
    $('#summaryCards').classList.add('hidden');
    clearBtn.classList.remove('visible');

    // Loading phases animation
    const phases = $$('.phase');
    let phaseIdx = 0;
    loadingPhaseInterval = setInterval(() => {
        phases.forEach(p => p.classList.remove('active'));
        phases[phaseIdx % phases.length].classList.add('active');
        phaseIdx++;
    }, 800);

    try {
        const params = new URLSearchParams({
            category, subcategory, brands,
            min_price: minP, max_price: maxP,
            pages: 3, sort_by: 'profit'
        });

        const resp = await fetch(`${API_BASE}/api/analyze?${params}`);

        if (!resp.ok) {
            const err = await resp.json().catch(() => ({ detail: 'Erreur serveur' }));
            throw new Error(err.detail || 'Erreur inconnue');
        }

        const data = await resp.json();
        credits++;
        creditsDisplay.textContent = credits;
        showToast('Analyse terminée avec succès ✅');

        clearInterval(loadingPhaseInterval);
        renderResults(data);
    } catch (err) {
        clearInterval(loadingPhaseInterval);
        loadingState.classList.add('hidden');
        emptyState.classList.remove('hidden');
        emptyState.innerHTML = `
            <div class="empty-graphic">
                <svg width="60" height="60" viewBox="0 0 24 24" fill="none" stroke="#ff5252" stroke-width="1.5">
                    <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
                </svg>
            </div>
            <h3 class="empty-title" style="color:var(--red)">Erreur</h3>
            <p class="empty-desc">${err.message}</p>
        `;
        showToast('Erreur : ' + err.message, 'error');
    } finally {
        isAnalyzing = false;
        analyzeBtn.disabled = false;
        analyzeBtn.querySelector('.btn-text').textContent = 'Analyser le marché';
    }
}

// ─── Render Results ───
function renderResults(data) {
    loadingState.classList.add('hidden');
    resultsList.classList.remove('hidden');
    $('#summaryCards').classList.remove('hidden');
    clearBtn.classList.add('visible');

    // Animated counters
    animateCounter(scanCount, data.total_items_scanned);
    animateCounter(oppCount, data.total_opportunities);
    animateValue(avgMargin.querySelector('.counter'), 0, data.average_margin, 800, '%');
    animateValue(avgProfit.querySelector('.counter'), 0, data.average_profit, 800, ' €');

    resultCount.textContent = data.product_analyzed + ' produits';

    // Hero stats
    animateValue(statsScanned, 0, data.total_items_scanned, 1000, '');
    animateValue(statsDeals, 0, data.total_opportunities, 1000, '');
    animateValue(statsMargin, 0, data.average_margin, 1000, '%');

    resultsList.innerHTML = '';

    if (!data.results || data.results.length === 0) {
        resultsList.innerHTML = `
            <div class="empty-state" style="padding:32px">
                <div class="empty-graphic">🔍</div>
                <h3 class="empty-title">Aucune opportunité</h3>
                <p class="empty-desc">Élargis ta recherche ou change de catégorie</p>
            </div>`;
        return;
    }

    data.results.forEach((group, gi) => {
        const div = document.createElement('div');
        div.className = 'product-group';
        div.style.animationDelay = `${gi * 0.06}s`;

        const opportunitiesHtml = group.opportunities.map((o, oi) => renderOpportunityCard(o, oi)).join('');

        div.innerHTML = `
            <div class="product-header" onclick="this.nextElementSibling.classList.toggle('hidden')">
                <div class="product-info">
                    <div class="product-brand">${esc(group.brand)}</div>
                    <div class="product-name">${esc(group.product)}</div>
                </div>
                <div class="product-metrics">
                    <div class="metric">
                        <div class="metric-value">${group.avg_price} €</div>
                        <div class="metric-label">Prix moy.</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value positive">${group.avg_margin}%</div>
                        <div class="metric-label">Marge moy.</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value positive">${group.avg_profit} €</div>
                        <div class="metric-label">Profit moy.</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">${group.sample_size}</div>
                        <div class="metric-label">Éch.</div>
                    </div>
                </div>
            </div>
            <div class="product-opportunities">${opportunitiesHtml}</div>
        `;

        resultsList.appendChild(div);
    });
}

function renderOpportunityCard(o, idx) {
    const pc = o.profit_estimation > 0 ? 'positive' : 'negative';
    const bg = o.margin_percentage > 20 ? 'rgba(0,200,83,0.12)' : 'rgba(255,171,0,0.12)';
    const c = o.margin_percentage > 20 ? 'var(--green)' : 'var(--orange)';

    const img = o.photo
        ? `src="${esc(o.photo)}" onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%2248%22 height=%2248%22><rect fill=%22%231a1a2e%22 width=%2248%22 height=%2248%22/><text fill=%22%239898b0%22 font-size=%2218%22 x=%2212%22 y=%2232%22>?</text></svg>'"`
        : `src="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%2248%22 height=%2248%22><rect fill=%22%231a1a2e%22 width=%2248%22 height=%2248%22/><text fill=%22%239898b0%22 font-size=%2218%22 x=%2212%22 y=%2232%22>?</text></svg>"`;

    return `
        <div class="opp-card" style="animation-delay:${idx * 0.04}s">
            <img class="opp-img" ${img} alt="${esc(o.title)}" loading="lazy">
            <div class="opp-info">
                <div class="opp-title">${esc(o.title)}</div>
                <div class="opp-details">
                    <span>${esc(o.size || 'N/A')}</span>
                    <span>•</span>
                    <span>${esc(o.condition || 'N/A')}</span>
                </div>
            </div>
            <div class="opp-prices">
                <div class="opp-buy">Achat: ${o.price} €</div>
                <div class="opp-sell">Revente: ${o.resale_estimation} €</div>
            </div>
            <div class="opp-profit">
                <div class="opp-profit-value ${pc}">${o.profit_estimation > 0 ? '+' : ''}${o.profit_estimation} €</div>
                <div class="opp-profit-margin" style="background:${bg};color:${c}">${o.margin_percentage}%</div>
            </div>
            <a class="opp-link" href="${o.url}" target="_blank" rel="noopener" title="Voir sur Vinted">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
                    <polyline points="15 3 21 3 21 9"/>
                    <line x1="10" y1="14" x2="21" y2="3"/>
                </svg>
            </a>
        </div>`;
}

function esc(s) {
    if (!s) return '';
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
}

// ─── Init ───
initBackground();
initCategories();
updateRange();

// Keyboard shortcut
document.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && e.target.tagName !== 'TEXTAREA' && e.target.tagName !== 'INPUT' && e.target.tagName !== 'SELECT') {
        doAnalyze();
    }
});
