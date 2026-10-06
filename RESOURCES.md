# Hồ sơ bàn giao phần Vision — MV-01 Parcel Inspection Cell

Cập nhật: 05/10/2026. Tài liệu này mô tả **những gì đã được lập trình và kiểm thử trong source hiện tại**, không khẳng định hệ thống đã được nghiệm thu trên băng tải thật. Người nhận nên đọc cùng [`README.md`](README.md), [`config/default.yaml`](config/default.yaml) và [`docs/esp32_contract.md`](docs/esp32_contract.md).

## 1. Mục tiêu, phạm vi và hiện trạng

Trạm dùng webcam Stafor “2K”, laptop Windows, nhãn A6 trên kiện, OpenCV và ZXing-C++ để đọc QR; nhận diện logo Shopee Xpress theo template; kiểm tra sơ bộ bề mặt và hình dạng kiện (móp, méo, rách cạnh, lỗ thủng nhìn thấy); hiển thị ảnh hiện trường, kết quả, KPI và Digital Twin. Hệ thống hiện ở **local/bench test**: Supabase tắt, camera chưa có đồ gá cuối cùng, robot và cơ cấu phân loại chưa nối điều khiển thật. Địa chỉ người gửi/nhận bằng OCR đã loại khỏi phạm vi vì chất lượng ảnh không ổn định.

Điều khiển băng tải ESP32/W5500 mới được tích hợp **thủ công** vào GUI. Không có trigger tự động từ thuật toán vision đến motor; không có phản hồi encoder/đo tốc độ. Digital Twin là mô hình 3D dựng bằng phần mềm với orbit/pan/zoom, không phải mesh CAD/GLB thực của máy; tab Assets/manifest chờ các file 3D của nhóm.

## 2. Luồng xử lý đang chạy

```text
Webcam → burst frame → focus/motion/glare gate → frame tốt nhất
                                   ├→ ZXing-C++ / OpenCV QR
                                   ├→ QR-anchor box kiện + ước lượng vùng nhãn A6
                                   ├→ hiệu chỉnh phối cảnh nhãn → SIFT logo
                                   └→ vùng kiện → nền chuẩn/hình dạng + dò điểm tối/lỗ
                          → rule-based classifier → local PASS/FAIL/REVIEW
                          → GUI live/snapshot + audit images + Digital Twin mô phỏng

Tab ESP32: thao tác viên → UDP FWD/REV/STOP/PING → ACK → trạng thái lệnh trên GUI/twin
```

Không dùng YOLO hay mô hình học sâu để phát hiện kiện: box hiện tại **phụ thuộc việc tìm được QR**, sau đó suy ra biên kiện bằng cạnh ảnh. Khi QR bị che/nhòe hoặc nhiều kiện sát nhau, việc định vị có thể không tin cậy. Các con số “confidence” của box là heuristic, **không phải xác suất đã hiệu chuẩn**.

## 3. Thu ảnh, quang học và ánh sáng

- Camera đặt 2560×1440, 30 FPS, FourCC YUY2, backend DirectShow trong [`config/default.yaml`](config/default.yaml). Đây là **cấu hình yêu cầu**; cần đọc lại độ phân giải/FPS camera thực sự cấp tại runtime. Không thể dùng xử lý ảnh để sửa hoàn toàn ảnh mất nét quang học.
- Dữ liệu thử trước đây trải 15–40 cm; cấu hình khuyến nghị mục tiêu nhãn 35–40 cm sau khi có đồ gá, nhưng `BENCH 15–30 CM` đang mặc định bật để thử trên sàn/bàn. Khoảng cách đo từ thấu kính tới **bề mặt nhãn**, không chỉ tới mặt băng tải; kiện cao làm thay đổi khoảng cách làm việc.
- Ring light 5 V nên đặt đồng trục quanh webcam, cách nhãn vừa đủ để chiếu đều và không phản chiếu trắng QR. Với nhãn bóng, lệch góc đèn/camera nhẹ hoặc thêm khuếch tán; nếu cần nhìn lỗ/rách cạnh có thể thêm nguồn sáng xiên thấp riêng để tạo bóng, nhưng phải kiểm tra ảnh QR dưới cả hai chế độ. Giữ ánh sáng/phơi sáng cố định khi chụp nền chuẩn. Chống rung camera và băng tải, tránh bóng tay. Cơ sở lựa chọn sáng đều và sáng xiên: [Cognex Lighting Guide](https://www.cognex.com/support/downloads/ns/1/11/89/1010.pdf), [Cognex lighting overview](https://www.cognex.cn/zh-cn/tools-and-resources/resource-center/machine-vision/the-importance-of-lighting).

## 4. Quality gate và focus peaking

Mỗi ảnh được đánh giá ở [`imaging/focus.py`](src/machine_vision/imaging/focus.py):

- **Variance of Laplacian**: phương sai đáp ứng đạo hàm bậc hai trên ảnh xám (sau Gaussian blur nhẹ); thấp thường biểu thị ít chi tiết sắc nét, nhưng vẫn nhạy với chữ/texture của nền.
- **Tenengrad**: trung bình `Sobel_x² + Sobel_y²`, đo năng lượng cạnh. Hai thước đo bổ trợ nhau, không cho biết webcam có thể lấy nét ở mọi khoảng cách.
- **Motion score**: trung bình sai khác tuyệt đối giữa hai frame xám đã thu về 320×180; một frame đơn lẻ không chứng minh vật đứng yên.
- **Highlight ratio**: tỷ lệ pixel xám từ 250 trở lên, dùng chặn chói sáng. Quality gate chọn frame tốt trong burst khi thỏa ngưỡng ở cấu hình, với ngưỡng bench riêng.
- **Focus peaking**: tô các cạnh Sobel vượt percentile cao bên trong box kiện/ROI nhãn. Đây chỉ là overlay thị giác để trợ giúp canh nét; không làm ảnh nét hơn, và cạnh sàn/nhãn vẫn có thể gây hiểu nhầm. Mặc định tắt.

Ngưỡng phải đo lại khi đổi đèn, độ cao, vật liệu nhãn hoặc góc camera; tránh sao chép nguyên ngưỡng bench sang băng tải thật.

Quality gate của burst hiện đo trên `label.roi` trong config và yêu cầu nhiều frame liên tiếp đạt ngưỡng. Trong các frame hợp lệ, score xếp hạng là `Laplacian + 0.02 × Tenengrad`. ROI này còn là vùng tìm kiếm rộng cố định, khác với box kiện động ở live preview; cần kiểm tra lại khi kiện lệch khỏi vùng quan sát. Phương pháp đo cạnh và giới hạn với ảnh nhiễu được trình bày tại [OpenCV focus measures](https://opencv.org/autofocus-using-opencv-a-comparative-study-of-focus-measures-for-sharpness-assessment/).

## 5. QR và định vị kiện

[`readers/qr_reader.py`](src/machine_vision/readers/qr_reader.py) thử nhiều biến thể xử lý ảnh (phóng to/đảo màu theo config), đọc bằng Python binding của ZXing-C++, rồi fallback `cv2.QRCodeDetector`. Kết quả gồm payload và 4 góc QR. [Tài liệu chính thức ZXing-C++ Python](https://github.com/zxing-cpp/zxing-cpp/blob/master/wrappers/python/README.md) mô tả API `read_barcodes`.

Các biến thể cụ thể trong [`imaging/enhancement.py`](src/machine_vision/imaging/enhancement.py): grayscale; CLAHE (tăng tương phản cục bộ và giới hạn khuếch đại nhiễu); unsharp mask `I_out = (1+a)I - a × Gaussian(I)`; upscale bằng cubic; Otsu chọn ngưỡng toàn ảnh; adaptive Gaussian threshold chọn ngưỡng theo lân cận; đảo trắng/đen. Chúng hỗ trợ decoder khi tương phản thấp, nhưng upscale chỉ nội suy pixel và không tạo lại chi tiết QR đã mất vì blur. Luôn giữ ảnh gốc để đánh giá, không dùng ảnh overlay focus peaking làm đầu vào decoder.

[`services/package_detection.py`](src/machine_vision/services/package_detection.py) dùng 4 góc QR và vị trí QR tương đối trên mẫu A6 để ước lượng hình chữ nhật nhãn. Canny tạo ảnh cạnh; phép chiếu theo cột tìm cụm cạnh dọc trái/phải nhãn, mở rộng thành box kiện, có fallback mở rộng theo tỷ lệ. Live preview dùng đường phát hiện nhanh ở ảnh thu nhỏ; inspection dùng frame tốt nhất. Nếu QR không thấy, không có target box đáng tin — phần mềm phải trả kết quả review/không xác định, **không** coi “không thấy lỗi” là kiện tốt.

[`imaging/perspective.py`](src/machine_vision/imaging/perspective.py) và pipeline chuẩn hóa nhãn A6 về khung 1050×1480 bằng biến đổi phối cảnh (homography). Mục đích là đưa QR/logo về ROI ổn định dù nhãn nghiêng. Homography chỉ phù hợp mặt nhãn gần phẳng; nhăn, cong, che khuất gây sai hình. [OpenCV homography tutorial](https://docs.opencv.org/4.x/d7/dff/tutorial_feature_homography.html).

## 6. Nhận diện logo

[`readers/logo_reader.py`](src/machine_vision/readers/logo_reader.py) nhận template logo do người vận hành cắt từ ảnh nhãn thật. Tiền xử lý xám + CLAHE để giảm chênh sáng; SIFT trích điểm đặc trưng; lọc cặp match bằng ratio test; kiểm tra số match và tỉ lệ inlier của mô hình hình học, kết hợp ngưỡng score cấu hình. Đây là **template matching theo feature**, không phải classifier huấn luyện nhiều hãng. Template mới có thể được chụp/cắt từ GUI (`ui/logo_calibration.py`); calibration JSON và template operator nằm ở thư mục runtime có thể ghi. Cần hiệu chuẩn lại khi đổi mẫu in, kích thước logo, đèn hoặc góc quan sát. [OpenCV feature matching và homography](https://docs.opencv.org/4.x/d7/dff/tutorial_feature_homography.html).

Triển khai dùng `BFMatcher.knnMatch(k=2)`, giữ match nếu `distance_1 < match_ratio × distance_2`; RANSAC loại outlier khi tìm homography. `score = số inlier / số keypoint template`; logo đạt khi cùng thỏa số match, tỉ lệ inlier và score. Score hiển thị trên GUI không phải accuracy hoặc xác suất hãng vận chuyển.

## 7. Kiểm tra móp, méo, rách, thủng

[`services/damage.py`](src/machine_vision/services/damage.py) có hai nhánh:

1. **Hình dạng/biên**: chụp ảnh nền trống cố định (`CHỤP NỀN TRỐNG` trong bench), Gaussian blur, sai khác tuyệt đối so với frame hiện tại, threshold và morphology open/close, lấy contour. Tính rectangularity = diện tích contour / diện tích minimum-area rectangle; solidity = diện tích contour / diện tích convex hull; số đỉnh polygon sau `approxPolyDP`. Ngưỡng thấp/số đỉnh cao gợi ý méo hoặc rách cạnh.
2. **Lỗ bề mặt nhìn thấy**: trong box kiện, che vùng nhãn để chữ đen/QR không bị nhầm là lỗ. Lấy ngưỡng tối tương đối với median bề mặt, morphology và lọc contour theo diện tích, aspect ratio, độ đầy. Overlay vẽ box đỏ và nhãn `THUNG LO` ở vị trí nghi vấn.

Đây là phát hiện **heuristic 2D**, không chứng minh độ sâu hay “thủng xuyên” vật liệu. Vết in đen, bóng đổ, khe nắp, tay người, thay đổi ánh sáng/nền có thể báo giả; lỗ cùng màu hoặc bị che có thể bỏ sót. Chưa có tập ảnh gán nhãn đủ lớn để công bố precision/recall hay xác nhận mọi loại kiện. Bắt buộc chạy pilot, gán nhãn ground truth và điều chỉnh ngưỡng trước khi phân loại tự động. [OpenCV image-processing tutorials](https://docs.opencv.org/4.x/d2/d96/tutorial_py_table_of_contents_imgproc.html) cung cấp nền tảng threshold/contour/morphology.

## 8. Quy tắc quyết định và dữ liệu

[`services/classifier.py`](src/machine_vision/services/classifier.py) áp dụng luật theo thứ tự: kiểm tra damage có hiệu chuẩn → lỗi damage thì REJECT/DEFECT → logo không hiệu chuẩn thì MANUAL_REVIEW, không khớp thì REJECT → QR/waybill thiếu thì REJECT → local test hợp lệ thì PASS nhưng rổ chỉ là `LOCAL_TEST`. Khi tắt local test, đường truy vấn repository Supabase có thể dùng nhưng **chưa được cấu hình/nghiệm thu trong bản này**. Không có OCR địa chỉ. Không có lệnh phần cứng tự động tới rổ; rổ trên GUI là kết quả phần mềm.

[`services/evidence.py`](src/machine_vision/services/evidence.py) lưu full frame, ảnh nhãn và ảnh debug theo config vào `captures/` để xem lại. Ảnh kiện/nhãn có thể chứa dữ liệu cá nhân: không đưa lên GitHub công khai. Phân quyền/retention phải do nhóm quyết định.

## 9. GUI và Digital Twin

- [`ui/main_window.py`](src/machine_vision/ui/main_window.py): live/snapshot hiện trường, quality metrics, QR/logo/damage, KPI, event log, cảnh báo và local-test badge. Kiểm tra manual; chưa tự kích từ cảm biến quang.
- [`ui/digital_twin.py`](src/machine_vision/ui/digital_twin.py): cảnh 3D phần mềm, camera orbit/pan/zoom/preset, lớp Equipment/Vision Zones/Telemetry, robot 6 trục điều khiển **mô phỏng** bằng slider. Chưa tích hợp robot thật và chưa tải mesh GLB thật. Manifest ở [`assets/digital_twin/scene_manifest.json`](assets/digital_twin/scene_manifest.json); quy trình thay mesh ở [`docs/3d_asset_handoff.md`](docs/3d_asset_handoff.md).
- Tab **BĂNG TẢI / ESP32**: chỉnh IP/port và PWM, PING/FWD/REV/STOP qua UDP không chặn UI. Chỉ ACK hợp lệ mới cập nhật trạng thái lệnh trên Digital Twin; camera bật không có nghĩa băng tải chạy. `PONG` xác nhận link, **không** xác nhận motor dừng/chạy. Khi timeout, trạng thái `UNKNOWN`.

## 10. ESP32, sơ đồ điện và an toàn

Firmware gốc nhóm: [`firmware/sketch_sep19a.ino`](firmware/sketch_sep19a.ino); schematic: [`hardware/esp32_conveyor_schematic.png`](hardware/esp32_conveyor_schematic.png); hợp đồng dữ liệu chi tiết: [`docs/esp32_contract.md`](docs/esp32_contract.md). ESP32 + W5500 nghe UDP `192.168.2.100:8120`, lệnh `PING`, `FWD:n`, `REV:n`, `STOP:0`, PWM 8-bit 5 kHz tới BTS7960. Schematic: W5500 SPI 23/19/18, CS5, RST4; BTS7960 RPWM25, LPWM26, R_EN27, L_EN14; nguồn 24 V motor và LM2596 5 V logic, chung GND. Chân sensor R_S34/L_S35 chưa được firmware đọc. [Arduino-ESP32 LEDC API](https://docs.espressif.com/projects/arduino-esp32/en/latest/api/ledc.html) là tham chiếu cho PWM.

**Cảnh báo:** firmware gốc không có watchdog dừng motor nếu PC/mạng chết. ACK UDP không chứng minh trục motor chuyển động; STOP GUI không phải E-stop. Chỉ thử có người giám sát, E-stop/ngắt nguồn động lực vật lý, che chắn cơ khí; chưa cho chạy không người hoặc nối auto-sort. Cần nâng firmware watchdog, interlock và xác nhận sensor trước nghiệm thu.

## 11. Cấu trúc bản bàn giao và chạy lại

Các thư mục cốt lõi: `src/` mã ứng dụng; `config/default.yaml` ngưỡng; `assets/logo/` template; `assets/digital_twin/` manifest; `firmware/` mã ESP32 gốc; `hardware/` sơ đồ; `tests/` kiểm thử; `scripts/` công cụ hiệu chuẩn/capture; `docs/` thiết kế; `README.md` cách chạy; `RESOURCES.md` hồ sơ này. Không đưa `.venv`, `build`, `exports` cũ, `captures`, `dataset/raw`, `tmp`, `work`, cache, `.env` hay khóa Supabase vào gói source.

```powershell
cd MachineVision
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m pytest -q -p no:cacheprovider --basetemp=build\pytest-temp
python -m machine_vision.app --config config\default.yaml
```

Kiểm thử hiện tại: **47 unit/integration tests passed** ngày 05/10/2026, gồm UDP giả lập trên localhost và worker GUI (PING, ACK STOP trước chạy, ưu tiên STOP khi request đang chờ, STOP khi đóng, timeout). Đã tạo screenshot giao diện offscreen. **Chưa kiểm thử với ESP32/motor thật trong phiên bàn giao này**, chưa đo FPS thực hoặc độ chính xác QR/logo/damage trên băng tải mới.

## 12. Việc cần làm tiếp

1. Gắn webcam/ring light cố định, đo lại khoảng cách lens–nhãn cho nhiều chiều cao kiện, khóa exposure/focus nếu webcam hỗ trợ; chụp nền trống lại và đánh giá chói sáng QR.
2. Thu tập dữ liệu có nhãn: bình thường, móp, méo, rách, thủng, điều kiện sáng/khoảng cách khác nhau; đo confusion matrix, precision/recall từng loại và tỉ lệ manual review.
3. Nếu QR có thể mất/che, huấn luyện hoặc tích hợp detector kiện độc lập QR trước khi inspection. Kiểm tra multi-parcel và vùng che khuất.
4. Nâng firmware/watchdog/interlock E-stop và telemetry thực; thử mất cáp/mất nguồn/treo GUI; chỉ sau đó mới thiết kế auto-start/stop và robot sorting.
5. Nhận CAD/GLB thật, xác định frame tọa độ, tỷ lệ và khớp robot rồi thay scene placeholder; tích hợp Supabase qua cấu hình bí mật khi được cấp quyền.

## 13. Tài liệu tham khảo bổ sung theo lịch sử project

- [KEYENCE — Lighting Selection Guide](https://www.keyence.com/products/vision/resources/vision-resources/basics-of-lighting-selection.jsp): bố trí sáng trực tiếp, khuếch tán, xiên và lựa chọn theo đặc điểm bề mặt.
- [Pysource — Detect when an image is blurry](https://pysource.com/2019/09/03/detect-when-an-image-is-blurry-opencv-with-python/): ví dụ ban đầu về đánh giá blur bằng Laplacian; ngưỡng ví dụ cần đo lại cho camera của nhóm.
- [GreenpantsDeveloper — Focus peaking](https://github.com/GreenpantsDeveloper/focus-peaking): ví dụ overlay cạnh khi canh nét. Overlay trong project đã được giới hạn ROI và dùng percentile thích nghi, không phải thuật toán điều khiển focus motor.

Các tài liệu giải thích nền tảng; thông số và mô tả triển khai trong hồ sơ này được đối chiếu với source hiện tại. Chúng không thay thế biên bản nghiệm thu của camera, băng tải và bộ phân loại thật.
