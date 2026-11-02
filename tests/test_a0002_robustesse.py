"""Fonctions de scripts/analyses/a0002_robustesse_d24.py (D24 §3)."""

import importlib.util

import pytest

from whospoke.experiment import REPO_ROOT

spec = importlib.util.spec_from_file_location(
    "a0002", REPO_ROOT / "scripts" / "analyses" / "a0002_robustesse_d24.py")
a0002 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a0002)


def row(m, fa, c, total, der):
    out = {"der_c0": der}
    for collar in ("c0", "c025"):
        out.update({f"manquee_{collar}_s": m, f"fausse_alarme_{collar}_s": fa, f"confusion_{collar}_s": c,
                    f"duree_reference_{collar}_s": total})
    return out


def test_der_en_rapport_des_sommes():
    rows = {"a": row(1.0, 1.0, 0.0, 10.0, 20.0), "b": row(0.0, 0.0, 0.0, 90.0, 0.0)}
    metrics = a0002.pooled(rows, ["a", "b"], "c0")
    assert metrics["der"] == pytest.approx(2.0)
    assert metrics["manquee"] == pytest.approx(1.0) and metrics["confusion"] == 0.0


def test_comparaison_appariee():
    worse = {"a": row(2.0, 0.0, 0.0, 10.0, 20.0), "b": row(1.0, 0.0, 0.0, 10.0, 10.0)}
    clean = {"a": row(1.0, 0.0, 0.0, 10.0, 10.0), "b": row(1.0, 0.0, 0.0, 10.0, 10.0)}
    out = a0002.compare(worse, clean, ["a", "b"], {"tirages": 200, "graine": 0})
    assert out["ecart_c0"] == pytest.approx(5.0)
    assert out["b_meilleur_c0"] == 1 and out["egalite_c0"] == 1 and out["a_meilleur_c0"] == 0


def test_rt60_t20_et_annexe_t60():
    import yaml

    conditions = yaml.safe_load((REPO_ROOT / "configs" / "summre_degrade.yaml").read_text())["conditions"]
    manifest = REPO_ROOT / "data" / "manifests" / "summre_degrade.csv"
    rows = {r["condition"]: r for r in a0002.rt60_rows(manifest, conditions)}
    assert set(rows) == {"rev04", "rev08", "salle"}
    for condition, target in (("rev04", 0.4), ("rev08", 0.8), ("salle", 0.6)):
        assert abs(rows[condition]["t20_mediane_s"] - target) < 0.15
        assert rows[condition]["annexe_t60_mediane_s"] > rows[condition]["t20_mediane_s"]
