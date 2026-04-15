from pydantic import BaseModel


class VisionPrediction(BaseModel):
    label: str
    confidence: float
    recommendation: str
