"""Chaîne du corpus maison, enregistrement par enregistrement (chantier E2).

Pas-à-pas complet : docs/corpus-maison/guide-annotation.md. Tout reste dans
`data/raw/maison/<Mxx>/` (non versionné) et sur cette machine : aucun accès réseau,
aucun modèle chargé (D27 ; corpus-maison/README.md).

    uv run python scripts/data/maison.py etat M01             # où en est la session, étape suivante
    uv run python scripts/data/maison.py synchroniser M01     # étape 1 : claquements, décalages, dérives
    uv run python scripts/data/maison.py preannoter M01       # étape 2 : étiquettes Audacity à corriger
    uv run python scripts/data/maison.py convertir M01        # étape 4 : RTTM, UEM et contrôles automatiques
    uv run python scripts/data/maison.py tirer-controle M01   # contrôle qualité : fenêtre de 2 min à ré-annoter
    uv run python scripts/data/maison.py accord M01           # contrôle qualité : DER entre les deux annotations
    uv run python scripts/data/maison.py versionner M01       # copie versionnée, si tous ont coché l'option 3

L'étape 3 (correction à l'écoute) se fait dans Audacity.

Séance sans claquement ni piste d'aide (M01, voiture) : pas de `synchroniser` ni de
`preannoter`. On annote à partir de zéro et on pose deux labels ponctuels `début` et `fin`
(casse et accents indifférents) qui bornent l'UEM ; `convertir` normalise alors la table
lui-même et consigne « repères manuels » comme source de l'UEM dans `conversion.json`.
`metadonnees.yaml` n'est pas exigé pour convertir, seulement pour versionner.

Fichiers d'une session :

    M01/table.<ext>, S1.<ext>, S2.<ext>…, fiche.md     déposés par la candidate (protocole §6)
    M01/metadonnees.yaml                                condition et options de consentement, sans nom
    M01/travail/                                        audio normalisé (16 kHz mono) et pistes alignées
    M01/synchro.json                                    claquements, décalages, dérives, alertes
    M01/preannotation/                                  S1.txt…, a_verifier.txt, parametres.json
    M01/annotation/                                     étiquettes corrigées, exportées d'Audacity
    M01/conversion.json                                 rapport de conversion et des contrôles automatiques
    M01/controle/                                       fenetre.json, étiquettes ré-annotées, accord.json

Références (conventions d'annotation, amendement du 01/11) : `data/processed/maison/`
(non versionné) reçoit `maison__M01.wav` (signal de test normalisé), `rttm/maison__M01.rttm`
et `uem/maison__M01.uem`, aux emplacements lus par l'évaluation (`whospoke.experiment`).
`versionner` les copie dans `data/splits/maison/{rttm,uem}/` (versionné) seulement si
`metadonnees.yaml` indique l'option 3 pour tous les participants ; la copie n'est pas
ajoutée à git par le script.

Pour l'interface, qui évalue de 0 à la durée du fichier, `convertir` écrit aussi
`audio/M01_uem.wav` (16 kHz mono, coupé du début à la fin de l'UEM, ffmpeg local) et
`rttm/M01_uem.rttm` (fichier `M01_uem`, instants décalés de −début de l'UEM), dans le même
dossier non versionné. Les zones exclues au milieu de l'UEM restent dans cet extrait.
"""

from __future__ import annotations

import argparse
import json
import re
import secrets
import shutil
import sys
from datetime import datetime
from pathlib import Path

import whospoke  # noqa: F401  (D27 : télémétrie coupée avant tout import tiers)
import numpy as np
from scipy.io import wavfile

from whospoke.audio import SAMPLE_RATE, load_waveform, normalize
from whospoke.experiment import DATA_DIR
from whospoke.maison import metadonnees as meta
from whospoke.maison import preannotation as pre
from whospoke.maison import reference as ref
from whospoke.maison import synchro

DEFAULT_ROOT = DATA_DIR / "raw" / "maison"
PROCESSED_DIR = DATA_DIR / "processed" / "maison"   # références, non versionnées
VERSIONED_DIR = DATA_DIR / "splits" / "maison"      # copie versionnée (option 3 de tous)
NOT_AUDIO = {".md", ".txt", ".json", ".csv", ".rttm", ".uem", ".yaml", ".yml", ".aup3", ".aup3-wal", ".aup3-shm"}
_AID = re.compile(r"^S\d+$")
CONTROL_WINDOW_S = 120.0      # conventions §5 : deux minutes ré-annotées
MIN_DELAY_H = 24.0            # conventions §5 : au moins un jour après la première annotation


class SessionError(RuntimeError):
    """Étape impossible en l'état (fichier manquant, contrôle bloquant…)."""


# --- Fichiers d'une session -------------------------------------------------------------


def uri_of(session: str) -> str:
    return f"maison__{session}"


def reference_paths(session: str, processed: Path = PROCESSED_DIR) -> dict[str, Path]:
    """Audio normalisé, RTTM et UEM de référence d'un enregistrement (mêmes chemins que
    `processed_wav`, `reference_rttm` et `uem_path` de `whospoke.experiment`)."""
    uri = uri_of(session)
    return {"wav": processed / f"{uri}.wav", "rttm": processed / "rttm" / f"{uri}.rttm",
            "uem": processed / "uem" / f"{uri}.uem"}


def sorted_codes(codes) -> list[str]:
    return sorted(codes, key=lambda code: (len(code), code))


def source_files(session_dir: Path) -> tuple[Path, dict[str, Path]]:
    """(signal de test, {code: piste d'aide}) parmi les fichiers déposés."""
    audio = [p for p in session_dir.iterdir() if p.is_file() and p.suffix.lower() not in NOT_AUDIO
             and not p.name.startswith(".")]
    tables = [p for p in audio if p.stem.lower() == "table"]
    if len(tables) != 1:
        raise SessionError(f"{session_dir} : un fichier « table.<ext> » attendu, {len(tables)} trouvé(s)")
    aids: dict[str, Path] = {}
    for path in audio:
        if _AID.match(path.stem.upper()):
            code = path.stem.upper()
            if code in aids:
                raise SessionError(f"{session_dir} : deux fichiers pour {code}")
            aids[code] = path
    return tables[0], {code: aids[code] for code in sorted_codes(aids)}


def normalized(src: Path, dst: Path) -> np.ndarray:
    """Signal normalisé en 16 kHz mono (ffmpeg), refait seulement si la source est plus récente."""
    if not dst.is_file() or dst.stat().st_mtime < src.stat().st_mtime:
        normalize(src, dst)
    waveform, _ = load_waveform(dst)
    return waveform[0].numpy()


def write_wav(path: Path, signal: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    wavfile.write(path, SAMPLE_RATE, np.round(np.clip(signal, -1.0, 1.0) * 32767.0).astype(np.int16))


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def read_json(path: Path, step: str) -> dict:
    if not path.is_file():
        raise SessionError(f"{path.name} absent : lancez d'abord l'étape « {step} »")
    return json.loads(path.read_text())


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def say(message: str = "") -> None:
    print(message, flush=True)


# --- Étape 1 : synchronisation ------------------------------------------------------------


def synchronize(session_dir: Path, session: str, already_aligned: bool = False,
                clap_start: float | None = None, clap_end: float | None = None,
                params: synchro.SyncParams = synchro.SyncParams()) -> dict:
    table_path, aid_paths = source_files(session_dir)
    work = session_dir / "travail"
    say(f"Normalisation de {table_path.name} et de {len(aid_paths)} piste(s) d'aide (16 kHz mono)…")
    table = normalized(table_path, work / "table.wav")
    start, end = synchro.find_table_claps(table, params, start_s=clap_start, end_s=clap_end)
    say(f"Claquements dans la table : {start:.3f} s et {end:.3f} s"
        + (" (imposés)" if clap_start is not None and clap_end is not None else ""))
    table_filtered = synchro.highpass(table, params.passe_haut_hz)
    tracks = []
    for code, path in aid_paths.items():
        aid = normalized(path, work / f"{code}.wav")
        sync = (synchro.identity(code, start, end) if already_aligned
                else synchro.sync_track(code, table_filtered, aid, start, end, params))
        write_wav(work / "alignees" / f"{code}.wav", synchro.align(aid, sync, start, len(table)))
        line = sync.to_dict(start)
        tracks.append(line)
        say(f"  {code} : décalage {line['decalage_s']:+.3f} s, dérive {line['derive_ppm']:+.0f} ppm"
            + (f", corrélations {line['correlation_debut']} / {line['correlation_fin']}" if not already_aligned else "")
            + "".join(f"\n    ALERTE : {alert}" for alert in sync.alertes))
    data = {
        "session": session, "date": now(),
        "methode": "pistes déjà alignées (aucune correction)" if already_aligned
        else "corrélation croisée autour des deux claquements",
        "table": {"fichier": table_path.name, "duree_s": round(len(table) / SAMPLE_RATE, 3)},
        "claquements_table_s": {"debut": round(start, 3), "fin": round(end, 3),
                                "imposes": {"debut": clap_start is not None, "fin": clap_end is not None}},
        "reglages": params.as_dict(),
        "pistes": tracks,
    }
    write_json(session_dir / "synchro.json", data)
    say(f"Écrit : {session_dir / 'synchro.json'} ; pistes alignées dans {work / 'alignees'}")
    return data


# --- Étape 2 : pré-annotation ------------------------------------------------------------


def preannotate(session_dir: Path, session: str,
                params: pre.PreannotationParams = pre.PreannotationParams()) -> dict:
    sync = read_json(session_dir / "synchro.json", "synchroniser")
    codes = [track["piste"] for track in sync["pistes"]]
    if not codes:
        raise SessionError("Aucune piste d'aide : annotation à partir de zéro (guide, cas M02)")
    tracks = {}
    for code in codes:
        waveform, _ = load_waveform(session_dir / "travail" / "alignees" / f"{code}.wav")
        tracks[code] = waveform[0].numpy()
    claps = sync["claquements_table_s"]
    start, end = claps["debut"] + ref.UEM_MARGIN_S, claps["fin"] - ref.UEM_MARGIN_S
    result = pre.preannotate(tracks, start, end, params)
    out = session_dir / "preannotation"
    for code, intervals in result.segments.items():
        ref.write_labels(out / f"{code}.txt", [(a, b, code) for a, b in intervals])
    ref.write_labels(out / "a_verifier.txt", result.a_verifier)
    counts = {code: {"n_segments": len(intervals), "temps_s": round(sum(b - a for a, b in intervals), 1)}
              for code, intervals in result.segments.items()}
    data = {"session": session, "date": now(), "zone_s": [round(start, 3), round(end, 3)],
            "reglages": params.as_dict(),
            "planchers_db": {code: round(value, 1) for code, value in result.planchers_db.items()},
            "pistes": counts, "n_zones_a_verifier": len(result.a_verifier)}
    write_json(out / "parametres.json", data)
    for code, count in counts.items():
        say(f"  {code} : {count['n_segments']} segments, {count['temps_s']} s")
    say(f"  à vérifier : {len(result.a_verifier)} zones")
    say(f"Écrit : {out}/ (à importer dans Audacity avec travail/table.wav)")
    return data


# --- Étape 4 : conversion et contrôles ----------------------------------------------------


def expected_speakers(sync: dict | None, session: str, n_speakers: int | None,
                      metadata: meta.Metadata | None = None, found: list[str] = ()) -> list[str]:
    """Participants attendus : `--locuteurs`, sinon les métadonnées, sinon une piste d'aide par
    participant ; sans synchronisation ni piste d'aide, les locuteurs des étiquettes."""
    if n_speakers is not None:
        return [f"{session}_S{i}" for i in range(1, n_speakers + 1)]
    if metadata is not None:
        return [f"{session}_{code}" for code in metadata.participants]
    if sync is not None and sync["pistes"]:
        return [f"{session}_{track['piste']}" for track in sync["pistes"]]
    return list(found)


def uem_bounds(session_dir: Path, annotation: ref.Annotation) -> tuple[list[ref.Interval], dict, list[str]]:
    """UEM, sa source (consignée dans conversion.json) et avertissements.

    Avec `synchro.json` : du claquement de début + 1 s au claquement de fin − 1 s. Sans
    synchronisation (séance sans claquement ni piste d'aide, M01) : du repère « début » au
    repère « fin » posés dans Audacity. Dans les deux cas, moins les zones « exclusion »."""
    warnings = []
    if (session_dir / "synchro.json").is_file():
        claps = read_json(session_dir / "synchro.json", "synchroniser")["claquements_table_s"]
        if annotation.markers:
            warnings.append("repères « début » / « fin » ignorés : l'UEM suit les claquements (synchro.json)")
        uem = ref.uem_intervals(claps["debut"], claps["fin"], annotation.exclusions)
        source = {"methode": "claquements", "claquements_s": [claps["debut"], claps["fin"]],
                  "marge_s": ref.UEM_MARGIN_S}
    else:
        start, end = ref.marker_bounds(annotation)
        uem = ref.uem_intervals(start, end, annotation.exclusions, margin_s=0.0)
        source = {"methode": "repères manuels", "reperes_s": [round(start, 3), round(end, 3)],
                  "emplacements": {key: annotation.markers[key][0][1] for key in ref.MARKERS}, "marge_s": 0.0}
    return uem, source, warnings


def interface_paths(session: str, processed: Path = PROCESSED_DIR) -> dict[str, Path]:
    """Copies pour l'interface, qui évalue de 0 à la durée du fichier : audio coupé à l'UEM
    et référence décalée de −(début de l'UEM)."""
    return {"wav": processed / "audio" / f"{session}_uem.wav", "rttm": processed / "rttm" / f"{session}_uem.rttm"}


def cut(src: Path, dst: Path, start: float, end: float, ffmpeg: str = "ffmpeg") -> None:
    """[start, end] de `src` en WAV 16 kHz mono (ffmpeg local, coupe à l'échantillon près)."""
    import subprocess

    dst.parent.mkdir(parents=True, exist_ok=True)
    command = [ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-i", str(src),
               "-af", f"atrim=start={start:.6f}:end={end:.6f},asetpts=PTS-STARTPTS",
               "-ac", "1", "-ar", str(SAMPLE_RATE), "-c:a", "pcm_s16le", str(dst)]
    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode != 0:
        raise SessionError(f"ffmpeg a échoué sur {src.name} : {completed.stderr.strip()[-300:]}")


def write_interface_copies(session: str, reference: ref.Reference, source_wav: Path,
                           processed: Path = PROCESSED_DIR) -> dict:
    """Écrit `audio/<Mxx>_uem.wav` et `rttm/<Mxx>_uem.rttm` (fichier `<Mxx>_uem`, même nom que
    l'audio pour l'interface) ; les zones exclues au milieu de l'UEM restent dans l'audio."""
    start, end = reference.uem[0][0], reference.uem[-1][1]
    paths = interface_paths(session, processed)
    cut(source_wav, paths["wav"], start, end)
    rate, samples = wavfile.read(paths["wav"])
    duration = len(samples) / rate
    if rate != SAMPLE_RATE or abs(duration - (end - start)) > 2.0 / SAMPLE_RATE:
        raise SessionError(f"{paths['wav'].name} : {duration:.4f} s à {rate} Hz au lieu de {end - start:.4f} s")
    shifted = {code: [(a - start, b - start) for a, b in intervals] for code, intervals in reference.speakers.items()}
    paths["rttm"].parent.mkdir(parents=True, exist_ok=True)
    paths["rttm"].write_text(ref.rttm_text(f"{session}_uem", shifted))
    inside = ref.subtract([(start, end)], reference.uem)
    return {"audio": str(paths["wav"]), "rttm": str(paths["rttm"]), "decalage_s": round(-start, 3),
            "duree_s": round(duration, 3),
            "exclusions_dans_l_extrait_s": [[round(a - start, 3), round(b - start, 3)] for a, b in inside]}


def convert(session_dir: Path, session: str, n_speakers: int | None = None,
            processed: Path = PROCESSED_DIR) -> dict:
    metadata = meta.load_optional(session_dir, session)
    annotation_dir = session_dir / "annotation"
    if not annotation_dir.is_dir():
        raise SessionError(f"{annotation_dir} absent : exportez les étiquettes corrigées d'Audacity (guide, étape 3)")
    annotation = ref.read_annotation(annotation_dir, session)
    sync_path = session_dir / "synchro.json"
    sync = read_json(sync_path, "synchroniser") if sync_path.is_file() else None
    uem, uem_source, uem_warnings = uem_bounds(session_dir, annotation)
    reference = ref.build_reference(annotation, uem)
    found = sorted_codes(annotation.speakers)
    report = ref.check_reference(reference, expected_speakers(sync, session, n_speakers, metadata, found))
    labels = {code: {"etiquettes": len(raw), "apres_union": len(ref.merge_intervals(raw, 0.0)),
                     "apres_fusion_200_ms": len(ref.merge_intervals(raw))}
              for code, raw in annotation.speakers.items()}
    uri = uri_of(session)
    paths = reference_paths(session, processed)
    rttm, uem_file = paths["rttm"], paths["uem"]
    warnings = annotation.warnings + uem_warnings
    data = {"session": session, "date": now(), "uri": uri,
            "condition": metadata.condition if metadata else None,
            "uem_source": uem_source, "fusion_s": ref.MERGE_GAP_S, "marge_uem_s": uem_source["marge_s"],
            "exclusions": [[round(a, 3), round(b, 3)] for a, b in sorted(annotation.exclusions)],
            "fusions": labels, "avertissements_lecture": warnings, "coupes_uem": reference.cropped} | report
    data["valide"] = not report["bloquants"]
    data["references"] = {key: str(path) for key, path in paths.items()} if data["valide"] else None
    data["interface"] = None
    if data["valide"]:
        for path in paths.values():
            path.parent.mkdir(parents=True, exist_ok=True)
        table_wav = session_dir / "travail" / "table.wav"
        if sync is None:                       # sans synchronisation, la table n'est pas encore normalisée
            table_path, _ = source_files(session_dir)
            say(f"Normalisation de {table_path.name} (16 kHz mono, ffmpeg local)…")
            normalized(table_path, table_wav)
        shutil.copyfile(table_wav, paths["wav"])
        rttm.write_text(ref.rttm_text(uri, reference.speakers))
        uem_file.write_text(ref.uem_text(uri, reference.uem))
        data["interface"] = write_interface_copies(session, reference, paths["wav"], processed)
    else:
        rttm.unlink(missing_ok=True)
        uem_file.unlink(missing_ok=True)
        for path in interface_paths(session, processed).values():
            path.unlink(missing_ok=True)
    write_json(session_dir / "conversion.json", data)
    stats = report["statistiques"]
    say(f"UEM ({uem_source['methode']}) : {stats['uem_s']:.1f} s"
        + (f", de {uem_source['reperes_s'][0]:.3f} à {uem_source['reperes_s'][1]:.3f} s"
           if "reperes_s" in uem_source else "")
        + f" ; parole : {stats['parole_s']:.1f} s ; {stats['n_locuteurs']} locuteur(s)")
    for code, row in stats["locuteurs"].items():
        merged = labels.get(code, {})
        say(f"  {code} : {row['n_segments']} segments, {row['temps_s']:.1f} s de parole ({100 * row['part']:.0f} %)"
            + (f" ; {merged['etiquettes']} étiquettes, {merged['apres_union']} après union des doublons et "
               f"recouvrements" if merged else ""))
    say(f"Chevauchement : {100 * (stats['taux_chevauchement'] or 0):.1f} % de la parole "
        f"({stats['chevauchement_s']:.1f} s)")
    for message in warnings + reference.cropped + report["avertissements"]:
        say(f"  avertissement : {message}")
    for message in report["bloquants"]:
        say(f"  BLOQUANT : {message}")
    if metadata is None:
        say(f"  avertissement : {meta.FILENAME} absent (condition et participants inconnus ; nécessaire pour versionner)")
    if data["interface"]:
        say(f"Interface : {data['interface']['audio']} ({data['interface']['duree_s']:.1f} s) et "
            f"{data['interface']['rttm']} (décalé de {data['interface']['decalage_s']:+.3f} s)")
        if data["interface"]["exclusions_dans_l_extrait_s"]:
            say("  avertissement : zones exclues au milieu de l'UEM, restées dans l'extrait de l'interface : "
                + ", ".join(f"{a:.1f}–{b:.1f} s" for a, b in data["interface"]["exclusions_dans_l_extrait_s"]))
    say(f"Écrit : {session_dir / 'conversion.json'}"
        + (f" ; références dans {processed} (audio, rttm/, uem/)" if data["valide"] else " ; RTTM et UEM NON écrits"))
    if not data["valide"]:
        raise SessionError("contrôles bloquants : corrigez les étiquettes dans Audacity, exportez, reconvertissez")
    return data


# --- Contrôle qualité : fenêtre ré-annotée et accord -------------------------------------


def read_rttm(path: Path) -> dict[str, list[ref.Interval]]:
    speakers: dict[str, list[ref.Interval]] = {}
    for line in path.read_text().splitlines():
        fields = line.split()
        if fields and fields[0] == "SPEAKER":
            start, duration = float(fields[3]), float(fields[4])
            speakers.setdefault(fields[7], []).append((start, start + duration))
    return speakers


def read_uem(path: Path) -> list[ref.Interval]:
    return [(float(f[2]), float(f[3])) for f in (line.split() for line in path.read_text().splitlines()) if f]


def draw_window(session_dir: Path, session: str, duration_s: float = CONTROL_WINDOW_S,
                seed: int | None = None, processed: Path = PROCESSED_DIR) -> dict:
    uem_file = reference_paths(session, processed)["uem"]
    if not uem_file.is_file():
        raise SessionError("Référence absente : lancez d'abord « convertir » sans contrôle bloquant")
    uem = read_uem(uem_file)
    longest = max(uem, key=lambda interval: interval[1] - interval[0])
    span = longest[1] - longest[0]
    seed = secrets.randbelow(10**6) if seed is None else seed
    start = longest[0] + np.random.default_rng(seed).uniform(0.0, max(0.0, span - duration_s))
    window = [round(start, 3), round(min(longest[1], start + duration_s), 3)]
    data = {"session": session, "date": now(), "graine": seed, "fenetre_s": window,
            "consigne": "ré-annoter cette fenêtre à partir de zéro, au moins un jour après la première "
                        "annotation, sans voir la pré-annotation ni la première annotation ; seule l'écoute "
                        "des pistes d'aide alignées est permise (conventions, amendement du 01/11)"}
    write_json(session_dir / "controle" / "fenetre.json", data)
    say(f"Fenêtre de contrôle : {window[0]:.3f} s à {window[1]:.3f} s (graine {seed})")
    say(f"Exportez les nouvelles étiquettes dans {session_dir / 'controle'}/, puis lancez « accord ».")
    return data


def _latest_mtime(paths: list[Path]) -> datetime | None:
    times = [p.stat().st_mtime for p in paths]
    return datetime.fromtimestamp(max(times)).astimezone() if times else None


def control_agreement(session_dir: Path, session: str, processed: Path = PROCESSED_DIR) -> dict:
    control_dir = session_dir / "controle"
    window_data = read_json(control_dir / "fenetre.json", "tirer-controle")
    uri = uri_of(session)
    paths = reference_paths(session, processed)
    first = read_rttm(paths["rttm"])
    uem = read_uem(paths["uem"])
    window = ref.intersect([tuple(window_data["fenetre_s"])], uem)
    control = ref.read_annotation(control_dir, session)
    second = {code: ref.merge_intervals(intervals) for code, intervals in control.speakers.items()}
    first_in = {code: ref.intersect(ref.merge_intervals(iv, 0.0), window) for code, iv in first.items()}
    second_in = {code: ref.intersect(iv, window) for code, iv in second.items()}
    first_in = {code: iv for code, iv in first_in.items() if iv}
    second_in = {code: iv for code, iv in second_in.items() if iv}
    if not second_in:
        raise SessionError("Aucune étiquette de contrôle dans la fenêtre tirée")
    scores = ref.agreement(first_in, second_in, window, uri)
    annotated = _latest_mtime(sorted((session_dir / "annotation").glob("*.txt")))
    controlled = _latest_mtime(sorted(control_dir.glob("*.txt")))
    delay_h = (controlled - annotated).total_seconds() / 3600 if annotated and controlled else None
    alerts = list(control.warnings)
    if delay_h is not None and delay_h < MIN_DELAY_H:
        alerts.append(f"ré-annotation {delay_h:.1f} h après la première (au moins {MIN_DELAY_H:.0f} h prévues, "
                      "conventions §5 ; d'après les dates des fichiers)")
    data = {"session": session, "date": now(), "fenetre_s": window_data["fenetre_s"],
            "duree_evaluee_s": round(sum(b - a for a, b in window), 3),
            "der_collar_0": round(scores["collar_0"]["der"], 2),
            "detail_collar_0": scores["collar_0"], "der_collar_0_25": round(scores["collar_0_25"]["der"], 2),
            "n_locuteurs": scores["n_locuteurs"],
            "dates_fichiers": {"annotation": annotated.isoformat(timespec="minutes") if annotated else None,
                               "controle": controlled.isoformat(timespec="minutes") if controlled else None,
                               "delai_h": None if delay_h is None else round(delay_h, 1)},
            "alertes": alerts,
            "lecture": "plancher de précision de la référence : aucun système ne peut être jugé meilleur "
                       "qu'à ce DER près (conventions §5) ; à reporter dans docs/corpus.md"}
    write_json(control_dir / "accord.json", data)
    say(f"Accord sur {data['duree_evaluee_s']:.0f} s : DER collar 0 = {data['der_collar_0']:.2f} % "
        f"(collar 0,25 s : {data['der_collar_0_25']:.2f} %)")
    for alert in alerts:
        say(f"  ALERTE : {alert}")
    return data


# --- Copie versionnée (option 3 de tous les participants) ----------------------------------


def version(session_dir: Path, session: str, processed: Path = PROCESSED_DIR,
            versioned: Path = VERSIONED_DIR) -> dict[str, Path]:
    """Copie RTTM et UEM dans le dossier versionné, si tous les participants ont coché l'option 3."""
    metadata = meta.load(session_dir, session)
    if not metadata.versioning_allowed():
        raise SessionError(f"option 3 non cochée par {', '.join(metadata.refusals())} : les références de "
                           f"{session} restent non versionnées (conventions, amendement du 01/11)")
    conversion = read_json(session_dir / "conversion.json", "convertir")
    paths = reference_paths(session, processed)
    if not conversion.get("valide") or not paths["rttm"].is_file() or not paths["uem"].is_file():
        raise SessionError("Références absentes ou non valides : lancez d'abord « convertir » sans contrôle bloquant")
    speakers = {code.split("_", 1)[1] for code in read_rttm(paths["rttm"])}
    missing = speakers - set(metadata.participants)
    if missing:
        raise SessionError(f"locuteurs {sorted(missing)} de la référence absents de {meta.FILENAME} : "
                           "leur consentement n'est pas consigné")
    copies = {}
    for kind in ("rttm", "uem"):
        target = versioned / kind / paths[kind].name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(paths[kind], target)
        copies[kind] = target
    say(f"Copié : {copies['rttm']} et {copies['uem']} (option 3 cochée par tous les participants). "
        "À vérifier avec `git status`, puis à commiter (`data:`) ; aucun audio, aucun nom.")
    return copies


# --- État d'une session -------------------------------------------------------------------


def status(session_dir: Path, session: str, processed: Path = PROCESSED_DIR) -> str:
    """Étape suivante, d'après les fichiers présents. `metadonnees.yaml` est signalé sans
    bloquer les étapes suivantes : seul `versionner` l'exige."""
    optional = f"{meta.FILENAME} (condition, options de consentement, sans nom ; exigé pour versionner seulement)"
    steps = [
        ("dépôt des fichiers (table.<ext>, S1.<ext>…, fiche.md)", lambda: _has_table(session_dir)),
        (optional, lambda: (session_dir / meta.FILENAME).is_file()),
        ("synchroniser (séance sans clap : repères « début » et « fin » dans les étiquettes)",
         lambda: (session_dir / "synchro.json").is_file() or _has_markers(session_dir, session)),
        ("preannoter (sauf session sans piste d'aide)", lambda: (session_dir / "preannotation").is_dir()
         or not (session_dir / "synchro.json").is_file()
         or not read_json(session_dir / "synchro.json", "synchroniser")["pistes"]),
        ("corriger dans Audacity et exporter dans annotation/",
         lambda: any((session_dir / "annotation").glob("*.txt"))),
        ("convertir", lambda: reference_paths(session, processed)["rttm"].is_file()),
        ("tirer-controle", lambda: (session_dir / "controle" / "fenetre.json").is_file()),
        ("ré-annoter la fenêtre (au moins un jour après) et exporter dans controle/",
         lambda: any((session_dir / "controle").glob("*.txt"))),
        ("accord", lambda: (session_dir / "controle" / "accord.json").is_file()),
    ]
    lines = []
    pending = None
    for label, done in steps:
        if label == optional:
            lines.append(f"  [{'x' if done() else ' '}] {label}")
            continue
        ok = pending is None and done()
        lines.append(f"  [{'x' if ok else ' '}] {label}")
        if not ok and pending is None:
            pending = label
    lines.append(f"Étape suivante : {pending}" if pending else "Session terminée.")
    return "\n".join(lines)


def _has_markers(session_dir: Path, session: str) -> bool:
    """Vrai si les étiquettes exportées portent les deux repères d'une séance sans clap."""
    try:
        annotation = ref.read_annotation(session_dir / "annotation", session)
    except (ref.LabelError, ValueError, OSError):
        return False
    return all(annotation.markers.get(key) for key in ref.MARKERS)


def _has_table(session_dir: Path) -> bool:
    try:
        source_files(session_dir)
    except SessionError:
        return False
    return True


# --- Ligne de commande -----------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Chaîne du corpus maison (synchronisation, pré-annotation, conversion, contrôle). "
                    "Pas-à-pas : docs/corpus-maison/guide-annotation.md.")
    parser.add_argument("--racine", type=Path, default=DEFAULT_ROOT,
                        help="dossier des sessions (défaut : data/raw/maison/)")
    parser.add_argument("--references", type=Path, default=PROCESSED_DIR,
                        help="dossier des références non versionnées (défaut : data/processed/maison/)")
    parser.add_argument("--versionnees", type=Path, default=VERSIONED_DIR,
                        help="dossier de la copie versionnée (défaut : data/splits/maison/)")
    commands = parser.add_subparsers(dest="commande", required=True)

    def session_command(name: str, help_text: str) -> argparse.ArgumentParser:
        command = commands.add_parser(name, help=help_text, description=help_text)
        command.add_argument("session", help="code de la session : M01, M02…")
        return command

    session_command("etat", "fichiers présents et étape suivante")
    sync = session_command("synchroniser", "étape 1 : normalisation, claquements, décalage et dérive de chaque piste d'aide")
    sync.add_argument("--deja-alignees", action="store_true",
                      help="pistes d'aide déjà alignées sur la table (pistes séparées d'un logiciel de visio) : "
                           "aucune correction")
    sync.add_argument("--clap-debut", type=float, help="instant (s) du claquement de début dans la table, s'il est mal détecté")
    sync.add_argument("--clap-fin", type=float, help="instant (s) du claquement de fin dans la table, s'il est mal détecté")
    defaults = pre.PreannotationParams()
    preannotate_cmd = session_command("preannoter", "étape 2 : pré-annotation par la piste d'aide la plus forte")
    preannotate_cmd.add_argument("--seuil-activite-db", type=float, default=defaults.seuil_activite_db,
                                 help=f"parole si la piste la plus forte dépasse son plancher de bruit de tant "
                                      f"de dB (défaut : {defaults.seuil_activite_db})")
    preannotate_cmd.add_argument("--marge-db", type=float, default=defaults.marge_db,
                                 help=f"zone « à vérifier » si la deuxième piste est à moins de tant de dB "
                                      f"(défaut : {defaults.marge_db})")
    convert_cmd = session_command("convertir", "étape 4 : étiquettes corrigées -> RTTM (fusion à 200 ms) et UEM "
                                               "(claquements, ou repères « début » et « fin » sans synchro.json), "
                                               "contrôles automatiques, copies coupées à l'UEM pour l'interface")
    convert_cmd.add_argument("--locuteurs", type=int,
                             help="nombre de participants attendus (défaut : un par piste d'aide)")
    draw = session_command("tirer-controle", "contrôle qualité : tire la fenêtre de 2 min à ré-annoter")
    draw.add_argument("--duree", type=float, default=CONTROL_WINDOW_S, help="durée de la fenêtre (s, défaut : 120)")
    draw.add_argument("--graine", type=int, help="graine du tirage (défaut : tirée au hasard et consignée)")
    session_command("accord", "contrôle qualité : DER entre l'annotation et la ré-annotation de la fenêtre")
    session_command("versionner", "copie RTTM et UEM dans data/splits/maison/, seulement si tous les participants "
                                  f"ont coché l'option 3 ({meta.FILENAME})")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not re.match(r"^M\d{2}$", args.session):
        say(f"Session {args.session!r} : M01, M02… attendu")
        return 2
    session_dir = args.racine.expanduser() / args.session
    processed = args.references.expanduser()
    if not session_dir.is_dir():
        say(f"Dossier absent : {session_dir}")
        return 1
    try:
        if args.commande == "etat":
            say(status(session_dir, args.session, processed))
        elif args.commande == "synchroniser":
            synchronize(session_dir, args.session, args.deja_alignees, args.clap_debut, args.clap_fin)
        elif args.commande == "preannoter":
            params = pre.PreannotationParams(seuil_activite_db=args.seuil_activite_db, marge_db=args.marge_db)
            preannotate(session_dir, args.session, params)
        elif args.commande == "convertir":
            convert(session_dir, args.session, args.locuteurs, processed)
        elif args.commande == "tirer-controle":
            draw_window(session_dir, args.session, args.duree, args.graine, processed)
        elif args.commande == "accord":
            control_agreement(session_dir, args.session, processed)
        elif args.commande == "versionner":
            version(session_dir, args.session, processed, args.versionnees.expanduser())
    except (SessionError, ref.LabelError, ValueError) as error:
        say(f"Arrêt : {error}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
