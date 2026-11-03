"""A-0004 — niveau d'entrée et parole manquée (D29 §1, hypothèse 1).

Usage :
    uv run python scripts/analyses/a0004_niveau_entree.py --config analyses/A-0004_niveau-entree/config.yaml

Analyse a posteriori (D21 §1, methode.md §4.7) : aucun moteur n'est exécuté. Pour chaque
fichier des jeux de la configuration, le niveau de la parole est mesuré sur l'audio normalisé
(D16 ; pour une condition de D24, l'audio dégradé) : valeur efficace (RMS) en dBFS sur les
zones de parole de la référence restreinte à l'UEM officiel, pleine échelle = 1,0 (PCM 16
bits divisé par 32 768). Sont aussi relevés le niveau sur tout l'UEM et la crête.

Puis, pour chaque système et chaque groupe de jeux (un corpus, ses partitions réunies ;
et AMI et SUMM-RE réunis), la corrélation de rang de Spearman entre ce niveau et la parole
manquée sans collar du fichier (`manquee_c0`, en % de la parole de référence, lue dans le
per_file de l'expérience). Descriptive, comme dans A-0003 : les fichiers ne sont pas des
tirages indépendants d'une même population ; aucune p-valeur n'est calculée.

Sorties : `niveaux.csv` (une ligne par corpus × fichier), `correlations.csv` (une ligne par
système × groupe), `execution.json` (commit, état de l'arbre, empreintes).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

import whospoke  # noqa: F401  (D27 : télémétrie coupée avant tout import tiers)
import numpy as np
import yaml
from scipy.io import wavfile
from scipy.stats import spearmanr

from whospoke.experiment import (
    REPO_ROOT, dataset_uris, git_state, load_rttm, load_uem, processed_wav, reference_rttm, uem_path,
)
from whospoke.partage import experiment_dir

SAMPLE_RATE = 16000
FULL_SCALE = 32768.0


def dbfs(samples: np.ndarray) -> float | None:
    if samples.size == 0:
        return None
    power = float(np.mean(np.square(samples, dtype=np.float64)))
    return None if power <= 0 else 10.0 * np.log10(power)


def mask_of(timeline, n: int) -> np.ndarray:
    mask = np.zeros(n, dtype=bool)
    for segment in timeline:
        mask[int(segment.start * SAMPLE_RATE): int(segment.end * SAMPLE_RATE)] = True
    return mask


def file_levels(corpus: str, uri: str) -> dict:
    """Niveaux d'un fichier : parole de la référence dans l'UEM, tout l'UEM, crête (dBFS)."""
    rate, data = wavfile.read(processed_wav(corpus, uri), mmap=True)
    if rate != SAMPLE_RATE or data.dtype != np.int16:
        raise ValueError(f"{corpus}/{uri} : PCM 16 bits à {SAMPLE_RATE} Hz attendu")
    signal = np.asarray(data, dtype=np.float64) / FULL_SCALE
    uem = load_uem(uem_path(corpus, uri), uri)
    speech = load_rttm(reference_rttm(corpus, uri), uri).get_timeline().support().crop(uem)
    in_uem, in_speech = mask_of(uem, len(signal)), mask_of(speech, len(signal))
    return {
        "niveau_parole_dbfs": dbfs(signal[in_speech]),
        "niveau_uem_dbfs": dbfs(signal[in_uem]),
        "crete_dbfs": 20.0 * np.log10(float(np.max(np.abs(signal)))) if np.any(signal) else None,
        "parole_s": round(float(in_speech.sum()) / SAMPLE_RATE, 1),
    }


def read_per_file(path: Path) -> dict[str, dict]:
    with path.open() as handle:
        return {row["uri"]: row for row in csv.DictReader(handle)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0],
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", required=True, type=Path, help="config.yaml de l'analyse (dans analyses/A-…)")
    args = parser.parse_args()
    config_path = args.config.resolve()
    out_dir = config_path.parent
    config = yaml.safe_load(config_path.read_text())
    if (out_dir / "execution.json").exists():
        sys.exit(f"{out_dir.name}/execution.json existe déjà : une analyse exécutée est immuable")
    state = git_state()

    levels: dict[tuple[str, str], dict] = {}
    rows = []
    for jeu in config["jeux"]:
        for uri in dataset_uris(jeu["liste"]):
            key = (jeu["corpus"], uri)
            if key in levels:
                continue
            levels[key] = file_levels(jeu["corpus"], uri)
            rows.append({"corpus": jeu["corpus"], "partition": jeu["partition"], "uri": uri,
                         **{k: (round(v, 2) if isinstance(v, float) else v) for k, v in levels[key].items()}})
    with (out_dir / "niveaux.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    sources_sha = {}
    correlations = []
    for system in config["systemes"]:
        points: dict[str, list[tuple[float, float]]] = {}
        for source in system["sources"]:
            directory = experiment_dir(source["exp_id"])
            for partition in source["partitions"]:
                path = directory / f"per_file_{source['corpus']}_{partition}.csv"
                sources_sha[str(path.relative_to(REPO_ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
                for uri, row in read_per_file(path).items():
                    level = levels[(source["corpus"], uri)]["niveau_parole_dbfs"]
                    for group in source["groupes"]:
                        points.setdefault(group, []).append((level, float(row["manquee_c0"])))
        for group, values in points.items():
            x, y = zip(*values)
            rho = spearmanr(x, y).statistic
            correlations.append({"systeme": system["nom"], "groupe": group, "n_fichiers": len(values),
                                 "rho_niveau_manquee_c0": round(float(rho), 3),
                                 "niveau_median_dbfs": round(float(np.median(x)), 2),
                                 "manquee_c0_mediane": round(float(np.median(y)), 2)})
    with (out_dir / "correlations.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(correlations[0]))
        writer.writeheader()
        writer.writerows(correlations)

    execution = {
        "analyse_id": config["analyse_id"],
        "date": datetime.now().astimezone().isoformat(timespec="seconds"),
        "git_commit": state["commit"], "arbre_propre": state["clean"], "fichiers_non_commites": state["dirty"],
        "config_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
        "sources_sha256": sources_sha,
        "n_fichiers_mesures": len(rows),
    }
    (out_dir / "execution.json").write_text(json.dumps(execution, ensure_ascii=False, indent=2) + "\n")
    print(f"[A-0004] {len(rows)} fichiers mesurés, {len(correlations)} corrélations, execution.json")
    for c in correlations:
        print(f"  {c['systeme']:10s} {c['groupe']:14s} n={c['n_fichiers']:3d} rho={c['rho_niveau_manquee_c0']:+.3f} "
              f"niveau médian {c['niveau_median_dbfs']} dBFS, manquée médiane {c['manquee_c0_mediane']} %")


if __name__ == "__main__":
    main()
