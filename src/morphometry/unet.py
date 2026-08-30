"""Small U-Net definition and annotation gate.

This module is intentionally optional. The Zenodo archive does not provide
pixel-wise reference masks, so the main pipeline refuses to report U-Net
metrics. Install PyTorch and supply expert masks before calling ``build_unet``.
"""

from pathlib import Path


def validate_annotation_set(mask_dir: str | Path, minimum_masks: int = 20) -> list[Path]:
    mask_dir = Path(mask_dir)
    masks = sorted(p for p in mask_dir.glob("**/*") if p.suffix.lower() in {".png", ".tif", ".tiff"})
    if len(masks) < minimum_masks:
        raise ValueError(
            f"U-Net comparison requires at least {minimum_masks} expert masks; found {len(masks)}. "
            "Do not substitute Otsu pseudo-labels for independent ground truth."
        )
    return masks


def build_unet(in_channels: int = 1, out_channels: int = 1, base: int = 16):
    try:
        import torch
        from torch import nn
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise ImportError("Install the optional 'torch' dependency to train U-Net.") from exc

    class Block(nn.Module):
        def __init__(self, a, b):
            super().__init__()
            self.net = nn.Sequential(
                nn.Conv2d(a, b, 3, padding=1), nn.BatchNorm2d(b), nn.ReLU(inplace=True),
                nn.Conv2d(b, b, 3, padding=1), nn.BatchNorm2d(b), nn.ReLU(inplace=True),
            )

        def forward(self, x):
            return self.net(x)

    class UNet(nn.Module):
        def __init__(self):
            super().__init__()
            self.e1, self.e2, self.e3 = Block(in_channels, base), Block(base, base * 2), Block(base * 2, base * 4)
            self.pool = nn.MaxPool2d(2)
            self.up2 = nn.ConvTranspose2d(base * 4, base * 2, 2, stride=2)
            self.d2 = Block(base * 4, base * 2)
            self.up1 = nn.ConvTranspose2d(base * 2, base, 2, stride=2)
            self.d1 = Block(base * 2, base)
            self.out = nn.Conv2d(base, out_channels, 1)

        def forward(self, x):
            a = self.e1(x); b = self.e2(self.pool(a)); c = self.e3(self.pool(b))
            y = self.d2(torch.cat([self.up2(c), b], dim=1))
            y = self.d1(torch.cat([self.up1(y), a], dim=1))
            return self.out(y)

    return UNet()
