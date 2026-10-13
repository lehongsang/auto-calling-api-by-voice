
from typing import Optional
from app.core.security import extract_account_id_from_token
from app.schemas.voice import (
    VoiceCommandRequest,
    VoiceCommandResponse,
    VoiceResponseStatus
)
from app.schemas.health_record import CreateHealthRecordPayload, HealthMetricType
from app.schemas.care_request import CreateCareRequestPayload
from app.services.session_manager import session_manager
from app.services.ai_engine import ai_engine
from app.services.vndoctor_client import vndoctor_client

class VoiceService:
    async def process_command(
        self,
        token: str,
        request: VoiceCommandRequest
    ) -> VoiceCommandResponse:
        # 1. Xác định session_id: Nếu App không truyền, dùng User ID giải mã từ Token
        user_id = extract_account_id_from_token(token)
        session_id = request.session_id or f"user_sess_{user_id}"

        # 2. Lấy phiên làm việc dở dang trước đó
        previous_session = session_manager.get_session(session_id)

        # 3. Phân tích ngữ nghĩa câu nói
        extraction = await ai_engine.extract_intent_and_slots(
            transcript=request.transcript,
            previous_session=previous_session
        )

        intent = extraction.get("intent")
        current_params = extraction.get("parameters", {})

        # Hợp nhất thông tin cũ và mới
        if previous_session and previous_session.get("intent") == intent:
            merged_params = previous_session.get("parameters", {})
            merged_params.update({k: v for k, v in current_params.items() if v is not None})
            current_params = merged_params

        # 4. Xử lý trường hợp không nhận diện được ý định
        if intent == "unknown":
            return VoiceCommandResponse(
                status=VoiceResponseStatus.UNKNOWN_INTENT,
                session_id=session_id,
                response_message="Cháu chưa hiểu rõ yêu cầu. Bác muốn lưu chỉ số sức khỏe (như huyết áp, đường huyết) hay cần gửi yêu cầu để bác sĩ hỗ trợ ạ?"
            )

        # 5. Xử lý Intent: Ghi nhận chỉ số sức khỏe (health-records)
        if intent == "create_health_record":
            health_profile_id = (
                request.context.health_profile_id if request.context and request.context.health_profile_id
                else previous_session.get("health_profile_id") if previous_session else None
            )

            metric_type = current_params.get("metricType")
            value_numeric = current_params.get("valueNumeric")

            # Kiểm tra thiếu loại chỉ số
            if not metric_type:
                session_manager.save_session(session_id, {"intent": intent, "parameters": current_params, "health_profile_id": health_profile_id})
                return VoiceCommandResponse(
                    status=VoiceResponseStatus.NEED_MORE_INFO,
                    session_id=session_id,
                    intent=intent,
                    missing_fields=["metricType"],
                    collected_data=current_params,
                    response_message="Bác muốn ghi nhận chỉ số nào ạ? Ví dụ như huyết áp, nhịp tim hay đường huyết?"
                )

            # Kiểm tra thiếu số đo
            if value_numeric is None:
                session_manager.save_session(session_id, {"intent": intent, "parameters": current_params, "health_profile_id": health_profile_id})
                metric_name_vi = {
                    "BLOOD_PRESSURE": "huyết áp",
                    "BLOOD_GLUCOSE": "đường huyết",
                    "HEART_RATE": "nhịp tim",
                    "WEIGHT": "cân nặng",
                    "TEMPERATURE": "nhiệt độ"
                }.get(metric_type, metric_type)
                return VoiceCommandResponse(
                    status=VoiceResponseStatus.NEED_MORE_INFO,
                    session_id=session_id,
                    intent=intent,
                    missing_fields=["valueNumeric"],
                    collected_data=current_params,
                    response_message=f"Bác vừa đo chỉ số {metric_name_vi} được bao nhiêu ạ?"
                )

            # Kiểm tra profile ID
            if not health_profile_id:
                session_manager.save_session(session_id, {"intent": intent, "parameters": current_params})
                return VoiceCommandResponse(
                    status=VoiceResponseStatus.NEED_MORE_INFO,
                    session_id=session_id,
                    intent=intent,
                    missing_fields=["healthProfileId"],
                    collected_data=current_params,
                    response_message="Bác muốn lưu chỉ số này vào hồ sơ sức khỏe của ai ạ? Bác vui lòng chọn hồ sơ trên màn hình nhé."
                )

            # Đã đủ thông tin -> Chuẩn bị payload gọi BE VN Doctor
            payload = CreateHealthRecordPayload(
                healthProfileId=health_profile_id,
                metricType=HealthMetricType(metric_type),
                valueNumeric=float(value_numeric),
                secondaryValue=float(current_params["secondaryValue"]) if current_params.get("secondaryValue") is not None else None,
                unit=current_params.get("unit", "mmHg"),
                note=current_params.get("note")
            )

            try:
                res = await vndoctor_client.create_health_record(token, payload)
                session_manager.clear_session(session_id)
                
                detail_val = f"{payload.valueNumeric}" + (f"/{payload.secondaryValue}" if payload.secondaryValue else "")
                return VoiceCommandResponse(
                    status=VoiceResponseStatus.SUCCESS,
                    session_id=session_id,
                    intent=intent,
                    response_message=f"Đã lưu thành công chỉ số {metric_type} ({detail_val} {payload.unit}) vào hồ sơ sức khỏe.",
                    api_result=res
                )
            except Exception as e:
                return VoiceCommandResponse(
                    status=VoiceResponseStatus.ERROR,
                    session_id=session_id,
                    intent=intent,
                    response_message=f"Đã xảy ra lỗi khi lưu vào hệ thống: {str(e)}"
                )

        # 6. Xử lý Intent: Yêu cầu chăm sóc y tế (care-requests)
        if intent == "create_care_request":
            title = current_params.get("title")
            description = current_params.get("description", title)
            subscription_id = (
                request.context.subscription_id if request.context and request.context.subscription_id
                else previous_session.get("subscription_id") if previous_session else None
            )

            # Tự động tra cứu gói ACTIVE nếu App chưa gửi lên
            if not subscription_id:
                subscription_id = await vndoctor_client.get_active_subscription_id(token)

            if not subscription_id:
                return VoiceCommandResponse(
                    status=VoiceResponseStatus.ERROR,
                    session_id=session_id,
                    intent=intent,
                    response_message="Tài khoản của bác hiện chưa có gói chăm sóc sức khỏe nào đang kích hoạt để gửi yêu cầu hỗ trợ."
                )

            if not title or len(title) < 5:
                session_manager.save_session(session_id, {"intent": intent, "parameters": current_params, "subscription_id": subscription_id})
                return VoiceCommandResponse(
                    status=VoiceResponseStatus.NEED_MORE_INFO,
                    session_id=session_id,
                    intent=intent,
                    missing_fields=["title"],
                    collected_data=current_params,
                    response_message="Bác vui lòng mô tả rõ hơn triệu chứng hoặc vấn đề cần bác sĩ giúp đỡ ạ?"
                )

            # Đã đủ thông tin -> Gọi BE VN Doctor
            payload = CreateCareRequestPayload(
                subscriptionId=subscription_id,
                title=title,
                description=description
            )

            try:
                res = await vndoctor_client.create_care_request(token, payload)
                session_manager.clear_session(session_id)
                return VoiceCommandResponse(
                    status=VoiceResponseStatus.SUCCESS,
                    session_id=session_id,
                    intent=intent,
                    response_message="Đã gửi yêu cầu hỗ trợ y tế đến đội ngũ chăm sóc sức khỏe thành công.",
                    api_result=res
                )
            except Exception as e:
                return VoiceCommandResponse(
                    status=VoiceResponseStatus.ERROR,
                    session_id=session_id,
                    intent=intent,
                    response_message=f"Đã xảy ra lỗi khi gửi yêu cầu chăm sóc: {str(e)}"
                )

        return VoiceCommandResponse(
            status=VoiceResponseStatus.UNKNOWN_INTENT,
            session_id=session_id,
            response_message="Yêu cầu chưa được xử lý. Bác vui lòng thử lại nhé."
        )

voice_service = VoiceService()
