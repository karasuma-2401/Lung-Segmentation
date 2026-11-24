from copy import deepcopy

import pytest

from lungseg.config import SmokeConfig, load_smoke_config


@pytest.fixture
def settings():
    return load_smoke_config("configs/smoke.yaml").to_dict()


@pytest.mark.parametrize("key,value", [
    ("seed", True), ("steps", 0), ("steps", 350), ("num_threads", -1),
    ("device", "gpu"), ("device", []), ("kind", "paper_reference"),
    ("spatial_shape", [15, 16, 16]), ("spatial_shape", [16, 16]),
    ("channels", [4, 8, False]), ("learning_rate", float("nan")),
    ("learning_rate", float("inf")), ("learning_rate", -0.1), ("output_dir", ""),
])
def test_reject_invalid_config(settings, key, value):
    settings[key] = value
    with pytest.raises(ValueError):
        SmokeConfig.from_dict(settings)


def test_missing_and_unknown_keys_are_actionable(settings):
    del settings["seed"]
    settings["sead"] = 42
    with pytest.raises(ValueError, match="missing=.*seed.*unknown=.*sead"):
        SmokeConfig.from_dict(settings)


def test_hash_tracks_resolved_values_not_mapping_order(settings):
    first = SmokeConfig.from_dict(settings)
    assert first.sha256 == SmokeConfig.from_dict(dict(reversed(list(settings.items())))).sha256
    changed = deepcopy(settings)
    changed["seed"] += 1
    assert first.sha256 != SmokeConfig.from_dict(changed).sha256
