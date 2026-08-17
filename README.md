# ERP Boutique, plateforme de tableaux de bord de gestion

Une plateforme qui **génère l'ERP complet d'une boutique à partir de deux
informations** : le type de commerce et son nom.


L'utilisateur arrive sur un écran d'accueil, choisit « Supermarché », « Pharmacie »,
« Quincaillerie »… saisit le nom de son enseigne, et obtient immédiatement un
tableau de bord de gestion à la manière d'Odoo : ventes, stock, achats, clients,
ressources humaines et finance, avec un historique d'activité déjà consolidé,
cohérent et exploitable.

**Le principe central : les données des départements sont centralisées.**
Il n'existe qu'une seule base SQL. Une vente saisie au département Ventes décharge
le stock, alimente la fiche client et le compte de résultat *au même instant*,
parce que ce sont des triggers SQL qui propagent l'écriture, pas du code applicatif
dupliqué dans chaque interface.

---

## Quatre interfaces, une seule base

| Interface | Technologie | Dossier | Lancement |
|---|---|---|---|
| Dashboard R | **R Shiny** + bslib, plotly, DT | `shiny/` | `Rscript -e "shiny::runApp('shiny', port=3838)"` |
| Dashboard Python | **Plotly Dash** | `python/dash_app/` | `cd python && python -m dash_app.app` |
| API REST | **FastAPI** | `python/api/` | `cd python && uvicorn api.main:app --port 8000` |
| Front web | **HTML / CSS / JavaScript** (zéro dépendance) | `web/` | `cd web && python3 -m http.server 8080` |
| Application SPA | **Angular 21** + TypeScript | `angular/` | `cd angular && npm install && npm start` |

Les deux fronts web consomment l'API REST ; les deux dashboards attaquent la base
directement. Tous voient donc toujours **exactement les mêmes chiffres**.

```
                      ┌──────────────────────────────┐
                      │   shared/schema.sql          │
                      │   base SQLite unique         │
                      │   tables + triggers + vues   │
                      └──────────────┬───────────────┘
              ┌──────────────┬───────┴────────┬──────────────┐
              │              │                │              │
        ┌─────▼─────┐  ┌─────▼─────┐    ┌─────▼──────┐       │
        │ R Shiny   │  │ Dash      │    │ FastAPI    │       │
        │ (DBI)     │  │ (sqlite3) │    │ (REST)     │       │
        └───────────┘  └───────────┘    └─────┬──────┘       │
                                     ┌────────┴────────┐     │
                                ┌────▼────┐      ┌─────▼───┐ │
                                │ web/    │      │ angular/│ │
                                │ JS+SVG  │      │ TS SPA  │ │
                                └─────────┘      └─────────┘ │
                                                    cli.py ──┘
```

---

## Le pipeline, de bout en bout

Chaque étage a **un seul objectif**, et ne connaît que le contrat de l'étage
précédent. C'est ce découpage qui permet d'avoir quatre interfaces sans
dupliquer une seule règle de gestion.

```
    ┌──────────────────────────────────────────────────────────────────┐
    │  ENTRÉE UTILISATEUR                                              │
    │  « Supermarché »  +  « Chez Aminata »          ← tout part de là │
    └───────────────────────────┬──────────────────────────────────────┘
                                │
    ①  ONBOARDING ──────────────┴─── objectif : ne demander que l'essentiel
    │   Deux questions, pas un formulaire de paramétrage. Le reste a des
    │   valeurs par défaut (devise, ville, profondeur d'historique).
    │      shiny/R/mod_onboarding.R      python/dash_app/onboarding.py
    │      web/index.html                angular/…/onboarding.component.ts
    │
    ▼
    ②  CATALOGUE MÉTIER ────────────── objectif : décrire un commerce, pas coder
    │   Rayons, produits, prix, fournisseurs, métiers, saisonnalité, structure
    │   de coûts. Ajouter un métier = ajouter une entrée JSON.
    │      shared/store_types.json
    │
    ▼
    ③  GÉNÉRATEUR ──────────────────── objectif : rendre la simulation crédible
    │   Déroule le temps dans l'ordre : stock d'ouverture → ventes jour après
    │   jour → réappro sur le mois écoulé → pertes → charges et paie.
    │   L'acheteur ne connaît que le passé : d'où des ruptures et des surstocks
    │   à piloter, au lieu d'une base parfaite et sans intérêt.
    │      python/erp/generator.py       shiny/R/generator.R
    │
    ▼
    ④  BASE SQL CENTRALE ───────────── objectif : une seule vérité partagée
    │   16 tables. Les départements n'ont pas « leurs » données : ils écrivent
    │   tous dans les mêmes.
    │      shared/schema.sql  →  data/erp.db
    │
    ├─ ⑤ TRIGGERS ─────────────────── objectif : propager sans code applicatif
    │      vente      → sortie de stock + TVA + coût des marchandises
    │      encaissement → points de fidélité du client
    │      réception  → entrée en stock + coût de revient lissé + audit
    │      inventaire → ajustement du niveau
    │
    ├─ ⑥ VUES ─────────────────────── objectif : calculer une fois pour toutes
    │      v_products · v_sales_daily · v_sales_monthly · v_stock_alerts
    │      v_customer_value · v_employee_performance · v_financial_monthly
    │      v_product_performance · v_department_dashboard
    │
    ▼
    ⑦  COUCHE DE LECTURE ───────────── objectif : traduire les vues, rien de plus
    │      python/erp/queries.py        shiny/R/queries.R
    │   Aucune règle de gestion ici : que des SELECT sur les vues ci-dessus.
    │
    ├──────────────┬───────────────────┬──────────────────────────┐
    ▼              ▼                   ▼                          ▼
  ⑧ DASHBOARD    ⑧ DASHBOARD        ⑨ API REST ──────┬──────► ⑩ FRONT WEB
    R SHINY        PYTHON DASH         FastAPI       │           HTML/CSS/JS
    (DBI direct)   (sqlite3 direct)    ~30 routes    └──────► ⑩ ANGULAR 21
                                                                 TypeScript
    objectif : montrer.  Aucune de ces interfaces ne calcule un indicateur.
```

**Le contrat, en une phrase par étage.** ① ne demande que deux informations.
② décrit le métier en JSON. ③ déroule le temps. ④ stocke. ⑤ propage.
⑥ consolide. ⑦ traduit. ⑧⑨⑩ affichent.

Si un chiffre est faux, il n'y a qu'un seul endroit à corriger, et les quatre
interfaces sont corrigées ensemble.

---

## Objectif de chaque dossier

| Dossier | Objectif général |
|---|---|
| `shared/` | **Le contrat commun.** Ce que les quatre interfaces doivent partager pour ne jamais diverger : le modèle SQL, le catalogue des métiers, les jetons de design. |
| `python/erp/` | **Le noyau métier.** Créer une entreprise, lire la base, formater. Consommé par le dashboard Dash, l'API et la ligne de commande, écrit une fois. |
| `python/dash_app/` | **Le tableau de bord Python.** Sept pages, une par département, pour l'analyste qui travaille déjà en Python. |
| `python/api/` | **La porte d'entrée des clients web.** Exposer la base en REST pour que les fronts n'aient pas besoin d'un accès direct. |
| `python/cli.py` | **L'usage sans écran.** Préparer une base, consulter les indicateurs, réinitialiser, utile en démonstration comme en intégration continue. |
| `shiny/` | **Le tableau de bord R.** Même produit, idiome R : pour l'utilisateur qui vit dans RStudio. |
| `web/` | **La preuve par la simplicité.** Un ERP consultable sans build, sans dépendance et sans réseau. Les graphiques SVG y sont écrits à la main. |
| `angular/` | **La version applicative.** Typage strict, chargement paresseux par département : la forme qu'aurait le produit dans une équipe front. |
| `tests/` | **Le filet.** Vérifier que les triggers propagent, que les sept métiers restent cohérents, et que R et Python lisent les mêmes chiffres. |
| `scripts/` | **Une commande pour tout.** `./scripts/run-tests.sh` exécute le pipeline entier ; `--install` pose d'abord les dépendances. |
| `.github/workflows/` | **Le même pipeline, à chaque poussée.** Installe les paquets Python, R et Node, puis rejoue les tests. |
| `docs/` | **Le pourquoi.** Architecture, choix techniques, guide de démarrage et dépannage. |

---

## Tester le pipeline

```bash
./scripts/run-tests.sh              # tout ce qui est disponible sur la machine
./scripts/run-tests.sh --install    # installe d'abord Python, R et Node
```

Ce que la suite vérifie :

| Étage | Contrôles |
|---|---|
| Ressources partagées | JSON valides, schéma applicable, 5 triggers et 9 vues présents |
| Triggers | vente → stock, commande non reçue → stock intact, réception → stock + audit, inventaire, fidélité |
| Générateur | les 7 métiers, `stock = somme des mouvements`, `sous-total = somme des lignes`, stock final positif, aucune écriture datée dans le futur, conversion de devise |
| Requêtes | les ~30 fonctions métier répondent, résultat = marge − charges − paie |
| API REST | 409 sans boutique, création, les 13 routes de lecture, écritures, erreurs 404 et 422 |
| Pile R | chargement du dossier `R/` sans `global.R`, générateur, modules d'interface, graphiques |
| **Parité R / Python** | sur **la même base**, les deux piles doivent renvoyer les mêmes CA, marge, panier, stock et résultat |
| Fronts web | syntaxe JavaScript, compilation Angular en TypeScript strict |

La parité est le test le plus sévère : si les deux piles divergent d'un centime,
c'est qu'une des deux a réimplémenté une règle au lieu de lire la vue SQL.

---

## Démarrage rapide

### 1. La plateforme Python (dashboard complet, le plus rapide)

```bash
cd python
pip install -r requirements.txt
python -m dash_app.app          # http://127.0.0.1:8050
```

L'écran d'accueil demande le type de boutique et son nom ; l'ERP est généré en
quelques secondes.

### 2. Les fronts web (API + navigateur)

```bash
cd python && uvicorn api.main:app --port 8000     # terminal 1
cd web     && python3 -m http.server 8080         # terminal 2  -> http://127.0.0.1:8080
```

Ou l'application Angular :

```bash
cd angular && npm install && npm start            # http://localhost:4200
```

### 3. Le dashboard R Shiny

```bash
cd shiny
Rscript install.R
Rscript -e "shiny::runApp('.', port = 3838)"      # http://127.0.0.1:3838
```

### 4. En ligne de commande

```bash
cd python
python cli.py types                                   # les métiers disponibles
python cli.py create "Chez Aminata" supermarche       # génération
python cli.py stats                                   # indicateurs
```

---

## Les sept métiers livrés

| Métier | Rayons | Spécificités simulées |
|---|---|---|
| 🛒 Supermarché / Grande surface | 5 | forte rotation, pertes, panier large |
| 💊 Pharmacie / Parapharmacie | 5 | TVA nulle, marges réglementées, saisonnalité sanitaire |
| 🔩 Quincaillerie / Matériaux | 5 | ventes B2B, paniers lourds, saison sèche |
| 👗 Boutique de mode | 5 | forte marge, saisonnalité, fidélité client |
| 📱 Électronique & Téléphonie | 5 | faible marge, valeur unitaire élevée |
| 🍽️ Restaurant / Cafétéria | 5 | matières premières, services midi/soir |
| 🏪 Boutique générale | 4 | modèle polyvalent à adapter |

Ajouter un métier = ajouter une entrée dans `shared/store_types.json`. Il apparaît
aussitôt dans **les quatre interfaces**, sans toucher au code.

Six devises sont proposées (XOF, XAF, MAD, EUR, USD, CAD) ; les prix du catalogue
sont convertis et arrondis commercialement à la création.

---

## Les six départements

| Département | Ce qu'il pilote | Vues SQL |
|---|---|---|
| 🧾 **Ventes** | tickets, panier moyen, canaux, affluence, performance vendeurs | `v_sales_daily`, `v_sales_monthly` |
| 📦 **Stock** | niveaux, valorisation, rotation, alertes, mouvements | `v_products`, `v_stock_alerts` |
| 🚚 **Achats** | fournisseurs, commandes, plan de réapprovisionnement | `v_stock_alerts` |
| 👥 **Clients** | segments, valeur vie, fidélité, clients dormants | `v_customer_value` |
| 🧑‍💼 **RH** | effectif, masse salariale, paie, performance commerciale | `v_employee_performance` |
| 💰 **Finance** | compte de résultat, charges, marge, passage CA → résultat | `v_financial_monthly` |

Et la **vue d'ensemble**, qui consolide les six via `v_department_dashboard`.

---

## La centralisation, concrètement

Ce que fait la base toute seule, sans une ligne de code applicatif :

| Écriture | Propagation automatique |
|---|---|
| une ligne de vente | mouvement de stock sortant, décrément du produit, totaux HT/TVA/TTC de la vente, coût des marchandises vendues |
| une vente encaissée | points de fidélité du client |
| une ligne d'achat reçue | entrée en stock, coût de revient moyen lissé, total de la commande |
| une commande passée à « reçue » | entrée en stock de toutes ses lignes + trace dans le journal d'audit |
| un inventaire, une perte, un retour | ajustement du niveau de stock |
| tout ce qui précède | compte de résultat, valorisation, alertes de réapprovisionnement |

Vérifiable en trois appels d'API :

```bash
curl -s localhost:8000/api/products | head -c 200          # stock = 1311,8
curl -s -X POST localhost:8000/api/purchases -H 'Content-Type: application/json' \
     -d '{"supplier_id":1,"lines":[{"product_id":22,"quantity":25}]}'   # stock inchangé
curl -s -X POST localhost:8000/api/purchases/48/receive                 # stock = 1336,8
```

---

## Structure du dépôt

```
shared/            ressources communes à toutes les interfaces
  schema.sql         le modèle SQL : tables, index, 5 triggers, 9 vues
  store_types.json   catalogue des métiers (rayons, produits, rôles, fournisseurs)
  theme.json         jetons de design (palette validée, statuts, surfaces)

python/
  erp/               noyau : config, base, générateur, requêtes, thème
  dash_app/          dashboard Plotly Dash (7 pages, une par département)
  api/               API REST FastAPI (documentation sur /docs)
  cli.py             création et statistiques en ligne de commande

shiny/
  app.R, global.R    application Shiny
  R/                 base, générateur, requêtes, thème, graphiques, modules
  www/styles.css     feuille de style

web/                 front HTML/CSS/JS sans dépendance (graphiques SVG maison)
angular/             application Angular 21 (standalone, signals, lazy loading)
docs/                architecture et guide de démarrage
```

---

## Choix techniques

**Pourquoi SQLite ?** Zéro serveur à installer, un seul fichier partagé par cinq
processus, et un dialecte SQL assez riche pour porter la logique métier
(triggers, vues, colonnes générées). Le schéma est écrit en SQL proche du standard
pour faciliter un portage PostgreSQL ou MySQL.

**Pourquoi la logique métier dans la base ?** Parce qu'il y a quatre interfaces.
Toute règle écrite en Python devrait être réécrite en R et en TypeScript, avec la
dérive que cela implique. Écrite en SQL, elle est appliquée une fois pour toutes.

**Pourquoi des graphiques SVG écrits à la main dans `web/` ?** Pour que le front
fonctionne sans réseau, sans CDN et sans étape de build, et pour montrer la
mécanique là où Dash, plotly et Angular la masquent.

Le système visuel est partagé (`shared/theme.json`) et sa palette catégorielle a
été validée : bande de clarté, plancher de chroma, séparation daltonisme
(ΔE ≥ 8 sur les paires adjacentes), plancher vision normale (ΔE ≥ 15). Les couleurs
de statut sont réservées et toujours accompagnées d'un libellé.

**Charte appliquée aux quatre interfaces**, et vérifiée par les tests :

| Règle | Ce que cela donne | Test |
|---|---|---|
| Aucune teinte bleue | palette vert / orangé / violet / doré, quatre séries au plus | `aucune teinte bleue` |
| Aucune transparence | pas de `rgba()`, pas d'`opacity`, pas d'ombre portée ; le relief vient de filets pleins | `aucune transparence dans les styles` |
| Aucune émoticône | les métiers sont désignés par un monogramme encadré (`QC`, `PH`, `SM`), les états par un libellé | `aucune emoticone dans l interface` |
| Times New Roman partout | même police dans les pages, les tableaux et les graphiques | `typographie serif partout` |
| Écritures aérées | interligne 1,7 ; cellules de tableau 11 × 16 px ; gouttière de 18 px | revue visuelle |

---

## Documentation

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md), le modèle de données, les triggers,
  les vues, et comment les quatre interfaces s'y branchent.
- [`docs/GUIDE-DEMARRAGE.md`](docs/GUIDE-DEMARRAGE.md), installation détaillée,
  variables d'environnement, ajout d'un métier, mise en production.
