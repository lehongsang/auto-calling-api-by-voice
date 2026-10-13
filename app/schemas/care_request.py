from typing import Optional, List
from pydantic import BaseModel, Field

class CreateCareRequestPayload(BaseModel):
    """
    Schema tương ứng với CreateCareRequestDto của VN Doctor BE.
    """
    subscriptionId: str = Field(..., description="ID gói chăm sóc ACTIVE của bệnh nhân")
    title: str = Field(..., min_length=5, max_length=255, description="Tiêu đề yêu cầu hỗ trợ")
    description: Optional[str] = Field(default=None, description="Mô tả chi tiết triệu chứng hoặc vấn đề")
    mediaUrls: Optional[List[str]] = Field(default=None, description="Danh sách URL hình ảnh đính kèm")
