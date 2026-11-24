"""Small MONAI U-Net fixture, deliberately distinct from reproduction models."""

import random

import numpy as np
import torch
from monai.losses import DiceLoss
from monai.networks.nets import UNet

from lungseg.config import SmokeConfig


def run_smoke(config: SmokeConfig, device_override: str | None = None) -> dict:
    requested = device_override or config.device
    if requested not in {"cpu", "cuda", "auto"}:
        raise ValueError("device must be cpu, cuda, or auto")
    device = "cuda" if requested == "auto" and torch.cuda.is_available() else requested
    if device == "auto":
        device = "cpu"
    if device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but unavailable; no GPU smoke was performed")
    random.seed(config.seed)
    np.random.seed(config.seed)
    torch.manual_seed(config.seed)
    if device == "cuda":
        torch.cuda.manual_seed_all(config.seed)
        torch.cuda.reset_peak_memory_stats()
    torch.set_num_threads(config.num_threads)
    torch.use_deterministic_algorithms(True)
    torch.backends.cudnn.benchmark = False
    model = UNet(spatial_dims=3, in_channels=1, out_channels=1, channels=config.channels,
                 strides=(2, 2), num_res_units=0, act="PRELU", norm="INSTANCE").to(device)
    model.train()
    ct = torch.randn((1, 1, *config.spatial_shape), device=device)
    target = torch.zeros_like(ct)
    slices = tuple(slice(size // 4, 3 * size // 4) for size in config.spatial_shape)
    target[(0, 0, *slices)] = 1
    # This fixture emits logits, so DiceLoss applies sigmoid exactly once.
    criterion = DiceLoss(sigmoid=True, reduction="mean", smooth_nr=1e-5, smooth_dr=1e-5)
    optimizer = torch.optim.Adam(model.parameters(), lr=config.learning_rate)
    before = [p.detach().clone() for p in model.parameters()]
    losses = []
    for _ in range(config.steps):
        optimizer.zero_grad(set_to_none=True)
        logits = model(ct)
        if logits.shape != target.shape or not torch.isfinite(logits).all().item():
            raise RuntimeError("Invalid output shape or nonfinite output")
        loss = criterion(logits, target)
        if loss.ndim != 0 or not torch.isfinite(loss).item():
            raise RuntimeError("Loss must be finite and scalar")
        loss.backward()
        gradients = [p.grad for p in model.parameters() if p.requires_grad]
        if any(g is None or not torch.isfinite(g).all().item() for g in gradients):
            raise RuntimeError("A trainable parameter has missing/nonfinite gradients")
        if not any(torch.count_nonzero(g).item() for g in gradients):
            raise RuntimeError("All gradients are zero")
        optimizer.step()
        if any(not torch.isfinite(p).all().item() for p in model.parameters()):
            raise RuntimeError("Optimizer produced nonfinite parameters")
        losses.append(loss.detach().item())
    delta = max((old - new.detach()).abs().max().item() for old, new in zip(before, model.parameters()))
    if delta <= 0:
        raise RuntimeError("Optimizer did not update any parameter")
    return {"status": "pass", "fixture": "monai_unet_small_not_reproduction_architecture",
            "research_result": False, "device_requested": requested, "device_used": device,
            "seed": config.seed, "tensor_shape": list(target.shape),
            "foreground_voxels": int(target.sum().item()), "optimizer_steps": config.steps,
            "losses": losses, "finite_gradients": True, "max_parameter_delta": delta,
            "loss": {"name": "DiceLoss", "sigmoid": True, "reduction": "mean",
                     "smooth_nr": 1e-5, "smooth_dr": 1e-5},
            "peak_cuda_allocated_bytes": torch.cuda.max_memory_allocated() if device == "cuda" else None}
