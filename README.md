# MachineVision

## Bản bàn giao hiện tại (05/10/2026)

Đọc [`RESOURCES.md`](RESOURCES.md) để nắm kiến trúc, lý thuyết/thuật toán, phần đã làm và giới hạn chưa nghiệm thu. Tab `BĂNG TẢI / ESP32` đã tích hợp điều khiển UDP thủ công dựa trên firmware gốc của nhóm; sơ đồ chân, IP, giao thức và cảnh báo an toàn ở [`docs/esp32_contract.md`](docs/esp32_contract.md). **Không** dùng STOP trên GUI thay E-stop phần cứng. Vision và băng tải hiện chưa liên động tự động; Digital Twin cho biết lệnh gần nhất được ACK, không phải telemetry motor thật.

Để tạo gói sạch cho nhóm (không xóa source/dữ liệu cũ):

```powershell
python scripts\package_handoff.py
```

Script tạo ZIP Core Source trong `exports/` và thêm ZIP Private Calibration khi dữ liệu hiệu chuẩn hiện trường còn có sẵn. Gói `MachineVision_Core_Source_2026-10-05.zip` dùng cho source GitHub riêng của nhóm; `MachineVision_Private_Calibration_2026-10-05.zip` **chỉ cho Drive riêng** (ảnh nền bench/băng tải). Core đã có logo lấy mẫu và ROI hiện tại. Giải nén cả hai đè vào cùng thư mục `MachineVision` nếu muốn tái lập hiệu chuẩn hiện tại. Không upload `captures/`, `dataset/raw/`, `.env`, khóa Supabase hay nhãn chứa địa chỉ lên GitHub công khai.

Phiên bản source là **0.2.0**, tiêu đề cửa sổ ghi `ESP32 UDP`. Các EXE 29/09/2026 là bản cũ; trong lần bàn giao này hãy chạy source hoặc build lại theo `docs/windows_exe.md` để có phần tích hợp mới.

Trạm thị giác máy dành cho băng tải phân loại kiện hàng. Phiên bản hiện tại cung cấp
khung kiến trúc và một vertical slice chạy được cho camera, quality gate, ZXing,
kiểm tra logo, tình trạng kiện hàng, phân loại và giao diện vận hành PyQt6.

## Giao diện HMI công nghiệp

Ứng dụng desktop có thanh trạng thái thiết bị, KPI theo phiên, chất lượng camera,
kết quả kiện hiện tại, alarm, event log và Digital Twin 3D tương tác của toàn trạm.
Xem [`docs/hmi_digital_twin.md`](docs/hmi_digital_twin.md) để biết state model,
kiến trúc giám sát từ xa và telemetry contract tối thiểu.

Màn Digital Twin dùng bố cục engineering workstation gồm Scene Explorer, viewport,
Inspector/Telemetry và trạng thái asset. Mô hình phần mềm hiện tại được giữ làm fallback.
Khi có file robot và băng tải thật, xem
[`docs/3d_asset_handoff.md`](docs/3d_asset_handoff.md) và khai báo chúng trong
`assets/digital_twin/scene_manifest.json` trước khi commissioning Qt Quick 3D.

## Kiến trúc chính

```text
Sensor trigger
      │
      ▼
Frame burst ──► Focus / motion / glare gate ──► Best frame
                                                    │
                                      ┌─────────────┴─────────────┐
                                      ▼                           ▼
                          QR-anchored package box      A6 perspective correction
                                      │                    ┌──────┴──────┐
                                      ▼                    ▼             ▼
                         Shape + surface-hole scan    ZXing QR      Logo SIFT
                                      └──────────────┬─────┴─────────────┘
                                                     ▼
                                            Validate + route
                                      ┌─────────────┴─────────────┐
                                      ▼                           ▼
                              LOCAL TEST (hiện tại)       Supabase (commissioning)
                                      └─────────────┬─────────────┘
                                                    ▼
                                      PASS / REJECT / MANUAL REVIEW
```

Xem thiết kế chi tiết tại [`docs/architecture.md`](docs/architecture.md).

## Chạy giao diện

Python 3.11 hoặc 3.12 được khuyến nghị.

```powershell
cd MachineVision
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
$env:PYTHONPATH = "$PWD\src"
python -m machine_vision.app --config config\default.yaml
```

Để bật Supabase:

```powershell
python -m pip install -e ".[database]"
Copy-Item .env.example .env
```

Không commit `.env`, ảnh nhãn, ảnh kiện hàng hoặc khóa Supabase.

## Test không cần Supabase

`config/default.yaml` đang bật `classification.local_test_mode: true`. Ở chế độ này,
ứng dụng vẫn kiểm tra độc lập QR, logo và tình trạng kiện, nhưng bỏ qua truy vấn vận đơn
trên Supabase. GUI luôn ghi rõ `LOCAL TEST`/`SUPABASE BYPASSED` để kết quả thử không bị
nhầm với kết quả vận hành thật.

Quy trình thử trên bàn hoặc nền nhà:

1. Kết nối camera và giữ nguyên vị trí, góc nhìn, ánh sáng.
2. Bỏ kiện ra khỏi toàn bộ khung hình, bật `BENCH 15–30 CM`, nhấn
   `CHỤP NỀN TRỐNG` và xác nhận.
3. Đặt mặt có nhãn hướng về camera và để QR nhìn thấy rõ. Box `KIỆN HÀNG` sẽ tự bám
   theo kiện mang QR; không cần ép kiện vào ROI vuông cố định. Đợi chỉ báo chất lượng
   chuyển sang `READY`, rồi nhấn `KIỂM TRA KIỆN`.
4. Xem riêng `QR PAYLOAD`, `LOGO`, `TÌNH TRẠNG KIỆN` và `KẾT QUẢ LOCAL`.
5. GUI tự chuyển sang `ẢNH KIỂM TRA` để giữ lại ảnh hiện trường tại thời điểm xử lý;
   có thể bấm `LIVE` để quay lại hình trực tiếp. Ảnh full frame và ảnh debug cũng được
   lưu trong thư mục `captures`.

Template logo hiện tại là mẫu trong `assets/logo/spx_template.png`. Nếu mẫu logo trên
nhãn thực tế khác, kết quả `KHÔNG KHỚP` là đúng theo cấu hình; hãy tạo lại template bằng
`scripts/calibrate_logo_template.py` trước khi đánh giá độ chính xác.

## Trình tự commissioning

1. Thu bộ ảnh nguyên bản từ 15 đến 40 cm:

   ```powershell
   python scripts\capture_2k_samples.py --camera 0 --backend dshow
   ```

   Nhấn `1`…`6` để chọn 15/20/25/30/35/40 cm, `SPACE` để chụp hoặc `B` để chụp
   10 ảnh. Khoảng cách phải đo từ mặt trước ống kính tới bề mặt nhãn.
2. Đặt hộp ở vị trí cảm biến sẽ dừng băng tải.
3. Chạy `scripts/calibrate_focus.py`, chỉnh khoảng cách/focus/ánh sáng.
4. Nhấn `SPACE` để lưu cả mẫu `good` và `bad`, sau đó chạy
   `python scripts/analyze_focus_samples.py focus_samples.csv`.
5. Cập nhật các ngưỡng `min_laplacian`, `min_tenengrad` và các ROI trong YAML.
6. Tạo template logo bằng `python scripts/calibrate_logo_template.py`, rồi chạy
   `python scripts/evaluate_logo_dataset.py`.
7. Dọn trống băng tải và chạy `python scripts/capture_empty_belt_reference.py` tại đúng
   vị trí camera/ánh sáng vận hành.
8. Thu tối thiểu 30 kiện bình thường và 30 kiện lỗi gồm móp, méo, rách mép để hiệu chỉnh
   `min_rectangularity`, `min_solidity` và `max_vertices`.
9. Khai báo schema Supabase rồi bật `supabase.enabled`.
10. Chỉ tích hợp ESP32 sau khi Vision đạt tiêu chí nghiệm thu trong tài liệu kiến trúc.

## Phím và thao tác UI

- **Kết nối camera**: mở hoặc đóng webcam.
- **BENCH 15–30 CM**: chế độ thử tạm khi webcam chưa có đồ gá và kiện đứng yên trên
  bàn/sàn. Cổng nét dùng ngưỡng riêng đã nới có kiểm soát; chế độ này đang bật mặc định
  trong `config/default.yaml`. Tắt chế độ trước khi vận hành trên băng tải.
- **Focus peaking**: tô vàng thích nghi chỉ trên vùng nhãn của kiện đã phát hiện;
  nền nhà, bàn tay và kiện khác không còn được tô tràn lan.
- **Chụp nền trống**: lưu bối cảnh hiện tại làm mốc cho kiểm tra đường bao, móp/méo,
  rách cạnh và lỗ thủng nhìn thấy được ở mặt đang quan sát. Phải chụp lại nếu camera,
  vị trí đặt kiện hoặc ánh sáng thay đổi.
- **Lấy mẫu logo**: mở cửa sổ hiệu chuẩn phụ, chụp nhãn thực tế bằng chính webcam,
  sau đó kéo chuột ôm sát biểu tượng và chữ logo. Hệ thống kiểm tra kích thước/số đặc
  trưng SIFT, sao lưu template cũ, tự mở rộng vùng tìm kiếm và nạp mẫu mới ngay lập
  tức. Mẫu được lưu cạnh ứng dụng trong `assets/logo`; thông số vùng tìm kiếm nằm tại
  `config/calibration/logo_calibration.json` và được dùng lại ở lần mở sau.
- **Live / Ảnh kiểm tra**: chuyển giữa luồng camera và ảnh hiện trường đã giữ lại tại
  đúng thời điểm kiểm tra.
- **Kiểm tra sản phẩm**: chọn frame tốt nhất trong burst hiện tại rồi chạy pipeline.

Kiện lỗi hình học được định tuyến vào `DEFECT`. Nếu thiếu template logo hoặc ảnh tham
chiếu băng tải trống, hệ thống trả `MANUAL_REVIEW` thay vì tự kết luận kiện đạt.

Detector tức thời hiện dùng QR làm neo và hình học cạnh hộp, không phải mô hình AI đã
huấn luyện. Nó chọn đúng kiện có QR khi nhiều vật cùng xuất hiện, che vùng nhãn trước
khi tìm điểm tối bất thường và khoanh `THỦNG LỖ`. Để phát hiện ổn định mọi loại móp,
rách và thủng trên nhiều kiểu thùng/ánh sáng, bước sản xuất tiếp theo vẫn là thu ảnh,
gán nhãn và huấn luyện detector/segmentation riêng.

Ở giai đoạn tích hợp, nút kiểm tra sẽ được thay/được gọi bởi tín hiệu sensor từ ESP32.
