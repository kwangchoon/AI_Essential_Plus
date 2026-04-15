from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, model_validator


Role = Literal["customer", "support", "admin"]
Intent = Literal["manual_info", "device_control", "troubleshooting", "handoff"]
DeviceType = Literal[
    "robot_vacuum",
    "washing_machine",
    "air_conditioner",
    "remote_hub",
]


class PendingAction(BaseModel):
    name: Literal["update_firmware", "factory_reset"]
    device_id: str
    args: dict[str, Any] = Field(default_factory=dict)


class DeviceActionPlan(BaseModel):
    intent: Intent
    device_id: Optional[str] = None
    device_type: Optional[DeviceType] = None
    action: Optional[str] = None
    question: Optional[str] = None
    symptom: Optional[str] = None
    error_code: Optional[str] = None
    safety_risk: bool = False
    confirmed: bool = False
    missing_fields: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_core_fields(self) -> "DeviceActionPlan":
        if self.intent == "device_control" and not self.action:
            raise ValueError("device_control intent requires action.")
        if self.intent == "manual_info" and not self.question:
            raise ValueError("manual_info intent requires question.")
        if self.intent == "troubleshooting" and not (self.symptom or self.error_code):
            raise ValueError("troubleshooting intent requires symptom or error_code.")
        return self


class ToolResult(BaseModel):
    ok: bool = True
    tool: str
    payload: dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


class ServiceTicket(BaseModel):
    ticket_id: str
    device_id: str
    summary: str
    severity: Literal["low", "medium", "high"]


class SupportReport(BaseModel):
    title: str
    intent: Intent
    severity: Literal["low", "medium", "high"]
    reply: str
    evidence: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    follow_up_question: Optional[str] = None
    needs_handoff: bool = False
    needs_confirmation: bool = False
    pending_action: Optional[PendingAction] = None
    ticket: Optional[ServiceTicket] = None
    tool_results: list[ToolResult] = Field(default_factory=list)
