# VintedPro SaaS - Déploiement

## Architecture actuelle
```
saas-vinted/
├── backend/          # Python FastAPI (avec DB + Auth)
│   ├── main.py, database.py, models.py, auth.py, schemas.py
│   ├── Procfile, runtime.txt, requirements.txt
│   └── data/         # SQLite (persistant)
├── frontend/         # Static HTML/CSS/JS
│   ├── index.html, styles.css, app.js, config.js
│   └── netlify.toml
├── Dockerfile
├── docker-compose.yml
└── start.ps1
```

**Important** : le backend sert aussi le frontend statiquement. Tu n'as plus besoin de déployer le frontend séparément.

---

## Option 1 : Docker (recommandé, le plus simple)

```bash
# 1. Build & lance
docker compose up -d

# 2. Accès : http://localhost:8001

# 3. Pour arrêter
docker compose down
```

Le volume `./backend/data` est persistant (ta DB reste après redémarrage).

---

## Option 2 : Railway / Render

### Railway
1. Crée un compte sur **railway.app**
2. `New Project` → `Deploy from GitHub repo`
3. Root directory: **`saas-vinted`** (la racine du projet)
4. Start command : `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
5. Ajouter une variable d'environnement : `JWT_SECRET=une-chaine-aleatoire-securisee`

### Render
1. Crée un compte sur **render.com**
2. `New Web Service` → connecte ton GitHub
3. Root directory: **`saas-vinted`**
4. Runtime: `Python 3`
5. Build command: `pip install -r backend/requirements.txt`
6. Start command: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
7. Ajouter `JWT_SECRET` en variable d'environnement

### Render avec le Procfile
Si Render détecte le `backend/Procfile` :
```
web: uvicorn backend.main:app --host 0.0.0.0 --port $PORT
```

---

## Option 3 : Docker personnalisé

```bash
# Build
docker build -t vintedpro .

# Run
docker run -d -p 8001:8001 -e JWT_SECRET=mon-secret --name vintedpro vintedpro
```

---

## Variables d'environnement

| Variable | Obligatoire | Défaut |
|----------|-------------|--------|
| `JWT_SECRET` | Non (mais recommandé en prod) | `vintedpro-super-secret-key-change-in-production` |
| `VINTED_PROXIES` | Non | Rotation automatique des User-Agents seulement |

Exemple avec proxies :
```
VINTED_PROXIES=http://proxy1:8080,http://proxy2:8080
```

---

## Déploiement frontend séparé (optionnel)

Si tu veux vraiment séparer frontend/backend (Netlify + Railway) :

1. Déploie le backend sur Railway (option 2)
2. Modifie `frontend/config.js` :
```js
const API_URL = 'https://ton-backend.railway.app';
```
3. Déploie `frontend/` sur Netlify :
   - `Add new site` → `Import existing project`
   - Publish directory: `frontend`
   - Le `netlify.toml` redirige `/api/*` vers ton backend
