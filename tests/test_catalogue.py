"""Chaque réglage renvoyé par describe() a son entrée dans le catalogue (D17, D19 §1)."""

import os

import pytest
from dotenv import load_dotenv

from whospoke.experiment import REPO_ROOT
from whospoke.pipelines.base import ORIGINS, load_catalogue
from whospoke.pipelines.baseline import Baseline

load_dotenv(REPO_ROOT / ".env")
CATALOGUE = load_catalogue()
REQUIRED = {"libelle", "etape", "effet", "composantes", "decision"}


def check_engine(engine):
    entries = CATALOGUE["moteurs"][engine.name]
    described = engine.describe()
    names = set()
    for step, settings in described.items():
        assert step in CATALOGUE["etapes"], step
        for setting in settings:
            assert setting.name in entries, f"{engine.name} : {setting.name} absent du catalogue"
            assert entries[setting.name]["etape"] == step, setting.name
            assert setting.origin in ORIGINS
            names.add(setting.name)
    return names, set(entries)


def test_entrees_completes():
    for engine, entries in CATALOGUE["moteurs"].items():
        for name, entry in entries.items():
            assert REQUIRED <= set(entry), f"{engine} : {name}"
            assert entry["etape"] in CATALOGUE["etapes"], f"{engine} : {name}"


def test_catalogue_baseline():
    described, catalogued = check_engine(Baseline(theta=0.5))
    assert described == catalogued  # pas d'entrée orpheline


@pytest.mark.skipif(not os.environ.get("HF_TOKEN"), reason="HF_TOKEN absent")
def test_catalogue_pyannote():
    from whospoke.pipelines.pyannote_community1 import PyannoteCommunity1

    described, catalogued = check_engine(PyannoteCommunity1(device="cpu"))
    assert described == catalogued
