from dataclasses import replace

import pytest
import torch

from lungseg.config import load_smoke_config
from lungseg.smoke import run_smoke


def test_cpu_forward_backward_update_and_seed_reproducibility():
    config = load_smoke_config("configs/smoke.yaml")
    result = run_smoke(config)
    assert result["tensor_shape"] == [1, 1, 16, 16, 16]
    assert 0 < result["foreground_voxels"] < 16**3
    assert result["finite_gradients"]
    assert result["max_parameter_delta"] > 0
    assert result["optimizer_steps"] == 2
    assert result["research_result"] is False
    assert result == run_smoke(config)


def test_cuda_request_does_not_silently_fall_back(monkeypatch):
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    config = replace(load_smoke_config("configs/smoke.yaml"), device="cuda")
    with pytest.raises(RuntimeError, match="CUDA requested but unavailable"):
        run_smoke(config)


def test_smoke_detects_optimizer_that_does_not_update(monkeypatch):
    monkeypatch.setattr(torch.optim.Adam, "step", lambda *args, **kwargs: None)
    with pytest.raises(RuntimeError, match="did not update"):
        run_smoke(load_smoke_config("configs/smoke.yaml"))
