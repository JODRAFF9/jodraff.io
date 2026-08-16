# Architecture

## L'idée directrice

Un ERP est d'abord un problème de **partage de données**, pas d'écrans. Un magasin
qui tient son stock dans un tableur, ses ventes dans une caisse et sa comptabilité
chez un tiers passe son temps à réconcilier trois vérités divergentes.

Cette plateforme applique la règle inverse : **une seule base, une seule vérité**.
Chaque département écrit dans les mêmes tables, et les règles qui relient les
départements vivent dans la base, pas dans l'application.

Conséquence directe : il existe quatre interfaces (R Shiny, Python Dash, front web
JavaScript, application Angular) et **aucune ne détient de logique métier propre**.
Elles affichent ce que la base calcule.

---

## Le modèle de données

`shared/schema.sql`, un seul fichier, appliqué à l'identique par toutes les
interfaces (`CREATE ... IF NOT EXISTS`, donc rejouable sans risque).

### Tables

| Domaine | Tables |
|---|---|
| Identité | `company` (ligne unique), `departments`, `app_meta` |
| Référentiels | `categories`, `products`, `suppliers`, `customers`, `employees` |
| Ventes | `sales`, `sale_items` |
| Achats | `purchases`, `purchase_items` |
| Stock | `stock_moves` (journal signé : + entrée / − sortie) |
| Finance | `expenses`, `payroll` |
| Traçabilité | `audit_log` |

Deux choix structurants :

- **`stock_moves` est un journal, pas un état.** Le niveau de stock d'un produit est
  la conséquence de ses mouvements. `products.stock` n'est qu'un cache maintenu par
  les triggers, ce qui garde les lectures rapides sans perdre l'historique.
- **`sale_items.line_total` est une colonne générée** (`quantity * unit_price - discount`,
  `STORED`). Le total d'une ligne ne peut pas diverger de ses composantes.

### Les triggers : la centralisation en action

| Trigger | Déclencheur | Effet |
|---|---|---|
| `trg_sale_item_insert` | ligne de vente insérée | mouvement de stock sortant, décrément du produit, mise à jour du sous-total, de la TVA, du TTC et du coût des marchandises de la vente |
| `trg_purchase_item_insert` | ligne d'achat insérée | si la commande est **reçue** : entrée en stock et lissage du coût de revient (70 / 30) ; total de la commande dans tous les cas |
| `trg_purchase_received` | commande passée à « reçue » | entrée en stock de toutes ses lignes + écriture dans `audit_log` |
| `trg_stock_move_manual` | inventaire, perte, retour | ajustement du niveau de stock |
| `trg_sale_loyalty` | total d'une vente mis à jour | points de fidélité du client |

C'est ce qui rend la démonstration vérifiable : une commande créée au statut
« commandée » ne bouge pas le stock ; la passer à « reçue » l'incrémente, sans
qu'aucun code Python, R ou TypeScript n'intervienne.

### Les vues : la lecture consolidée

| Vue | Ce qu'elle répond |
|---|---|
| `v_products` | catalogue enrichi : marge unitaire, taux, valeur du stock, état (`ok`/`faible`/`alerte`/`rupture`) |
| `v_sales_daily`, `v_sales_monthly` | chiffre d'affaires, marge brute, panier moyen par jour et par mois |
| `v_product_performance` | quantités, chiffre d'affaires et marge par produit |
| `v_stock_alerts` | ce qu'il faut commander, avec quantité suggérée, coût et fournisseur |
| `v_customer_value` | valeur vie, fréquence, ancienneté du dernier achat |
| `v_employee_performance` | jointure RH × Ventes : salaire d'un côté, tickets et CA de l'autre |
| `v_financial_monthly` | compte de résultat mensuel : CA, coût des marchandises, charges, paie, résultat |
| `v_department_dashboard` | un indicateur phare par département, la vue « données centrées » |

Ces vues sont le contrat entre la base et les interfaces. Le front web et le
dashboard R affichent la même colonne `net_result` ; elle n'est calculée qu'une fois.

---

## Le générateur

C'est le cœur de la « plateforme » : transformer **type + nom** en entreprise
complète. Implémenté deux fois, `python/erp/generator.py` et
`shiny/R/generator.R`, avec la même logique, pour que chaque pile reste autonome.

L'enchaînement est **chronologique**, et c'est ce qui rend les données crédibles :

1. **Référentiels**, rayons, produits (prix convertis dans la devise choisie),
   fournisseurs, personnel selon les métiers du secteur, fichier clients segmenté.
2. **Stock initial**, une commande d'ouverture couvrant 16 à 55 jours de vente
   selon une politique d'approvisionnement tirée *par article*.
3. **Ventes, jour par jour**, le nombre de tickets dépend de la saisonnalité du
   métier, du jour de la semaine, d'une croissance douce et d'un aléa. Les
   quantités par ligne sont corrélées au prix : on n'achète pas un téléviseur
   comme on achète du savon.
4. **Réapprovisionnement mensuel**, l'acheteur commande sur la base du **mois
   précédent** et du stock simulé à cet instant. Ce décalage est délibéré : il
   produit naturellement des surstocks et des ruptures à piloter, au lieu d'une
   base parfaite et sans intérêt.
5. **Pertes et inventaires**, puis **charges et paie**, les charges de structure
   sont calées sur la **marge brute** du mois, jamais sur le chiffre d'affaires :
   une activité à 18 % de marge (électronique) ne supporte pas la structure de
   coûts d'une activité à 52 % (mode).

Résultat, sur 12 mois d'historique :

| Métier | Tickets | Panier moyen | Résultat / CA | Ruptures | Alertes |
|---|---|---|---|---|---|
| Mode | 24 000 | 70 k FCFA | 31 % | 3 | 2 / 19 |
| Supermarché | 77 000 | 27 k FCFA | 15 % | 1 | 4 / 22 |
| Pharmacie | 41 000 | 17 k FCFA | 22 % | 0 | 5 / 19 |
| Quincaillerie | 19 000 | 66 k FCFA | 16 % | 3 | 7 / 21 |
| Électronique | 17 000 | 165 k FCFA | 11 % | 0 | 6 / 19 |

La génération prend de 1,5 s (électronique) à 14 s (supermarché, 250 000 lignes de
vente) sur la pile Python.

---

## Comment les interfaces se branchent

### Accès direct à la base

- **`python/erp/`**, `database.py` (connexion, schéma, helpers), `queries.py`
  (une trentaine de fonctions métier renvoyant des `list[dict]`). Le dashboard Dash
  et l'API REST consomment tous deux `queries.py` : les mêmes chiffres, un seul code.
- **`shiny/R/`**, `db.R` et `queries.R` jouent le même rôle avec DBI/RSQLite. Les
  requêtes sont volontairement identiques : elles s'appuient sur les vues SQL, donc
  il n'y a rien à réimplémenter.

### Accès par l'API

`python/api/main.py` expose une trentaine de routes REST documentées
(`http://127.0.0.1:8000/docs`) :

| Route | Rôle |
|---|---|
| `GET /api/health` | la boutique est-elle configurée ? |
| `GET /api/store-types` | catalogue des métiers et devises (alimente l'écran d'accueil) |
| `POST /api/company` | **crée l'ERP** à partir du type et du nom |
| `GET /api/overview?days=30` | consolidation tous départements |
| `GET /api/sales|stock|purchasing|customers|hr|finance` | un département |
| `POST /api/sales` | enregistre une vente (les triggers font le reste) |
| `POST /api/stock/moves` | inventaire, perte, retour |
| `POST /api/purchases`, `POST /api/purchases/{id}/receive` | commande puis réception |

Le front `web/` et l'application `angular/` ne parlent qu'à cette API.

---

## Les quatre interfaces comparées

| | R Shiny | Python Dash | Web JS | Angular |
|---|---|---|---|---|
| Rendu | serveur | serveur | client | client |
| Graphiques | plotly | plotly | SVG maison | SVG dans le gabarit |
| Tableaux | DT | dash_table | HTML triable | composant générique |
| Accès données | DBI direct | sqlite3 direct | API REST | API REST |
| Build | aucun | aucun | aucun | `ng build` (77 kB initial) |
| Points forts | statistique, prototypage | intégration Python | zéro dépendance, hors ligne | typage strict, lazy loading |

Elles partagent : le catalogue des métiers, le schéma SQL, les jetons de design,
la structure de navigation et les libellés. Ce qui change est l'idiome, pas le
produit.

---

## Le système visuel

`shared/theme.json` centralise la palette. Elle a été **validée**, pas choisie à
l'œil : bande de clarté, plancher de chroma, séparation daltonisme sur les paires
adjacentes (ΔE ≥ 8 en OKLab ×100), plancher vision normale (ΔE ≥ 15).

Règles appliquées dans les quatre interfaces :

- couleurs de série assignées dans un **ordre fixe**, jamais recyclé, un filtre qui
  réduit le nombre de séries ne repeint pas les survivantes ;
- **jamais deux axes Y** : deux mesures d'échelles différentes donnent deux
  graphiques (voir « CA et tickets » dans le département Ventes) ;
- les couleurs de **statut** (rupture, alerte) sont réservées et toujours
  accompagnées d'une icône et d'un libellé, la couleur ne porte jamais seule
  l'information ;
- chaque graphique a sa **vue table** correspondante, triable ;
- répartitions en barres horizontales triées plutôt qu'en camemberts ;
- magnitudes en rampe mono-teinte clair → foncé, jamais en arc-en-ciel.

---

## Limites assumées

- **SQLite en écriture concurrente.** Le mode WAL supporte plusieurs lecteurs et un
  écrivain. Pour un déploiement multi-caisses, porter le schéma sur PostgreSQL, les triggers et les vues sont écrits en SQL proche du standard, la traduction est
  mécanique (principalement la syntaxe `CREATE TRIGGER`).
- **Pas d'authentification.** La plateforme est un générateur de tableaux de bord,
  pas un logiciel de caisse en production. Ajouter des comptes utilisateurs et des
  droits par département serait le prochain chantier.
- **Données synthétiques.** Les prix des catalogues sont plausibles mais indicatifs ;
  ils servent à démontrer la mécanique, pas à faire référence sur un marché.
- **Écart de version Angular.** Le projet est calé sur Angular 21 : la 22 exige
  Node ≥ 22.22.3, absent de l'environnement de développement.
- **Le CLI Angular ne rend pas toujours la main** après un build réussi. Le script
  de test le contourne en surveillant son journal, mais c'est un contournement.


---

## Comment on vérifie tout cela

`./scripts/run-tests.sh` rejoue le pipeline entier ; `.github/workflows/ci.yml`
fait la même chose à chaque poussée, en installant au préalable les paquets
Python, R et Node.

| Suite | Fichier | Ce qu'elle protège |
|---|---|---|
| Pipeline Python | `tests/test_pipeline.py` | schéma, triggers, générateur sur les 7 métiers, requêtes, API REST |
| Dashboard R | `tests/test_shiny.R` | chargement du dossier `R/`, générateur, modules d'interface, graphiques |
| Parité | `tests/parity_reference.py` + `tests/test_shiny.R` | **R et Python doivent lire les mêmes chiffres sur la même base** |

Les invariants vérifiés sur chaque base générée :

```
products.stock        ==  SUM(stock_moves.quantity)      par produit
sales.subtotal        ==  SUM(sale_items.line_total)     par vente
sales.total           ==  subtotal × (1 + taux de TVA)
net_result            ==  marge brute − charges − paie   par mois
SUM(stock × coût)     >   0                              stock global positif
MAX(sale_date)        <=  aujourd'hui                    pas d'écriture future
PRAGMA foreign_key_check et integrity_check              base saine
```

Le test de parité est le plus sévère du lot. Il crée une base avec la pile
Python, relève ses indicateurs, puis demande à la pile R de lire **le même
fichier** : chiffre d'affaires, marge, panier moyen, valeur de stock, effectif
et résultat doivent coïncider au centime. Une divergence signifierait qu'une des
deux piles a réimplémenté une règle au lieu de lire la vue SQL, exactement ce
que l'architecture cherche à empêcher.

Deux bugs ont été trouvés par cette démarche, tous deux côté R :

1. `theme.R` lisait `THEME` à l'évaluation du fichier, alors que Shiny charge le
   dossier `R/` avant `global.R`, d'où « objet 'THEME' introuvable » au premier
   lancement. Corrigé en déplaçant les ressources dans `R/aaa_shared.R`, qui ne
   dépend de rien et se charge en premier.
2. La boucle de réapprovisionnement retranchait la consommation du mois **avant**
   de passer commande, ce qui sous-commandait d'un mois entier et laissait un
   stock global négatif. Corrigé en rétablissant la chronologie du générateur
   Python. Le test `stock final positif` verrouille la régression.
