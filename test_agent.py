import sys
import asyncio

import io
if isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout.reconfigure(encoding='utf-8')

from app.main import app
from app.schemas.voice import VoiceCommandRequest, VoiceRequestContext
from app.services.voice_service import voice_service

async def run_tests():
    print("=== 1. KIEM THU KHOI DONG UNG DUNG ===")
    print(f"Title: {app.title}, Version: {app.version}")
    
    mock_token = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6InVzZXJfZGVtb18wMDEifQ.signature"
    profile_id = "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11"
    
    print("\n=== 2. TEST CASE 1: BENH NHAN NOI THIEU SO DO HUYET AP ===")
    req1 = VoiceCommandRequest(
        transcript="Tôi vừa đo huyết áp xong",
        context=VoiceRequestContext(health_profile_id=profile_id)
    )
    res1 = await voice_service.process_command(mock_token, req1)
    print(f"Status: {res1.status.value}")
    print(f"Missing fields: {res1.missing_fields}")
    print(f"Response message: {res1.response_message}")
    
    print("\n=== 3. TEST CASE 2: BENH NHAN BO SUNG SO DO (SLOT FILLING) ===")
    req2 = VoiceCommandRequest(
        transcript="Một trăm hai mươi trên tám mươi",
        context=VoiceRequestContext(health_profile_id=profile_id)
    )
    res2 = await voice_service.process_command(mock_token, req2)
    print(f"Status: {res2.status.value}")
    print(f"Intent: {res2.intent}")
    print(f"Response message: {res2.response_message}")
    
    print("\n=== 4. TEST CASE 3: YEU CAU CHAM SOC (CARE REQUEST) ===")
    req3 = VoiceCommandRequest(
        transcript="Tôi bị chóng mặt và buồn nôn sau khi uống thuốc huyết áp",
        context=VoiceRequestContext(subscription_id="sub_active_123")
    )
    res3 = await voice_service.process_command(mock_token, req3)
    print(f"Status: {res3.status.value}")
    print(f"Intent: {res3.intent}")
    print(f"Response message: {res3.response_message}")

if __name__ == "__main__":
    asyncio.run(run_tests())
