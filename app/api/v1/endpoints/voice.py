from typing import Optional
from fastapi import APIRouter, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.schemas.voice import VoiceCommandRequest, VoiceCommandResponse
from app.services.voice_service import voice_service

router = APIRouter(prefix="/voice-command", tags=["Voice Agent (AI Trợ lý Thoại)"])
security = HTTPBearer(auto_error=False)

@router.post(
    "/process",
    response_model=VoiceCommandResponse,
    summary="Tiếp nhận câu lệnh giọng nói từ Bệnh nhân",
    description="Xử lý câu lệnh văn bản từ App, tự động kiểm tra đủ trường để gọi API Health Record hoặc Care Request."
)
async def process_voice_command(
    request: VoiceCommandRequest,
    auth_credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> VoiceCommandResponse:
    # Lấy token từ HTTPBearer (ổ khóa Authorize trên Swagger)
    raw_token = auth_credentials.credentials if auth_credentials else "mock_test_token_patient_123"

    return await voice_service.process_command(raw_token, request)
