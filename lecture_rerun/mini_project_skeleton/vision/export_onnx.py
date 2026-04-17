from __future__ import annotations

import argparse
from pathlib import Path

import onnx
import torch

from .train import TrainConfig, build_model


def export_model(checkpoint_path: str | Path, output_path: str | Path) -> str:
    checkpoint = torch.load(checkpoint_path, map_location="cpu")
    config_dict = checkpoint.get("config", {})
    image_size = int(config_dict.get("image_size", TrainConfig.image_size))

    model = build_model(num_classes=2)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()

    dummy_input = torch.randn(1, 3, image_size, image_size)
    output_path = str(output_path)
    torch.onnx.export(
        model,
        dummy_input,
        output_path,
        input_names=["image"],
        output_names=["logits"],
        dynamic_axes={"image": {0: "batch"}, "logits": {0: "batch"}},
        opset_version=18,
    )
    onnx_model = onnx.load(output_path)
    onnx.checker.check_model(onnx_model)
    return output_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export appliance classifier to ONNX")
    parser.add_argument(
        "--checkpoint",
        default=str(Path(__file__).resolve().parent / "artifacts" / "filter_classifier.pt"),
    )
    parser.add_argument(
        "--output",
        default=str(Path(__file__).resolve().parent / "artifacts" / "filter_classifier.onnx"),
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    path = export_model(args.checkpoint, args.output)
    print(path)


if __name__ == "__main__":
    main()
