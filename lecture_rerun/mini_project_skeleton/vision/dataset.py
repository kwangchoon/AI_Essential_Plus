from __future__ import annotations

from pathlib import Path

import pandas as pd
import torch
from PIL import Image
from torch.utils.data import Dataset
from torchvision import transforms


LABEL_TO_ID = {"clean": 0, "dirty": 1}
ID_TO_LABEL = {value: key for key, value in LABEL_TO_ID.items()}
RECOMMENDATIONS = {
    "clean": "필터 상태가 양호합니다. 정기 점검만 유지하세요.",
    "dirty": "필터 오염 가능성이 높습니다. 청소 또는 교체를 권장합니다.",
}


def build_transforms(train: bool, image_size: int) -> transforms.Compose:
    ops: list[transforms.Compose | transforms.Resize | transforms.RandomHorizontalFlip | transforms.ToTensor] = [
        transforms.Resize((image_size, image_size)),
    ]
    if train:
        ops.append(transforms.RandomHorizontalFlip())
    ops.extend(
        [
            transforms.ToTensor(),
            transforms.Normalize(mean=(0.5, 0.5, 0.5), std=(0.5, 0.5, 0.5)),
        ]
    )
    return transforms.Compose(ops)


class ApplianceVisionDataset(Dataset):
    def __init__(self, manifest_path: str | Path, split: str, image_size: int = 64):
        manifest = pd.read_csv(manifest_path)
        self.rows = manifest[manifest["split"] == split].reset_index(drop=True)
        self.root = Path(manifest_path).parent
        self.transform = build_transforms(train=split == "train", image_size=image_size)

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, int, str]:
        row = self.rows.iloc[index]
        image_path = self.root / row["path"]
        image = Image.open(image_path).convert("RGB")
        image = self.transform(image)
        label = LABEL_TO_ID[row["label"]]
        return image, label, str(image_path)
