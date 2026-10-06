# Parcel Vision System

Hệ thống thị giác máy phục vụ kiểm tra kiện hàng trên băng tải, kết hợp đọc QR, nhận diện logo, kiểm tra dấu hiệu hư hỏng, giao diện vận hành PyQt6 và Digital Twin 3D. ESP32/W5500 được tích hợp để điều khiển băng tải thủ công qua Ethernet UDP.

| Thông tin | Giá trị |
|---|---|
| Phiên bản mã nguồn | `0.2.0` |
| Cập nhật tài liệu | 06/10/2026 |
| Môi trường triển khai hiện tại | Windows, Python, webcam USB |
| Chế độ mặc định | Kiểm tra cục bộ, thử nghiệm bench; chưa cần Supabase |
| Trạng thái dự án | Prototype phục vụ thử nghiệm và đánh giá kỹ thuật |

**Bắt đầu tại [Cài đặt và chạy](#3-cài-đặt-và-chạy).** Nếu đã mở được GUI, chuyển tới [Thử nghiệm Vision](#4-thử-nghiệm-vision) hoặc [Điều khiển băng tải](#5-điều-khiển-băng-tải-esp32).

## 1. Chức năng và phạm vi

| Thành phần | Chức năng hiện có | Phạm vi hiện tại |
|---|---|---|
| Thu ảnh | Kết nối webcam, xem live, lấy chuỗi frame để kiểm tra | Độ phân giải/FPS thực phụ thuộc camera và driver |
| Chất lượng ảnh | Đánh giá độ nét, chuyển động, vùng chói; chọn frame phù hợp | Ngưỡng cần hiệu chuẩn theo setup |
| QR | ZXing-C++ với OpenCV fallback; lấy payload và mã vận đơn | QR phải nhìn thấy và có đủ chi tiết |
| Định vị kiện | QR làm neo, ước lượng nhãn A6 và cạnh hộp, vẽ box kiện | Phương pháp hình học; chưa có detector AI độc lập QR |
| Logo | SIFT, matching và RANSAC; lấy template trực tiếp từ GUI | Đối chiếu với mẫu logo đã hiệu chuẩn |
| Hư hỏng | Kiểm tra đường bao, biến dạng và điểm tối nghi lỗ thủng | Heuristic 2D trên mặt đang quan sát |
| HMI | Live/snapshot, kết quả, KPI, event log và trạng thái thiết bị | Kiểm tra do thao tác viên kích hoạt |
| Digital Twin | Orbit/pan/zoom, lớp hiển thị, robot 6 trục mô phỏng | Cảnh dựng bằng phần mềm; chờ mô hình 3D thật |
| Băng tải | PING, chạy tiến/lùi, PWM và STOP qua ESP32/W5500 | Điều khiển thủ công; chưa có encoder hoặc liên động phân loại |
| Dữ liệu | Lưu ảnh và kết quả cục bộ; có adapter Supabase | Supabase mặc định tắt, chưa nghiệm thu |

OCR địa chỉ người gửi/người nhận đã được loại khỏi phạm vi. Kết quả Vision hiện chưa tự phát lệnh điều khiển motor hoặc robot.

## 2. Luồng xử lý

```text
Webcam → Chuỗi frame → Cổng chất lượng ảnh → Frame được chọn
                                              │
                           ┌──────────────────┼──────────────────┐
                           ▼                  ▼                  ▼
                      Đọc QR          Chuẩn hóa nhãn A6    Định vị vùng kiện
                           │                  │                  │
                      Mã vận đơn         So khớp logo      Kiểm tra hư hỏng
                           └──────────────────┼──────────────────┘
                                              ▼
                                  PASS / REJECT / MANUAL_REVIEW
                                              ▼
                                   GUI + ảnh kiểm tra + nhật ký

Thao tác viên → Tab ESP32 → Lệnh UDP → ACK → Trạng thái lệnh trên GUI/Digital Twin
```

Cổng chất lượng ảnh là bước kiểm tra độ nét/chuyển động/chói trước khi phân tích. Một frame đạt `READY` vẫn có thể có QR không đọc được, logo không khớp hoặc kiện lỗi.

## 3. Cài đặt và chạy

### 3.1. Yêu cầu

- Windows 10/11; môi trường thử hiện tại của dự án là Windows.
- Python **3.11 hoặc 3.12** được khuyến nghị. Máy đích cần có Python trước khi cài source.
- Webcam USB để thử Vision. Có thể mở GUI và Digital Twin khi chưa kết nối webcam.
- Internet cho lần cài thư viện đầu tiên. Kiểm tra cục bộ sau đó không cần Supabase.
- ESP32, W5500 và băng tải chỉ cần khi thử điều khiển phần cứng.

### 3.2. Lấy source và mở PowerShell

Trên GitHub, chọn **Code → Download ZIP**, rồi giải nén. Nếu dùng gói bàn giao Core Source, giải nén gói đó.

Mở thư mục chứa `README.md`, `pyproject.toml` và `src/`. Nhấp vào thanh địa chỉ File Explorer, nhập `powershell`, rồi nhấn Enter. Đây là thư mục gốc của dự án; tên thư mục có thể là `parcel-vision-system-main` hoặc `MachineVision`.

Kiểm tra:

```powershell
python --version
Get-Item .\pyproject.toml
```

Nếu không tìm thấy `pyproject.toml`, hãy mở tiếp thư mục bên trong gói đã giải nén. Nếu chưa nhận lệnh `python`, cài Python và bật tùy chọn thêm Python vào PATH, rồi mở lại PowerShell.

### 3.3. Tạo môi trường riêng và cài thư viện

Chạy lần lượt:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e .
```

`.venv` chứa các thư viện riêng của dự án. Các lệnh dưới đây gọi trực tiếp Python trong môi trường này, nên không cần chạy `Activate.ps1` hoặc thay đổi chính sách PowerShell.

### 3.4. Khởi động GUI

```powershell
.\.venv\Scripts\python.exe -m machine_vision.app --config .\config\default.yaml
```

Ở những lần sử dụng sau, chỉ cần mở PowerShell tại thư mục dự án và chạy lại lệnh này.

Khi khởi động đúng, tiêu đề cửa sổ hiển thị **Machine Vision v0.2.0 · ESP32 UDP**, với ba tab:

| Tab | Mục đích |
|---|---|
| `VẬN HÀNH` | Xem camera, hiệu chuẩn và kiểm tra kiện |
| `DIGITAL TWIN 3D` | Quan sát mô hình trạm và mô phỏng khớp robot |
| `BĂNG TẢI / ESP32` | Kiểm tra kết nối và gửi lệnh motor thủ công |

Camera chưa kết nối và controller chưa cấu hình là trạng thái bình thường lúc mở ứng dụng. Gói Core không chứa ảnh nền thực tế; cảnh báo `Commissioning required` về ảnh nền chưa có có thể được đóng để tiếp tục hiệu chuẩn.

## 4. Thử nghiệm Vision

### 4.1. Chuẩn bị camera và kiện

1. Đặt webcam cố định; mặt có nhãn A6 hướng về camera.
2. Bật ánh sáng ổn định, tránh vùng trắng chói trên QR/logo.
3. Trong tab `VẬN HÀNH`, nhấn **KẾT NỐI CAMERA**.
4. Giữ chế độ **BENCH 15–30 CM** khi thử kiện đứng yên trên bàn/sàn. Khoảng cách ghi trên chế độ là bối cảnh thử tạm, không bảo đảm webcam lấy nét ở mọi vị trí.
5. Điều chỉnh khoảng cách thực tế tới bề mặt nhãn để QR và logo rõ. Giữ kiện đứng yên và đưa tay ra khỏi khung ảnh trước khi kiểm tra.

Camera mặc định được yêu cầu cấp ảnh 2560×1440, 30 FPS qua DirectShow. Nếu camera không đáp ứng, cần kiểm tra cấu hình và độ phân giải thực do driver cung cấp.

### 4.2. Chụp nền trống

1. Lấy tất cả kiện ra khỏi khung camera.
2. Giữ nguyên camera, nền và ánh sáng.
3. Nhấn **CHỤP NỀN TRỐNG** rồi xác nhận.
4. Kiểm tra chỉ báo `NỀN DAMAGE` chuyển sang `SẴN SÀNG`.

Ảnh nền giúp kiểm tra hình dạng kiện bằng cách so sánh với bối cảnh trống. Chụp lại nếu thay đổi vị trí camera, nền hoặc ánh sáng.

### 4.3. Hiệu chuẩn logo khi mẫu thực tế khác

1. Đặt kiện có logo cần nhận diện vào khung hình.
2. Nhấn **LẤY MẪU LOGO**.
3. Trong cửa sổ hiệu chuẩn, nhấn **CHỤP ẢNH NHÃN**.
4. Kéo chuột chọn sát biểu tượng và chữ logo; tránh lấy QR, mã vận đơn hoặc vùng nền quá lớn.
5. Nhấn **LƯU TEMPLATE**. Nếu mẫu bị từ chối, kiểm tra độ nét, kích thước và chi tiết của vùng chọn rồi chụp lại.

Template được lưu tại `assets/logo/spx_template.png`; vùng tìm kiếm được lưu tại `config/calibration/logo_calibration.json`. Mẫu mới được nạp vào detector và dùng lại ở lần mở sau.

### 4.4. Kiểm tra một kiện

1. Đặt kiện vào vùng quan sát, để QR và mặt cần kiểm tra nhìn thấy.
2. Đợi vật đứng yên và chỉ báo chất lượng đạt `READY`.
3. Nhấn **KIỂM TRA KIỆN**.
4. Xem riêng các trường **QR PAYLOAD**, **MÃ VẬN ĐƠN**, **LOGO**, **TÌNH TRẠNG KIỆN** và lý do quyết định.
5. GUI chuyển sang **ẢNH KIỂM TRA** để giữ ảnh đã xử lý. Nhấn **LIVE** để trở lại camera.

Box kiện dựa vào QR và cạnh ảnh. Bộ chọn frame vẫn dùng vùng `label.roi` trong cấu hình; nếu kiện lệch nhiều khỏi vùng này, cần điều chỉnh ROI hoặc setup camera.

### 4.5. Đọc kết quả

| Hiển thị trong chế độ local | Ý nghĩa |
|---|---|
| `LOCAL PASS` | Các điều kiện QR, logo và damage theo cấu hình đã đạt; đã bỏ qua tra cứu database |
| `LOCAL FAIL` | Có điều kiện kiểm tra không đạt hoặc phát hiện dấu hiệu hư hỏng |
| `LOCAL REVIEW` | Chưa đủ dữ liệu/hiệu chuẩn để kết luận; cần người kiểm tra |
| `QUALITY HOLD` | Chưa có frame đạt cổng chất lượng; chưa hoàn tất inspection |

`SCAN SUCCESS` là tỷ lệ inspection đọc được QR trong phiên, không phải tỷ lệ kiện đạt. Kết quả local chưa xác nhận vận đơn tồn tại trên Supabase và chưa kích hoạt cơ cấu phân loại.

Nên thử ít nhất một kiện bình thường, một mẫu logo sai/không khớp và một kiện có lỗi nhìn thấy; đối chiếu ảnh kiểm tra với kết quả thực tế.

## 5. Điều khiển băng tải ESP32

### 5.1. Kết nối mạng

Firmware và sơ đồ của nhóm nằm tại:

- [Firmware ESP32](firmware/sketch_sep19a.ino).
- [Schematic](hardware/esp32_conveyor_schematic.png).
- [Giao thức, chân kết nối và giới hạn phần cứng](docs/esp32_contract.md).

Firmware gốc dùng Arduino-ESP32 core 3.x và thư viện Ethernet. Cấu hình mạng mặc định:

| Thiết bị/tham số | Giá trị |
|---|---|
| ESP32/W5500 | `192.168.2.100` |
| Laptop, ví dụ cấu hình cùng subnet | `192.168.2.10` |
| Subnet mask | `255.255.255.0` |
| UDP port | `8120` |
| PWM | 1–255 trên GUI; giá trị đặt, chưa phải tốc độ đo |

Kết nối laptop với W5500 qua Ethernet và cấu hình IPv4 của card Ethernet cùng subnet. Với mạng LAN đã có thiết bị khác, chọn địa chỉ chưa bị sử dụng và giữ đồng nhất với firmware.

### 5.2. Trình tự thử

1. Mở tab **BĂNG TẢI / ESP32**; nhập IP và port đúng với firmware.
2. Nhấn **PING**. `PONG` xác nhận ESP32 trả lời qua UDP.
3. Nhấn **DỪNG** và đợi ACK STOP. GUI cần xác nhận này trước khi cho chạy.
4. Chọn PWM phù hợp với motor, tải và điều kiện thử; nhấn **CHẠY TIẾN** hoặc **CHẠY LÙI**.
5. Để thay đổi PWM, đổi slider rồi nhấn lại nút chạy cùng chiều. Slider không tự gửi lệnh.
6. Để đảo chiều, nhấn **DỪNG**, đợi ACK và quan sát motor đã dừng, rồi mới chạy chiều còn lại.
7. Kết thúc thử bằng **DỪNG**, kiểm tra motor tại chỗ.

GUI cập nhật trạng thái lệnh sau ACK hợp lệ. Khi timeout, trạng thái là `UNKNOWN`; khi đóng ứng dụng đã gửi lệnh chạy, GUI thử gửi STOP.

**Giới hạn cần biết trước khi thử motor:** firmware gốc chưa có watchdog tự dừng khi mất mạng/GUI treo. STOP qua UDP không thay thế E-stop hoặc công tắc ngắt nguồn motor. Cần giám sát trực tiếp và có phương tiện ngắt nguồn động lực khi thử. PONG/ACK chưa chứng minh tốc độ cơ học thực.

## 6. Digital Twin

Trong tab **DIGITAL TWIN 3D**:

- Kéo chuột trái để xoay góc nhìn; kéo chuột phải để pan.
- Dùng con lăn để zoom; double-click để reset.
- Chọn preset `ISOMETRIC`, `TOP`, `FRONT` hoặc `ROBOT`.
- Bật/tắt các lớp trong Scene Explorer.
- Dùng slider J1–J6 để thay góc khớp robot **mô phỏng**.

Băng tải trên Twin hiển thị lệnh gần nhất được ESP32 xác nhận. Chuyển động robot chưa nối phần cứng. Khi nhóm có mô hình GLB/CAD thực, làm theo [3D asset handoff](docs/3d_asset_handoff.md); manifest hiện tại chưa tự thay cảnh phần mềm bằng mesh thật.

## 7. Cấu hình và dữ liệu

Cấu hình chính nằm tại [config/default.yaml](config/default.yaml). Các nhóm thường cần điều chỉnh:

| Nhóm cấu hình | Mục đích |
|---|---|
| `camera` | Camera index, backend, kích thước ảnh, FPS và thuộc tính camera |
| `acquisition` | Ngưỡng nét/chuyển động/chói và profile bench |
| `label`, `package_detection` | ROI nhãn, phối cảnh và định vị kiện |
| `logo` | Template và ngưỡng matching |
| `damage` | Ảnh nền và ngưỡng dấu hiệu hư hỏng |
| `classification` | Điều kiện quyết định và local test |
| `controller` | IP ESP32, UDP port, PWM mặc định |
| `audit` | Lưu ảnh và kết quả |
| `supabase` | Adapter database tùy chọn, hiện tắt |

Mặc định `classification.local_test_mode: true` và `supabase.enabled: false`. Khi tích hợp database, cần cài extra `database`, cấu hình biến môi trường và xác nhận schema/quyền truy cập trước khi chuyển chế độ.

Mỗi inspection hoàn tất được lưu trong `captures/<ngày>/<inspection-id>/`, gồm `result.json`, ảnh hiện trường, ảnh nhãn và ảnh debug theo cấu hình. Metadata dùng thời gian UTC; thời gian trên GUI theo đồng hồ máy vận hành.

**Gói Private Calibration** chứa ảnh nền và bản hiệu chuẩn hiện trường; tên “private” chỉ nhắc chia sẻ nội bộ, không biểu thị ZIP có mật khẩu. Giải nén vào cùng thư mục dự án để tái lập setup cũ. Khi camera/đèn thay đổi, chụp nền mới phù hợp với setup hiện tại.

Không commit `.env`, khóa truy cập hoặc ảnh nhãn có thông tin cá nhân. `.env.example` chỉ chứa giá trị mẫu. `.gitignore` loại môi trường Python, cache, dữ liệu ảnh và build khỏi luồng Git thông thường.

## 8. Xử lý sự cố

| Triệu chứng | Cách kiểm tra |
|---|---|
| `No module named machine_vision` | Mở đúng thư mục chứa `pyproject.toml`, chạy lại lệnh cài `-e .` bằng Python trong `.venv` |
| Không mở được webcam | Đóng ứng dụng khác đang dùng camera; kiểm tra quyền camera Windows và `camera.index`; thử backend `msmf` nếu `dshow` không phù hợp |
| `Commissioning required` hoặc thiếu ảnh nền | Kiểm tra đường dẫn thông báo; chụp nền trống cho profile đang dùng |
| `QUALITY HOLD` | Giữ kiện đứng yên, bỏ tay khỏi ảnh, cải thiện nét/ánh sáng, giảm chói; hiệu chuẩn ngưỡng thay vì chỉ hạ ngưỡng để cho qua |
| QR không đọc được | Kiểm tra nét, kích thước QR trong ảnh, góc nghiêng, che khuất và phản chiếu |
| Logo `KHÔNG KHỚP` | Tạo template đúng logo hiện tại; kiểm tra vùng chọn và ảnh nhãn sau phối cảnh |
| Damage `KHÔNG TÌM THẤY KIỆN` hoặc review | Kiểm tra QR/box mục tiêu và ảnh nền; đảm bảo vùng cần đánh giá nhìn thấy rõ |
| ESP32 `timed out` hoặc controller `FAULT` | Kiểm tra nguồn/W5500, cáp Ethernet, IP/subnet/port, log Serial và firewall cho ứng dụng/UDP phù hợp |
| Nhấn chạy bị khóa sau PING | Nhấn DỪNG và đợi ACK STOP; PONG chưa cung cấp trạng thái motor |
| GUI không có tab ESP32 mới | Kiểm tra đang chạy source 0.2.0; các EXE ngày 29/09/2026 chưa chứa phần tích hợp này |

Nếu lỗi chưa rõ, ghi lại bước tái hiện, thông báo lỗi, cấu hình camera và ảnh kiểm tra tương ứng để nhóm đối chiếu.

## 9. Kiểm thử và phát triển

Cài thư viện kiểm thử rồi chạy:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp=build\pytest-temp
```

Mốc kiểm tra ngày **05/10/2026**: **47 tests passed**, gồm thuật toán xử lý ảnh, quy tắc phân loại và giao tiếp UDP/worker GUI với ESP32 giả lập. Kết quả này không thay thế kiểm thử camera, motor hoặc độ chính xác trên băng tải thật.

Để build EXE từ source hiện tại:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[build]"
.\.venv\Scripts\python.exe scripts\build_windows_exe.py
```

File build nằm tại `build/windows/dist/MachineVision.exe`. Xem [hướng dẫn Windows EXE](docs/windows_exe.md) để triển khai. Gói Core Source hiện không kèm EXE cập nhật.

## 10. Cấu trúc repository

```text
parcel-vision-system/
├── src/machine_vision/   # Vision pipeline, camera, GUI, Twin, controller UDP
├── config/              # Cấu hình và tham số hiệu chuẩn
├── assets/              # Logo template và Digital Twin manifest
├── firmware/            # Firmware ESP32 của nhóm
├── hardware/            # Sơ đồ kết nối
├── tests/               # Kiểm thử tự động
├── scripts/             # Capture, hiệu chuẩn, đánh giá và build
├── docs/                # Tài liệu thiết kế/tích hợp
├── README.md            # Hướng dẫn bắt đầu và vận hành thử
├── RESOURCES.md         # Lý thuyết, thuật toán và hồ sơ công việc
└── pyproject.toml       # Dependencies và cấu hình package
```

`.venv/`, `captures/`, `build/` và `exports/` có thể được tạo khi cài đặt/chạy; chúng không thuộc source cần upload.

## 11. Tài liệu kỹ thuật

| Tài liệu | Nội dung |
|---|---|
| [RESOURCES.md](RESOURCES.md) | Các phương pháp, thuật toán, tài liệu tham khảo và hiện trạng công việc |
| [Kiến trúc hệ thống](docs/architecture.md) | Thành phần và luồng dữ liệu |
| [Giao thức ESP32](docs/esp32_contract.md) | UDP, ACK, chân kết nối và các giới hạn phần cứng |
| [Hiệu chuẩn damage](docs/damage_commissioning.md) | Chuẩn bị ảnh nền và đánh giá kiện lỗi |
| [HMI và Digital Twin](docs/hmi_digital_twin.md) | Thiết kế giao diện và mô hình trạng thái |
| [Bàn giao mô hình 3D](docs/3d_asset_handoff.md) | Quy cách asset và hướng tích hợp mô hình thật |

## 12. Điều kiện trước khi triển khai trên hệ thống thật

Độ tin cậy hiện còn phụ thuộc QR nhìn thấy, hình dạng hộp, nền và ánh sáng. Vết in đen hoặc bóng đổ có thể giống lỗ thủng; lỗi trên mặt khuất có thể không được phát hiện. Chưa có số liệu nghiệm thu đủ để công bố accuracy/precision/recall cho toàn bộ hệ thống.

Các bước tiếp theo gồm cố định camera và đèn, đánh giá trên tập ảnh gán nhãn, hiệu chuẩn các ngưỡng, bổ sung watchdog/liên động motor, tích hợp tín hiệu sensor và robot, rồi xác minh mô hình 3D và database. Các yêu cầu này cần được kiểm thử trước khi chuyển từ kiểm tra thủ công sang phân loại tự động.
