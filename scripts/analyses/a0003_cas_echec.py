"""A-0003 — cas d'échec (D28 §1) : classement, descripteurs, corrélations, catégories d'erreur, extraits.

Usage :
    uv run python scripts/analyses/a0003_cas_echec.py --config analyses/A-0003_cas-echec/config.yaml
    uv run python scripts/analyses/a0003_cas_echec.py --config … --donnees ~/Dev/Who-Spoke/data \\
        --sortie data/processed/a0003/essai        # essai : rien n'est écrit dans analyses/

Analyse a posteriori (D21 §1, methode.md §4.7) : aucun système n'est exécuté. Pour chaque
système déclaré dans la configuration (une ou plusieurs expériences sources, une par corpus),
le script lit les RTTM, les `per_file_<corpus>_<partition>.csv`, les références et l'UEM
officiel, puis écrit :

- `classement.csv` : fichiers classés par DER sans collar, par système et corpus (partitions
  réunies), rang 1 = pire, avec les `n_pires` marqués ;
- `descripteurs.csv` : descripteurs de chaque fichier tirés de la référence (nombre de
  locuteurs, part de chevauchement, part des tours courts, durée moyenne d'un tour, part de
  parole, type de réunion) ;
- `correlations.csv` : rho de Spearman entre composantes du DER et descripteurs, par système
  et corpus ; descriptif, sans p-valeur ;
- `categories.csv` et `categories_par_fichier.csv` : secondes d'erreur par catégorie de la
  carte « Expliquer cette erreur » de l'application ;
- `extraits.csv` et le dossier d'écoute (hors du dépôt) : 6 à 8 extraits des corpus publics,
  avec `index.html` et `grille.csv`, où la candidate note la cause perçue ;
- `execution.json` : commit, arbre propre (D18), empreintes, contrôle des totaux.

Catégories d'erreur : aucune seconde définition. Les zones d'erreur et leur contexte viennent
de `app.sortie.error_map` (appariement optimal du DER, `_Context.describe`) ; une zone relève
d'une catégorie quand la carte de l'interface affiche le constat correspondant
(`app.app._context_sentences` : chevauchement > 0, tour court, pause, frontière), ou quand son
locuteur de référence n'est pas apparié. Pour retrouver le DER du protocole, référence et
hypothèse sont restreintes à l'UEM officiel avant l'appel : la carte de l'application prend
l'UEM de 0 à la durée, sans parole ni hypothèse hors de l'UEM, le décompte est le même.

Corpus maison : ses extraits ne sont exportés que dans le dossier local `extraits.locaux`
(liste comprise), jamais dans le dossier de l'analyse ; il est refusé dans `extraits.corpus`.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import math
import statistics
import sys
from datetime import datetime
from pathlib import Path

import whospoke  # noqa: F401  (D27 : télémétrie coupée avant tout import tiers)
import numpy as np
import yaml
from pyannote.core import Annotation, Timeline
from scipy.io import wavfile
from scipy.stats import spearmanr

from whospoke.experiment import (
    DATA_DIR, REPO_ROOT, annotation_corpus, dataset_uris, git_state, hypothesis_dir, load_rttm,
    load_uem, processed_wav, reference_rttm, uem_path,
)
from whospoke.partage import EXPERIMENTS_DIR, experiment_dir

sys.path.insert(0, str(REPO_ROOT))   # paquet `app` (carte des erreurs de l'application)
from app import sortie  # noqa: E402

ERROR_TYPES = ("manquee", "fausse_alarme", "confusion")
CATEGORIES = ("chevauchement", "tour_court", "frontiere", "pause", "non_apparie")
NONE = "aucune"
LOCAL_CORPORA = {"maison"}       # extraits jamais versionnés ni publiés (D27, D28 §1)
RESOLUTION_S = 0.05              # grille de la recherche des fenêtres d'écoute
TOTALS_TOLERANCE_S = 0.01        # écart admis entre la carte et le per_file, par composante
SPLITS_DIR = DATA_DIR / "splits"  # listes et UEM versionnés, toujours lus dans le dépôt


# --- Emplacements ------------------------------------------------------------------------


def located(path: Path, data_root: Path) -> Path:
    """Chemin du protocole (`whospoke.experiment`) sous la racine de données `data_root` ;
    les fichiers versionnés de `data/splits/` restent lus dans le dépôt."""
    relative = path.relative_to(DATA_DIR)
    if relative.parts[0] == "splits":
        return SPLITS_DIR.joinpath(*relative.parts[1:])
    return data_root / relative


def sha256_files(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda p: p.name):
        digest.update(path.name.encode() + b"\0" + path.read_bytes() + b"\0")
    return digest.hexdigest()


def read_per_file(path: Path) -> dict[str, dict]:
    with path.open() as handle:
        return {row["uri"]: row for row in csv.DictReader(handle)}


def write_csv(path: Path, rows: list[dict], fields: list[str] | None = None) -> None:
    fields = fields or (list(rows[0]) if rows else [])
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


# --- Descripteurs (D28 §1.2) -------------------------------------------------------------


def descriptors(reference: Annotation, uem: Timeline, short_turn_s: float) -> dict:
    """Descripteurs d'un fichier, tirés de la référence restreinte à l'UEM."""
    ref = reference.crop(uem, mode="intersection")
    speech_s = ref.get_timeline().support().duration()
    overlap_s = ref.get_overlap().support().duration()
    turns = [segment.duration for segment, _ in ref.itertracks()]
    uem_s = uem.support().duration()
    return {
        "n_locuteurs": len(ref.labels()),
        "n_tours": len(turns),
        "part_chevauchement": round(overlap_s / speech_s, 4) if speech_s else None,
        "part_tours_courts": round(sum(d < short_turn_s for d in turns) / len(turns), 4) if turns else None,
        "duree_moyenne_tour_s": round(statistics.fmean(turns), 3) if turns else None,
        "part_parole": round(speech_s / uem_s, 4) if uem_s else None,
        "duree_parole_s": round(speech_s, 3),
        "duree_uem_s": round(uem_s, 3),
    }


# --- Catégories d'erreur (D28 §1.4) ------------------------------------------------------


def file_errors(reference: Annotation, hypothesis: Annotation, uem: Timeline) -> dict:
    """Carte des erreurs de l'application (`app.sortie.error_map`), restreinte à l'UEM officiel."""
    ref = reference.crop(uem, mode="intersection")
    hyp = hypothesis.crop(uem, mode="intersection")
    ref.uri = hyp.uri = reference.uri
    return sortie.error_map(ref, hyp, uem.extent().end)


def zone_categories(zone: dict, pairs: dict) -> set[str]:
    """Catégories d'une zone : les constats affichés par la carte « Expliquer cette erreur »
    (conditions de `app.app._context_sentences`), plus le locuteur de référence non apparié."""
    context = zone["contexte"]
    found = set()
    if context["chevauchement_s"] > 0:
        found.add("chevauchement")
    if context["tour_court"]:
        found.add("tour_court")
    if context["frontiere_s"] is not None:
        found.add("frontiere")
    if context["pause"]:
        found.add("pause")
    if zone["reference"] is not None and zone["reference"] not in pairs:
        found.add("non_apparie")
    return found


def categorized_zones(errors: dict) -> list[dict]:
    pairs = errors["appariement"]
    return [{"type": z["type"], "debut": z["debut"], "fin": z["fin"], "reference": z["reference"],
             "hypothese": z["hypothese"], "categories": zone_categories(z, pairs)} for z in errors["zones"]]


def tally(zones: list[dict]) -> dict[str, dict]:
    """Secondes d'erreur par type (et `tous`) : total, par catégorie, seules, et sans catégorie."""
    out = {}
    for kind in ("tous", *ERROR_TYPES):
        selected = [z for z in zones if kind == "tous" or z["type"] == kind]
        durations = [z["fin"] - z["debut"] for z in selected]
        row = {"erreur_s": sum(durations), "n_zones": len(selected),
               "durees_zones": durations}
        for category in CATEGORIES:
            row[f"{category}_s"] = sum(d for d, z in zip(durations, selected) if category in z["categories"])
            row[f"{category}_seule_s"] = sum(d for d, z in zip(durations, selected) if z["categories"] == {category})
        row[f"{NONE}_s"] = sum(d for d, z in zip(durations, selected) if not z["categories"])
        out[kind] = row
    return out


def tally_row(counts: dict, with_share: bool) -> dict:
    row = {"erreur_s": round(counts["erreur_s"], 3), "n_zones": counts["n_zones"],
           "duree_mediane_zone_s": round(statistics.median(counts["durees_zones"]), 3) if counts["durees_zones"] else None}
    total = counts["erreur_s"]
    for key in [*(f"{c}_s" for c in CATEGORIES), *(f"{c}_seule_s" for c in CATEGORIES), f"{NONE}_s"]:
        row[key] = round(counts[key], 3)
        if with_share:
            row[key.removesuffix("_s") + "_pct"] = round(100.0 * counts[key] / total, 2) if total else None
    return row


def merge_tallies(tallies: list[dict]) -> dict:
    merged = {}
    for kind in ("tous", *ERROR_TYPES):
        rows = [t[kind] for t in tallies]
        merged[kind] = {key: (sum((r[key] for r in rows), []) if key == "durees_zones" else sum(r[key] for r in rows))
                        for key in rows[0]} if rows else {}
    return merged


# --- Corrélations (D28 §1.3) -------------------------------------------------------------


def spearman(x: list, y: list) -> float | None:
    """Rho de Spearman (descriptif) ; None si moins de 3 paires ou une série constante."""
    pairs = [(a, b) for a, b in zip(x, y) if a is not None and b is not None]
    if len(pairs) < 3 or len({a for a, _ in pairs}) < 2 or len({b for _, b in pairs}) < 2:
        return None
    rho = spearmanr([a for a, _ in pairs], [b for _, b in pairs]).statistic
    return None if math.isnan(rho) else round(float(rho), 3)


# --- Extraits d'écoute (D28 §1.5) --------------------------------------------------------


def window_scores(zones: list[dict], start_s: float, end_s: float, duration_s: float,
                  step_s: float) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    """Débuts de fenêtre possibles (pas `step_s`, dans [start_s, end_s − duration_s]) et
    secondes d'erreur de chaque fenêtre : `tous`, chaque catégorie et `aucune`."""
    n = int(math.ceil((end_s - start_s) / RESOLUTION_S)) + 1
    keys = ("tous", *CATEGORIES, NONE)
    cover = {key: np.zeros(n) for key in keys}
    for zone in zones:
        a = max(0, int(round((zone["debut"] - start_s) / RESOLUTION_S)))
        b = min(n, int(round((zone["fin"] - start_s) / RESOLUTION_S)))
        if b <= a:
            continue
        for key in ("tous", *(zone["categories"] or {NONE})):
            cover[key][a:b] += RESOLUTION_S
    width = int(round(duration_s / RESOLUTION_S))
    last = max(0.0, end_s - start_s - duration_s)
    starts = np.arange(0.0, last + 1e-9, step_s)
    index = np.minimum(np.round(starts / RESOLUTION_S).astype(int), n - 1)
    scores = {}
    for key, values in cover.items():
        cumulative = np.concatenate([[0.0], np.cumsum(values)])
        scores[key] = cumulative[np.minimum(index + width, n)] - cumulative[index]
    return starts + start_s, scores


def select_excerpts(candidates: list[dict], spec: dict) -> list[dict]:
    """Sélection : une fenêtre par catégorie (puis `aucune`), où la catégorie a le plus de
    secondes d'erreur et en a au moins autant que toute autre ; puis les pires fichiers
    (fenêtre de plus forte erreur) jusqu'à `n_max`. Un fichier au plus une fois ; plafonds
    par système et par corpus. Chaque extrait garde son candidat dans `_source` (interne)."""
    duration, step = float(spec["duree_s"]), float(spec["pas_s"])
    for candidate in candidates:
        candidate["fenetres"] = window_scores(candidate["zones"], candidate["uem_debut"], candidate["uem_fin"],
                                              duration, step)
    chosen: list[dict] = []

    def allowed(candidate):
        used = {(c["corpus"], c["uri"]) for c in chosen}
        return ((candidate["corpus"], candidate["uri"]) not in used
                and sum(c["systeme"] == candidate["systeme"] for c in chosen) < spec["max_par_systeme"]
                and sum(c["corpus"] == candidate["corpus"] for c in chosen) < spec["max_par_corpus"])

    def add(candidate, position, motif, category):
        starts, scores = candidate["fenetres"]
        chosen.append({**{k: candidate[k] for k in ("systeme", "exp_id", "corpus", "partition", "uri", "der_c0")},
                       "motif": motif, "categorie": category,
                       "debut": round(float(starts[position]), 2),
                       "fin": round(float(min(starts[position] + duration, candidate["uem_fin"])), 2),
                       **{f"fenetre_{key}_s": round(float(values[position]), 2) for key, values in scores.items()},
                       "_source": candidate})

    for category in (*CATEGORIES, NONE):
        if len(chosen) >= spec["n_max"]:
            break
        best = None
        for candidate in candidates:
            if not allowed(candidate):
                continue
            starts, scores = candidate["fenetres"]
            others = np.max([scores[k] for k in (*CATEGORIES, NONE) if k != category], axis=0)
            score = np.where((scores[category] > 0) & (scores[category] >= others), scores[category], -1.0)
            position = int(np.argmax(score))
            if score[position] > 0 and (best is None or score[position] > best[0]):
                best = (float(score[position]), candidate, position)
        if best is not None:
            add(best[1], best[2], "categorie", category)
    for candidate in sorted(candidates, key=lambda c: -c["der_c0"]):
        if len(chosen) >= spec["n_max"]:
            break
        if allowed(candidate):
            add(candidate, int(np.argmax(candidate["fenetres"][1]["tous"])), "pire_fichier", "")
    if len(chosen) < spec["n_min"]:
        print(f"[A-0003] {len(chosen)} extraits seulement (minimum {spec['n_min']}) : pas assez de fichiers candidats")
    for number, excerpt in enumerate(chosen, start=1):
        excerpt["extrait"] = f"x{number}"
    return chosen


CAUSES = ("voix proches", "rires", "acquiescements", "micro éloigné", "bruit")   # D28 §1.5


def public_fields(excerpt: dict) -> dict:
    """Colonnes d'un extrait écrites dans les CSV (sans les données internes `_…`)."""
    return {k: v for k, v in excerpt.items() if not k.startswith("_")}


def export_excerpts(excerpts: list[dict], target: Path, data_root: Path, title: str) -> None:
    """Écrit les WAV, `grille.csv` (cause perçue à remplir), `index.html` et `extraits.csv`."""
    target.mkdir(parents=True, exist_ok=True)
    for old in target.glob("x*.wav"):
        old.unlink()
    blocks = []
    for excerpt in excerpts:
        source = located(processed_wav(excerpt["corpus"], excerpt["uri"]), data_root)
        rate, data = wavfile.read(source, mmap=True)
        piece = np.array(data[int(excerpt["debut"] * rate): int(excerpt["fin"] * rate)])
        name = f"{excerpt['extrait']}_{excerpt['uri']}_{int(excerpt['debut'])}s.wav"
        wavfile.write(target / name, rate, piece)
        excerpt["fichier_audio"] = name
        blocks.append(_excerpt_html(excerpt, data_root))
    write_csv(target / "extraits.csv", [public_fields(e) for e in excerpts])
    grid = [{"extrait": e["extrait"], "fichier_audio": e["fichier_audio"], "systeme": e["systeme"],
             "motif": e["motif"], "categorie": e["categorie"], **{cause: "" for cause in CAUSES},
             "autre_cause": "", "remarques": ""} for e in excerpts]
    write_csv(target / "grille.csv", grid, ["extrait", "fichier_audio", "systeme", "motif", "categorie",
                                            *CAUSES, "autre_cause", "remarques"])
    (target / "index.html").write_text(_page(title, blocks), encoding="utf-8")


def _excerpt_html(excerpt: dict, data_root: Path) -> str:
    corpus, uri = excerpt["corpus"], excerpt["uri"]
    reference = load_rttm(located(reference_rttm(corpus, uri), data_root), uri)
    hypothesis = load_rttm(excerpt["_source"]["rttm"], uri)
    a, b = excerpt["debut"], excerpt["fin"]
    rows = [("Réf. " + str(label), reference, label) for label in sorted(reference.labels(), key=str)]
    rows += [("Trouvé " + str(label), hypothesis, label) for label in sorted(hypothesis.labels(), key=str)]
    width, label_w, row_h = 900, 150, 16
    scale = (width - label_w) / max(b - a, 1e-6)
    shapes = []
    shown = []
    for label_text, annotation, label in rows:
        segments = [(max(s.start, a), min(s.end, b)) for s, _, l in annotation.itertracks(yield_label=True)
                    if l == label and s.end > a and s.start < b]
        if segments:
            shown.append((label_text, segments))
    for i, (label_text, segments) in enumerate(shown):
        y = i * (row_h + 4)
        css = "ref" if label_text.startswith("Réf.") else "hyp"
        shapes.append(f'<text x="0" y="{y + 12}" class="lab">{html.escape(label_text)}</text>')
        shapes += [f'<rect class="{css}" x="{label_w + (s - a) * scale:.1f}" y="{y}" '
                   f'width="{max((e - s) * scale, 1):.1f}" height="{row_h}"/>' for s, e in segments]
    y = len(shown) * (row_h + 4)
    shapes.append(f'<text x="0" y="{y + 12}" class="lab">Erreurs</text>')
    for zone in excerpt["_source"]["zones"]:
        if zone["fin"] > a and zone["debut"] < b:
            s, e = max(zone["debut"], a), min(zone["fin"], b)
            title = f"{zone['type']} : {', '.join(sorted(zone['categories'])) or NONE}"
            shapes.append(f'<rect class="err {zone["type"]}" x="{label_w + (s - a) * scale:.1f}" y="{y}" '
                          f'width="{max((e - s) * scale, 1):.1f}" height="{row_h}"><title>{html.escape(title)}</title></rect>')
    height = y + row_h + 4
    svg = (f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="Référence, hypothèse et erreurs">'
           + "".join(shapes) + "</svg>")
    motif = ("Pire fichier" if excerpt["motif"] == "pire_fichier"
             else f"Catégorie dominante : {excerpt['categorie']}")
    composition = ", ".join(f"{key} {excerpt[f'fenetre_{key}_s']:.1f} s" for key in (*CATEGORIES, NONE)
                            if excerpt[f"fenetre_{key}_s"] > 0)
    checks = "".join(f'<label><input type="checkbox" name="{html.escape(c)}"> {html.escape(c)}</label>' for c in CAUSES)
    return (f'<section class="x" data-extrait="{excerpt["extrait"]}" data-audio="{html.escape(excerpt["fichier_audio"])}" '
            f'data-systeme="{html.escape(excerpt["systeme"])}" data-motif="{excerpt["motif"]}" '
            f'data-categorie="{html.escape(excerpt["categorie"])}">'
            f'<h2>{excerpt["extrait"]} — {html.escape(motif)}</h2>'
            f'<p>{html.escape(excerpt["systeme"])} ({excerpt["exp_id"]}), {html.escape(uri)} ({excerpt["partition"]}), '
            f'{a:.1f} – {b:.1f} s ; DER du fichier {excerpt["der_c0"]:.1f} % ; erreur dans la fenêtre '
            f'{excerpt["fenetre_tous_s"]:.1f} s ({html.escape(composition) or "—"}).</p>'
            f'<audio controls preload="none" src="{html.escape(excerpt["fichier_audio"])}"></audio>{svg}'
            f'<fieldset><legend>Cause perçue</legend>{checks}'
            f'<label class="w">Autre : <input type="text" name="autre_cause"></label>'
            f'<label class="w">Remarques : <input type="text" name="remarques"></label></fieldset></section>')


def _page(title: str, blocks: list[str]) -> str:
    causes = json.dumps(list(CAUSES), ensure_ascii=False)
    return f"""<!doctype html><html lang="fr"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{html.escape(title)}</title>
<style>
:root{{--fond:#fff;--texte:#1d1d1f;--doux:#666;--ref:#4a6fa5;--hyp:#5a8f5a;--manquee:#c0392b;--fa:#d68910;--conf:#7d3c98;--bord:#ddd}}
@media (prefers-color-scheme: dark){{:root{{--fond:#1b1b1d;--texte:#eee;--doux:#aaa;--ref:#7fa3d6;--hyp:#8cc08c;--manquee:#e57366;--fa:#f0b04c;--conf:#b78ad0;--bord:#444}}}}
body{{background:var(--fond);color:var(--texte);font-family:system-ui,sans-serif;margin:16px;max-width:960px}}
section.x{{border-top:1px solid var(--bord);padding:8px 0 16px}} h2{{font-size:1.05rem;margin:8px 0}}
p{{color:var(--doux);margin:4px 0 8px}} audio{{width:100%;max-width:520px}} svg{{width:100%;height:auto;margin:8px 0}}
.lab{{font-size:11px;fill:var(--texte)}} .ref{{fill:var(--ref)}} .hyp{{fill:var(--hyp)}}
.err.manquee{{fill:var(--manquee)}} .err.fausse_alarme{{fill:var(--fa)}} .err.confusion{{fill:var(--conf)}}
fieldset{{border:1px solid var(--bord);display:flex;flex-wrap:wrap;gap:6px 16px}} label.w{{flex-basis:100%}}
label.w input{{width:70%}} button{{font-size:1rem;padding:6px 12px;margin:12px 0}}
.legende span{{display:inline-block;width:12px;height:12px;margin:0 4px 0 12px;vertical-align:middle}}
</style>
<h1>{html.escape(title)}</h1>
<p>Écoutez chaque extrait et cochez la ou les causes que vous percevez (D28 §1.5). Les zones colorées
sont des constats sur la référence, pas des causes. Les réponses restent dans ce navigateur ; le bouton
en bas télécharge la grille remplie (CSV), à remettre au cockpit.</p>
<p class="legende">Erreurs :<span style="background:var(--manquee)"></span>parole manquée
<span style="background:var(--fa)"></span>fausse alarme<span style="background:var(--conf)"></span>confusion</p>
{"".join(blocks)}
<button type="button" id="exporter">Télécharger la grille remplie (CSV)</button>
<script>
const CAUSES = {causes};
const KEY = "a0003-grille-" + document.title;
function lire() {{ try {{ return JSON.parse(localStorage.getItem(KEY) || "{{}}"); }} catch (e) {{ return {{}}; }} }}
function ecrire(etat) {{ try {{ localStorage.setItem(KEY, JSON.stringify(etat)); }} catch (e) {{}} }}
const etat = lire();
document.querySelectorAll("section.x").forEach(s => {{
  const id = s.dataset.extrait, valeurs = etat[id] || {{}};
  s.querySelectorAll("input").forEach(i => {{
    if (i.type === "checkbox") i.checked = !!valeurs[i.name]; else i.value = valeurs[i.name] || "";
    i.addEventListener("input", () => {{
      const e = lire(); e[id] = e[id] || {{}};
      e[id][i.name] = i.type === "checkbox" ? i.checked : i.value; ecrire(e);
    }});
  }});
}});
function champ(v) {{ v = String(v ?? ""); return /[",\\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v; }}
document.getElementById("exporter").addEventListener("click", () => {{
  const lignes = [["extrait", "fichier_audio", "systeme", "motif", "categorie", ...CAUSES, "autre_cause", "remarques"]];
  document.querySelectorAll("section.x").forEach(s => {{
    const val = n => s.querySelector(`input[name="${{n}}"]`);
    lignes.push([s.dataset.extrait, s.dataset.audio, s.dataset.systeme, s.dataset.motif, s.dataset.categorie,
      ...CAUSES.map(c => val(c).checked ? "x" : ""), val("autre_cause").value, val("remarques").value]);
  }});
  const blob = new Blob([lignes.map(l => l.map(champ).join(",")).join("\\n") + "\\n"], {{type: "text/csv"}});
  const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = "grille_remplie.csv"; a.click();
}});
</script></html>
"""


# --- Point d'entrée ----------------------------------------------------------------------


def run(config: dict, out_dir: Path, data_root: Path, listen_dir: Path | None,
        experiments_root: Path = EXPERIMENTS_DIR) -> dict:
    """Calcule l'analyse et écrit ses CSV dans `out_dir` (et les extraits dans `listen_dir`,
    sauf si None) ; renvoie les éléments d'`execution.json` propres à l'analyse."""
    if LOCAL_CORPORA & set(config["extraits"]["corpus"]):
        sys.exit(f"extraits.corpus : {sorted(LOCAL_CORPORA)} interdit (extraits locaux seulement, D28 §1)")
    short_turn = float(config["descripteurs"]["tour_court_s"])
    meeting_lists = {corpus: {uri for liste in lists for uri in dataset_uris(liste)}
                     for corpus, lists in (config["descripteurs"].get("type_reunion") or {}).items()}
    n_worst = int(config["classement"]["n_pires"])
    criterion = config["classement"]["critere"]

    ranking, per_file_categories, aggregated, candidates = [], [], [], []
    descriptor_rows: dict[tuple[str, str], dict] = {}
    fingerprints, controls = {}, {}
    references_used: dict[str, list[Path]] = {}
    for system in config["systemes"]:
        corpora = [s["corpus"] for s in system["sources"]]
        if len(set(corpora)) != len(corpora):
            sys.exit(f"{system['nom']} : plusieurs sources pour un même corpus")
        for source in system["sources"]:
            exp_id, corpus = source["exp_id"], source["corpus"]
            exp_dir = experiment_dir(exp_id, experiments_root)
            ref_corpus = annotation_corpus(corpus)
            files, tallies, deviation = [], [], 0.0
            for partition in source["partitions"]:
                per_file_path = exp_dir / f"per_file_{corpus}_{partition}.csv"
                per_file = read_per_file(per_file_path)
                fingerprints[str(per_file_path.relative_to(experiments_root.parent))] = hashlib.sha256(
                    per_file_path.read_bytes()).hexdigest()
                hyp_dir = hypothesis_dir(exp_dir, corpus)
                rttms = []
                for uri in dataset_uris(SPLITS_DIR / ref_corpus / f"{partition}.txt"):
                    if uri not in per_file:
                        sys.exit(f"{exp_id} : {uri} absent de {per_file_path.name}")
                    row = per_file[uri]
                    ref_path = located(reference_rttm(corpus, uri), data_root)
                    references_used.setdefault(ref_corpus, []).append(ref_path)
                    reference = load_rttm(ref_path, uri)
                    uem = load_uem(located(uem_path(corpus, uri), data_root), uri)
                    rttms.append(hyp_dir / f"{uri}.rttm")
                    hypothesis = load_rttm(rttms[-1], uri)
                    if (corpus, uri) not in descriptor_rows:
                        meeting = ""
                        if ref_corpus in meeting_lists:
                            meeting = "zoom" if uri in meeting_lists[ref_corpus] else "autre"
                        descriptor_rows[(corpus, uri)] = {"corpus": corpus, "partition": partition, "uri": uri,
                                                          **descriptors(reference, uem, short_turn),
                                                          "type_reunion": meeting}
                    errors = file_errors(reference, hypothesis, uem)
                    for kind in ERROR_TYPES:
                        deviation = max(deviation, abs(errors["totaux"][kind] - float(row[f"{kind}_c0_s"])))
                    zones = categorized_zones(errors)
                    counts = tally(zones)
                    tallies.append(counts)
                    for kind, values in counts.items():
                        per_file_categories.append({"systeme": system["nom"], "exp_id": exp_id, "corpus": corpus,
                                                    "partition": partition, "uri": uri, "type_erreur": kind,
                                                    **tally_row(values, with_share=False)})
                    k_ref, k_hyp = int(row["n_locuteurs_reference"]), int(row["n_locuteurs_hypothese"])
                    files.append({"systeme": system["nom"], "exp_id": exp_id, "corpus": corpus,
                                  "partition": partition, "uri": uri, "rang": None, "pire": False,
                                  **{key: float(row[key]) for key in ("der_c0", "manquee_c0", "fausse_alarme_c0",
                                                                      "confusion_c0", "der_c025")},
                                  "n_locuteurs_reference": k_ref, "n_locuteurs_hypothese": k_hyp,
                                  "erreur_n_locuteurs": k_hyp - k_ref})
                    if corpus in set(config["extraits"]["corpus"]) | set(
                            (config["extraits"].get("locaux") or {}).get("corpus", [])):
                        candidates.append({"systeme": system["nom"], "exp_id": exp_id, "corpus": corpus,
                                           "partition": partition, "uri": uri, "der_c0": float(row["der_c0"]),
                                           "uem_debut": uem.extent().start, "uem_fin": uem.extent().end,
                                           "zones": zones, "rttm": rttms[-1]})
                fingerprints[str(hyp_dir.relative_to(experiments_root.parent)) + f" ({partition})"] = sha256_files(rttms)
            controls[f"{system['nom']}/{corpus}"] = round(deviation, 4)
            if deviation > TOTALS_TOLERANCE_S:
                sys.exit(f"{exp_id} {corpus} : carte des erreurs et per_file diffèrent de {deviation:.3f} s")
            files.sort(key=lambda f: (-f[criterion], f["partition"], f["uri"]))
            for rank, entry in enumerate(files, start=1):
                entry["rang"], entry["pire"] = rank, rank <= n_worst
            ranking += files
            merged = merge_tallies(tallies)
            for kind, values in merged.items():
                aggregated.append({"systeme": system["nom"], "exp_id": exp_id, "corpus": corpus,
                                   "partitions": "+".join(source["partitions"]), "n_fichiers": len(files),
                                   "type_erreur": kind, **tally_row(values, with_share=True)})

    correlations = []
    spec = config["correlations"]
    for system in config["systemes"]:
        for source in system["sources"]:
            files = [f for f in ranking if f["systeme"] == system["nom"] and f["corpus"] == source["corpus"]]
            table = []
            for f in files:
                d = descriptor_rows[(f["corpus"], f["uri"])]
                table.append({**f, **d, "erreur_n_locuteurs_abs": abs(f["erreur_n_locuteurs"]),
                              "zoom": {"zoom": 1, "autre": 0}.get(d["type_reunion"])})
            for component in spec["composantes"]:
                for name in spec["descripteurs"]:
                    values = [t[name] for t in table]
                    if all(v is None for v in values):
                        continue           # descripteur sans objet pour ce corpus (type de réunion)
                    correlations.append({"systeme": system["nom"], "corpus": source["corpus"], "composante": component,
                                         "descripteur": name, "n_fichiers": sum(v is not None for v in values),
                                         "rho_spearman": spearman(values, [t[component] for t in table])})

    out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(out_dir / "classement.csv", ranking)
    write_csv(out_dir / "descripteurs.csv", list(descriptor_rows.values()))
    write_csv(out_dir / "correlations.csv", correlations)
    write_csv(out_dir / "categories.csv", aggregated)
    write_csv(out_dir / "categories_par_fichier.csv", per_file_categories)

    spec = config["extraits"]
    listing = {}
    groups = [("public", set(spec["corpus"]), listen_dir, "A-0003 — écoute des cas d'échec")]
    local = spec.get("locaux") or {}
    if listen_dir is not None and local:
        groups.append(("local", set(local.get("corpus", [])), listen_dir.parent / Path(local["dossier"]).name,
                       "A-0003 — écoute, corpus maison (local, jamais publié)"))
    excerpts = []
    for name, corpora, target, title in groups:
        selected = select_excerpts([c for c in candidates if c["corpus"] in corpora], spec)
        if name == "public":
            excerpts = selected
        if target is not None and selected:
            export_excerpts(selected, target, data_root, title)
            listing[name] = len(selected)
    fields = list(public_fields(excerpts[0])) if excerpts else ["extrait"]
    write_csv(out_dir / "extraits.csv", [public_fields(e) for e in excerpts], fields)

    return {
        "sources_sha256": fingerprints,
        "references_rttm_sha256": {corpus: sha256_files(sorted(set(paths))) for corpus, paths in references_used.items()},
        "app_sortie_sha256": hashlib.sha256(Path(sortie.__file__).read_bytes()).hexdigest(),
        "seuils_carte": {"tour_court_s": sortie.SHORT_TURN_S, "pause_courte_s": sortie.SHORT_PAUSE_S,
                         "frontiere_s": sortie.BOUNDARY_S, "contigu_s": sortie.TOUCH_S},
        "controle_totaux_ecart_max_s": controls,
        "extraits": listing,
    }


def _home(path: Path) -> str:
    return str(path).replace(str(Path.home()), "~", 1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0],
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", required=True, type=Path, help="config.yaml de l'analyse (dans analyses/A-…)")
    parser.add_argument("--donnees", type=Path, default=DATA_DIR,
                        help="racine des données non versionnées (références, audio) ; défaut : data/ du dépôt")
    parser.add_argument("--sortie", type=Path, default=None,
                        help="essai : dossier des résultats (et des extraits, dans ecoute/) à la place du dossier "
                             "de l'analyse, qui reste inchangé")
    parser.add_argument("--experiences", type=Path, default=EXPERIMENTS_DIR,
                        help="dossier des expériences sources ; défaut : experiments/ du dépôt")
    parser.add_argument("--sans-extraits", action="store_true", help="ne pas exporter les extraits d'écoute")
    args = parser.parse_args()
    config_path = args.config.resolve()
    config = yaml.safe_load(config_path.read_text())
    trial = args.sortie is not None
    out_dir = args.sortie.resolve() if trial else config_path.parent
    if (out_dir / "execution.json").exists():
        sys.exit(f"{out_dir.name}/execution.json existe déjà : une analyse exécutée est immuable")
    if trial and out_dir.is_relative_to(REPO_ROOT / "analyses"):
        sys.exit("--sortie : un essai ne s'écrit pas dans analyses/")
    listen_dir = None if args.sans_extraits else (
        out_dir / "ecoute" if trial else REPO_ROOT / config["extraits"]["dossier"])
    state = git_state()
    details = run(config, out_dir, args.donnees.resolve(), listen_dir, args.experiences.resolve())
    execution = {
        "analyse_id": config["analyse_id"],
        "essai": trial,
        "date": datetime.now().astimezone().isoformat(timespec="seconds"),
        "git_commit": state["commit"], "arbre_propre": state["clean"], "fichiers_non_commites": state["dirty"],
        "config_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
        "donnees": _home(args.donnees.resolve()),
        "experiences": _home(args.experiences.resolve()),
        "dossier_ecoute": None if listen_dir is None else _home(listen_dir),
        **details,
    }
    (out_dir / "execution.json").write_text(json.dumps(execution, ensure_ascii=False, indent=2) + "\n")
    print(f"[A-0003] {'essai, ' if trial else ''}résultats dans {_home(out_dir)} ; extraits : {details['extraits']}")


if __name__ == "__main__":
    main()
