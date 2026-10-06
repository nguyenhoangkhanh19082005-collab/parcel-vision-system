# Hiệu chuẩn kiểm tra tình trạng kiện hàng

## Điều kiện bắt buộc

- Mặt kiện có nhãn và QR phải nhìn thấy rõ để detector chọn đúng kiện mục tiêu.
- Camera, băng tải và đèn phải được cố định trước khi chụp ảnh tham chiếu.
- Băng tải dùng nền ít hoa văn; tránh bóng đổ thay đổi theo ánh sáng môi trường.
- Mỗi lần đổi vị trí camera, exposure hoặc đèn phải chụp lại ảnh băng tải trống.

Không còn ROI vuông cố định: box kiện được suy ra từ QR trên nhãn và hai cạnh đứng gần
nhất. Nếu QR hoặc cạnh hộp bị che, detector trả `MANUAL_REVIEW`. Với kiện quá lớn,
cần tăng trường nhìn hoặc dùng thêm camera; không suy luận phần khuất khỏi một ảnh.

## Trình tự

1. Dọn sạch băng tải và bật hệ thống đèn vận hành.
2. Chạy:

   ```powershell
   .\.venv\Scripts\python.exe scripts\capture_empty_belt_reference.py
   ```

3. Xác nhận file `config/calibration/empty_belt.png` được tạo.
4. Thu ảnh kiện tại đúng vị trí dừng:
   - ít nhất 30 kiện bình thường;
   - ít nhất 10 kiện móp;
   - ít nhất 10 kiện méo;
   - ít nhất 10 kiện rách chạm mép;
   - ít nhất 10 kiện rách nằm trong bề mặt.
5. Hiệu chỉnh ngưỡng trong `config/default.yaml` trên tập train, sau đó khóa ngưỡng và
   đánh giá trên tập test khác.

## Ý nghĩa metric

| Metric | Dấu hiệu lỗi |
|---|---|
| `rectangularity` | Thấp khi kiện bị méo hoặc mất góc |
| `solidity` | Thấp khi biên kiện bị lõm, móp hoặc rách mép |
| `vertices` | Cao khi đường bao quá gồ ghề/bất thường |
| `surface_holes` | Số vùng tối, đặc và đủ diện tích trên bề mặt carton sau khi che nhãn |

Detector hiện tại che toàn bộ nhãn rồi tìm vùng tối đặc bất thường trên carton, vì vậy
có thể khoanh các lỗ thủng nhìn thấy như ảnh thử nghiệm. Nếp gấp, băng keo tối hoặc bóng
đổ mạnh vẫn có thể tạo false positive. Cần detector được huấn luyện từ ảnh thật
(object detection/segmentation hoặc anomaly detection) trước khi vận hành tự động.

## Tiêu chí nghiệm thu đề xuất

- Không false PASS trên tập kiện lỗi.
- Recall lỗi tổng ≥ 95% trước khi điều khiển cơ cấu phân loại tự động.
- Kiện không thấy đủ contour luôn `MANUAL_REVIEW`.
- P95 thời gian kiểm tra tình trạng ≤ 500 ms trên laptop mục tiêu.
