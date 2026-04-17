from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch
from PIL import Image

from .dataset import ID_TO_LABEL, RECOMMENDATIONS, build_transforms
from .schema import VisionPrediction
from .train import TrainConfig, build_model


def predict(image_path: str | Path, checkpoint_path: str | Path) -> VisionPrediction:
    checkpoint = torch.load(checkpoint_path, map_location="cpu")
    config_dict = checkpoint.get("config", {})
    image_size = int(config_dict.get("image_size", TrainConfig.image_size))
    model = build_model(num_classes=2)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()

    transform = build_transforms(train=False, image_size=image_size)
    image = Image.open(image_path).convert("RGB")
    tensor = transform(image).unsqueeze(0)
    with torch.no_grad():
        logits = model(tensor)
        probs = torch.softmax(logits, dim=-1)[0]
        pred_index = int(probs.argmax().item())

    label = ID_TO_LABEL[pred_index]
    return VisionPrediction(
        label=label,
        confidence=float(probs[pred_index].item()),
        recommendation=RECOMMENDATIONS[label],
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Predict appliance filter state")
    parser.add_argument("image_path")
    parser.add_argument(
        "--checkpoint",
        default=str(Path(__file__).resolve().parent / "artifacts" / "filter_classifier.pt"),
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    prediction = predict(args.image_path, args.checkpoint)
    print(json.dumps(prediction.model_dump(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
