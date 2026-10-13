from enum import Enum
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field

class HealthMetricType(str, Enum):
    BLOOD_PRESSURE = "BLOOD_PRESSURE"
    BLOOD_GLUCOSE = "BLOOD_GLUCOSE"
    HEART_RATE = "HEART_RATE"
    SPO2 = "SPO2"
    TEMPERATURE = "TEMPERATURE"
    WEIGHT = "WEIGHT"
    HEIGHT = "HEIGHT"
    BMI = "BMI"

class CreateHealthRecordPayload(BaseModel):
    """
    Schema tương ứng với CreateHealthRecordDto của VN Doctor BE.
    Sử dụng camelCase alias để serialize gửi sang NestJS BE.
    """
    healthProfileId: str = Field(..., description="UUID của hồ sơ sức khỏe cá nhân")
    metricType: HealthMetricType = Field(..., description="Loại chỉ số sức khỏe")
    valueNumeric: float = Field(..., description="Giá trị đo chính")
    secondaryValue: Optional[float] = Field(default=None, description="Giá trị đo phụ (vd: huyết áp tâm trương)")
    unit: str = Field(..., description="Đơn vị đo chuẩn (mmHg, mmol/L, bpm, %, °C, kg, cm)")
    note: Optional[str] = Field(default=None, description="Ghi chú ngữ cảnh đo")
    measuredAt: Optional[str] = Field(default=None, description="Thời điểm đo ISO string")
