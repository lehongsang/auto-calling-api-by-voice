import json
import logging
import re
from typing import Dict, Any, Optional, List

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None  # type: ignore
    types = None  # type: ignore

try:
    from openai import AsyncOpenAI
    from openai.types.chat import ChatCompletionMessageParam
except ImportError:
    AsyncOpenAI = None  # type: ignore
    ChatCompletionMessageParam = Any  # type: ignore

from app.core.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
Bạn là Trợ lý Y tế Thông minh của ứng dụng VN Doctor, hỗ trợ bệnh nhân ghi nhận thông số sức khỏe và gửi yêu cầu hỗ trợ y tế qua giọng nói.

Nhiệm vụ của bạn:
1. Phân tích câu nói của bệnh nhân để xác định ý định (intent):
   - 'create_health_record': Ghi nhận chỉ số sức khỏe đo lường (huyết áp, đường huyết, nhịp tim, oxy SpO2, nhiệt độ, cân nặng, chiều cao).
   - 'create_care_request': Yêu cầu bác sĩ / điều dưỡng hỗ trợ, phản ánh triệu chứng bệnh (đau đầu, sốt, đau bụng, tức ngực, mệt mỏi...).
   - 'confirmation': Bệnh nhân xác nhận hoặc từ chối hành động (ví dụ: "ừ", "gửi đi", "đồng ý", "không", "thôi", "khỏi").
   - 'unknown': Không thuộc các ý định trên.

2. Đánh giá MỨC ĐỘ KHẨN CẤP (urgency):
   - 'URGENT': Triệu chứng nguy hiểm tính mạng cần gọi Bác sĩ NGAY LẬP TỨC:
     * Đau ngực, tức ngực, khó thở, không thở được, ngất xỉu, co giật, đột quỵ, méo miệng, liệt/tê nửa người, sốc phản vệ, chảy máu nặng, ngộ độc.
   - 'MODERATE': Triệu chứng thực tế cần khám sàng lọc thích ứng (Adaptive Screening):
     * Đau đầu, sốt, đau bụng, buồn nôn, chóng mặt, đau lưng, đau khớp, mệt mỏi, mất ngủ, tiêu chảy, ho, phát ban...
   - 'LOW': Thắc mắc chung, hỏi thăm, cảm ơn, hoặc CÂU PHỦ ĐỊNH ("tôi không đau gì", "hết đau rồi", "khỏe rồi").

3. Trích xuất các trường dữ liệu (slots):
   - Với 'create_health_record':
     * metricType: Enum ['BLOOD_PRESSURE', 'BLOOD_GLUCOSE', 'HEART_RATE', 'SPO2', 'TEMPERATURE', 'WEIGHT', 'HEIGHT', 'BMI']
     * valueNumeric: Số đo chính
     * secondaryValue: Số đo phụ (huyết áp tâm trương)
     * unit: Đơn vị chuẩn ('mmHg', 'mmol/L', 'bpm', '%', '°C', 'kg', 'cm')
     * note: Ghi chú nếu có

   - Với 'create_care_request' (Đặc biệt cho quy trình Sàng lọc lâm sàng):
     * primary_symptom: Triệu chứng chính (ví dụ: 'đau đầu', 'sốt', 'đau bụng', 'chóng mặt'...)
     * duration: Thời gian kéo dài / khởi phát nếu người dùng nhắc đến (ví dụ: 'hơn 2 tiếng', 'từ sáng', '3 ngày', 'mới bị 10 phút')
     * is_prolonged: true nếu >= 1 tiếng, nhiều ngày, hoặc từ sáng/đêm qua; false nếu mới bị < 30 phút
     * medication: Thuốc hoặc biện pháp đã dùng (ví dụ: 'uống 1 viên panadol', 'xoa dầu', 'chưa uống gì')
     * medication_relief: true nếu đã đỡ, false nếu uống nhưng không đỡ/vẫn đau
     * associated_symptoms: Mảng các triệu chứng đi kèm (ví dụ: ['buồn nôn', 'hoa mắt'])
     * title: Tiêu đề tóm tắt ngắn gọn
     * description: Mô tả chi tiết lời nói

   - Với 'confirmation':
     * confirmed: true nếu đồng ý (ừ, ok, gửi đi, được, vâng, có), false nếu từ chối (không, thôi, khỏi, hủy)

4. QUY TẮC QUAN TRỌNG:
   - Nếu bệnh nhân PHỦ ĐỊNH ("tôi không đau gì", "khỏe rồi"), trả urgency = "LOW", intent = "unknown".
   - Nếu bệnh nhân đang trả lời về thời gian, thuốc hoặc triệu chứng kèm theo, cập nhật vào parameters tương ứng.
   - Phải trả về JSON hợp lệ tuyệt đối.

5. Cấu trúc JSON trả về:
{
  "intent": "create_health_record" | "create_care_request" | "confirmation" | "unknown",
  "urgency": "URGENT" | "MODERATE" | "LOW",
  "confidence": 0.0 - 1.0,
  "parameters": { ... }
}
"""

# Bảng từ số tiếng Việt sang số
VIETNAMESE_NUMBERS = {
    "không": 0, "một": 1, "mốt": 1, "hai": 2, "ba": 3, "bốn": 4, "tư": 4, "năm": 5, "lăm": 5,
    "sáu": 6, "bảy": 7, "bảy": 7, "tám": 8, "chín": 9, "mười": 10
}

# 🔴 URGENT: Triệu chứng nguy hiểm tính mạng
URGENT_KEYWORDS = [
    "đau ngực", "tức ngực", "nặng ngực", "đè ngực",
    "khó thở", "không thở được", "nghẹt thở", "ngạt thở", "thở không nổi",
    "ngất", "xỉu", "bất tỉnh", "mất ý thức", "hôn mê",
    "co giật", "giật", "động kinh",
    "chảy máu không cầm", "xuất huyết", "chảy máu nhiều",
    "đột quỵ", "méo miệng", "tê nửa người", "liệt", "không nhấc được",
    "sốc phản vệ", "sưng mặt", "phù mặt", "không nuốt được",
    "tim đập nhanh bất thường", "tim ngừng đập",
    "ngộ độc", "uống nhầm thuốc",
]

# 🟡 MODERATE: Danh sách triệu chứng chính
MODERATE_SYMPTOM_MAP = {
    "đau đầu": ["đau đầu", "nhức đầu", "đau nửa đầu", "buốt đầu"],
    "sốt": ["sốt", "nóng người", "nóng sốt", "hâm hấp sốt", "ớn lạnh", "rét run"],
    "đau bụng": ["đau bụng", "đau dạ dày", "đau bao tử", "quặn bụng", "đau thượng vị"],
    "buồn nôn": ["buồn nôn", "nôn", "ói", "mắc ói"],
    "chóng mặt": ["chóng mặt", "hoa mắt", "xây xẩm", "choáng váng", "chòng chành"],
    "đau nhức": ["đau lưng", "đau khớp", "nhức mỏi", "đau chân", "đau tay", "đau vai", "đau cổ"],
    "mệt mỏi": ["mệt", "kiệt sức", "uể oải", "mệt mỏi", "đuối sức"],
    "mất ngủ": ["mất ngủ", "không ngủ được", "khó ngủ", "trằn trọc"],
    "tiêu hóa": ["tiêu chảy", "đi ngoài", "đi phân lỏng", "táo bón"],
    "hô hấp nhẹ": ["ho", "đau họng", "viêm họng", "ngứa họng", "nghẹt mũi", "sổ mũi"],
    "dị ứng nhẹ": ["phát ban", "nổi mẩn", "ngứa", "dị ứng da"],
}

# Từ khóa PHỦ ĐỊNH — nếu gặp trước triệu chứng, không tạo phiếu
NEGATION_PATTERNS = [
    r"không\s+(?:còn\s+)?(?:bị\s+)?(?:đau|nhức|mệt|khó thở|chóng mặt|sốt|buồn nôn|ho)",
    r"hết\s+(?:đau|nhức|mệt|khó thở|chóng mặt|sốt|buồn nôn|ho)",
    r"(?:khỏe|ổn|bình thường)\s+rồi",
    r"không\s+(?:sao|có gì)",
    r"đỡ\s+(?:rồi|nhiều|hơn)",
    r"không\s+đau\s+gì",
    r"bớt\s+(?:đau|nhức|mệt|khó thở|chóng mặt|sốt)",
]

# Từ khóa XÁC NHẬN (confirmation)
CONFIRM_POSITIVE = ["ừ", "ừm", "ờ", "ok", "được", "gửi đi", "gửi", "gửi giúp", "vâng", "dạ", "đồng ý", "có", "ổn", "đúng rồi", "chắc chắn", "nhờ cháu", "nhờ bác sĩ"]
CONFIRM_NEGATIVE = ["không", "thôi", "khỏi", "hủy", "bỏ", "đừng", "chưa", "để sau", "không cần", "không gửi", "theo dõi thêm", "để tôi xem sao"]

def extract_vietnamese_numbers(text: str) -> list[float]:
    digits = re.findall(r'\d+(?:[.,]\d+)?', text)
    if digits:
        return [float(d.replace(',', '.')) for d in digits]
        
    found_nums = []
    text_lower = text.lower()
    if "một trăm hai mươi" in text_lower or "120" in text_lower:
        found_nums.append(120.0)
    elif "một trăm ba mươi" in text_lower or "130" in text_lower:
        found_nums.append(130.0)
    elif "một trăm bốn mươi" in text_lower or "140" in text_lower:
        found_nums.append(140.0)
    elif "một trăm mười" in text_lower or "110" in text_lower:
        found_nums.append(110.0)

    if "tám mươi" in text_lower or "80" in text_lower:
        found_nums.append(80.0)
    elif "tám lăm" in text_lower or "tám mươi lăm" in text_lower or "85" in text_lower:
        found_nums.append(85.0)
    elif "bảy mươi" in text_lower or "70" in text_lower:
        found_nums.append(70.0)
    elif "chín mươi" in text_lower or "90" in text_lower:
        found_nums.append(90.0)
        
    return found_nums

def _is_negated(text: str) -> bool:
    for pattern in NEGATION_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False

def _check_dangerous_vitals(metric_type: str, value: Optional[float], secondary: Optional[float] = None) -> bool:
    if value is None:
        return False
    try:
        val = float(value)
        sec = float(secondary) if secondary is not None else None
    except (ValueError, TypeError):
        return False

    if metric_type == "BLOOD_PRESSURE":
        if val >= 180 or (sec is not None and sec >= 120):
            return True
        if val <= 80 or (sec is not None and sec <= 50):
            return True
    elif metric_type == "HEART_RATE":
        if val > 150 or val < 40:
            return True
    elif metric_type == "SPO2":
        if val < 90:
            return True
    elif metric_type == "TEMPERATURE":
        if val > 40 or val < 35:
            return True
    return False

def _detect_duration(text: str) -> tuple[Optional[str], Optional[bool]]:
    """
    Trích xuất thông tin thời gian khởi phát và cờ kéo dài (is_prolonged).
    Trả về (duration_str, is_prolonged)
    """
    prolonged_patterns = [
        r"(?:hơn\s+)?(\d+|một|hai|ba|bốn|năm)\s*(?:tiếng|giờ)",
        r"(từ\s+(?:sáng|trưa|hôm qua|tối qua|đêm qua))",
        r"(\d+\s*ngày)",
        r"(mấy\s*ngày)",
        r"(lâu\s*rồi)",
        r"(suốt\s*từ\s*\w+)",
        r"(cả\s*ngày)",
        r"(nửa\s*ngày)",
    ]
    for p in prolonged_patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return m.group(0), True

    short_patterns = [
        r"(mới\s*bị)",
        r"(\d+\s*phút)",
        r"(vừa\s*mới)",
        r"(chốc\s*lát)",
        r"(vừa\s*xong)"
    ]
    for p in short_patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return m.group(0), False

    return None, None

def _detect_medication(text: str) -> tuple[Optional[str], Optional[bool]]:
    """
    Trích xuất thuốc/xử trí đã dùng và hiệu quả.
    Trả về (medication_str, relieved)
    """
    med_keywords = ["panadol", "paracetamol", "thuốc giảm đau", "thuốc hạ sốt", "thuốc", "men tiêu hóa", "dầu gió", "cao dán", "uống viên"]
    found_med = None
    for kw in med_keywords:
        if kw in text:
            found_med = kw
            break

    if not found_med and ("uống rồi" in text or "có uống" in text or "đã uống" in text):
        found_med = "đã dùng thuốc"

    if found_med:
        if any(w in text for w in ["không đỡ", "chưa đỡ", "vẫn đau", "không bớt", "không giảm", "chẳng đỡ", "vẫn sốt", "không thấy đỡ"]):
            return found_med, False
        if any(w in text for w in ["đỡ rồi", "bớt rồi", "có đỡ", "giảm rồi"]):
            return found_med, True
        return found_med, False # Mặc định nếu nhắc thuốc trong ngữ cảnh gọi trợ lý thì thường chưa đỡ

    if "chưa uống" in text or "chưa làm gì" in text or "chưa dùng" in text:
        return "chưa dùng thuốc", None

    return None, None

def _detect_associated_symptoms(text: str, current_symptom: Optional[str]) -> list[str]:
    """Tìm các triệu chứng đi kèm khác với triệu chứng chính"""
    results = []
    candidates = {
        "buồn nôn": ["buồn nôn", "nôn", "mắc ói"],
        "chóng mặt": ["chóng mặt", "hoa mắt", "xây xẩm"],
        "sốt": ["sốt", "nóng người"],
        "tê tay chân": ["tê tay", "tê chân", "tê bì"],
        "đau đầu": ["đau đầu", "nhức đầu"],
        "tiêu chảy": ["tiêu chảy", "đi ngoài"],
        "mệt mỏi": ["mệt mỏi", "kiệt sức"]
    }
    for sym_name, kws in candidates.items():
        if current_symptom and current_symptom in sym_name:
            continue
        if any(kw in text for kw in kws):
            results.append(sym_name)
    return results

class AiEngine:
    provider: str
    openai_client: Optional[Any]
    gemini_client: Optional[Any]

    def __init__(self):
        self.provider = settings.AI_PROVIDER
        self.openai_client = None
        self.gemini_client = None

        if settings.OPENAI_API_KEY and AsyncOpenAI is not None:
            try:
                self.openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            except Exception as e:
                logger.warning(f"[AI Engine] Lỗi khởi tạo OpenAI: {e}")

        if settings.GEMINI_API_KEY and genai is not None:
            try:
                self.gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)
            except Exception as e:
                logger.warning(f"[AI Engine] Lỗi khởi tạo Gemini: {e}")

    async def extract_intent_and_slots(
        self,
        transcript: str,
        previous_session: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        # 1. Gọi Gemini nếu có cấu hình
        if self.provider == "GEMINI" and self.gemini_client and settings.GEMINI_API_KEY:
            try:
                return await self._call_gemini(transcript, previous_session)
            except Exception as e:
                logger.warning(f"[AI Engine Warning] Lỗi gọi Gemini: {e}, dùng fallback parser.")

        # 2. Gọi OpenAI nếu có cấu hình
        if self.provider == "OPENAI" and self.openai_client and settings.OPENAI_API_KEY:
            try:
                return await self._call_openai(transcript, previous_session)
            except Exception as e:
                logger.warning(f"[AI Engine Warning] Lỗi gọi OpenAI: {e}, dùng fallback parser.")

        # 3. Rule-based Fallback Parser
        return self._rule_based_parse(transcript, previous_session)

    async def _call_gemini(self, transcript: str, previous_session: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if not self.gemini_client or types is None:
            raise RuntimeError("Gemini client chưa khởi tạo")

        client = self.gemini_client
        prompt_content = f"Câu nói của bệnh nhân: \"{transcript}\""
        if previous_session:
            prompt_content = f"Ngữ cảnh phiên trước: {json.dumps(previous_session, ensure_ascii=False)}\n\n" + prompt_content

        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            response_mime_type="application/json",
            temperature=0.1,
        )

        candidate_models = [settings.GEMINI_MODEL, "gemini-3.5-flash-lite", "gemini-flash-latest"]
        last_error = None

        for model_name in candidate_models:
            try:
                response = await client.aio.models.generate_content(
                    model=model_name,
                    contents=prompt_content,
                    config=config,
                )
                if not response.text:
                    raise ValueError(f"Model {model_name} trả về nội dung rỗng")
                return json.loads(response.text.strip())
            except Exception as e:
                last_error = e
                continue

        raise last_error or RuntimeError("Không thể gọi Gemini")

    async def _call_openai(self, transcript: str, previous_session: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if not self.openai_client:
            raise RuntimeError("OpenAI client chưa khởi tạo")

        client = self.openai_client
        messages: List[ChatCompletionMessageParam] = [{"role": "system", "content": SYSTEM_PROMPT}]
        if previous_session:
            messages.append({
                "role": "assistant",
                "content": f"Ngữ cảnh phiên trước: {json.dumps(previous_session, ensure_ascii=False)}"
            })
        messages.append({
            "role": "user",
            "content": f"Câu nói của bệnh nhân: \"{transcript}\""
        })

        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.1
        )
        content = response.choices[0].message.content
        if not content:
            raise ValueError("OpenAI trả về rỗng")
        return json.loads(content)

    def _rule_based_parse(self, transcript: str, previous_session: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        text = transcript.lower().strip()
        prev_intent = previous_session.get("intent") if previous_session else None
        prev_params = previous_session.get("parameters", {}) if previous_session else {}
        prev_step = previous_session.get("screening_step") if previous_session else None

        # ============================================================
        # 0. XỬ LÝ XÁC NHẬN (CONFIRMATION) KHI ĐANG Ở BƯỚC HỎI Ý KIẾN
        # ============================================================
        if prev_step in ["AWAITING_CONFIRMATION", "PROPOSE_CARE_REQUEST", "ADVISE_HOME"]:
            if any(kw in text for kw in CONFIRM_POSITIVE):
                return {
                    "intent": "confirmation",
                    "urgency": "MODERATE",
                    "confidence": 0.95,
                    "parameters": {"confirmed": True}
                }
            if any(kw in text for kw in CONFIRM_NEGATIVE):
                return {
                    "intent": "confirmation",
                    "urgency": "LOW",
                    "confidence": 0.95,
                    "parameters": {"confirmed": False}
                }

        # ============================================================
        # 1. KIỂM TRA PHỦ ĐỊNH ("không đau gì", "hết sốt rồi", "khỏe rồi")
        # ============================================================
        if _is_negated(text):
            return {
                "intent": "unknown",
                "urgency": "LOW",
                "confidence": 0.95,
                "parameters": {},
                "friendly_message": "Thật tuyệt vời ạ! Bác cứ yên tâm nghỉ ngơi nhé. Nếu cần gì bác cứ gọi cháu."
            }

        # ============================================================
        # 2. KIỂM TRA 🔴 URGENT (Triệu chứng nguy hiểm tính mạng)
        # ============================================================
        for kw in URGENT_KEYWORDS:
            if kw in text:
                return {
                    "intent": "create_care_request",
                    "urgency": "URGENT",
                    "confidence": 0.98,
                    "parameters": {
                        "title": f"CẤP CỨU: {transcript[:80]}",
                        "description": f"Bệnh nhân báo triệu chứng NGUY HIỂM: {transcript}",
                        "primary_symptom": kw
                    }
                }

        # ============================================================
        # 3. ĐO CHỈ SỐ SỨC KHỎE (Health Records)
        # ============================================================
        nums = extract_vietnamese_numbers(text)
        if "huyết áp" in text or (prev_intent == "create_health_record" and prev_params.get("metricType") == "BLOOD_PRESSURE"):
            val_num = nums[0] if len(nums) > 0 else prev_params.get("valueNumeric")
            sec_val = nums[1] if len(nums) > 1 else prev_params.get("secondaryValue")
            urgency = "URGENT" if (val_num and _check_dangerous_vitals("BLOOD_PRESSURE", val_num, sec_val)) else "MODERATE"
            return {
                "intent": "create_health_record",
                "urgency": urgency,
                "confidence": 0.90,
                "parameters": {
                    "metricType": "BLOOD_PRESSURE",
                    "valueNumeric": val_num,
                    "secondaryValue": sec_val,
                    "unit": "mmHg"
                }
            }

        if "đường huyết" in text or "tiểu đường" in text:
            return {
                "intent": "create_health_record",
                "urgency": "MODERATE",
                "confidence": 0.85,
                "parameters": {"metricType": "BLOOD_GLUCOSE", "valueNumeric": nums[0] if nums else None, "unit": "mmol/L"}
            }

        if "nhịp tim" in text or "mạch" in text:
            val = nums[0] if nums else None
            urgency = "URGENT" if (val and _check_dangerous_vitals("HEART_RATE", val)) else "MODERATE"
            return {
                "intent": "create_health_record",
                "urgency": urgency,
                "confidence": 0.85,
                "parameters": {"metricType": "HEART_RATE", "valueNumeric": val, "unit": "bpm"}
            }

        if "spo2" in text or "oxy" in text:
            val = nums[0] if nums else None
            urgency = "URGENT" if (val and _check_dangerous_vitals("SPO2", val)) else "MODERATE"
            return {
                "intent": "create_health_record",
                "urgency": urgency,
                "confidence": 0.85,
                "parameters": {"metricType": "SPO2", "valueNumeric": val, "unit": "%"}
            }

        if "nhiệt độ" in text or "sốt" in text and nums:
            val = nums[0] if nums else None
            urgency = "URGENT" if (val and _check_dangerous_vitals("TEMPERATURE", val)) else "MODERATE"
            return {
                "intent": "create_health_record",
                "urgency": urgency,
                "confidence": 0.85,
                "parameters": {"metricType": "TEMPERATURE", "valueNumeric": val, "unit": "°C"}
            }

        # ============================================================
        # 4. SÀNG LỌC TRIỆU CHỨNG 🟡 MODERATE (Adaptive Screening)
        # ============================================================
        detected_sym = None
        for sym_group, keywords in MODERATE_SYMPTOM_MAP.items():
            if any(kw in text for kw in keywords):
                detected_sym = sym_group
                break

        # Nếu không thấy triệu chứng mới nhưng đang trong phiên screening dở
        if not detected_sym and prev_intent == "create_care_request":
            detected_sym = prev_params.get("primary_symptom")

        if detected_sym or prev_intent == "create_care_request":
            sym_name = detected_sym or "khó chịu"
            duration, is_prolonged = _detect_duration(text)
            medication, med_relieved = _detect_medication(text)
            assoc_syms = _detect_associated_symptoms(text, sym_name)

            # Ghép dữ liệu đã thu thập trước đó
            params = {
                "primary_symptom": sym_name,
                "duration": duration or prev_params.get("duration"),
                "is_prolonged": is_prolonged if is_prolonged is not None else prev_params.get("is_prolonged"),
                "medication": medication or prev_params.get("medication"),
                "medication_relief": med_relieved if med_relieved is not None else prev_params.get("medication_relief"),
                "associated_symptoms": list(set(assoc_syms + prev_params.get("associated_symptoms", []))),
                "title": f"Bệnh nhân có triệu chứng {sym_name}",
                "description": transcript
            }

            return {
                "intent": "create_care_request",
                "urgency": "MODERATE",
                "confidence": 0.90,
                "parameters": params
            }

        # ============================================================
        # 5. KHÔNG RÕ Ý ĐỊNH
        # ============================================================
        return {
            "intent": "unknown",
            "urgency": "LOW",
            "confidence": 0.50,
            "parameters": {}
        }

ai_engine = AiEngine()
