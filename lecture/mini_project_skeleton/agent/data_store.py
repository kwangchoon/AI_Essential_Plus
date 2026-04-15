from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class SupportDataStore:
    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir)
        self.devices_path = self.data_dir / "devices.json"
        self.events_path = self.data_dir / "events.json"
        self.policies_path = self.data_dir / "policies.json"
        self.tickets_path = self.data_dir / "tickets.json"
        self.scenarios_path = self.data_dir / "scenarios.json"
        self.devices = self._read_json(self.devices_path)
        self.events = self._read_json(self.events_path)
        self.policies = self._read_json(self.policies_path)
        self.tickets = self._read_json(self.tickets_path)
        self.scenarios = self._read_json(self.scenarios_path)

    @staticmethod
    def _read_json(path: Path) -> Any:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)

    def save_tickets(self) -> None:
        with self.tickets_path.open("w", encoding="utf-8") as handle:
            json.dump(self.tickets, handle, ensure_ascii=False, indent=2)

    def get_device(self, device_id: str) -> dict[str, Any] | None:
        return self.devices.get(device_id)

    def find_device_by_type(self, device_type: str) -> tuple[str, dict[str, Any]] | None:
        for device_id, device in self.devices.items():
            if device.get("device_type") == device_type:
                return device_id, device
        return None

    def get_events(self, device_id: str) -> list[dict[str, Any]]:
        return self.events.get(device_id, [])

    def create_ticket(self, device_id: str, summary: str, severity: str) -> dict[str, Any]:
        ticket = {
            "ticket_id": f"TCK-{1000 + len(self.tickets)}",
            "device_id": device_id,
            "summary": summary[:200],
            "severity": severity,
        }
        self.tickets.append(ticket)
        self.save_tickets()
        return ticket
