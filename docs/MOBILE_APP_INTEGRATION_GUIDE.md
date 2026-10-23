# HƯỚNG DẪN TÍCH HỢP AI VOICE AGENT CHO MOBILE APP (CLIENT INTEGRATION GUIDE)
## Phiên bản: 2.0 (Hỗ trợ Triage 3 tầng & Sàng lọc Lâm sàng Thích ứng)

Tài liệu này hướng dẫn đội ngũ phát triển Mobile App (Flutter / React Native / iOS / Android) cách tích hợp và gọi API vào dịch vụ **AI Voice Agent Server** (`automatic-calling-api`).

---

## 1. TỔNG QUAN KIẾN TRÚC & LUỒNG TƯƠNG TÁC (WORKFLOW)

Hệ thống hoạt động theo mô hình **Client-side STT/TTS + Server AI Triage & Slot-Filling**:

```
[Bệnh nhân nói qua Mic]
      │
      ▼
[Mobile App]
  ├── 1. Thu âm & chuyển giọng nói thành văn bản (Native STT)
  └── 2. Gửi transcript lên AI Server kèm Bearer JWT Token của người dùng
      │
      ▼ POST /api/v1/voice-command/process (Authorization: Bearer <Token>)
[AI Server (automatic-calling-api)]
  ├── Phân loại Ý định (Intent): Ghi chỉ số sức khỏe HOẶC Báo triệu chứng
  ├── Phân loại Mức độ Khẩn cấp (Urgency Triage):
  │     ├── 🔴 URGENT (Nguy hiểm tính mạng): Gọi API Backend NGAY, không hỏi lại
  │     ├── 🟡 MODERATE (Đau đầu, sốt, đau bụng...): Sàng lọc bệnh sử & Hỏi xác nhận
  │     └── 🟢 LOW / Phủ định (Không đau, khỏe rồi): Tư vấn nhẹ, KHÔNG gọi API
  └── Trả về kết quả cho Mobile App:
        ├── SUCCESS: API đã được gọi thành công (Đọc TTS + thông báo UI)
        ├── NEED_MORE_INFO: Cần hỏi thêm thông tin (Mở lại Mic)
        ├── PENDING_CONFIRMATION: Đang chờ bệnh nhân xác nhận (Hiển thị nút/Mở Mic)
        └── UNKNOWN_INTENT: Chưa hiểu ý định
```

---

## 2. THÔNG TIN KẾT NỐI API (API SPECIFICATION)

### 2.1. Endpoint chính
* **URL**: `POST /api/v1/voice-command/process`
  * Môi trường Local: `http://localhost:8000/api/v1/voice-command/process`
  * Môi trường Server: `http://<IP_OR_DOMAIN_AI_SERVER>:8000/api/v1/voice-command/process`
* **Content-Type**: `application/json`
* **Authentication**: `Authorization: Bearer <USER_JWT_TOKEN>` *(Sử dụng chính token đăng nhập của bệnh nhân trên hệ thống VN Doctor)*

---

### 2.2. Request Payload (Dữ liệu App gửi lên)

```json
{
  "transcript": "Tôi bị đau đầu từ sáng đến giờ",
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
| `session_id` | `string` | Không | ID của phiên hội thoại.<br>• **Lượt nói đầu tiên**: Để `null` (AI Server tự sinh).<br>• **Lượt nói trả lời bổ sung / xác nhận**: Truyền lại `session_id` nhận được từ phản hồi trước. |
| `context` | `object` | Không | Ngữ cảnh hiện tại trên màn hình App của bệnh nhân. |
| `context.health_profile_id` | `string (UUID)` | Không | UUID của hồ sơ sức khỏe bệnh nhân đang chọn hoặc xem trên App. |
| `context.subscription_id` | `string (UUID)` | Không | UUID của gói chăm sóc active. Nếu không truyền, AI Server sẽ tự tra cứu. |

---

### 2.3. Response Payload (Dữ liệu AI Server trả về)

```json
{
  "status": "PENDING_CONFIRMATION",
  "session_id": "user_sess_01a11412-f8e4-71a4-80d2-197d052d5152",
  "intent": "create_care_request",
  "urgency": "MODERATE",
  "response_message": "Dạ, tình trạng đau đầu của bác đã kéo dài hơn 2 tiếng, uống thuốc chưa đỡ và kèm buồn nôn. Cháu đề xuất gửi ngay yêu cầu để Bác sĩ xem và liên hệ hỗ trợ bác nhé, bác có đồng ý không ạ?",
  "missing_fields": null,
  "collected_data": {
    "primary_symptom": "đau đầu",
    "duration": "hơn 2 tiếng",
    "is_prolonged": true,
    "medication": "1 viên Panadol",
    "medication_relief": false,
    "associated_symptoms": ["buồn nôn"]
  },
  "api_result": null
}
```

#### Chi tiết các trường Response:
| Trường | Kiểu dữ liệu | Mô tả |
| :--- | :--- | :--- |
| `status` | `enum` | **Trạng thái cốt lõi để App điều khiển UI**: Xem mục 3. |
| `urgency` | `enum` | Mức độ khẩn cấp: `URGENT` (🔴 Cấp cứu), `MODERATE` (🟡 Bình thường), `LOW` (🟢 Nhẹ/Phủ định). |
| `session_id` | `string` | ID phiên hội thoại. App **phải lưu lại** để gửi kèm trong lượt tiếp theo nếu chưa kết thúc. |
| `intent` | `string` | Ý định: `create_care_request` (yêu cầu hỗ trợ), `create_health_record` (chỉ số đo), `confirmation`. |
| `response_message` | `string` | **Câu phản hồi tự nhiên bằng tiếng Việt**. App dùng chuỗi này để hiển thị UI và đọc TTS cho bệnh nhân nghe. |
| `missing_fields` | `list[string]` | Danh sách trường còn thiếu nếu `status` là `NEED_MORE_INFO` (vd: `["duration"]`, `["valueNumeric"]`). |
| `collected_data` | `object` | Dữ liệu lâm sàng đã thu thập được tính đến thời điểm hiện tại. |
| `api_result` | `object` | Dữ liệu trả về từ Backend VN Doctor (khi `status` là `SUCCESS` và API đã được gọi). |

---

## 3. BẢNG MÃ TRẠNG THÁI `status` & HÀNH ĐỘNG CỦA MOBILE APP

| Trạng thái (`status`) | Mức độ `urgency` | Ý nghĩa | Hành động của App |
| :--- | :--- | :--- | :--- |
| **`SUCCESS`** | `URGENT` | 🔴 **Cấp cứu khẩn cấp**: AI đã tự động gọi API tạo phiếu Bác sĩ tức thì. | 1. Đọc TTS `response_message`.<br>2. Hiện popup Cảnh báo khẩn cấp màu đỏ.<br>3. Xóa `session_id`. |
| **`SUCCESS`** | `MODERATE` | Bệnh nhân đã đồng ý xác nhận và AI đã gửi phiếu Bác sĩ thành công. | 1. Đọc TTS `response_message`.<br>2. Báo gửi thành công (Toast/Popup xanh).<br>3. Xóa `session_id`. |
| **`SUCCESS`** | `LOW` | Câu phủ định ("Tôi không đau gì cả") hoặc bệnh nhân từ chối gửi phiếu. | 1. Đọc TTS `response_message`.<br>2. Xóa `session_id`. Không gọi API. |
| **`PENDING_CONFIRMATION`** | `MODERATE` | AI đã sàng lọc xong bệnh sử và đang hỏi ý kiến bệnh nhân có muốn gửi Bác sĩ không. | 1. Lưu `session_id`.<br>2. Đọc TTS `response_message`.<br>3. **Hiện 2 nút lựa chọn: [Gửi Bác sĩ] & [Để theo dõi thêm]**, hoặc tự động mở mic để bệnh nhân nói "Ừ" / "Không". |
| **`NEED_MORE_INFO`** | `MODERATE` | Thiếu thông tin bệnh sử (thời gian bị, thuốc đã dùng...) hoặc thiếu số đo. | 1. Lưu `session_id`.<br>2. Đọc TTS `response_message`.<br>3. Tự động bật Mic cho bệnh nhân trả lời tiếp lượt sau. |
| **`UNKNOWN_INTENT`** | `LOW` | Chưa hiểu ý định người nói. | Đọc TTS `response_message` hướng dẫn người bệnh. |
| **`ERROR`** | Bất kỳ | Token lỗi hoặc lỗi kết nối. | Hiển thị thông báo lỗi từ `response_message`. |

---

## 4. CÁC KỊCH BẢN TƯƠNG TÁC THỰC TẾ

### Kịch bản 1: 🔴 Cấp cứu khẩn cấp (Single-turn Auto Call)
* **Bệnh nhân nói**: *"Tôi bị đau ngực và khó thở dữ dội"*
* **App gửi**:
  ```json
  POST /api/v1/voice-command/process
  Headers: { "Authorization": "Bearer <TOKEN>" }
  Body: {
    "transcript": "Tôi bị đau ngực và khó thở dữ dội"
  }
  ```
* **AI Server trả về**:
  ```json
  {
    "status": "SUCCESS",
    "urgency": "URGENT",
    "intent": "create_care_request",
    "response_message": "Cháu đã gửi tín hiệu hỗ trợ KHẨN CẤP đến Bác sĩ và đội ngũ y tế. Bác hãy giữ bình tĩnh, ngồi nghỉ tựa lưng và chờ Bác sĩ liên hệ ngay nhé!",
    "api_result": { "id": "care_req_123" }
  }
  ```
* **App xử lý**: Bật TTS đọc to câu trả lời, hiển thị UI cảnh báo khẩn cấp màu đỏ.

---

### Kịch bản 2: 🟡 Sàng lọc triệu chứng thông thường (Multi-turn Screening)
* **Lượt 1 - Khởi đầu**:
  * 👤 Bệnh nhân: *"Tôi bị đau đầu quá"*
  * 📱 App gửi: `transcript: "Tôi bị đau đầu quá"`, `session_id: null`
  * 🤖 AI Server trả về:
    ```json
    {
      "status": "NEED_MORE_INFO",
      "session_id": "sess_headache_001",
      "missing_fields": ["duration"],
      "response_message": "Dạ cháu nghe rồi ạ. Bác bị đau đầu từ lúc nào, được bao lâu rồi bác?"
    }
    ```
  * 📱 App: Lưu `session_id = "sess_headache_001"`, đọc TTS câu hỏi, tự động mở Mic lượt 2.

* **Lượt 2 - Trả lời thời gian**:
  * 👤 Bệnh nhân: *"Bị từ sáng đến giờ, chắc hơn 2 tiếng rồi"*
  * 📱 App gửi: `transcript: "Bị từ sáng đến giờ, chắc hơn 2 tiếng rồi"`, `session_id: "sess_headache_001"`
  * 🤖 AI Server trả về:
    ```json
    {
      "status": "PENDING_CONFIRMATION",
      "session_id": "sess_headache_001",
      "response_message": "Dạ, tình trạng đau đầu của bác đã kéo dài từ sáng đến giờ, hơn 2 tiếng. Cháu đề xuất gửi ngay yêu cầu để Bác sĩ xem và liên hệ hỗ trợ bác nhé, bác có đồng ý không ạ?"
    }
    ```
  * 📱 App: Đọc TTS câu hỏi, hiện UI có 2 nút: **[Gửi Bác sĩ]** và **[Để theo dõi thêm]** hoặc mở mic.

* **Lượt 3a - Bệnh nhân Đồng ý**:
  * 👤 Bệnh nhân bấm nút **[Gửi Bác sĩ]** hoặc nói: *"Ừ gửi giúp tôi đi"*
  * 📱 App gửi: `transcript: "Ừ gửi giúp tôi đi"`, `session_id: "sess_headache_001"`
  * 🤖 AI Server: Tự động đóng gói phiếu đầy đủ bệnh sử và gọi BE VN Doctor:
    ```json
    {
      "status": "SUCCESS",
      "urgency": "MODERATE",
      "response_message": "Dạ cháu đã gửi thông tin bệnh sử chi tiết đến Bác sĩ phụ trách rồi ạ. Trong lúc chờ Bác sĩ liên hệ, bác hãy nghỉ ngơi ở nơi thoáng mát và tránh nhìn vào màn hình nhé!",
      "api_result": { "id": "care_req_456" }
    }
    ```
  * 📱 App: Xóa `session_id`, đọc TTS và đóng popup.

* **Lượt 3b - Bệnh nhân Từ chối (Không làm phiền Bác sĩ)**:
  * 👤 Bệnh nhân bấm nút **[Để theo dõi thêm]** hoặc nói: *"Thôi không cần đâu"*
  * 📱 App gửi: `transcript: "Thôi không cần đâu"`, `session_id: "sess_headache_001"`
  * 🤖 AI Server: Không gọi API, trả về:
    ```json
    {
      "status": "SUCCESS",
      "urgency": "LOW",
      "response_message": "Dạ vâng, bác cứ nghỉ ngơi theo dõi thêm nhé. Bất cứ khi nào thấy mệt hơn hoặc cần Bác sĩ, bác cứ gọi cháu nhé!"
    }
    ```
  * 📱 App: Xóa `session_id`, đọc TTS động viên và đóng popup.

---

### Kịch bản 3: 🟢 Câu phủ định (Không tạo phiếu rác)
* **Bệnh nhân nói**: *"Tôi không đau gì cả, hôm nay thấy khỏe rồi"*
* **App gửi**: `transcript: "Tôi không đau gì cả, hôm nay thấy khỏe rồi"`
* **AI Server trả về**:
  ```json
  {
    "status": "SUCCESS",
    "urgency": "LOW",
    "response_message": "Thật tuyệt vời ạ! Bác cứ yên tâm nghỉ ngơi nhé. Nếu cần gì bác cứ gọi cháu."
  }
  ```
* **App xử lý**: Đọc TTS, không tạo phiếu trên hệ thống.

---

### Kịch bản 4: Ghi nhận Chỉ số Sức khỏe (Health Record)
* **Bệnh nhân nói**: *"Huyết áp sáng nay 120 trên 80"*
* **App gửi**:
  ```json
  Body: {
    "transcript": "Huyết áp sáng nay 120 trên 80",
    "context": { "health_profile_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11" }
  }
  ```
* **AI Server trả về**:
  ```json
  {
    "status": "SUCCESS",
    "intent": "create_health_record",
    "response_message": "Đã lưu thành công chỉ số BLOOD_PRESSURE (120.0/80.0 mmHg) vào hồ sơ sức khỏe.",
    "api_result": { ... }
  }
  ```
* **App xử lý**: Đọc TTS, reload lại biểu đồ huyết áp trên App.

---

## 5. MẪU CODE TÍCH HỢP CHO CLIENT (FLUTTER / DART)

```dart
class VoiceCommandService {
  final String baseUrl = "http://your-ai-server:8000/api/v1";
  String? currentSessionId;

  Future<void> sendVoiceTranscript({
    required String transcript,
    required String userToken,
    String? healthProfileId,
    String? subscriptionId,
  }) async {
    final url = Uri.parse("$baseUrl/voice-command/process");

    final body = jsonEncode({
      "transcript": transcript,
      "session_id": currentSessionId,
      "context": {
        if (healthProfileId != null) "health_profile_id": healthProfileId,
        if (subscriptionId != null) "subscription_id": subscriptionId,
      }
    });

    final response = await http.post(
      url,
      headers: {
        "Content-Type": "application/json",
        "Authorization": "Bearer $userToken",
      },
      body: body,
    );

    if (response.statusCode == 200) {
      final data = jsonDecode(utf8.decode(response.bodyBytes));
      final status = data["status"];
      final urgency = data["urgency"];
      final responseMessage = data["response_message"] ?? "";
      currentSessionId = data["session_id"];

      // 1. Luôn đọc TTS câu phản hồi của AI
      await speakTTS(responseMessage);

      // 2. Điều phối theo trạng thái
      switch (status) {
        case "SUCCESS":
          currentSessionId = null; // Kết thúc phiên
          if (urgency == "URGENT") {
            showEmergencyAlertModal(responseMessage);
          } else {
            showToastSuccess(responseMessage);
          }
          break;

        case "PENDING_CONFIRMATION":
          // Hiển thị 2 nút xác nhận trên UI hoặc tự động mở mic nghe "Ừ" / "Không"
          showConfirmationDialog(
            message: responseMessage,
            onConfirm: () => sendVoiceTranscript(transcript: "Đồng ý gửi", userToken: userToken),
            onCancel: () => sendVoiceTranscript(transcript: "Thôi không cần", userToken: userToken),
          );
          break;

        case "NEED_MORE_INFO":
          // Tự động mở micro sau khi TTS đọc xong câu hỏi
          await Future.delayed(Duration(seconds: 3));
          startListeningMicrophone();
          break;

        case "UNKNOWN_INTENT":
        case "ERROR":
          showToastError(responseMessage);
          break;
      }
    }
  }
}
```
