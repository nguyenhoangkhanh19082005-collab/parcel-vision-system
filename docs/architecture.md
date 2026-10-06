# Kiến trúc Vision Station

## 1. Mục tiêu kỹ thuật

Trạm nhận một kiện hàng đã dừng, chụp burst ảnh, chọn ảnh đạt chất lượng, đọc QR,
kiểm tra logo, kiểm tra hình dạng kiện và đối chiếu Supabase, sau đó sinh một quyết định:

- `PASS`: có dữ liệu hợp lệ và xác định được rổ đích.
- `REJECT`: kiện hư hỏng, thiếu logo/QR hoặc không khớp dữ liệu trạm.
- `MANUAL_REVIEW`: dữ liệu tồn tại nhưng chưa đủ thông tin định tuyến an toàn.

Mọi quyết định phải có `reason`, timestamp và ảnh bằng chứng. Điều khiển motor không
được nằm trong thuật toán ảnh; nó thuộc tầng station control và chỉ nhận kết quả đã chốt.

## 2. Các tầng phần mềm

| Tầng | Trách nhiệm | Module |
|---|---|---|
| Acquisition | Mở UVC camera, đặt MJPG/2K, đọc lại thông số thực | `camera/opencv_camera.py` |
| Image quality | Laplacian, Tenengrad, motion, highlight ratio | `imaging/focus.py` |
| Enhancement | CLAHE, unsharp nhẹ, resize, threshold variants | `imaging/enhancement.py` |
| Recognition | ZXing/OpenCV QR và logo SIFT + RANSAC | `readers/` |
| Condition | Tách nền, rectangularity, solidity và đường bao kiện | `services/damage.py` |
| Interpretation | Chuẩn hóa chuỗi, tìm mã vận đơn | `services/label_parser.py` |
| Decision | Luật PASS/REJECT/REVIEW, lookup repository | `services/classifier.py` |
| Orchestration | Chọn frame và chạy toàn bộ inspection | `services/pipeline.py` |
| Operator UI | Camera preview, quality gate, kết quả, lịch sử | `ui/main_window.py` |
| Integration | Supabase hiện có; ESP32 sẽ bổ sung ở phase 2 | `repositories/`, phase 2 |

## 3. State machine dự kiến

```text
IDLE
  └─ sensor=ON ─► STOPPING_CONVEYOR
                     └─ motor_stopped ─► ACQUIRING
                                           ├─ quality timeout ─► REJECT
                                           └─ best frame ─► RECOGNIZING
                                                               ├─ damaged ─► DEFECT
                                                               ├─ invalid ─► REJECT
                                                               └─ valid ─► LOOKUP
                                                                            ├─ mismatch ─► REJECT
                                                                            └─ match ─► RELEASE
RELEASE ─► conveyor downstream ─► ROBOT_READY ─► PICK ─► IDLE
REJECT  ─► reject actuator pulse ───────────────────────────────► IDLE
```

ESP32 phải có watchdog và trạng thái lỗi riêng. PC không gửi lệnh motor liên tục;
PC gửi command có sequence ID, ESP32 trả ACK và trạng thái thực tế.

## 4. Chiến lược lấy ảnh

- Camera được gắn vuông góc với bề mặt nhãn, khoảng cách trong vùng nét thật.
- Dùng 2K MJPEG; với vật đã dừng, ưu tiên pixel thay vì FPS.
- Khi sensor kích hoạt, bỏ 3–5 frame đầu sau khi motor dừng rồi thu burst 10–20 frame.
- Quality gate chạy trên ROI nhãn, không chạy toàn frame.
- Chỉ frame thỏa focus, motion và glare mới là ứng viên.
- Chỉ bắt đầu chọn sau số frame ổn định liên tiếp được cấu hình; frame đầu tiên không
  thể tự chứng minh vật đã đứng yên.
- Điểm chọn frame ban đầu: `laplacian + 0.02 × tenengrad`.
- Ngưỡng phải được hiệu chỉnh từ ảnh thật; không dùng ngưỡng trên Internet như hằng số.

## 5. Focus và ánh sáng

Focus peaking là công cụ commissioning, không phải thuật toán khôi phục ảnh mờ.
Nếu nhãn nằm dưới minimum focus distance của webcam, cần một trong các cách:

1. Nâng camera cao hơn và crop ROI từ ảnh 2K.
2. Gắn close-up/macro lens.
3. Thay camera có manual focus.

Dùng hai đèn tán sáng đặt chéo 45°. Exposure nên đủ ngắn để tránh rung sau khi băng tải
dừng, gain thấp và autofocus/exposure được khóa sau commissioning.

## 6. Định vị nhãn, QR và logo

MVP giả định gá đặt khiến nhãn nằm trong ROI tương đối được cấu hình. Sau khi có ảnh mẫu:

- Nếu layout cố định: giữ ROI tĩnh, nhanh và dễ kiểm chứng.
- Nếu hộp xoay: tìm contour nhãn hoặc bốn góc QR, sau đó `warpPerspective`.
- Nếu có nhiều layout: tạo một template logo/recipe cho từng layout.

QR là fiducial để chỉnh nhãn về A6 1050×1480. QR và logo có ROI riêng trên ảnh chuẩn.
Logo dùng đặc trưng SIFT, Lowe ratio test và RANSAC homography; không phụ thuộc vào việc
đọc được chữ địa chỉ.

## 7. Kiểm tra móp, méo và rách

Ảnh băng tải trống được chụp tại đúng camera/ánh sáng vận hành. Mỗi frame được so sánh
với ảnh này để lấy mask kiện; contour lớn nhất được đánh giá bằng:

- `rectangularity = diện tích contour / diện tích minAreaRect`;
- `solidity = diện tích contour / diện tích convex hull`;
- số đỉnh của contour sau `approxPolyDP`.

Rectangularity thấp phát hiện méo; solidity thấp phát hiện lõm/móp hoặc rách chạm biên;
đường bao quá nhiều đỉnh báo hình dạng bất thường. Vết rách nằm hoàn toàn bên trong bề
mặt không làm thay đổi silhouette nên cần bộ ảnh lỗi và model texture/object detection
riêng. Không dùng cạnh nhãn hoặc băng keo làm bằng chứng rách vì false positive cao.

Thiếu ảnh băng tải trống hoặc không tìm thấy contour kiện phải trả `MANUAL_REVIEW`.
Không được mặc định kiện là tốt.

## 8. Dữ liệu và an toàn quyết định

Khóa lookup mặc định là `waybill_code`. Database trả `destination_bin`. Các tên cột
được cấu hình vì schema thật chưa được chốt.

Luồng quyết định:

1. Hư hỏng hình học → `REJECT/DEFECT`.
2. Logo thiếu/sai → `REJECT`.
3. QR/mã vận đơn xác định record.
4. Record Supabase xác định rổ.
5. Detector chưa hiệu chuẩn → `MANUAL_REVIEW`, không đoán.

Mỗi inspection được lưu trong thư mục riêng với UUID, metadata JSON và các ảnh crop.
File metadata được ghi tạm rồi thay thế nguyên tử. Thư mục `captures/` bị loại khỏi Git;
ảnh QR có thể chứa mã vận đơn nên vẫn phải được bảo vệ như dữ liệu vận hành.

## 9. Tiêu chí nghiệm thu Vision trước phase ESP32

- 100 kiện thử, ít nhất 20 kiện lỗi/không thuộc database.
- Tỷ lệ đọc QR ≥ 99% trên nhãn đạt chuẩn.
- Không có false PASS trong tập nghiệm thu.
- Logo recall ≥ 99% trên nhãn đúng và không false PASS với nhãn sai/không logo.
- Bộ lỗi phải gồm móp, méo, rách mép và vết rách bề mặt; không false PASS trong tập lỗi.
- P95 từ trigger đến decision ≤ 1.5 giây với laptop mục tiêu.
- Toàn bộ trường hợp quality gate fail sinh ảnh debug và lý do.
- Chạy liên tục 500 chu kỳ không crash hoặc rò rỉ camera handle.

## 10. Thông tin còn cần đo từ hệ thống thật

- Model webcam, khoảng focus hỗ trợ và các giá trị UVC hợp lệ.
- Ảnh băng tải trống tại đúng camera và ánh sáng vận hành.
- Ảnh 2K của tối thiểu 30 kiện tốt và 30 kiện lỗi có nhãn ground truth.
- Kích thước nhãn/QR và số layout nhãn.
- Nội dung QR và quy tắc mã vận đơn.
- Schema bảng Supabase, tên cột và ví dụ record đã ẩn dữ liệu nhạy cảm.
- Encoder/cảm biến và liên động motor cần đo thêm. Chân W5500/BTS7960 và UDP của firmware nhóm được ghi tại `docs/esp32_contract.md`.
