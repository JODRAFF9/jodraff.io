# Journal des versions

## v1.0.0 — première version

Plateforme complète : à partir du **type de commerce** et du **nom de l'enseigne**,
elle génère un ERP de gestion de boutique — ventes, stock, achats, clients,
ressources humaines et finance — avec un historique d'activité déjà consolidé.

### Le principe : des données de départements centralisées

Une seule base SQL. Les règles qui relient les départements vivent dans la base,
sous forme de triggers, et non dans le code applicatif :

| Écriture | Propagation automatique |
|---|---|
| une ligne de vente | mouvement de stock sortant, décrément du produit, totaux HT/TVA/TTC, coût des marchandises vendues |
| une vente encaissée | points de fidélité du client |
| une ligne d'achat reçue | entrée en stock, coût de revient moyen lissé |
| une commande passée à « reçue » | entrée en stock de toutes ses lignes + journal d'audit |
| inventaire, perte, retour | ajustement du niveau de stock |

Les cinq interfaces affichent donc toujours les mêmes chiffres : aucune ne
recalcule quoi que ce soit de son côté.

### Interfaces

- **Dashboard R Shiny** (`shiny/`) — bslib, plotly, DT ; un module par département.
- **Dashboard Python** (`python/dash_app/`) — Plotly Dash, 7 pages, CSS autonome
  sans CDN.
- **API REST** (`python/api/`) — FastAPI, une trentaine de routes documentées.
- **Front web** (`web/`) — HTML / CSS / JavaScript sans aucune dépendance,
  graphiques SVG écrits à la main, fonctionne hors ligne.
- **Application Angular** (`angular/`) — Angular 21, composants standalone,
  signals, routes paresseuses, TypeScript strict.
- **Ligne de commande** (`python/cli.py`) — création, statistiques, remise à zéro.

### Ressources partagées

- `shared/schema.sql` — 16 tables, 5 triggers, 9 vues consolidées, colonnes
  générées, index.
- `shared/store_types.json` — 7 métiers (supermarché, pharmacie, quincaillerie,
  mode, électronique, restaurant, boutique générale) avec rayons, produits,
  fournisseurs, rôles, saisonnalité et structure de coûts. Ajouter un métier ici
  suffit à le faire apparaître dans les quatre écrans d'accueil.
- `shared/theme.json` — jetons de design communs ; palette catégorielle validée
  (bande de clarté, plancher de chroma, séparation daltonisme ΔE ≥ 8 sur paires
  adjacentes, plancher vision normale ΔE ≥ 15).

Six devises : XOF, XAF, MAD, EUR, USD, CAD.

### Vérifications

- Génération testée sur les **7 métiers** et 3 devises.
- Intégrité SQL contrôlée (`integrity_check`, `foreign_key_check`), cohérence
  **stock = somme des mouvements** et **sous-total de vente = somme des lignes**
  vérifiée sur 130 000 lignes.
- Propagation des triggers vérifiée par l'API : commande créée (stock inchangé)
  → réception (+25) → perte (−3), avec trace dans le journal d'audit.
- Dashboard Dash, front web et application Angular ouverts dans un navigateur :
  les 7 pages rendues, parcours d'onboarding complet joué, aucune erreur console.
- Build Angular réussi : 77 kB initial, un bundle paresseux par département.

### Limites connues

- **Le code R Shiny n'a pas été exécuté** : R n'était pas installé dans
  l'environnement de développement. Sa logique reproduit celle du générateur
  Python, qui est testé, et ses requêtes s'appuient sur les mêmes vues SQL — mais
  un premier lancement mérite d'être surveillé (`shiny/install.R` pose les
  dépendances).
- **Angular est en version 21** et non 22 : la 22 exige Node ≥ 22.22.3, contre
  22.22.2 disponible lors du développement.
- **Pas d'authentification** : la plateforme génère des tableaux de bord, ce n'est
  pas un logiciel de caisse en production.
- **SQLite** supporte plusieurs lecteurs et un écrivain (mode WAL). Pour un
  déploiement multi-caisses, porter le schéma sur PostgreSQL — il est écrit en SQL
  proche du standard.
