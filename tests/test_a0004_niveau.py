"""Fonctions de scripts/analyses/a0004_niveau_entree.py (D29 §1)."""

import importlib.util

import numpy as np
import pytest
from pyannote.core import Segment, Timeline

from whospoke.experiment import REPO_ROOT

spec = importlib.util.spec_from_file_location(
    "a0004", REPO_ROOT / "scripts" / "analyses" / "a0004_niveau_entree.py")
a0004 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a0004)


def test_dbfs_pleine_echelle():
    assert a0004.dbfs(np.ones(100)) == pytest.approx(0.0)
    assert a0004.dbfs(np.full(100, 0.1)) == pytest.approx(-20.0)
    assert a0004.dbfs(np.zeros(10)) is None and a0004.dbfs(np.array([])) is None


def test_masque_des_zones():
    mask = a0004.mask_of(Timeline([Segment(0.5, 1.0)]), 32000)
    assert mask.sum() == 8000 and mask[8000] and not mask[7999] and not mask[16000]
