"""Synchronisation des pistes d'aide sur le signal de test par les claquements (E2, étape 1).

Protocole d'enregistrement §5 : un claquement de mains net au début et un à la fin,
après le démarrage de tous les appareils. Les instants s'expriment dans le temps du
signal de test (« table ») ; une piste d'aide est reliée à la table par une application
affine :

    temps_aide = aide_debut + rapport × (temps_table − clap_debut)

`aide_debut` et `aide_fin` sont les instants des deux claquements dans la piste d'aide,
trouvés par corrélation croisée normalisée d'un gabarit pris dans la table autour de
chaque claquement ; `rapport` corrige la dérive d'horloge entre appareils. Les signaux
sont d'abord filtrés en passe-haut : un claquement est large bande, la parole concentre
son énergie sous 1 kHz, et le filtre réduit l'effet des voix captées différemment par
chaque appareil.

Seuils (choisis a priori, validés sur signaux de synthèse seulement ; consignés dans
`synchro.json`) : voir `SyncParams`.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
from scipy.signal import butter, fftconvolve, sosfiltfilt

from whospoke.audio import SAMPLE_RATE


@dataclass(frozen=True)
class SyncParams:
    """Réglages de la synchronisation. Durées en secondes."""

    fenetre_clap_s: float = 60.0      # claquements cherchés dans la première et la dernière minute de la table
    passe_haut_hz: float = 1000.0     # filtre avant détection et corrélation
    trame_s: float = 0.005            # trame de l'enveloppe d'énergie (détection du claquement)
    contexte_s: float = 0.5           # référence de l'attaque : médiane des 0,5 s qui précèdent
    gabarit_avant_s: float = 0.1      # gabarit pris dans la table : 0,1 s avant le claquement…
    gabarit_apres_s: float = 0.5      # … et 0,5 s après (claquement et sa réverbération)
    recherche_aide_s: float = 180.0   # claquement de début cherché dans les 3 premières minutes de chaque piste d'aide
    marge_fin_s: float = 5.0          # claquement de fin cherché à ±5 s de sa position prévue sans dérive
    correlation_min: float = 0.3      # en dessous : claquement douteux, à vérifier à l'oreille
    derive_max_ppm: float = 1000.0    # au-delà de 0,1 % : appariement des claquements douteux

    def as_dict(self) -> dict:
        return asdict(self)


def highpass(signal: np.ndarray, cutoff_hz: float, sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    sos = butter(4, cutoff_hz, btype="highpass", fs=sample_rate, output="sos")
    return sosfiltfilt(sos, np.asarray(signal, dtype=np.float64))


def detect_clap(filtered: np.ndarray, start_s: float, end_s: float, params: SyncParams = SyncParams(),
                sample_rate: int = SAMPLE_RATE) -> float:
    """Instant (s) de l'attaque la plus franche de `filtered` (déjà en passe-haut) entre
    `start_s` et `end_s` : trame dont l'énergie dépasse le plus la médiane des trames qui
    la précèdent (`contexte_s`), en dB."""
    frame = max(1, int(round(params.trame_s * sample_rate)))
    lo = max(0, int(start_s * sample_rate))
    hi = min(len(filtered), int(end_s * sample_rate))
    n = (hi - lo) // frame
    if n < 2:
        raise ValueError("Fenêtre trop courte pour chercher un claquement")
    energy = (filtered[lo:lo + n * frame].reshape(n, frame) ** 2).mean(axis=1)
    db = 10.0 * np.log10(energy + 1e-12)
    context = max(1, int(round(params.contexte_s / params.trame_s)))
    padded = np.concatenate([np.full(context, db[0]), db])
    windows = np.lib.stride_tricks.sliding_window_view(padded[:-1], context)
    rise = db - np.median(windows, axis=1)
    return (lo + int(np.argmax(rise)) * frame) / sample_rate


def normalized_xcorr(template: np.ndarray, region: np.ndarray) -> np.ndarray:
    """Corrélation croisée normalisée de `template` glissé sur `region` (valeurs dans [-1, 1]).

    Indice k : `template` comparé à `region[k : k + len(template)]`.
    """
    m = len(template)
    if len(region) < m:
        return np.zeros(0)
    t = template - template.mean()
    norm_t = np.linalg.norm(t)
    corr = fftconvolve(region, t[::-1], mode="valid")
    squares = np.concatenate([[0.0], np.cumsum(region.astype(np.float64) ** 2)])
    sums = np.concatenate([[0.0], np.cumsum(region.astype(np.float64))])
    local_energy = (squares[m:] - squares[:-m]) - (sums[m:] - sums[:-m]) ** 2 / m
    floor = 1e-10 * m
    denominator = norm_t * np.sqrt(np.maximum(local_energy, floor))
    return corr / denominator if norm_t > 0 else np.zeros_like(corr)


def locate(template: np.ndarray, offset_in_template_s: float, region: np.ndarray, region_start_s: float,
           sample_rate: int = SAMPLE_RATE) -> tuple[float, float]:
    """(instant du claquement dans la piste, coefficient de corrélation au pic).

    `offset_in_template_s` : position du claquement dans le gabarit ; `region_start_s` :
    instant, dans la piste, du premier échantillon de `region`.
    """
    corr = normalized_xcorr(template, region)
    if len(corr) == 0:
        raise ValueError("Zone de recherche plus courte que le gabarit")
    best = int(np.argmax(np.abs(corr)))
    return region_start_s + best / sample_rate + offset_in_template_s, float(abs(corr[best]))


@dataclass
class TrackSync:
    """Alignement d'une piste d'aide sur la table (temps en secondes)."""

    piste: str
    aide_debut_s: float
    aide_fin_s: float | None
    rapport: float
    correlation_debut: float | None   # None : pistes déjà alignées, aucune corrélation
    correlation_fin: float | None
    alertes: list[str]

    def to_dict(self, clap_debut_s: float) -> dict:
        return {
            "piste": self.piste,
            "decalage_s": round(self.aide_debut_s - clap_debut_s, 6),
            "derive_ppm": round((self.rapport - 1.0) * 1e6, 1),
            "rapport": self.rapport,
            "claquement_debut_dans_la_piste_s": round(self.aide_debut_s, 6),
            "claquement_fin_dans_la_piste_s": None if self.aide_fin_s is None else round(self.aide_fin_s, 6),
            "correlation_debut": None if self.correlation_debut is None else round(self.correlation_debut, 3),
            "correlation_fin": None if self.correlation_fin is None else round(self.correlation_fin, 3),
            "alertes": self.alertes,
        }


def find_table_claps(table: np.ndarray, params: SyncParams = SyncParams(), sample_rate: int = SAMPLE_RATE,
                     start_s: float | None = None, end_s: float | None = None) -> tuple[float, float]:
    """Claquements de début et de fin dans la table ; `start_s` et `end_s` les imposent.

    Chacun est cherché dans `fenetre_clap_s` au début ou à la fin, sans dépasser la moitié
    de l'enregistrement.
    """
    duration = len(table) / sample_rate
    window = min(params.fenetre_clap_s, duration / 2)
    filtered = highpass(table, params.passe_haut_hz, sample_rate)
    if start_s is None:
        start_s = detect_clap(filtered, 0.0, window, params, sample_rate)
    if end_s is None:
        end_s = detect_clap(filtered, duration - window, duration, params, sample_rate)
    if end_s <= start_s:
        raise ValueError(f"Claquement de fin ({end_s:.2f} s) avant celui de début ({start_s:.2f} s) : "
                         "imposez-les à la main")
    return start_s, end_s


def sync_track(name: str, table_filtered: np.ndarray, aid: np.ndarray, clap_start_s: float, clap_end_s: float,
               params: SyncParams = SyncParams(), sample_rate: int = SAMPLE_RATE) -> TrackSync:
    """Instants des deux claquements dans la piste d'aide, dérive et alertes."""
    aid_filtered = highpass(aid, params.passe_haut_hz, sample_rate)
    before = int(params.gabarit_avant_s * sample_rate)
    after = int(params.gabarit_apres_s * sample_rate)
    alerts: list[str] = []

    def template(clap_s: float) -> tuple[np.ndarray, float]:
        """Gabarit autour du claquement et position du claquement dans le gabarit (s)."""
        center = int(round(clap_s * sample_rate))
        lead = min(before, center)
        return table_filtered[center - lead:center + after], lead / sample_rate

    region_end = min(len(aid_filtered), int(params.recherche_aide_s * sample_rate))
    aid_start, corr_start = locate(*template(clap_start_s), aid_filtered[:region_end], 0.0, sample_rate)
    if corr_start < params.correlation_min:
        alerts.append(f"claquement de début douteux (corrélation {corr_start:.2f} < {params.correlation_min})")

    expected_end = aid_start + (clap_end_s - clap_start_s)
    lo = max(0, int((expected_end - params.gabarit_avant_s - params.marge_fin_s) * sample_rate))
    hi = min(len(aid_filtered), int((expected_end + params.gabarit_apres_s + params.marge_fin_s) * sample_rate))
    aid_end: float | None = None
    corr_end: float | None = None
    if hi - lo > before + after:
        aid_end, corr_end = locate(*template(clap_end_s), aid_filtered[lo:hi], lo / sample_rate, sample_rate)
        if corr_end < params.correlation_min:
            alerts.append(f"claquement de fin douteux (corrélation {corr_end:.2f} < {params.correlation_min})")
    else:
        alerts.append("claquement de fin hors de la piste : dérive non corrigée")
    ratio = 1.0 if aid_end is None else (aid_end - aid_start) / (clap_end_s - clap_start_s)
    if abs(ratio - 1.0) * 1e6 > params.derive_max_ppm:
        alerts.append(f"dérive de {(ratio - 1.0) * 1e6:.0f} ppm, au-delà de {params.derive_max_ppm:.0f} ppm : "
                      "appariement des claquements douteux, dérive non corrigée")
        ratio, aid_end, corr_end = 1.0, None, None
    return TrackSync(name, aid_start, aid_end, ratio, corr_start, corr_end, alerts)


def identity(name: str, clap_start_s: float, clap_end_s: float) -> TrackSync:
    """Piste déjà alignée sur la table (pistes séparées d'un logiciel de visio) : aucun décalage."""
    return TrackSync(name, clap_start_s, clap_end_s, 1.0, None, None, [])


def align(aid: np.ndarray, sync: TrackSync, clap_start_s: float, n_samples: int,
          sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    """Piste d'aide rééchantillonnée sur l'axe de temps de la table (`n_samples` échantillons),
    par interpolation linéaire ; zéros hors de la piste."""
    table_times = np.arange(n_samples, dtype=np.float64) / sample_rate
    aid_index = (sync.aide_debut_s + sync.rapport * (table_times - clap_start_s)) * sample_rate
    return np.interp(aid_index, np.arange(len(aid), dtype=np.float64), aid.astype(np.float64),
                     left=0.0, right=0.0).astype(np.float32)
