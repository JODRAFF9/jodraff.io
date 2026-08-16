#!/usr/bin/env bash
# =====================================================================
#  Pipeline de test complet, une seule commande.
#
#      ./scripts/run-tests.sh                 tout ce qui est disponible
#      ./scripts/run-tests.sh --install       installe d'abord les dépendances
#
#  Chaque étape est facultative : si R, Node ou une dépendance Python
#  manque, l'étape est signalée « ignorée » et le pipeline continue.
#  Seuls les échecs réels font échouer la commande.
# =====================================================================
set -uo pipefail

RACINE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$RACINE"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

ECHECS=()
IGNORES=()

titre()   { printf '\n\033[1m▸ %s\033[0m\n'    "$1"; }
succes()  { printf '  \033[32m✓ %s\033[0m\n'   "$1"; }
echec()   { printf '  \033[31m✗ %s\033[0m\n'   "$1"; ECHECS+=("$1"); }
ignore()  { printf '  \033[33m− %s\033[0m\n'   "$1"; IGNORES+=("$1"); }

# ---------------------------------------------------------------------
# Installation des dépendances (option --install)
# ---------------------------------------------------------------------
if [[ "${1:-}" == "--install" ]]; then
  titre "Installation des dépendances"

  if command -v python3 > /dev/null; then
    python3 -m pip install --quiet -r python/requirements.txt && succes "paquets Python" \
      || echec "installation des paquets Python"
    python3 -m pip install --quiet httpx > /dev/null 2>&1 && succes "client de test HTTP" || true
  else
    ignore "Python absent"
  fi

  if command -v Rscript > /dev/null; then
    Rscript shiny/install.R > /dev/null 2>&1 && succes "paquets R" \
      || ignore "paquets R non installés (voir shiny/install.R)"
  else
    ignore "R absent"
  fi

  if command -v npm > /dev/null; then
    (cd angular && npm install --no-audit --no-fund > /dev/null 2>&1) \
      && succes "paquets Node (Angular)" || ignore "installation Angular impossible"
  else
    ignore "Node absent"
  fi
fi

# ---------------------------------------------------------------------
# 1. Ressources partagées : le contrat entre les interfaces
# ---------------------------------------------------------------------
titre "1. Ressources partagées"
for fichier in shared/store_types.json shared/theme.json; do
  if python3 -c "import json,sys; json.load(open(sys.argv[1], encoding='utf-8'))" "$fichier" 2>/dev/null; then
    succes "$fichier est un JSON valide"
  else
    echec "$fichier est invalide"
  fi
done
if python3 -c "
import sqlite3, sys
con = sqlite3.connect(':memory:')
con.executescript(open('shared/schema.sql', encoding='utf-8').read())
kinds = dict(con.execute('SELECT type, COUNT(*) FROM sqlite_master GROUP BY type').fetchall())
assert kinds.get('trigger') == 5 and kinds.get('view') == 9, kinds
" 2>/dev/null; then
  succes "shared/schema.sql s'applique (5 triggers, 9 vues)"
else
  echec "shared/schema.sql ne s'applique pas"
fi

# ---------------------------------------------------------------------
# 2. Pile Python : noyau, requêtes, API
# ---------------------------------------------------------------------
titre "2. Pile Python (noyau, requêtes, API REST)"
if python3 tests/test_pipeline.py; then
  succes "tests du pipeline Python"
else
  echec "tests du pipeline Python"
fi

if python3 -m compileall -q python > /dev/null 2>&1; then
  succes "tous les modules Python compilent"
else
  echec "erreur de compilation Python"
fi

# ---------------------------------------------------------------------
# 3. Pile R : chargement, générateur, interface, et parité avec Python
# ---------------------------------------------------------------------
titre "3. Pile R (dashboard Shiny) et parité avec Python"
if command -v Rscript > /dev/null; then
  BASE_PARITE="$TMP/parite.db"
  if python3 tests/parity_reference.py "$BASE_PARITE" > /dev/null; then
    succes "base de parité produite par la pile Python"
  else
    echec "production de la base de parité"
  fi

  if LANG=C.UTF-8 LC_ALL=C.UTF-8 Rscript tests/test_shiny.R "$BASE_PARITE" 2>&1 \
       | grep -v "deprecated\|ggplotly\|^Warning\|^In addition\|^[0-9]*:"; then
    succes "tests R (dont parité des chiffres avec Python)"
  else
    echec "tests R"
  fi
else
  ignore "R absent : dashboard Shiny non testé"
fi

# ---------------------------------------------------------------------
# 4. Fronts web
# ---------------------------------------------------------------------
titre "4. Fronts web"
if command -v node > /dev/null; then
  ERREURS_JS=0
  for fichier in web/js/*.js; do
    node --check "$fichier" 2>/dev/null || { echo "      syntaxe : $fichier"; ERREURS_JS=1; }
  done
  [[ $ERREURS_JS -eq 0 ]] && succes "syntaxe JavaScript du front web" \
                          || echec "syntaxe JavaScript du front web"

  if [[ -d angular/node_modules ]]; then
    # Le CLI Angular ne rend pas toujours la main après un build réussi
    # (descripteur resté ouvert). On le lance en arrière-plan, on surveille
    # son journal, et on coupe dès qu'il annonce la fin du bundle.
    : > "$TMP/ng.log"
    (cd angular && NG_CLI_ANALYTICS=false \
       node node_modules/@angular/cli/bin/ng.js build > "$TMP/ng.log" 2>&1) &
    NG_PID=$!
    for _ in $(seq 1 150); do            # 5 minutes au maximum
      grep -q "bundle generation complete\|ERROR" "$TMP/ng.log" && break
      kill -0 "$NG_PID" 2>/dev/null || break
      sleep 2
    done
    kill "$NG_PID" 2>/dev/null
    wait "$NG_PID" 2>/dev/null || true
    if grep -q "bundle generation complete" "$TMP/ng.log"; then
      succes "compilation Angular (TypeScript strict + gabarits)"
    else
      echec "compilation Angular"
      sed 's/\x1b\[[0-9;]*m//g' "$TMP/ng.log" | tail -20 | sed 's/^/      /'
    fi
  else
    ignore "angular/node_modules absent : lancez ./scripts/run-tests.sh --install"
  fi
else
  ignore "Node absent : fronts web non vérifiés"
fi

# ---------------------------------------------------------------------
# Bilan
# ---------------------------------------------------------------------
printf '\n%s\n' "──────────────────────────────────────────────────────────────"
if [[ ${#IGNORES[@]} -gt 0 ]]; then
  printf '  %d étape(s) ignorée(s) :\n' "${#IGNORES[@]}"
  printf '    − %s\n' "${IGNORES[@]}"
fi
if [[ ${#ECHECS[@]} -gt 0 ]]; then
  printf '  \033[31m%d échec(s) :\033[0m\n' "${#ECHECS[@]}"
  printf '    ✗ %s\n' "${ECHECS[@]}"
  exit 1
fi
printf '  \033[32mPipeline vert.\033[0m\n'
