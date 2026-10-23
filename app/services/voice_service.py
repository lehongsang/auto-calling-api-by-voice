import logging
from typing import Optional, Dict, Any, List

from app.core.security import extract_account_id_from_token
from app.schemas.voice import (
    VoiceCommandRequest,
    VoiceCommandResponse,
    VoiceResponseStatus,
    UrgencyLevel
)
from app.schemas.health_record import CreateHealthRecordPayload, HealthMetricType
from app.schemas.care_request import CreateCareRequestPayload
from app.services.session_manager import session_manager
from app.services.ai_engine import ai_engine
from app.services.vndoctor_client import vndoctor_client

logger = logging.getLogger(__name__)

# Từ điển câu hỏi thích ứng (Dynamic Screening Questions)
SYMPTOM_QUESTIONS: Dict[str, Dict[str, str]] = {
    "đau đầu": {
        "ask_duration": "Dạ cháu nghe rồi ạ. Bác bị đau đầu từ lúc nào, được bao lâu rồi bác?",
        "ask_medication": "Dạ {duration} rồi ạ. Bác đã uống viên thuốc giảm đau nào như Panadol hay nằm nghỉ ngơi chưa bác?",
        "ask_associated": "Bác có bị hoa mắt, buồn nôn hoặc tê bì tay chân kèm theo không ạ?",
        "advise_home": "Dạ nếu mới bị {duration}, bác thử uống một cốc nước ấm, thả lỏng vai gáy và nghỉ ngơi chừng 20-30 phút xem sao nhé. Bác có muốn cháu kết nối Bác sĩ luôn không hay theo dõi thêm ạ?",
        "propose_confirm": "Dạ, tình trạng đau đầu của bác đã {duration_text}{med_text}{assoc_text}. Cháu đề xuất gửi ngay yêu cầu để Bác sĩ xem và liên hệ hỗ trợ bác nhé, bác có đồng ý không ạ?"
    },
    "sốt": {
        "ask_duration": "Dạ bác, bác bắt đầu thấy nóng sốt từ khi nào, được bao lâu rồi ạ?",
        "ask_medication": "Dạ {duration} rồi. Bác có đo được bao nhiêu độ và đã uống viên hạ sốt nào chưa ạ?",
        "ask_associated": "Bác có bị rét run, đau họng, ho nhiều hay mệt lả không ạ?",
        "advise_home": "Dạ nếu mới sốt nhẹ {duration}, bác nên uống nhiều nước ấm hoặc oresol, chườm ấm trán và nách. Bác có muốn cháu gửi phiếu cho Bác sĩ luôn không ạ?",
        "propose_confirm": "Dạ, tình trạng sốt của bác đã {duration_text}{med_text}{assoc_text}. Cháu đề xuất gửi phiếu để Bác sĩ hỗ trợ tư vấn cho bác ngay nhé, bác có muốn gửi không ạ?"
    },
    "đau bụng": {
        "ask_duration": "Dạ bác bị đau bụng từ lúc nào ạ? Bác đau âm ỉ hay quặn từng cơn vậy bác?",
        "ask_medication": "Bác đã uống men tiêu hóa, nước gừng hay xoa dầu gì chưa ạ?",
        "ask_associated": "Bác có bị buồn nôn, đi ngoài hay kèm theo sốt không ạ?",
        "advise_home": "Dạ nếu mới đau nhẹ {duration}, bác thử uống chút nước ấm hoặc gừng ấm và nghỉ ngơi xem sao nhé. Bác có muốn gửi Bác sĩ luôn không ạ?",
        "propose_confirm": "Dạ, tình trạng đau bụng của bác đã {duration_text}{med_text}{assoc_text}. Cháu đề xuất gửi phiếu yêu cầu chăm sóc để Bác sĩ hỗ trợ bác nhé, bác đồng ý chứ ạ?"
    },
    "chóng mặt": {
        "ask_duration": "Dạ bác bị chóng mặt từ bao giờ, có bị từ sáng không ạ?",
        "ask_medication": "Bác đã nằm nghỉ và đo lại huyết áp chưa ạ?",
        "ask_associated": "Bác nhìn mọi thứ có bị xoay tròn hay tối sầm lại không ạ?",
        "advise_home": "Dạ bác nên nằm yên trên giường, tránh thay đổi tư thế đột ngột. Bác có muốn cháu gửi yêu cầu đến Bác sĩ luôn không ạ?",
        "propose_confirm": "Dạ, tình trạng chóng mặt của bác đã {duration_text}{med_text}{assoc_text}. Cháu đề xuất gửi phiếu yêu cầu chăm sóc để Bác sĩ hỗ trợ bác nhé, bác có đồng ý không ạ?"
    },
    "default": {
        "ask_duration": "Dạ cháu nghe rồi ạ. Bác cảm thấy khó chịu như vậy từ lúc nào, được bao lâu rồi ạ?",
        "ask_medication": "Dạ {duration} rồi. Bác đã dùng thuốc gì hay nghỉ ngơi cho đỡ chưa ạ?",
        "ask_associated": "Bác có thấy xuất hiện thêm dấu hiệu bất thường nào khác không ạ?",
        "advise_home": "Dạ nếu mới bị {duration}, bác nên nghỉ ngơi và theo dõi thêm. Bác có muốn cháu gửi yêu cầu đến Bác sĩ luôn không ạ?",
        "propose_confirm": "Dạ, tình trạng khó chịu của bác đã {duration_text}{med_text}{assoc_text}. Cháu đề xuất gửi yêu cầu để Bác sĩ hỗ trợ bác nhé, bác có đồng ý không ạ?"
    }
}

class VoiceService:
    async def process_command(
        self,
        token: str,
        request: VoiceCommandRequest
    ) -> VoiceCommandResponse:
        # 1. Xác định session_id
        user_id = extract_account_id_from_token(token)
        session_id = request.session_id or f"user_sess_{user_id}"

        # 2. Lấy phiên làm việc trước đó
        previous_session = session_manager.get_session(session_id)

        # 3. Phân tích ngữ nghĩa câu nói
        from app.services.ai_engine import _is_negated
        if _is_negated(request.transcript):
            session_manager.clear_session(session_id)
            return VoiceCommandResponse(
                status=VoiceResponseStatus.SUCCESS,
                session_id=session_id,
                urgency=UrgencyLevel.LOW,
                response_message="Thật tuyệt vời ạ! Bác cứ yên tâm nghỉ ngơi nhé. Nếu cần gì bác cứ gọi cháu."
            )

        extraction = await ai_engine.extract_intent_and_slots(
            transcript=request.transcript,
            previous_session=previous_session
        )

        intent = extraction.get("intent")
        urgency = extraction.get("urgency", UrgencyLevel.LOW.value)
        current_params = extraction.get("parameters", {})

        # Trả về lời chúc nếu là câu phủ định (ví dụ "tôi không đau gì cả")
        if extraction.get("friendly_message"):
            session_manager.clear_session(session_id)
            return VoiceCommandResponse(
                status=VoiceResponseStatus.SUCCESS,
                session_id=session_id,
                urgency=UrgencyLevel.LOW,
                response_message=extraction["friendly_message"]
            )

        # ============================================================
        # 4. XỬ LÝ 🔴 URGENT: NGUY HIỂM TÍNH MẠNG -> GỌI API NGAY LẬP TỨC
        # ============================================================
        if urgency == UrgencyLevel.URGENT.value or urgency == "URGENT":
            return await self._handle_urgent_care_request(token, session_id, request, current_params)

        # ============================================================
        # 5. XỬ LÝ XÁC NHẬN (CONFIRMATION) CHO TẦNG MODERATE
        # ============================================================
        if intent == "confirmation":
            return await self._handle_confirmation(token, session_id, request, previous_session, current_params)

        # ============================================================
        # 6. XỬ LÝ ĐO CHỈ SỐ SỨC KHỎE (create_health_record)
        # ============================================================
        if intent == "create_health_record":
            return await self._handle_health_record(token, session_id, request, previous_session, current_params, urgency)

        # ============================================================
        # 7. XỬ LÝ SÀNG LỌC TRIỆU CHỨNG 🟡 MODERATE (Adaptive Screening)
        # ============================================================
        if intent == "create_care_request":
            return await self._handle_moderate_screening(token, session_id, request, previous_session, current_params)

        # ============================================================
        # 8. Ý ĐỊNH CHƯA RÕ (UNKNOWN_INTENT)
        # ============================================================
        return VoiceCommandResponse(
            status=VoiceResponseStatus.UNKNOWN_INTENT,
            session_id=session_id,
            urgency=UrgencyLevel.LOW,
            response_message="Cháu chưa hiểu rõ yêu cầu. Bác muốn lưu chỉ số sức khỏe (như huyết áp, đường huyết) hay cần gửi yêu cầu để bác sĩ hỗ trợ ạ?"
        )

    # ----------------------------------------------------------------
    # SUB-HANDLERS
    # ----------------------------------------------------------------

    async def _handle_urgent_care_request(
        self,
        token: str,
        session_id: str,
        request: VoiceCommandRequest,
        params: Dict[str, Any]
    ) -> VoiceCommandResponse:
        """Xử lý trường hợp cấp cứu khẩn cấp: GỌI API TỨC THÌ, KHÔNG HỎI"""
        subscription_id = (
            request.context.subscription_id if request.context and request.context.subscription_id
            else await vndoctor_client.get_active_subscription_id(token)
        )

        if not subscription_id:
            return VoiceCommandResponse(
                status=VoiceResponseStatus.ERROR,
                session_id=session_id,
                urgency=UrgencyLevel.URGENT,
                response_message="Tài khoản của bác hiện chưa có gói chăm sóc sức khỏe active để gửi yêu cầu hỗ trợ khẩn cấp."
            )

        title = params.get("title") or f"KHẨN CẤP: {request.transcript[:60]}"
        description = f"🚨 YÊU CẦU CẤP CỨU KHẨN CẤP\nLời nói bệnh nhân: \"{request.transcript}\"\nMức độ: NGUY HIỂM TÍNH MẠNG."

        payload = CreateCareRequestPayload(
            subscriptionId=subscription_id,
            title=title,
            description=description
        )

        try:
            res = await vndoctor_client.create_care_request(token, payload)
            session_manager.clear_session(session_id)
            session_manager.record_action(session_id, "create_care_request", title)
            return VoiceCommandResponse(
                status=VoiceResponseStatus.SUCCESS,
                session_id=session_id,
                intent="create_care_request",
                urgency=UrgencyLevel.URGENT,
                response_message="Cháu đã gửi tín hiệu hỗ trợ KHẨN CẤP đến Bác sĩ và đội ngũ y tế. Bác hãy giữ bình tĩnh, ngồi nghỉ tựa lưng và chờ Bác sĩ liên hệ ngay nhé!",
                api_result=res
            )
        except Exception as e:
            return VoiceCommandResponse(
                status=VoiceResponseStatus.ERROR,
                session_id=session_id,
                urgency=UrgencyLevel.URGENT,
                response_message=f"Đã xảy ra lỗi khi gửi yêu cầu khẩn cấp: {str(e)}"
            )

    async def _handle_confirmation(
        self,
        token: str,
        session_id: str,
        request: VoiceCommandRequest,
        previous_session: Optional[Dict[str, Any]],
        current_params: Dict[str, Any]
    ) -> VoiceCommandResponse:
        """Xử lý câu trả lời Xác nhận (ừ, gửi đi / không, thôi)"""
        confirmed = current_params.get("confirmed", True)

        if not previous_session or previous_session.get("intent") != "create_care_request":
            session_manager.clear_session(session_id)
            return VoiceCommandResponse(
                status=VoiceResponseStatus.SUCCESS,
                session_id=session_id,
                urgency=UrgencyLevel.LOW,
                response_message="Dạ vâng, bác cần cháu hỗ trợ thêm điều gì nữa không ạ?"
            )

        # Bệnh nhân từ chối -> Không gọi API
        if not confirmed:
            session_manager.clear_session(session_id)
            return VoiceCommandResponse(
                status=VoiceResponseStatus.SUCCESS,
                session_id=session_id,
                urgency=UrgencyLevel.LOW,
                response_message="Dạ vâng, bác cứ nghỉ ngơi theo dõi thêm nhé. Bất cứ khi nào thấy mệt hơn hoặc cần Bác sĩ, bác cứ gọi cháu nhé!"
            )

        # Bệnh nhân ĐỒNG Ý -> Đóng gói phiếu gửi Bác sĩ
        p = previous_session.get("parameters", {})
        sym = p.get("primary_symptom", "khó chịu")
        duration = p.get("duration", "Chưa rõ thời gian")
        med = p.get("medication", "Chưa dùng thuốc")
        assoc = ", ".join(p.get("associated_symptoms", [])) if p.get("associated_symptoms") else "Không có"

        title = f"{sym.capitalize()} (khởi phát: {duration})"
        if p.get("associated_symptoms"):
            title += f" kèm {assoc}"

        description = (
            f"📋 THÔNG TIN BỆNH SỬ SƠ BỘ (Tự động ghi nhận qua giọng nói):\n"
            f"- Triệu chứng chính: {sym.capitalize()}\n"
            f"- Thời gian khởi phát / kéo dài: {duration}\n"
            f"- Thuốc / can thiệp đã dùng: {med}\n"
            f"- Dấu hiệu đi kèm: {assoc}\n"
            f"- Đánh giá: Bệnh nhân đã được sàng lọc sơ bộ và đồng ý kết nối Bác sĩ chuyên khoa."
        )

        subscription_id = (
            request.context.subscription_id if request.context and request.context.subscription_id
            else previous_session.get("subscription_id") or await vndoctor_client.get_active_subscription_id(token)
        )

        if not subscription_id:
            return VoiceCommandResponse(
                status=VoiceResponseStatus.ERROR,
                session_id=session_id,
                response_message="Tài khoản của bác hiện chưa có gói chăm sóc sức khỏe active để gửi yêu cầu."
            )

        payload = CreateCareRequestPayload(
            subscriptionId=subscription_id,
            title=title[:255],
            description=description
        )

        try:
            res = await vndoctor_client.create_care_request(token, payload)
            session_manager.clear_session(session_id)
            session_manager.record_action(session_id, "create_care_request", title)
            return VoiceCommandResponse(
                status=VoiceResponseStatus.SUCCESS,
                session_id=session_id,
                intent="create_care_request",
                urgency=UrgencyLevel.MODERATE,
                response_message="Dạ cháu đã gửi thông tin bệnh sử chi tiết đến Bác sĩ phụ trách rồi ạ. Trong lúc chờ Bác sĩ liên hệ, bác hãy nghỉ ngơi ở nơi thoáng mát và tránh nhìn vào màn hình nhé!",
                api_result=res
            )
        except Exception as e:
            return VoiceCommandResponse(
                status=VoiceResponseStatus.ERROR,
                session_id=session_id,
                response_message=f"Đã xảy ra lỗi khi gửi yêu cầu chăm sóc: {str(e)}"
            )

    async def _handle_moderate_screening(
        self,
        token: str,
        session_id: str,
        request: VoiceCommandRequest,
        previous_session: Optional[Dict[str, Any]],
        current_params: Dict[str, Any]
    ) -> VoiceCommandResponse:
        """Quy trình sàng lọc sơ bộ thích ứng (Adaptive Screening Multi-turn Dialogue)"""
        # Hợp nhất dữ liệu phiên trước và phiên hiện tại
        merged_params = {}
        if previous_session and previous_session.get("intent") == "create_care_request":
            merged_params = previous_session.get("parameters", {}).copy()

        for k, v in current_params.items():
            if v is not None:
                if k == "associated_symptoms" and isinstance(v, list):
                    prev_assoc = merged_params.get("associated_symptoms", [])
                    merged_params[k] = list(set(prev_assoc + v))
                else:
                    merged_params[k] = v

        primary_sym = merged_params.get("primary_symptom") or "khó chịu"
        q_dict = SYMPTOM_QUESTIONS.get(primary_sym, SYMPTOM_QUESTIONS["default"])

        duration = merged_params.get("duration")
        is_prolonged = merged_params.get("is_prolonged")
        medication = merged_params.get("medication")
        med_relief = merged_params.get("medication_relief")
        assoc_syms = merged_params.get("associated_symptoms", [])

        # Kiểm tra điều kiện đủ để CHỐT HỎI KẾT NỐI BÁC SĨ (AWAITING_CONFIRMATION):
        # 1. Kéo dài >= 1 tiếng / từ sáng / nhiều ngày (is_prolonged == True)
        # 2. Hoặc đã uống thuốc mà không đỡ (med_relief == False)
        # 3. Hoặc có từ 2 triệu chứng trở lên (có assoc_syms)
        should_propose = (
            (is_prolonged is True and (medication or len(assoc_syms) > 0)) or
            (med_relief is False) or
            (is_prolonged is True and duration is not None)
        )

        if should_propose:
            # Soạn câu hỏi chốt xác nhận
            dur_text = f"kéo dài {duration}" if duration else "kéo dài"
            med_text = f", uống thuốc chưa đỡ" if (med_relief is False or medication) else ""
            assoc_text = f" và kèm {', '.join(assoc_syms)}" if assoc_syms else ""

            msg = q_dict["propose_confirm"].format(
                duration_text=dur_text,
                med_text=med_text,
                assoc_text=assoc_text
            )

            # Lưu session ở bước chờ xác nhận
            session_manager.save_session(session_id, {
                "intent": "create_care_request",
                "screening_step": "AWAITING_CONFIRMATION",
                "parameters": merged_params,
                "subscription_id": request.context.subscription_id if request.context else None
            })

            return VoiceCommandResponse(
                status=VoiceResponseStatus.PENDING_CONFIRMATION,
                session_id=session_id,
                intent="create_care_request",
                urgency=UrgencyLevel.MODERATE,
                collected_data=merged_params,
                response_message=msg
            )

        # Nếu bệnh nhân mới bị nhẹ (< 30 phút, chưa dùng gì)
        if is_prolonged is False and duration:
            msg = q_dict["advise_home"].format(duration=duration)
            session_manager.save_session(session_id, {
                "intent": "create_care_request",
                "screening_step": "ADVISE_HOME",
                "parameters": merged_params
            })
            return VoiceCommandResponse(
                status=VoiceResponseStatus.PENDING_CONFIRMATION,
                session_id=session_id,
                intent="create_care_request",
                urgency=UrgencyLevel.LOW,
                collected_data=merged_params,
                response_message=msg
            )

        # Nếu chưa có thông tin thời gian -> Hỏi thời gian (Bước 1)
        if not duration:
            msg = q_dict["ask_duration"]
            session_manager.save_session(session_id, {
                "intent": "create_care_request",
                "screening_step": "ASK_DURATION",
                "parameters": merged_params
            })
            return VoiceCommandResponse(
                status=VoiceResponseStatus.NEED_MORE_INFO,
                session_id=session_id,
                intent="create_care_request",
                urgency=UrgencyLevel.MODERATE,
                missing_fields=["duration"],
                collected_data=merged_params,
                response_message=msg
            )

        # Đã có thời gian nhưng chưa có thông tin thuốc/xử trí -> Hỏi thuốc (Bước 2)
        if not medication:
            msg = q_dict["ask_medication"].format(duration=duration)
            session_manager.save_session(session_id, {
                "intent": "create_care_request",
                "screening_step": "ASK_MEDICATION",
                "parameters": merged_params
            })
            return VoiceCommandResponse(
                status=VoiceResponseStatus.NEED_MORE_INFO,
                session_id=session_id,
                intent="create_care_request",
                urgency=UrgencyLevel.MODERATE,
                missing_fields=["medication"],
                collected_data=merged_params,
                response_message=msg
            )

        # Mặc định chuyển sang xác nhận
        msg = q_dict["propose_confirm"].format(
            duration_text=f"kéo dài {duration}",
            med_text=f", đã dùng {medication}",
            assoc_text=""
        )
        session_manager.save_session(session_id, {
            "intent": "create_care_request",
            "screening_step": "AWAITING_CONFIRMATION",
            "parameters": merged_params
        })
        return VoiceCommandResponse(
            status=VoiceResponseStatus.PENDING_CONFIRMATION,
            session_id=session_id,
            intent="create_care_request",
            urgency=UrgencyLevel.MODERATE,
            collected_data=merged_params,
            response_message=msg
        )

    async def _handle_health_record(
        self,
        token: str,
        session_id: str,
        request: VoiceCommandRequest,
        previous_session: Optional[Dict[str, Any]],
        current_params: Dict[str, Any],
        urgency: str
    ) -> VoiceCommandResponse:
        """Xử lý ghi nhận chỉ số sức khỏe"""
        health_profile_id = (
            request.context.health_profile_id if request.context and request.context.health_profile_id
            else previous_session.get("health_profile_id") if previous_session else None
        )

        metric_type = current_params.get("metricType")
        value_numeric = current_params.get("valueNumeric")

        if not metric_type:
            session_manager.save_session(session_id, {"intent": "create_health_record", "parameters": current_params, "health_profile_id": health_profile_id})
            return VoiceCommandResponse(
                status=VoiceResponseStatus.NEED_MORE_INFO,
                session_id=session_id,
                intent="create_health_record",
                missing_fields=["metricType"],
                collected_data=current_params,
                response_message="Bác muốn ghi nhận chỉ số nào ạ? Ví dụ như huyết áp, nhịp tim hay đường huyết?"
            )

        if value_numeric is None:
            session_manager.save_session(session_id, {"intent": "create_health_record", "parameters": current_params, "health_profile_id": health_profile_id})
            metric_name_vi = {
                "BLOOD_PRESSURE": "huyết áp",
                "BLOOD_GLUCOSE": "đường huyết",
                "HEART_RATE": "nhịp tim",
                "WEIGHT": "cân nặng",
                "TEMPERATURE": "nhiệt độ",
                "SPO2": "SpO2"
            }.get(metric_type, metric_type)
            return VoiceCommandResponse(
                status=VoiceResponseStatus.NEED_MORE_INFO,
                session_id=session_id,
                intent="create_health_record",
                missing_fields=["valueNumeric"],
                collected_data=current_params,
                response_message=f"Bác vừa đo chỉ số {metric_name_vi} được bao nhiêu ạ?"
            )

        if not health_profile_id:
            session_manager.save_session(session_id, {"intent": "create_health_record", "parameters": current_params})
            return VoiceCommandResponse(
                status=VoiceResponseStatus.NEED_MORE_INFO,
                session_id=session_id,
                intent="create_health_record",
                missing_fields=["healthProfileId"],
                collected_data=current_params,
                response_message="Bác muốn lưu chỉ số này vào hồ sơ sức khỏe của ai ạ? Bác vui lòng chọn hồ sơ trên màn hình nhé."
            )

        payload = CreateHealthRecordPayload(
            healthProfileId=health_profile_id,
            metricType=HealthMetricType(metric_type),
            valueNumeric=float(value_numeric),
            secondaryValue=float(current_params["secondaryValue"]) if current_params.get("secondaryValue") is not None else None,
            unit=current_params.get("unit", "mmHg"),
            note=current_params.get("note", "Ghi nhận qua giọng nói")
        )

        try:
            res = await vndoctor_client.create_health_record(token, payload)
            session_manager.clear_session(session_id)
            detail_val = f"{payload.valueNumeric}" + (f"/{payload.secondaryValue}" if payload.secondaryValue else "")
            
            warning_text = ""
            if urgency == UrgencyLevel.URGENT.value or urgency == "URGENT":
                warning_text = " Lưu ý: Chỉ số này đang ở mức NGUY HIỂM, bác hãy nghỉ ngơi và liên hệ bác sĩ nếu thấy khó chịu ạ."

            return VoiceCommandResponse(
                status=VoiceResponseStatus.SUCCESS,
                session_id=session_id,
                intent="create_health_record",
                urgency=UrgencyLevel(urgency) if urgency in UrgencyLevel.__members__ else UrgencyLevel.MODERATE,
                response_message=f"Đã lưu thành công chỉ số {metric_type} ({detail_val} {payload.unit}) vào hồ sơ sức khỏe.{warning_text}",
                api_result=res
            )
        except Exception as e:
            return VoiceCommandResponse(
                status=VoiceResponseStatus.ERROR,
                session_id=session_id,
                response_message=f"Đã xảy ra lỗi khi lưu vào hệ thống: {str(e)}"
            )

voice_service = VoiceService()
