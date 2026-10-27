"""Tests du choix de périphérique (D15)."""

import pytest
import torch

from whospoke import device as device_module
from whospoke.device import select_device


def fake_availability(monkeypatch, available):
    monkeypatch.setattr(device_module, "_is_available", lambda name: name in available)


@pytest.mark.parametrize(
    ("available", "expected"),
    [
        ({"cuda", "mps", "cpu"}, "cuda"),
        ({"mps", "cpu"}, "mps"),
        ({"cpu"}, "cpu"),
    ],
)
def test_choix_automatique_par_priorite(monkeypatch, available, expected):
    fake_availability(monkeypatch, available)
    assert select_device("auto") == torch.device(expected)
    assert select_device(None) == torch.device(expected)


def test_forcage(monkeypatch):
    fake_availability(monkeypatch, {"cuda", "mps", "cpu"})
    assert select_device("cpu") == torch.device("cpu")
    assert select_device("MPS") == torch.device("mps")


def test_forcage_indisponible(monkeypatch):
    fake_availability(monkeypatch, {"cpu"})
    with pytest.raises(RuntimeError):
        select_device("cuda")


def test_nom_inconnu():
    with pytest.raises(ValueError):
        select_device("tpu")


def test_machine_reelle():
    """Sur la machine courante, le choix automatique renvoie un périphérique utilisable."""
    chosen = select_device()
    torch.zeros(1, device=chosen)
