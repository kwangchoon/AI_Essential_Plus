from __future__ import annotations

import argparse
import json

from .engine import SupportCopilot


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SmartHome Care Copilot CLI skeleton")
    parser.add_argument("--message", help="single-turn input message")
    parser.add_argument("--role", choices=["customer", "support", "admin"], default="customer")
    parser.add_argument("--session-id", default="demo")
    parser.add_argument("--interactive", action="store_true")
    return parser


def run_interactive(role: str, session_id: str) -> None:
    copilot = SupportCopilot()
    print("SmartHome Care Copilot interactive mode. 종료하려면 'exit' 입력.")
    while True:
        message = input("user> ").strip()
        if message.lower() in {"exit", "quit"}:
            break
        report = copilot.process(message, role=role, session_id=session_id)
        print(json.dumps(report.model_dump(), ensure_ascii=False, indent=2))


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.interactive or not args.message:
        run_interactive(args.role, args.session_id)
        return

    copilot = SupportCopilot()
    report = copilot.process(args.message, role=args.role, session_id=args.session_id)
    print(json.dumps(report.model_dump(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
