"""Load the model, taxonomy and client profile YAML files."""
from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"

# NY counties that are NOT "upstate" for this project.
DOWNSTATE_NY = {"new york", "kings", "queens", "bronx", "richmond",
                "nassau", "suffolk", "westchester", "rockland"}


def _load(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_model(path: Path | None = None) -> dict:
    model = _load(path or CONFIG_DIR / "model.yaml")
    total = sum(model["weights"].values())
    if total != 100:
        raise ValueError(f"model.yaml weights add to {total}, not 100")
    return model


def load_taxonomy(path: Path | None = None) -> dict:
    return _load(path or CONFIG_DIR / "taxonomy.yaml")


def load_client(client_id: str, clients_dir: Path | None = None) -> dict:
    path = (clients_dir or CONFIG_DIR / "clients") / f"{client_id}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"No client profile at {path}")
    client = _load(path)
    client.setdefault("id", client_id)
    client.setdefault("mode", "seek")
    client.setdefault("secondary_states", [])
    client.setdefault("focus_counties", [])
    client.setdefault("secondary_counties", [])
    client.setdefault("peers", [])
    client.setdefault("validation_seeds", [])
    client.setdefault("flag_lobbying", False)
    for key in ("primary_states", "secondary_states"):
        client[key] = [s.upper() for s in client[key]]
    client["focus_counties"] = [clean_county(c) for c in client["focus_counties"]]
    sc = client["secondary_counties"]
    client["secondary_counties"] = sc if sc == "upstate" else [clean_county(c) for c in sc]
    return client


def clean_county(name: str | None) -> str:
    """'Steuben County' -> 'steuben'."""
    if not name:
        return ""
    n = name.lower().strip()
    for suffix in (" county", " borough", " parish"):
        if n.endswith(suffix):
            n = n[: -len(suffix)]
    return n.strip()


def county_bucket(client: dict, state: str | None, county: str | None) -> str | None:
    """Return 'focus', 'secondary' or None for a recipient's county."""
    if not county or (state or "").upper() not in client["primary_states"]:
        return None
    c = clean_county(county)
    if c in client["focus_counties"]:
        return "focus"
    sec = client["secondary_counties"]
    if sec == "upstate":
        if (state or "").upper() == "NY" and c not in DOWNSTATE_NY:
            return "secondary"
    elif c in sec:
        return "secondary"
    return None


def is_upstate_ny(state: str | None, county: str | None) -> bool:
    return (state or "").upper() == "NY" and bool(county) and clean_county(county) not in DOWNSTATE_NY
