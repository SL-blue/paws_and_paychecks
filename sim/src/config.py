"""Load the YAML config files and apply overrides (used by sweeps and recommendations)."""
import copy
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
ECONOMY_PATH = ROOT / "data" / "economy.yaml"
POLICIES_PATH = ROOT / "data" / "policies.yaml"


def load_yaml(path):
    with open(path) as f:
        return yaml.safe_load(f)


def load_economy(path=ECONOMY_PATH):
    return load_yaml(path)


def load_policies(path=POLICIES_PATH):
    return load_yaml(path)


def get_path(cfg, dotted):
    node = cfg
    for key in dotted.split("."):
        node = node[key]
    return node


def set_path(cfg, dotted, value):
    keys = dotted.split(".")
    node = cfg
    for key in keys[:-1]:
        node = node[key]
    node[keys[-1]] = value


def with_overrides(cfg, overrides):
    """Return a copy of cfg with {dotted.path: value} overrides applied."""
    new = copy.deepcopy(cfg)
    for dotted, value in (overrides or {}).items():
        set_path(new, dotted, value)
    return new


def deep_merge(base, overlay):
    """Return a copy of base with the nested dict overlay merged in (overlay wins)."""
    out = copy.deepcopy(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out
