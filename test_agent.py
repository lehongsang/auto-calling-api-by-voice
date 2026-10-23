import sys
import asyncio
import io

if isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout.reconfigure(encoding='utf-8')

from app.main import app
from app.schemas.voice import VoiceCommandRequest, VoiceRequestContext
from app.services.voice_service import voice_service

async def run_tests():
    print("=" * 60)
    print("🏥 KIỂM THỬ HỆ THỐNG PHÂN LOẠI & SÀNG LỌC TRIỆU CHỨNG")
    print("=" * 60)

    mock_token = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6InVzZXJfZGVtb18wMDEifQ.signature"
    profile_id = "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11"
    sub_id = "sub_active_123"

    # ============================================================
    # TEST CASE 1: 🔴 URGENT — NGUY HIỂM TÍNH MẠNG (GỌI API TỨC THÌ)
    # ============================================================
    print("\n[TEST 1] 🔴 CẤP CỨU: 'Tôi bị đau ngực và khó thở dữ dội'")
    req1 = VoiceCommandRequest(
        transcript="Tôi bị đau ngực và khó thở dữ dội",
        session_id="test_sess_urgent",
        context=VoiceRequestContext(subscription_id=sub_id)
    )
    res1 = await voice_service.process_command(mock_token, req1)
    print(f"Status: {res1.status.value}")
    print(f"Urgency: {res1.urgency.value if res1.urgency else 'None'}")
    print(f"Phản hồi AI: {res1.response_message}")

    # ============================================================
    # TEST CASE 2: 🟡 MODERATE — SÀNG LỌC ĐA LƯỢT (ĐAU ĐẦU KÉO DÀI)
    # ============================================================
    print("\n" + "=" * 60)
    print("[TEST 2] 🟡 SÀNG LỌC THÍCH ỨNG: Bệnh nhân đau đầu kéo dài > 2 tiếng")
    sess_mod = "test_sess_moderate_headache"

    # Lượt 1: Bệnh nhân nói triệu chứng ban đầu
    print("\n--- Lượt 1: Bệnh nhân nói 'Tôi bị đau đầu quá' ---")
    req2_1 = VoiceCommandRequest(
        transcript="Tôi bị đau đầu quá",
        session_id=sess_mod,
        context=VoiceRequestContext(subscription_id=sub_id)
    )
    res2_1 = await voice_service.process_command(mock_token, req2_1)
    print(f"Status: {res2_1.status.value}")
    print(f"Missing fields: {res2_1.missing_fields}")
    print(f"Phản hồi AI: {res2_1.response_message}")

    # Lượt 2: Bệnh nhân trả lời thời gian
    print("\n--- Lượt 2: Bệnh nhân trả lời 'Bị từ sáng đến giờ, chắc hơn 2 tiếng rồi' ---")
    req2_2 = VoiceCommandRequest(
        transcript="Bị từ sáng đến giờ, chắc hơn 2 tiếng rồi",
        session_id=sess_mod,
        context=VoiceRequestContext(subscription_id=sub_id)
    )
    res2_2 = await voice_service.process_command(mock_token, req2_2)
    print(f"Status: {res2_2.status.value}")
    print(f"Phản hồi AI: {res2_2.response_message}")

    # Lượt 3: Bệnh nhân nói đã uống thuốc nhưng không đỡ và buồn nôn
    print("\n--- Lượt 3: Bệnh nhân trả lời 'Tôi có uống 1 viên Panadol mà chưa đỡ, giờ thấy buồn nôn' ---")
    req2_3 = VoiceCommandRequest(
        transcript="Tôi có uống 1 viên Panadol mà chưa đỡ, giờ thấy buồn nôn",
        session_id=sess_mod,
        context=VoiceRequestContext(subscription_id=sub_id)
    )
    res2_3 = await voice_service.process_command(mock_token, req2_3)
    print(f"Status: {res2_3.status.value}")
    print(f"Collected data: {res2_3.collected_data}")
    print(f"Phản hồi AI: {res2_3.response_message}")

    # Lượt 4: Bệnh nhân đồng ý gửi Bác sĩ
    print("\n--- Lượt 4: Bệnh nhân xác nhận 'Ừ gửi giúp tôi đi' ---")
    req2_4 = VoiceCommandRequest(
        transcript="Ừ gửi giúp tôi đi",
        session_id=sess_mod,
        context=VoiceRequestContext(subscription_id=sub_id)
    )
    res2_4 = await voice_service.process_command(mock_token, req2_4)
    print(f"Status: {res2_4.status.value}")
    print(f"Phản hồi AI: {res2_4.response_message}")

    # ============================================================
    # TEST CASE 3: PHỦ ĐỊNH TRIỆU CHỨNG ("Tôi không đau gì cả")
    # ============================================================
    print("\n" + "=" * 60)
    print("[TEST 3] 🟢 PHỦ ĐỊNH: 'Tôi không đau gì cả, hôm nay thấy khỏe rồi'")
    req3 = VoiceCommandRequest(
        transcript="Tôi không đau gì cả, hôm nay thấy khỏe rồi",
        session_id="test_sess_negation"
    )
    res3 = await voice_service.process_command(mock_token, req3)
    print(f"Status: {res3.status.value}")
    print(f"Urgency: {res3.urgency.value if res3.urgency else 'None'}")
    print(f"Phản hồi AI: {res3.response_message}")

    # ============================================================
    # TEST CASE 4: BỆNH NHÂN TỪ CHỐI GỬI BÁC SĨ (KHÔNG GỌI API)
    # ============================================================
    print("\n" + "=" * 60)
    print("[TEST 4] 🟡 TỪ CHỐI: Bệnh nhân chọn tự theo dõi, không làm phiền Bác sĩ")
    sess_reject = "test_sess_reject"
    # Giả lập trước đó đã ở bước chờ xác nhận
    await voice_service.process_command(mock_token, VoiceCommandRequest(
        transcript="Tôi bị sốt từ hôm qua hơn 38 độ",
        session_id=sess_reject,
        context=VoiceRequestContext(subscription_id=sub_id)
    ))
    # Bệnh nhân từ chối
    res4 = await voice_service.process_command(mock_token, VoiceCommandRequest(
        transcript="Thôi không cần đâu, để tôi theo dõi thêm",
        session_id=sess_reject
    ))
    print(f"Status: {res4.status.value}")
    print(f"Phản hồi AI: {res4.response_message}")

if __name__ == "__main__":
    asyncio.run(run_tests())
