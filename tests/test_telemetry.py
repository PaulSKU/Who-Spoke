"""Télémétrie des bibliothèques tierces coupée au niveau du paquet (D27)."""

import ast
import os
import subprocess
import sys

import pytest

from whospoke.experiment import REPO_ROOT
from whospoke.telemetry import TELEMETRY_OFF, disable_telemetry

# Valeurs qui réactiveraient chaque télémétrie : l'import de whospoke doit les écraser.
HOSTILE = {
    "PYANNOTE_METRICS_ENABLED": "true",
    "HF_HUB_DISABLE_TELEMETRY": "0",
    "GRADIO_ANALYTICS_ENABLED": "True",
    "OTEL_SDK_DISABLED": "false",
}

# Contrôles faits dans le processus enfant, après les imports du point d'entrée.
CHECKS = (
    "import os\n"
    "from whospoke.telemetry import TELEMETRY_OFF\n"
    "assert all(os.environ[k] == v for k, v in TELEMETRY_OFF.items()), 'variables non posées'\n"
    "import huggingface_hub.constants as c\n"
    "assert c.HF_HUB_DISABLE_TELEMETRY and not c.HF_HUB_OFFLINE, 'télémétrie du Hub active'\n"
    "from pyannote.audio.telemetry.metrics import is_metrics_enabled\n"
    "assert not is_metrics_enabled(), 'télémétrie de pyannote.audio active'\n"
    "from opentelemetry.sdk.trace import TracerProvider\n"
    "from opentelemetry.trace import NoOpTracer\n"
    "assert isinstance(TracerProvider().get_tracer('t'), NoOpTracer), 'SDK OpenTelemetry actif'\n"
    "print('coupée')\n"
)

ENTRY_POINTS = sorted(
    [path.relative_to(REPO_ROOT) for path in (REPO_ROOT / "scripts").rglob("*.py")]
    + [REPO_ROOT.joinpath("app", "app.py").relative_to(REPO_ROOT),
       REPO_ROOT.joinpath("src", "whospoke", "cli.py").relative_to(REPO_ROOT)]
)


def _child_env() -> dict[str, str]:
    env = {key: value for key, value in os.environ.items() if key not in TELEMETRY_OFF and key != "HF_HUB_OFFLINE"}
    return {**env, **HOSTILE}


def _run(code: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-c", code], cwd=REPO_ROOT, env=_child_env(),
                          capture_output=True, text=True, timeout=180)


def test_variables_imposees():
    environ = dict(HOSTILE, AUTRE="x")
    disable_telemetry(environ)
    assert environ == {**TELEMETRY_OFF, "AUTRE": "x"}
    assert set(TELEMETRY_OFF) == {"PYANNOTE_METRICS_ENABLED", "HF_HUB_DISABLE_TELEMETRY",
                                  "GRADIO_ANALYTICS_ENABLED", "OTEL_SDK_DISABLED"}


def test_import_du_paquet_coupe_tout():
    """Environnement hostile : `import whospoke` seul suffit, avant tout import tiers."""
    completed = _run("import whospoke\n" + CHECKS
                     + "import gradio.analytics\nassert not gradio.analytics.analytics_enabled()\n")
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip().splitlines()[-1] == "coupée"


def test_paquet_whospoke_sans_import_tiers():
    """`whospoke/__init__.py`, `whospoke/telemetry.py` et la commande en ligne `whospoke/cli.py`
    n'importent que la bibliothèque standard à leur chargement."""
    for name in ("__init__.py", "telemetry.py", "cli.py"):
        tree = ast.parse((REPO_ROOT / "src" / "whospoke" / name).read_text())
        for node in tree.body:
            if isinstance(node, ast.Import | ast.ImportFrom):
                modules = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module]
                for module in modules:
                    top = module.split(".")[0]
                    assert top in sys.stdlib_module_names or top == "whospoke" or top == "__future__", (name, module)


def _first_third_party_import(path) -> str | None:
    tree = ast.parse((REPO_ROOT / path).read_text())
    for node in tree.body:
        if isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            modules = [node.module]
        else:
            continue
        for module in modules:
            top = module.split(".")[0]
            if top != "__future__" and top not in sys.stdlib_module_names:
                return top
    return None


@pytest.mark.parametrize("path", ENTRY_POINTS, ids=str)
def test_point_d_entree_importe_whospoke_en_premier(path):
    """Tout point d'entrée importe `whospoke` (ou `app`, qui l'importe) avant tout autre module tiers."""
    assert _first_third_party_import(path) in ("whospoke", "app", None), path


def test_paquet_app_importe_whospoke():
    assert _first_third_party_import("app/__init__.py") == "whospoke"


@pytest.mark.parametrize("path", ["scripts/run_experiment.py", "scripts/evaluate.py",
                                  "scripts/prefetch_models.py",
                                  "scripts/analyses/a0001_sensibilite_reference.py"])
def test_point_d_entree_reel(path):
    """Le script est chargé dans un environnement hostile (sans exécuter `main`) : tout est coupé."""
    code = ("import runpy, sys\n"
            f"sys.argv = [{path!r}]\n"
            f"runpy.run_path({path!r}, run_name='module')\n" + CHECKS)
    completed = _run(code)
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip().splitlines()[-1] == "coupée"
