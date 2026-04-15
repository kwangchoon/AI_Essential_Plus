from __future__ import annotations

import argparse
import csv
import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader
from torchvision import models

from .dataset import ApplianceVisionDataset, ID_TO_LABEL, RECOMMENDATIONS
from .schema import VisionPrediction


@dataclass
class TrainConfig:
    data_dir: str = str(Path(__file__).resolve().parent / "data")
    output_path: str = str(Path(__file__).resolve().parent / "artifacts" / "filter_classifier.pt")
    demo_output_path: str = str(Path(__file__).resolve().parent / "artifacts" / "demo_predictions.csv")
    epochs: int = 3
    batch_size: int = 8
    image_size: int = 64
    lr: float = 1e-3
    num_workers: int = 0
    seed: int = 7


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def build_model(num_classes: int) -> nn.Module:
    model = models.resnet18(weights=None)
    model.fc = nn.Linear(model.fc.in_features, num_classes)
    return model


def train_one_epoch(model: nn.Module, loader: DataLoader, criterion: nn.Module, optimizer: torch.optim.Optimizer, device: torch.device) -> float:
    model.train()
    running_loss = 0.0
    for images, labels, _ in loader:
        images = images.to(device)
        labels = labels.to(device)
        optimizer.zero_grad()
        logits = model(images)
        loss = criterion(logits, labels)
        loss.backward()
        optimizer.step()
        running_loss += float(loss.item())
    return running_loss / max(len(loader), 1)


def evaluate(model: nn.Module, loader: DataLoader, device: torch.device) -> tuple[float, list[VisionPrediction], list[str]]:
    model.eval()
    correct = 0
    total = 0
    predictions: list[VisionPrediction] = []
    paths: list[str] = []
    with torch.no_grad():
        for images, labels, image_paths in loader:
            images = images.to(device)
            labels = labels.to(device)
            logits = model(images)
            probs = torch.softmax(logits, dim=-1)
            preds = probs.argmax(dim=-1)
            correct += int((preds == labels).sum().item())
            total += int(labels.numel())
            for index in range(len(image_paths)):
                label = ID_TO_LABEL[int(preds[index].cpu().item())]
                confidence = float(probs[index, preds[index]].cpu().item())
                predictions.append(
                    VisionPrediction(
                        label=label,
                        confidence=confidence,
                        recommendation=RECOMMENDATIONS[label],
                    )
                )
                paths.append(image_paths[index])
    accuracy = correct / max(total, 1)
    return accuracy, predictions, paths


def save_demo_table(output_path: str | Path, predictions: list[VisionPrediction], image_paths: list[str]) -> None:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with Path(output_path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["image_path", "label", "confidence", "recommendation"])
        writer.writeheader()
        for path, prediction in zip(image_paths, predictions):
            writer.writerow(
                {
                    "image_path": path,
                    "label": prediction.label,
                    "confidence": round(prediction.confidence, 4),
                    "recommendation": prediction.recommendation,
                }
            )


def run_training(config: TrainConfig) -> dict[str, float | str]:
    set_seed(config.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    manifest_path = Path(config.data_dir) / "manifest.csv"
    train_dataset = ApplianceVisionDataset(manifest_path, split="train", image_size=config.image_size)
    val_dataset = ApplianceVisionDataset(manifest_path, split="val", image_size=config.image_size)
    train_loader = DataLoader(train_dataset, batch_size=config.batch_size, shuffle=True, num_workers=config.num_workers)
    val_loader = DataLoader(val_dataset, batch_size=config.batch_size, shuffle=False, num_workers=config.num_workers)

    model = build_model(num_classes=2).to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=config.lr)

    last_loss = 0.0
    for _ in range(config.epochs):
        last_loss = train_one_epoch(model, train_loader, criterion, optimizer, device)

    accuracy, predictions, image_paths = evaluate(model, val_loader, device)
    save_demo_table(config.demo_output_path, predictions, image_paths)

    artifact_path = Path(config.output_path)
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "class_names": ["clean", "dirty"],
            "config": asdict(config),
            "accuracy": accuracy,
        },
        artifact_path,
    )
    return {
        "checkpoint": str(artifact_path),
        "loss": round(last_loss, 4),
        "accuracy": round(accuracy, 4),
        "demo_predictions": str(config.demo_output_path),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Train appliance filter classifier skeleton")
    parser.add_argument("--data-dir", default=TrainConfig.data_dir)
    parser.add_argument("--output-path", default=TrainConfig.output_path)
    parser.add_argument("--demo-output-path", default=TrainConfig.demo_output_path)
    parser.add_argument("--epochs", type=int, default=TrainConfig.epochs)
    parser.add_argument("--batch-size", type=int, default=TrainConfig.batch_size)
    parser.add_argument("--image-size", type=int, default=TrainConfig.image_size)
    parser.add_argument("--lr", type=float, default=TrainConfig.lr)
    parser.add_argument("--seed", type=int, default=TrainConfig.seed)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    config = TrainConfig(
        data_dir=args.data_dir,
        output_path=args.output_path,
        demo_output_path=args.demo_output_path,
        epochs=args.epochs,
        batch_size=args.batch_size,
        image_size=args.image_size,
        lr=args.lr,
        seed=args.seed,
    )
    summary = run_training(config)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
