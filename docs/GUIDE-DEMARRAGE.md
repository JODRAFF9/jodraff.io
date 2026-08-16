# Guide de démarrage

## Prérequis

| Pile | Nécessaire |
|---|---|
| Python (dashboard, API, CLI) | Python ≥ 3.10 |
| R (dashboard Shiny) | R ≥ 4.1 |
| Angular | Node.js ≥ 20.19 ou ≥ 22.12 |
| Front web | rien, un navigateur suffit |

La base de données est **SQLite** : aucun serveur à installer.

---

## 1. Plateforme Python

```bash
cd python
pip install -r requirements.txt
```

### Dashboard Dash

```bash
python -m dash_app.app
```

→ <http://127.0.0.1:8050>. Au premier lancement, l'écran d'accueil demande le type
de boutique et son nom ; l'ERP est généré puis le tableau de bord s'ouvre.

### API REST

```bash
uvicorn api.main:app --port 8000 --reload
```

→ Documentation interactive sur <http://127.0.0.1:8000/docs>.

### Ligne de commande

```bash
python cli.py types                                  # les métiers disponibles
python cli.py create "Chez Aminata" supermarche      # génération avec barre de progression
python cli.py create "Pharmacie du Plateau" pharmacie --months 24 --currency EUR
python cli.py stats                                  # indicateurs consolidés
python cli.py reset                                  # vider la base
```

---

## 2. Front web (HTML / CSS / JavaScript)

Il consomme l'API : démarrez-la d'abord.

```bash
cd python && uvicorn api.main:app --port 8000    # terminal 1
cd web     && python3 -m http.server 8080        # terminal 2
```

→ <http://127.0.0.1:8080>

Pour pointer vers une API distante : `http://127.0.0.1:8080/?api=https://mon-api.example`

Aucune étape de build, aucune dépendance, aucun CDN : les graphiques SVG sont
écrits à la main dans `web/js/charts.js`. La page fonctionne hors ligne.

---

## 3. Application Angular

```bash
cd angular
npm install
npm start                    # http://localhost:4200
```

Construction pour la production :

```bash
npm run build                # dist/erp-boutique/browser  (~77 kB initial)
```

Le résultat est un site statique : servez-le derrière n'importe quel serveur web.
L'URL de l'API se surcharge de la même manière : `?api=https://mon-api.example`.

---

## 4. Dashboard R Shiny

```bash
cd shiny
Rscript install.R                                        # shiny, bslib, DBI, RSQLite, jsonlite, plotly, DT
Rscript -e "shiny::runApp('.', port = 3838, launch.browser = FALSE)"
```

→ <http://127.0.0.1:3838>

Depuis RStudio : ouvrir `shiny/app.R`, puis **Run App**.

---

## Variables d'environnement

| Variable | Défaut | Usage |
|---|---|---|
| `ERP_DB_PATH` | `data/erp.db` | emplacement de la base SQLite |
| `ERP_SHARED_DIR` | `shared/` | catalogue des métiers, schéma SQL, thème |
| `ERP_PORT` / `ERP_HOST` | `8050` / `127.0.0.1` | dashboard Dash |
| `ERP_API_PORT` / `ERP_API_HOST` | `8000` / `127.0.0.1` | API REST |

Faire pointer plusieurs interfaces sur **la même base** est le mode d'emploi normal :

```bash
export ERP_DB_PATH=/var/lib/erp/boutique.db
```

Le dashboard R, le dashboard Python et l'API liront alors le même fichier, et une
vente enregistrée dans l'un apparaîtra dans les autres au rafraîchissement.

---

## Ajouter un nouveau métier

Tout se passe dans `shared/store_types.json`. Ajoutez une entrée sous `types` :

```json
"librairie": {
  "label": "Librairie / Papeterie",
  "icon": "📚",
  "tagline": "Rotation lente, saisonnalité scolaire, nombreuses références.",
  "tax_rate": 0.055,
  "margin_target": 0.35,
  "daily_tickets": 60,
  "basket_lines": [1, 4],
  "seasonality": [0.8, 0.85, 0.9, 0.95, 1.0, 0.9, 0.85, 1.6, 1.4, 1.0, 1.05, 1.3],
  "roles": [{ "title": "Libraire", "department": "Ventes", "salary": 180000 }],
  "suppliers": ["Hachette Distribution", "Papeterie du Centre"],
  "expense_lines": ["Loyer", "Électricité", "Marketing"],
  "categories": [
    {
      "name": "Scolaire",
      "products": [
        { "name": "Cahier 96 pages", "unit": "pièce", "cost": 250, "price": 450 }
      ]
    }
  ]
}
```

Le métier apparaît immédiatement dans **les quatre écrans d'accueil** : celui du
dashboard R, celui du dashboard Python, celui du front web et celui d'Angular.
Aucun code à modifier.

Points d'attention :

- `seasonality` doit contenir **12 coefficients** (janvier → décembre), centrés sur 1.
- `daily_tickets` est le nombre de tickets un jour moyen ; il est ensuite modulé par
  la saisonnalité, le jour de la semaine et l'intensité choisie à l'onboarding.
- Les prix s'expriment en francs CFA ; ils sont convertis automatiquement dans la
  devise retenue via le facteur `scale` défini dans `currencies`.

---

## Changer la palette

`shared/theme.json` contient tous les jetons. Si vous substituez vos propres
couleurs de série, vérifiez qu'elles restent distinguables :

- clarté comparable entre les huit teintes ;
- séparation suffisante pour les daltonismes sur les **paires adjacentes** ;
- contraste ≥ 3:1 avec la surface, sinon prévoir des étiquettes directes visibles.

Les couleurs de statut (`good`, `warning`, `serious`, `critical`) doivent rester
distinctes des couleurs de série : elles signalent un état, pas une catégorie.

---

## Mise en production

**Dashboard Dash**, servir via un serveur WSGI :

```bash
gunicorn "dash_app.app:server" --bind 0.0.0.0:8050 --workers 2
```

**API REST** :

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 2
```

Restreindre les origines autorisées dans `api/main.py` (`allow_origins`) avant toute
exposition publique : la valeur `["*"]` livrée convient au développement, pas à une
mise en ligne.

**Front web et Angular**, ce sont des fichiers statiques (`web/`,
`angular/dist/erp-boutique/browser/`) : n'importe quel serveur web fait l'affaire.

**Dashboard Shiny**, Shiny Server, ou :

```bash
Rscript -e "shiny::runApp('shiny', host = '0.0.0.0', port = 3838)"
```

**Base de données**, sauvegarder le fichier pointé par `ERP_DB_PATH`. Avec le mode
WAL, sauvegarder aussi les fichiers `-wal` et `-shm`, ou passer par
`sqlite3 base.db ".backup sauvegarde.db"`.

---

## Dépannage

| Symptôme | Cause probable | Solution |
|---|---|---|
| « API injoignable » sur le front web | l'API n'est pas lancée | `cd python && uvicorn api.main:app --port 8000` |
| « Catalogue introuvable » | dossier `shared/` non trouvé | définir `ERP_SHARED_DIR` |
| L'écran d'accueil revient sans cesse | base vide ou non accessible en écriture | vérifier les droits sur `ERP_DB_PATH` |
| Génération très lente | supermarché + 24 mois + forte affluence | réduire l'historique ou l'intensité dans les options avancées |
| `ng build` échoue sur la version de Node | Angular exige Node ≥ 20.19 / ≥ 22.12 | mettre Node à jour |
| Erreur de package R au lancement | dépendances manquantes | `Rscript install.R` |
