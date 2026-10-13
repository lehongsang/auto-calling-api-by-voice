# HƯỚNG DẪN TÍCH HỢP AI VOICE AGENT CHO MOBILE APP (CLIENT INTEGRATION GUIDE)

Tài liệu này hướng dẫn đội ngũ phát triển Mobile App (Flutter / React Native / iOS / Android) cách tích hợp và gọi API vào dịch vụ **AI Voice Agent Server** (`automatic-calling-api`).

---

## 1. TỔNG QUAN KIẾN TRÚC & LUỒNG TƯƠNG TÁC (WORKFLOW)

Hệ thống hoạt động theo mô hình **Client-side STT/TTS + Server AI Slot-Filling**:

```
[Bệnh nhân nói]
      │
      ▼
[Mobile App]
  ├── 1. Thu âm & chuyển giọng nói thành văn bản (Native STT)
  └── 2. Gửi text lên AI Server kèm Bearer JWT Token của người dùng
      │
      ▼ POST /api/v1/voice-command/process (Authorization: Bearer <Token>)
[AI Server (automatic-calling-api)]
  ├── Nhận diện Ý định (Intent): Ghi chỉ số sức khỏe HOẶC Gửi yêu cầu chăm sóc
  ├── Bóc tách dữ liệu (Slot Extraction): Trích xuất huyết áp, đường huyết, triệu chứng...
  └── Kiểm tra tính đầy đủ:
        ├── THIẾU THÔNG TIN ──────────────┐
        │                                  ▼
        │                          [Mobile App nhận NEED_MORE_INFO]
        │                          - Bật TTS đọc câu hỏi cho bệnh nhân
        │                          - Lưu session_id để gửi tiếp lượt sau
        │
        └── ĐỦ THÔNG TIN ─────────────────┐
                                          ▼
                               [AI Server tự gọi VN Doctor Backend]
                               - POST /health-records hoặc /care-requests
                               - Chuyển tiếp nguyên vẹn Bearer Token
                                          │
                                          ▼
                               [Mobile App nhận SUCCESS]
                               - Hiển thị kết quả & TTS đọc thông báo thành công
```

---

## 2. THÔNG TIN KẾT NỐI API (API SPECIFICATION)

### 2.1. Endpoint chính
* **URL**: `POST /api/v1/voice-command/process`
  * Môi trường Local: `http://localhost:8000/api/v1/voice-command/process`
  * Môi trường Server/Dev: `http://<IP_OR_DOMAIN_AI_SERVER>:8000/api/v1/voice-command/process`
* **Content-Type**: `application/json`
* **Authentication**: `Authorization: Bearer <USER_JWT_TOKEN>` *(Sử dụng chính token đăng nhập của bệnh nhân trên hệ thống VN Doctor)*

---

### 2.2. Request Payload (Dữ liệu App gửi lên)

```json
{
  "transcript": "Huyết áp của tôi là 120 trên 80",
  "session_id": "user_sess_01a11412-f8e4-71a4-80d2-197d052d5152",
  "context": {
    "health_profile_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
    "subscription_id": "b1ffbc88-8b0a-3ef7-aa5c-5aa8ad270b22"
  }
}
```

#### Chi tiết các trường Request:
| Trường | Kiểu dữ liệu | Bắt buộc | Mô tả |
| :--- | :--- | :---: | :--- |
| `transcript` | `string` | **Có** | Văn bản nhận diện được từ giọng nói của bệnh nhân (kết quả từ STT). |
| `session_id` | `string` | Không | ID của phiên hội thoại. <br>• **Lượt nói đầu tiên**: Để `null` (AI Server sẽ tự sinh theo user ID). <br>• **Lượt nói trả lời bổ sung**: Truyền lại `session_id` nhận được từ phản hồi trước. |
| `context` | `object` | Không | Ngữ cảnh hiện tại trên màn hình App của bệnh nhân. |
| `context.health_profile_id` | `string (UUID)` | Không | UUID của hồ sơ sức khỏe bệnh nhân đang chọn hoặc xem trên App. |
| `context.subscription_id` | `string (UUID)` | Không | UUID của gói chăm sóc sức khỏe đang chọn. Nếu không truyền, AI Server sẽ tự tra cứu gói `ACTIVE` của người dùng. |

---

### 2.3. Response Payload (Dữ liệu AI Server trả về cho App)

```json
{
  "status": "SUCCESS",
  "session_id": "user_sess_01a11412-f8e4-71a4-80d2-197d052d5152",
  "intent": "create_health_record",
  "response_message": "Đã lưu thành công chỉ số BLOOD_PRESSURE (120.0/80.0 mmHg) vào hồ sơ sức khỏe.",
  "missing_fields": null,
  "collected_data": null,
  "api_result": {
    "id": "e81d7632-1111-4f12-a123-abcdef123456",
    "metricType": "BLOOD_PRESSURE",
    "valueNumeric": 120,
    "secondaryValue": 80,
    "unit": "mmHg"
  }
}
```

#### Chi tiết các trường Response:
| Trường | Kiểu dữ liệu | Mô tả |
| :--- | :--- | :--- |
| `status` | `enum` | Trạng thái xử lý: `SUCCESS`, `NEED_MORE_INFO`, `UNKNOWN_INTENT`, `ERROR`. |
| `session_id` | `string` | ID phiên hội thoại. App **phải lưu lại** để gửi kèm trong lượt nói tiếp theo nếu status là `NEED_MORE_INFO`. |
| `intent` | `string` | Ý định nhận diện: `create_health_record` (chỉ số sức khỏe) hoặc `create_care_request` (yêu cầu chăm sóc). |
| `response_message` | `string` | **Câu phản hồi tự nhiên bằng tiếng Việt**. App dùng chuỗi này để hiển thị lên UI và truyền vào bộ đọc giọng nói (TTS) cho bệnh nhân nghe. |
| `missing_fields` | `list[string]` | Danh sách trường còn thiếu nếu `status` là `NEED_MORE_INFO` (vd: `["valueNumeric"]`, `["healthProfileId"]`). |
| `collected_data` | `object` | Dữ liệu các trường đã gom được tính tới thời điểm hiện tại. |
| `api_result` | `object` | Dữ liệu trả về từ Backend VN Doctor (chỉ có khi `status` là `SUCCESS`). |

---

## 3. CÁC TRẠNG THÁI `status` VÀ HÀNH ĐỘNG CỦA MOBILE APP

| Trạng thái (`status`) | Ý nghĩa | Hành động của App |
| :--- | :--- | :--- |
| **`SUCCESS`** | Đã thu thập đủ thông tin và AI Server đã gọi Backend VN Doctor lưu thành công. | 1. Đọc TTS chuỗi `response_message`.<br>2. Xóa `session_id` đã lưu.<br>3. Reload lại danh sách chỉ số / yêu cầu trên màn hình. |
| **`NEED_MORE_INFO`** | Người bệnh nói thiếu thông tin (vd: chỉ nói *"Tôi vừa đo huyết áp"* mà chưa đọc số). | 1. Lưu lại `session_id`.<br>2. Đọc TTS chuỗi `response_message` (vd: *"Bác vừa đo được bao nhiêu ạ?"*).<br>3. Tự động bật micro cho bệnh nhân trả lời tiếp lượt 2. |
| **`UNKNOWN_INTENT`** | AI chưa hiểu được ý định câu nói của bệnh nhân. | Đọc TTS `response_message` hướng dẫn người bệnh nói rõ lại nhu cầu. |
| **`ERROR`** | Xảy ra lỗi (Token hết hạn, lỗi kết nối Backend...). | Hiển thị thông báo lỗi từ `response_message`. |

---

## 4. CÁC KỊCH BẢN THỰC TẾ (USE CASES & CÁCH GỌI)

### Kịch bản 1: Bệnh nhân đọc đủ chỉ số trong 1 câu (Single-turn)
* **Bệnh nhân nói**: *"Huyết áp của tôi sáng nay là 120 trên 80"*
* **App gửi**:
  ```json
  POST /api/v1/voice-command/process
  Headers: { "Authorization": "Bearer <TOKEN>" }
  Body: {
    "transcript": "Huyết áp của tôi sáng nay là 120 trên 80",
    "context": { "health_profile_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11" }
  }
  ```
* **AI Server trả về**:
  ```json
  {
    "status": "SUCCESS",
    "session_id": "user_sess_123",
    "intent": "create_health_record",
    "response_message": "Đã lưu thành công chỉ số BLOOD_PRESSURE (120.0/80.0 mmHg) vào hồ sơ sức khỏe.",
    "api_result": { ... }
  }
  ```
* **App xử lý**: Bật TTS đọc câu trả lời và đóng popup thu âm.

---

### Kịch bản 2: Bệnh nhân nói thiếu chỉ số (Multi-turn Slot Filling)
* **Lượt 1 - Bệnh nhân nói**: *"Tôi vừa đo đường huyết xong"*
  * **App gửi**:
    ```json
    Body: {
      "transcript": "Tôi vừa đo đường huyết xong",
      "context": { "health_profile_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11" }
    }
    ```
  * **AI Server trả về**:
    ```json
    {
      "status": "NEED_MORE_INFO",
      "session_id": "user_sess_123",
      "intent": "create_health_record",
      "missing_fields": ["valueNumeric"],
      "response_message": "Bác vừa đo chỉ số đường huyết được bao nhiêu mmol/L hoặc mg/dL ạ?"
    }
    ```
  * **App xử lý**: Lưu `session_id = "user_sess_123"`. Đọc TTS câu hỏi, sau đó mở micro thu âm câu trả lời của người bệnh.

* **Lượt 2 - Bệnh nhân nói tiếp**: *"Sáu phẩy năm lúc đói"*
  * **App gửi** *(Bắt buộc kèm `session_id` đã lưu)*:
    ```json
    Body: {
      "session_id": "user_sess_123",
      "transcript": "Sáu phẩy năm lúc đói",
      "context": { "health_profile_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11" }
    }
    ```
  * **AI Server trả về**:
    ```json
    {
      "status": "SUCCESS",
      "session_id": "user_sess_123",
      "intent": "create_health_record",
      "response_message": "Đã lưu thành công chỉ số BLOOD_GLUCOSE (6.5 mmol/L) vào hồ sơ sức khỏe.",
      "api_result": { ... }
    }
    ```
  * **App xử lý**: Xóa `session_id`, đọc TTS thông báo thành công.

---

### Kịch bản 3: Gửi yêu cầu chăm sóc y tế / Phản ánh triệu chứng (Care Request)
* **Bệnh nhân nói**: *"Bác sĩ ơi tôi uống thuốc huyết áp xong cảm thấy đau đầu và buồn nôn"*
* **App gửi**:
  ```json
  POST /api/v1/voice-command/process
  Headers: { "Authorization": "Bearer <TOKEN>" }
  Body: {
    "transcript": "Bác sĩ ơi tôi uống thuốc huyết áp xong cảm thấy đau đầu và buồn nôn"
  }
  ```
* **AI Server tự động**:
  1. Nhận diện `intent = "create_care_request"`.
  2. Tự động lấy gói chăm sóc `ACTIVE` của bệnh nhân.
  3. Trích xuất tiêu đề tóm tắt: *"Cảm thấy đau đầu và buồn nôn sau khi uống thuốc huyết áp"*.
  4. Gọi API `POST /care-requests` sang VN Doctor Backend.
* **AI Server trả về**:
  ```json
  {
    "status": "SUCCESS",
    "intent": "create_care_request",
    "response_message": "Đã gửi yêu cầu hỗ trợ y tế đến đội ngũ chăm sóc sức khỏe thành công."
  }
  ```

---

## 5. CODE MẪU TÍCH HỢP CHO CLIENT

### 5.1. Code mẫu Flutter (Dart)

```dart
import 'dart:convert';
import 'package:http/http.dart' as http;

class VoiceAgentService {
  final String baseUrl = "http://10.0.2.2:8000"; // Android Emulator trỏ về máy tính
  String? currentSessionId;

  Future<void> sendVoiceCommand({
    required String userToken,
    required String transcript,
    String? healthProfileId,
    String? subscriptionId,
    required Function(String speechText) onSpeakResponse,
  }) async {
    final uri = Uri.parse("$baseUrl/api/v1/voice-command/process");

    final Map<String, dynamic> body = {
      "transcript": transcript,
      if (currentSessionId != null) "session_id": currentSessionId,
      "context": {
        if (healthProfileId != null) "health_profile_id": healthProfileId,
        if (subscriptionId != null) "subscription_id": subscriptionId,
      }
    };

    final response = await http.post(
      uri,
      headers: {
        "Content-Type": "application/json",
        "Authorization": "Bearer $userToken",
      },
      body: jsonEncode(body),
    );

    if (response.statusCode == 200) {
      final data = jsonDecode(utf8.decode(response.bodyBytes));
      final String status = data["status"];
      final String message = data["response_message"] ?? "";
      
      // 1. Đọc phản hồi bằng TTS cho bệnh nhân nghe
      onSpeakResponse(message);

      // 2. Quản lý phiên đa lượt
      if (status == "NEED_MORE_INFO") {
        currentSessionId = data["session_id"];
        // TODO: Chờ đọc xong TTS rồi tự động kích hoạt thu âm lượt tiếp theo
      } else {
        // Hoàn tất hoặc Lỗi -> Reset session
        currentSessionId = null;
      }
    } else {
      onSpeakResponse("Có lỗi xảy ra khi kết nối tới trợ lý y tế.");
    }
  }
}
```

---

### 5.2. Code mẫu React Native / TypeScript (Axios)

```typescript
import axios from 'axios';

const AI_SERVER_URL = 'http://localhost:8000/api/v1/voice-command/process';
let currentSessionId: string | null = null;

interface VoiceContext {
  health_profile_id?: string;
  subscription_id?: string;
}

export const processVoiceCommand = async (
  token: string,
  transcript: string,
  context?: VoiceContext,
  speakTTS?: (text: string) => void
) => {
  try {
    const payload = {
      transcript,
      session_id: currentSessionId,
      context: context || {},
    };

    const response = await axios.post(AI_SERVER_URL, payload, {
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
    });

    const { status, session_id, response_message, api_result } = response.data;

    // Đọc giọng nói TTS phản hồi
    if (speakTTS && response_message) {
      speakTTS(response_message);
    }

    if (status === 'NEED_MORE_INFO') {
      // Lưu lại session để gửi kèm câu trả lời tiếp theo
      currentSessionId = session_id;
      return { needMoreInfo: true, message: response_message };
    } else {
      // Thành công hoặc lỗi -> Reset session
      currentSessionId = null;
      return { success: status === 'SUCCESS', data: api_result, message: response_message };
    }
  } catch (error) {
    console.error('Lỗi khi gọi AI Voice Agent:', error);
    if (speakTTS) speakTTS('Không thể kết nối đến máy chủ trợ lý.');
    throw error;
  }
};
```

---

## 6. DANH SÁCH CHỈ SỐ SỨC KHỎE ĐƯỢC HỖ TRỢ TỰ ĐỘNG

AI Server tự động nhận diện tiếng Việt và ánh xạ sang chuẩn Backend VN Doctor:

| Chỉ số | Từ khóa tiếng Việt nhận diện | `metricType` BE | Đơn vị chuẩn (`unit`) |
| :--- | :--- | :--- | :--- |
| **Huyết áp** | *huyết áp, đo huyết áp, trên...* | `BLOOD_PRESSURE` | `mmHg` |
| **Đường huyết** | *đường huyết, tiểu đường, đường máu...* | `BLOOD_GLUCOSE` | `mmol/L` hoặc `mg/dL` |
| **Nhịp tim** | *nhịp tim, mạch đập, tim đập...* | `HEART_RATE` | `bpm` |
| **Nồng độ oxy SpO2** | *oxy trong máu, spo2, nồng độ oxy...* | `SPO2` | `%` |
| **Nhiệt độ** | *nhiệt độ, cặp nhiệt độ, sốt, độ...* | `TEMPERATURE` | `°C` |
| **Cân nặng** | *cân nặng, nặng, ký, kg...* | `WEIGHT` | `kg` |
| **Chiều cao** | *chiều cao, cao, mét, cm...* | `HEIGHT` | `cm` |

---

## 7. MẸO & LƯU Ý KHI TÍCH HỢP
1. **Âm thanh STT trên App**: App chỉ cần dùng thư viện Native Speech-to-Text của hệ điều hành (Apple Speech Framework trên iOS, Google SpeechRecognizer trên Android) để nhận diện ra chuỗi `transcript`, không cần gửi file âm thanh thô lên server.
2. **Context Profile**: Khi người dùng đang đứng ở màn hình hồ sơ của ai (bản thân hoặc người thân), App nên truyền `health_profile_id` trong trường `context` để AI tự gán luôn vào người đó mà không cần hỏi lại.
3. **Session Timeout**: Phiên hỏi dở (`session_id`) có thời hạn sống mặc định là 5 phút (300 giây). Nếu quá 5 phút bệnh nhân mới nói lại, hệ thống sẽ tự động coi là phiên mới.
