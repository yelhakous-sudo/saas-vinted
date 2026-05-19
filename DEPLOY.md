# VintedPro SaaS - Analyseur de Marge

## Architecture
```
saas-vinted/
├── backend/          # Python FastAPI → déploiement Railway/Render
│   ├── main.py
│   ├── Procfile
│   ├── runtime.txt
│   └── requirements.txt
└── frontend/         # Static HTML/CSS/JS → déploiement Netlify
    ├── index.html
    ├── styles.css
    ├── app.js
    ├── config.js
    └── netlify.toml
```

## Déploiement

### 1. Backend (Railway)

```bash
cd backend
```

1. Crée un compte sur **railway.app**
2. `New Project` → `Deploy from GitHub repo`
3. Ajoute `backend/` comme root directory
4. Railway détecte automatiquement `requirements.txt` + `Procfile`
5. Déploiement automatique

### 2. Backend (Render - alternative)

1. Crée un compte sur **render.com**
2. `New Web Service` → connecte ton GitHub
3. Root directory: `backend`
4. Runtime: `Python 3`
5. Build command: `pip install -r requirements.txt`
6. Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`

### 3. Configurer l'URL backend

Une fois le backend déployé, copie son URL (ex: `https://ton-backend.railway.app`)

Modifie `frontend/config.js` :
```js
const API_URL = 'https://ton-backend.railway.app';
```

### 4. Frontend (Netlify)

1. Crée un compte sur **netlify.com**
2. `Add new site` → `Import existing project`
3. Connecte ton GitHub
4. `Publish directory`: `frontend`
5. Déploiement automatique

Le `netlify.toml` redirige les appels `/api/*` vers le backend.

### 5. Option tout-en-un (Railway seulement)

Tu peux aussi déployer le projet entier sur Railway :
1. Root directory: `.`
2. Start command: `cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT`

## Développement local

```powershell
.\start.ps1
```

Accès : http://localhost:8001/
