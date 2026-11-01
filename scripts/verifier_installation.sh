#!/usr/bin/env bash
# Vérification d'une installation à partir de zéro (audit du 01/11, R-R4 ; chantier E6 ;
# planning : jeudi 12/11, machine vierge).
#
#   bash scripts/verifier_installation.sh                          # branche main, modèles en cache requis
#   bash scripts/verifier_installation.sh --sans-modeles           # ni préchargement ni modèle, ni inférence
#   bash scripts/verifier_installation.sh --env .env --telecharger # préchargement réel (réseau, jeton)
#   bash scripts/verifier_installation.sh --moteurs-externes       # + environnements de Nemotron 3 et DiariZen
#
# Dans un dossier temporaire : clone du dépôt depuis GitHub, `uv sync --locked`,
# `scripts/check_env.py`, suite rapide, préchargement des modèles, démarrage de
# l'application (`--sans-prechauffage` si la version clonée a cette option) puis arrêt par
# SIGTERM, `whospoke diarize --help` ; en option, `scripts/envs/nemotron.sh` et
# `scripts/envs/diarizen.sh` (sans les poids). Chaque étape est chronométrée à la seconde,
# son journal est gardé, et un rapport est écrit dans `--sortie` (par défaut
# results/installation/<date>_<heure>/ du dépôt qui contient ce script).
#
# Préchargement : si les modèles sont déjà dans le cache Hugging Face aux révisions figées,
# `prefetch_models.py --verifier` (chargement hors ligne) ; sinon, avec `--telecharger`,
# `prefetch_models.py` (jeton requis : `--env`) ; sinon arrêt, avec la marche à suivre
# (compte, conditions de community-1, jeton). `--sans-modeles` saute cette étape et exclut
# les tests marqués `modele` ; tout tourne alors hors ligne pour le Hub.
#
# Le jeton n'est jamais affiché : le fichier de `--env` est copié sans être lu.
# Lancer sous `nice -n 19` quand une autre piste calcule.
set -u

URL=https://github.com/PaulSKU/Who-Spoke.git
BRANCH=main
WITH_MODELS=1
DOWNLOAD=0
ENV_FILE=
EXTERNAL=0
FRESH_UV_CACHE=0
PORT=7870
KEEP=0
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
OUTPUT="$SCRIPT_DIR/../results/installation/$(date +%Y-%m-%d_%Hh%M)"
READY_TIMEOUT_S=300
STOP_TIMEOUT_S=30

usage() { sed -n '2,26p' "$0" | sed 's/^# \{0,1\}//'; exit "${1:-0}"; }

while [ $# -gt 0 ]; do
    case "$1" in
        --depot) URL=$2; shift ;;
        --branche) BRANCH=$2; shift ;;
        --sans-modeles) WITH_MODELS=0 ;;
        --telecharger) DOWNLOAD=1 ;;
        --env) ENV_FILE=$2; shift ;;
        --moteurs-externes) EXTERNAL=1 ;;
        --cache-uv-vierge) FRESH_UV_CACHE=1 ;;
        --port) PORT=$2; shift ;;
        --garder) KEEP=1 ;;
        --sortie) OUTPUT=$2; shift ;;
        -h|--help) usage 0 ;;
        *) echo "Option inconnue : $1" >&2; usage 2 ;;
    esac
    shift
done
if [ -n "$ENV_FILE" ] && [ ! -f "$ENV_FILE" ]; then
    echo "--env : $ENV_FILE introuvable" >&2; exit 2
fi
if [ "$DOWNLOAD" = 1 ] && [ -z "$ENV_FILE" ]; then
    echo "--telecharger demande --env (fichier .env portant HF_TOKEN)" >&2; exit 2
fi

mkdir -p "$OUTPUT/journaux"
OUTPUT=$(cd "$OUTPUT" && pwd)
LOGS="$OUTPUT/journaux"
STEPS="$OUTPUT/etapes.tsv"
REPORT="$OUTPUT/rapport.md"
printf 'etape\tstatut\tduree_s\tcommentaire\n' > "$STEPS"
WORK=$(mktemp -d "${TMPDIR:-/tmp}/whospoke-installation.XXXXXX")
CLONE="$WORK/Who-Spoke"
APP_PID=
# Environnement de l'appelant sans effet sur le clone.
unset VIRTUAL_ENV UV_PROJECT_ENVIRONMENT PYTHONPATH
if [ "$FRESH_UV_CACHE" = 1 ]; then
    export UV_CACHE_DIR="$WORK/cache-uv"
fi

say() { printf '%s\n' "$*"; }
clean_text() { tr '\t|' '  ' | tr -s ' ' | cut -c1-200; }
record() { printf '%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$(printf '%s' "$4" | clean_text)" >> "$STEPS"; }
last_line() { grep -v '^[[:space:]]*$' "$1" 2>/dev/null | tail -1; }

cleanup() {
    if [ -n "$APP_PID" ] && kill -0 "$APP_PID" 2>/dev/null; then
        kill -TERM "$APP_PID" 2>/dev/null
    fi
    if [ "$KEEP" = 1 ]; then
        say "Dossier gardé : $WORK"
    else
        rm -rf "$WORK"
    fi
}
trap cleanup EXIT

# step <id> <libellé> <commande…> : chronomètre, garde le journal, consigne le statut.
# Commentaire du rapport : dernière ligne du journal, ou dernière ligne qui correspond à
# SUMMARY (expression régulière étendue) si cette variable est posée pour l'appel.
step() {
    local id=$1 label=$2 start code comment
    shift 2
    say "▶ $label"
    start=$(date +%s)
    "$@" > "$LOGS/$id.log" 2>&1
    code=$?
    DURATION=$(( $(date +%s) - start ))
    if [ -n "${SUMMARY:-}" ] && grep -Eq "$SUMMARY" "$LOGS/$id.log"; then
        comment=$(grep -E "$SUMMARY" "$LOGS/$id.log" | tail -1)
    else
        comment=$(last_line "$LOGS/$id.log")
    fi
    if [ "$code" = 0 ]; then
        record "$id" ok "$DURATION" "$comment"
        say "  ok en ${DURATION} s"
    else
        record "$id" "échec (code $code)" "$DURATION" "$comment"
        say "  ÉCHEC (code $code) en ${DURATION} s : $comment"
    fi
    return "$code"
}

skip() { record "$1" "non lancé" 0 "$2"; say "– $1 : non lancé ($2)"; }

# --- Rapport ---------------------------------------------------------------------------

minutes() { printf '%d min %02d s' $(( $1 / 60 )) $(( $1 % 60 )); }

write_report() {
    local total=$1 verdict=$2
    {
        echo "# Vérification de l'installation — $(date '+%d/%m/%Y %H:%M')"
        echo
        echo "Script : \`scripts/verifier_installation.sh\` (R-R4, chantier E6). Verdict : **$verdict** ; durée totale : $(minutes "$total")."
        echo
        echo "| | |"
        echo "|---|---|"
        echo "| Dépôt cloné | \`$URL\`, branche \`$BRANCH\`, commit \`${COMMIT:-—}\` |"
        echo "| Options | modèles : $([ "$WITH_MODELS" = 1 ] && echo oui || echo 'non (--sans-modeles)') ; téléchargement : $([ "$DOWNLOAD" = 1 ] && echo oui || echo non) ; .env fourni : $([ -n "$ENV_FILE" ] && echo oui || echo non) ; moteurs externes : $([ "$EXTERNAL" = 1 ] && echo oui || echo non) ; cache de uv : $([ "$FRESH_UV_CACHE" = 1 ] && echo 'vierge (--cache-uv-vierge)' || echo "celui de la machine") |"
        echo "| Système | $(sw_vers -productName 2>/dev/null) $(sw_vers -productVersion 2>/dev/null), $(uname -m) |"
        echo "| uv | $(uv --version 2>/dev/null || echo absent) |"
        echo "| git | $(git --version 2>/dev/null || echo absent) |"
        echo "| ffmpeg | $(command -v ffmpeg >/dev/null && ffmpeg -version 2>/dev/null | head -1 | cut -d' ' -f1-3 || echo absent) ($(command -v ffmpeg || echo '—')) |"
        echo "| Homebrew | $(brew --version 2>/dev/null | head -1 || echo absent) |"
        echo "| Environnement \`.venv\` du clone | ${VENV_SIZE:-—} ; espace libre au départ : ${FREE_SPACE:-—} |"
        echo
        echo "| Étape | Statut | Durée | Dernière ligne du journal |"
        echo "|---|---|---|---|"
        tail -n +2 "$STEPS" | while IFS="$(printf '\t')" read -r id status duration comment; do
            echo "| $id | $status | $(minutes "$duration") | ${comment:-—} |"
        done
        echo
        echo "Durées à l'horloge murale, à la seconde. Journaux de chaque étape dans \`journaux/\`."
        if [ "$FRESH_UV_CACHE" = 0 ]; then
            echo "Le cache de uv de la machine était utilisé : sur une machine vierge, \`uv sync\` télécharge en plus Python 3.11 et les paquets (torch compris)."
        fi
    } > "$REPORT"
}

finish() {
    local verdict=$1
    write_report $(( $(date +%s) - T0 )) "$verdict"
    # Dossier personnel remplacé par ~ dans tout ce qui est écrit (rapport versionnable).
    for file in "$REPORT" "$LOGS"/*.log; do
        [ -f "$file" ] && sed -i '' "s|$HOME|~|g" "$file"
    done
    say
    say "Rapport : $REPORT"
    case "$verdict" in
        "installation vérifiée"|"vérification partielle réussie"*) exit 0 ;;
        *) exit 1 ;;
    esac
}

# --- Étapes ----------------------------------------------------------------------------

T0=$(date +%s)
FAILED=0
COMMIT=
FREE_SPACE=$(df -h "$WORK" | awk 'NR == 2 {print $4}')

say "Dossier de travail : $WORK"
for tool in uv git; do
    if ! command -v "$tool" >/dev/null; then
        record prerequis "échec" 0 "$tool absent du PATH"
        say "Arrêt : $tool absent du PATH (docs/installation.md)"
        finish "installation impossible"
    fi
done
if command -v ffmpeg >/dev/null; then
    record prerequis ok 0 "uv, git et ffmpeg présents"
else
    record prerequis "échec" 0 "ffmpeg absent du PATH (docs/installation.md, problèmes connus)"
    FAILED=1
fi

step clone "Clone de $URL ($BRANCH)" git clone --quiet --depth 1 --branch "$BRANCH" "$URL" "$CLONE" \
    || finish "installation impossible"
COMMIT=$(git -C "$CLONE" rev-parse --short=12 HEAD)
cd "$CLONE" || finish "installation impossible"
if [ -n "$ENV_FILE" ]; then
    cp "$ENV_FILE" .env && chmod 600 .env
fi

SUMMARY='^(Resolved|Prepared|Installed) ' step uv_sync "uv sync --locked" uv sync --locked \
    || finish "installation impossible"
VENV_SIZE=$(du -sh .venv 2>/dev/null | cut -f1)

if [ "$WITH_MODELS" = 0 ]; then
    export HF_HUB_OFFLINE=1   # rien ne doit venir du Hub sans modèles
fi
step check_env "scripts/check_env.py" uv run --no-sync python scripts/check_env.py || FAILED=1

if [ "$WITH_MODELS" = 1 ]; then
    step tests "Suite rapide (sans les tests lents)" uv run --no-sync pytest -q -p no:cacheprovider || FAILED=1
else
    step tests "Suite rapide (sans les tests lents ni ceux qui chargent un modèle)" \
        uv run --no-sync pytest -q -p no:cacheprovider -m "not lent and not modele" || FAILED=1
fi

if [ "$WITH_MODELS" = 0 ]; then
    skip prefetch_models "--sans-modeles : ni téléchargement ni vérification"
else
    if uv run --no-sync python - > "$LOGS/cache_modeles.log" 2>&1 <<'EOF'
import sys
from pathlib import Path

sys.path.insert(0, "scripts")
from huggingface_hub.constants import HF_HUB_CACHE
from prefetch_models import REPOS

missing = []
for repo in REPOS:
    snapshot = Path(HF_HUB_CACHE) / f"models--{repo.repo_id.replace('/', '--')}" / "snapshots" / repo.revision
    print(f"{repo.repo_id}@{repo.revision[:12]} : {'en cache' if snapshot.is_dir() else 'absent'}")
    if not snapshot.is_dir():
        missing.append(repo.repo_id)
sys.exit(1 if missing else 0)
EOF
    then
        step prefetch_models "Modèles en cache : prefetch_models.py --verifier (hors ligne)" \
            uv run --no-sync python scripts/prefetch_models.py --verifier || FAILED=1
    elif [ "$DOWNLOAD" = 1 ]; then
        step prefetch_models "prefetch_models.py (téléchargement, puis vérification hors ligne)" \
            uv run --no-sync python scripts/prefetch_models.py || FAILED=1
    else
        record prefetch_models "arrêt" 0 "modèles absents du cache : jeton et conditions de community-1 requis"
        cat <<'EOF'

Arrêt : les modèles ne sont pas dans le cache Hugging Face (journaux/cache_modeles.log).
pyannote/speaker-diarization-community-1 est un modèle à accès restreint. Avant le préchargement :
  1. créer un compte sur https://huggingface.co ;
  2. accepter les conditions d'utilisation sur
     https://huggingface.co/pyannote/speaker-diarization-community-1 (connecté à ce compte) ;
  3. créer un jeton en lecture (Settings > Access Tokens) ;
  4. l'écrire dans un fichier .env : HF_TOKEN=<jeton> (modèle : .env.example) ;
  5. relancer : bash scripts/verifier_installation.sh --env <chemin du .env> --telecharger
     (ou, dans le dépôt : uv run python scripts/prefetch_models.py).
Sans modèles, seule une vérification partielle est possible : --sans-modeles.
EOF
        finish "arrêt : modèles absents du cache"
    fi
fi

start_app() {
    local args=(--port "$PORT") start code
    if uv run --no-sync python -m app.app --help 2>/dev/null | grep -q -- --sans-prechauffage; then
        args+=(--sans-prechauffage)
        APP_NOTE="avec --sans-prechauffage"
    else
        APP_NOTE="option --sans-prechauffage absente de cette version : lancée sans"
    fi
    if curl -s -o /dev/null "http://127.0.0.1:$PORT/"; then
        echo "port $PORT déjà occupé"; return 1
    fi
    echo "lancement : python -m app.app ${args[*]} ($APP_NOTE)"
    start=$(date +%s)
    HF_HUB_OFFLINE=1 .venv/bin/python -m app.app "${args[@]}" &
    APP_PID=$!
    until [ "$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/")" = 200 ]; do
        if ! kill -0 "$APP_PID" 2>/dev/null; then
            wait "$APP_PID"; echo "arrêt prématuré de l'application (code $?)"; APP_PID=; return 1
        fi
        if [ $(( $(date +%s) - start )) -ge "$READY_TIMEOUT_S" ]; then
            echo "pas de réponse HTTP en ${READY_TIMEOUT_S} s"; return 1
        fi
        sleep 1
    done
    APP_READY_S=$(( $(date +%s) - start ))
    echo "réponse HTTP 200 après ${APP_READY_S} s"
    kill -TERM "$APP_PID"
    start=$(date +%s)
    while kill -0 "$APP_PID" 2>/dev/null; do
        if [ $(( $(date +%s) - start )) -ge "$STOP_TIMEOUT_S" ]; then
            kill -KILL "$APP_PID"; echo "pas d'arrêt en ${STOP_TIMEOUT_S} s après SIGTERM : tuée"; APP_PID=; return 1
        fi
        sleep 1
    done
    wait "$APP_PID"; code=$?
    APP_PID=
    if curl -s -o /dev/null "http://127.0.0.1:$PORT/"; then
        echo "port $PORT encore ouvert après l'arrêt"; return 1
    fi
    echo "arrêt propre (SIGTERM, code $code) en $(( $(date +%s) - start )) s ; prête en ${APP_READY_S} s, $APP_NOTE"
    return "$code"
}
step application "Application : démarrage puis arrêt propre" start_app || FAILED=1

SUMMARY='^usage: ' step cli "whospoke diarize --help" uv run --no-sync whospoke diarize --help || FAILED=1

if [ "$EXTERNAL" = 1 ]; then
    step env_nemotron "Environnement de Nemotron 3 (scripts/envs/nemotron.sh, sans les poids)" \
        sh scripts/envs/nemotron.sh || FAILED=1
    step env_diarizen "Environnement de DiariZen (scripts/envs/diarizen.sh, sans les poids)" \
        sh scripts/envs/diarizen.sh || FAILED=1
else
    skip env_nemotron "option --moteurs-externes non demandée"
    skip env_diarizen "option --moteurs-externes non demandée"
fi

if [ "$FAILED" = 0 ]; then
    if [ "$WITH_MODELS" = 1 ]; then finish "installation vérifiée"; else finish "vérification partielle réussie (sans modèles)"; fi
fi
finish "échec d'au moins une étape"
