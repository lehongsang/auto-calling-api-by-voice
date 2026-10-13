from typing import Optional, Dict, Any, List
from enum import Enum
from pydantic import BaseModel, Field

class VoiceResponseStatus(str, Enum):
    SUCCESS = "SUCCESS"                    # Đã gọi API BE thành công
    NEED_MORE_INFO = "NEED_MORE_INFO"      # Cần hỏi thêm thông tin còn thiếu
    UNKNOWN_INTENT = "UNKNOWN_INTENT"      # Chưa hiểu ý định người dùng
    ERROR = "ERROR"                        # Lỗi gọi BE hoặc logic

class VoiceRequestContext(BaseModel):
    health_profile_id: Optional[str] = Field(default=None, description="Hồ sơ sức khỏe bệnh nhân đang chọn trên App (UUID)")
    subscription_id: Optional[str] = Field(default=None, description="Gói chăm sóc sức khỏe active (UUID)")

class VoiceCommandRequest(BaseModel):
    transcript: str = Field(..., description="Văn bản nhận diện từ giọng nói bệnh nhân")
    session_id: Optional[str] = Field(default=None, description="ID phiên hội thoại (tùy chọn, nếu không có sẽ tự lấy theo Token)")
    context: Optional[VoiceRequestContext] = Field(default=None, description="Ngữ cảnh profile/subscription gửi kèm từ App")

class VoiceCommandResponse(BaseModel):
    status: VoiceResponseStatus
    session_id: str
    intent: Optional[str] = None
    response_message: str = Field(..., description="Câu phản hồi tự nhiên để App hiển thị và đọc TTS cho bệnh nhân")
    missing_fields: Optional[List[str]] = None
    collected_data: Optional[Dict[str, Any]] = None
    api_result: Optional[Dict[str, Any]] = None
