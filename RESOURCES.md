# Engineering Resources — Parcel Vision System

Hồ sơ tài nguyên và cơ sở kỹ thuật của trạm kiểm tra kiện hàng **MV-01**. Tài liệu giải thích hệ thống sử dụng những tài nguyên nào, vì sao sử dụng, cách chúng liên kết với mã nguồn và cách đánh giá kết quả.

| Thông tin quản lý tài liệu | Giá trị |
|---|---|
| Phiên bản source được đối chiếu | `0.2.0` |
| Ngày cập nhật | 06/10/2026 |
| Người đọc mục tiêu | Thành viên mới, người phát triển Vision và người kiểm tra tích hợp |
| Trạng thái hệ thống | Thử nghiệm cục bộ/bench, điều khiển băng tải thủ công |
| Nguồn mô tả triển khai | Source, cấu hình, firmware và schematic trong repository |

[README.md](README.md) hướng dẫn **cài đặt và chạy**. Hồ sơ này giải thích **tài nguyên, nguyên lý và cách kiểm chứng**. Thông số trong [config/default.yaml](config/default.yaml) và mã nguồn là căn cứ khi tài liệu cần được đối chiếu.

## 1. Lộ trình đọc cho người mới

1. Đọc mục 2–4 để hiểu thuật ngữ, phần cứng và thư viện.
2. Đọc mục 5–8 để theo dõi quá trình từ ảnh camera tới QR, logo và dấu hiệu hư hỏng.
3. Đọc mục 9–10 để hiểu quyết định, GUI, Digital Twin và điều khiển ESP32.
4. Đọc mục 11–13 để tìm dữ liệu, công cụ và cách đánh giá.
5. Dùng danh mục tài liệu ở mục 14 khi muốn học sâu một phương pháp.

Có thể mở GUI và Digital Twin trước khi có phần cứng đầy đủ. Không cần Supabase để thử quy trình local.

### Thuật ngữ sử dụng

| Thuật ngữ | Giải thích trong dự án |
|---|---|
| Frame | Một ảnh lấy từ luồng webcam |
| Burst | Một chuỗi frame dùng để chọn ảnh phù hợp |
| ROI — Region of Interest | Vùng ảnh cần xử lý; giúp tập trung vào nhãn hoặc kiện |
| Bounding box | Hình chữ nhật bao vùng mục tiêu trên ảnh |
| Template | Ảnh logo mẫu để đối chiếu |
| Feature/keypoint | Đặc điểm cục bộ, ví dụ góc hoặc vùng có biến đổi độ sáng rõ |
| Descriptor | Dãy số mô tả một feature để so sánh giữa hai ảnh |
| Inlier | Cặp feature phù hợp với mô hình biến đổi hình học |
| Heuristic | Quy tắc dựa trên đặc điểm ảnh và ngưỡng; cần đánh giá thực nghiệm |
| Calibration — Hiệu chuẩn | Lấy mẫu hoặc điều chỉnh tham số cho setup thực tế |
| Ground truth | Nhãn đúng do người kiểm tra xác nhận, dùng để đánh giá thuật toán |
| Telemetry | Dữ liệu trạng thái/đo lường gửi từ thiết bị |
| ACK | Phản hồi xác nhận lệnh; ý nghĩa cụ thể phụ thuộc firmware |

## 2. Phạm vi và bản đồ tài nguyên

Dự án kiểm tra QR, logo và dấu hiệu lỗi ở mặt kiện đang quan sát; lưu bằng chứng; hiển thị GUI và mô hình trạm; gửi lệnh băng tải thủ công. OCR địa chỉ gửi/nhận đã được loại khỏi phạm vi.

```text
PHẦN CỨNG           XỬ LÝ ẢNH                          KẾT QUẢ
Webcam + đèn → Burst → Cổng nét/chuyển động/chói → Frame được chọn
                                                    ├→ QR + mã vận đơn
                                                    ├→ Nhãn A6 + logo
                                                    └→ Box kiện + damage
                                                  → Quy tắc quyết định
                                                  → GUI + ảnh/JSON + Twin

Thao tác viên → GUI ESP32 → UDP → ESP32/W5500 → BTS7960 → Motor
                            ← PONG / ACK ←───────────────┘
```

Hai luồng hiện độc lập: kiểm tra Vision không tự gửi lệnh motor. Robot trên Twin đang mô phỏng, và manifest 3D đang chờ file mô hình thật.

## 3. Tài nguyên phần cứng

### 3.1. Danh mục và vai trò

| Tài nguyên | Vai trò | Điều kiện cần kiểm tra |
|---|---|---|
| Laptop Windows | Chạy xử lý ảnh, GUI và client UDP | Python, driver camera, Ethernet và thời gian xử lý |
| Webcam Stafor được người dùng mô tả là “2K” | Thu ảnh kiện và nhãn | Độ phân giải thực, khoảng lấy nét và thuộc tính camera có thể chỉnh |
| Ring light 5 V | Bổ sung sáng cho nhãn/bề mặt kiện | Độ đều sáng, phản chiếu và nguồn đúng với đèn thực tế |
| Nhãn A6 | Bề mặt mang QR/logo, cơ sở bố trí vùng xử lý | Layout nhãn, vị trí QR và độ phẳng |
| ESP32 DevKit | Nhận lệnh và tạo PWM điều khiển motor | Firmware, chân GPIO, nguồn và trạng thái sau reset |
| W5500 | Giao tiếp Ethernet cho ESP32 | SPI, IP/subnet, cáp và UDP port |
| BTS7960 | Driver công suất điều khiển motor | Kết nối điều khiển và thông số motor/driver thực |
| LM2596 | Hạ nguồn theo schematic của nhóm | Điện áp đầu ra và khả năng cấp dòng của module thực |
| Băng tải/motor | Cơ cấu vận chuyển kiện | Chiều chạy, tải, phản hồi và dừng vật lý |

Repository chưa cung cấp datasheet/model chi tiết đủ để xác nhận toàn bộ thông số webcam, ring light hoặc cụm motor. Các giá trị nguồn/chân kết nối dưới đây được đối chiếu với schematic và firmware của nhóm; khi thay module phải kiểm tra tài liệu của module đó.

### 3.2. Camera và khoảng cách làm việc

Cấu hình mặc định yêu cầu **2560×1440, 30 FPS, YUY2, DirectShow**. Giá trị yêu cầu khác với giá trị driver thực sự cung cấp. [OpenCVCamera](src/machine_vision/camera/opencv_camera.py) có phương thức `negotiated_properties()`; công cụ hiệu chuẩn focus in thông số này để kiểm tra.

Ảnh thử trước đây được chụp ở 15, 20, 25, 30, 35 và 40 cm. Cấu hình installation ghi khoảng cách mục tiêu lens–nhãn 35–40 cm; đây là điểm xuất phát cần kiểm tra lại với kiện/đèn/đồ gá cuối cùng.

Đo khoảng cách từ lens tới **bề mặt nhãn**. Với camera nhìn từ trên xuống, nếu lens cao `H` so với mặt băng tải và kiện cao `h`, khoảng cách tới nhãn xấp xỉ `H - h`. Ví dụ `H = 40 cm`, `h = 12 cm` thì lens–nhãn còn khoảng 28 cm. Cùng một đồ gá có thể tạo điều kiện nét khác nhau cho các kiện cao thấp khác nhau.

### 3.3. Ánh sáng

| Bố trí | Mục đích | Cách đánh giá trong dự án |
|---|---|---|
| Ring light gần trục camera | Chiếu sáng mặt nhãn | QR/logo rõ và vùng nhãn được chiếu đều |
| Khuếch tán hoặc thay góc đèn | Giảm phản chiếu trên nhãn bóng | Vùng trắng chói không che chi tiết QR |
| Sáng xiên thấp, nếu bổ sung | Làm nổi cạnh/biến đổi bề mặt qua bóng và tương phản | Thử với lỗi thật và mẫu tốt để tránh báo giả |

Đây là phương án thử dựa trên nguyên tắc chiếu sáng machine vision, chưa phải setup đã nghiệm thu. Nguồn tham khảo: [KEYENCE lighting selection](https://www.keyence.com/products/vision/resources/vision-resources/basics-of-lighting-selection.jsp) và [Cognex Lighting Guide](https://www.cognex.com/support/downloads/ns/1/11/89/1010.pdf).

Giữ camera, ánh sáng và nền cố định khi dùng ảnh nền chuẩn. Khi thay setup, chụp nền lại và kiểm tra ngưỡng chất lượng ảnh.

## 4. Tài nguyên phần mềm

### 4.1. Dependencies

Các phiên bản dưới đây là **mức tối thiểu khai báo trong [pyproject.toml](pyproject.toml)**, không phải toàn bộ phiên bản thư viện đã được khóa cho một bản release.

| Tài nguyên | Khai báo | Vai trò |
|---|---|---|
| Python | `>=3.11`; khuyến nghị 3.11/3.12 trong README | Ngôn ngữ và môi trường chạy |
| NumPy | `>=2.0` | Lưu ảnh dưới dạng mảng, tính toán và thao tác mask |
| OpenCV — `opencv-python` | `>=4.10` | Camera, tiền xử lý, hình học, feature và contour |
| ZXing-C++ — `zxing-cpp` | `>=2.2` | Đọc payload và tọa độ QR |
| PyQt6 | `>=6.7` | GUI, sự kiện, timer, worker và cảnh 3D phần mềm |
| PyYAML | `>=6.0` | Đọc cấu hình YAML |
| `supabase`, `python-dotenv` | Extra `database` | Adapter database và đọc biến môi trường, tùy chọn |
| `pytest`, `ruff` | Extra `dev` | Kiểm thử và kiểm tra style/code, tùy chọn |
| PyInstaller | Extra `build` | Đóng gói EXE Windows, tùy chọn |

Thư viện chuẩn Python như `socket`, `json`, `pathlib`, `dataclasses` và `datetime` được dùng cho UDP, dữ liệu, đường dẫn và metadata; không phải cài riêng bằng pip.

Dự án hiện không đóng gói model YOLO, trọng số deep learning hoặc OCR engine. Detector QR-anchor và damage đang dựa vào xử lý ảnh/quy tắc.

### 4.2. Quan hệ giữa thư viện và source

| Nhóm chức năng | File triển khai chính |
|---|---|
| Khởi tạo ứng dụng/cấu hình | [app.py](src/machine_vision/app.py), [config.py](src/machine_vision/config.py) |
| Thu ảnh | [opencv_camera.py](src/machine_vision/camera/opencv_camera.py) |
| Điều phối Vision | [pipeline.py](src/machine_vision/services/pipeline.py) |
| Tiền xử lý và chất lượng ảnh | [enhancement.py](src/machine_vision/imaging/enhancement.py), [focus.py](src/machine_vision/imaging/focus.py) |
| QR và mã vận đơn | [qr_reader.py](src/machine_vision/readers/qr_reader.py), [label_parser.py](src/machine_vision/services/label_parser.py) |
| Nhãn/box kiện | [perspective.py](src/machine_vision/imaging/perspective.py), [package_detection.py](src/machine_vision/services/package_detection.py) |
| Logo | [logo_reader.py](src/machine_vision/readers/logo_reader.py) |
| Hư hỏng và quyết định | [damage.py](src/machine_vision/services/damage.py), [classifier.py](src/machine_vision/services/classifier.py) |
| Bằng chứng và database | [evidence.py](src/machine_vision/services/evidence.py), [shipments.py](src/machine_vision/repositories/shipments.py) |
| GUI và hiệu chuẩn logo | [main_window.py](src/machine_vision/ui/main_window.py), [logo_calibration.py](src/machine_vision/ui/logo_calibration.py) |
| Digital Twin | [digital_twin.py](src/machine_vision/ui/digital_twin.py), [asset_manifest.py](src/machine_vision/ui/asset_manifest.py) |
| Điều khiển UDP/worker GUI | [conveyor_udp.py](src/machine_vision/controllers/conveyor_udp.py), [conveyor_panel.py](src/machine_vision/ui/conveyor_panel.py) |

## 5. Chất lượng ảnh và tiền xử lý

### 5.1. Cổng chất lượng ảnh

Trước inspection, hệ thống kiểm tra chuỗi frame trên `label.roi`. Một ảnh đơn lẻ không đủ để xác nhận vật đang đứng yên.

| Chỉ số | Cách hiểu | Tính toán hiện tại |
|---|---|---|
| Laplacian variance | Mức biến đổi chi tiết qua đạo hàm bậc hai | Phương sai Laplacian trên ảnh xám đã Gaussian blur nhẹ |
| Tenengrad | Năng lượng cạnh theo hai hướng | Trung bình `Sobel_x² + Sobel_y²` |
| Motion | Mức khác nhau giữa hai frame | Trung bình sai khác tuyệt đối sau khi thu về 320×180 |
| Highlight ratio | Tỷ lệ vùng gần trắng bão hòa | Số pixel xám `>=250` / tổng pixel |

Thông số mặc định trong YAML:

| Điều kiện | Profile băng tải | Profile bench |
|---|---:|---:|
| Laplacian tối thiểu | 12.5 | 3.0 |
| Tenengrad tối thiểu | 1180 | 450 |
| Motion tối đa | 3.5 | 4.5 |
| Highlight ratio tối đa | 0.03 | 0.06 |
| Số frame liên tiếp đạt yêu cầu | 4 | 2 |

Burst mặc định giữ tối đa 15 frame. Trong các frame hợp lệ, bộ chọn dùng `score = Laplacian + 0.02 × Tenengrad`. Đây là quy tắc xếp hạng của dự án; các ngưỡng không có đơn vị khoảng cách hay độ nét quang học và cần hiệu chuẩn theo ảnh thực.

Thước đo cạnh có thể bị ảnh hưởng bởi nhiễu, texture và bố trí ROI. Nền nhiều chi tiết không chứng minh QR đã rõ. Tài liệu học thêm: [OpenCV focus measures](https://opencv.org/autofocus-using-opencv-a-comparative-study-of-focus-measures-for-sharpness-assessment/).

### 5.2. Focus peaking

Focus peaking tô các cạnh mạnh để người vận hành canh nét. GUI giới hạn overlay trong vùng nhãn tìm được hoặc ROI tìm kiếm khi chưa có box; ngưỡng cạnh kết hợp mức tối thiểu và percentile thích nghi.

Overlay chỉ hỗ trợ quan sát. Nó không điều khiển lens và không phục hồi ảnh mất nét. Decoder xử lý ảnh gốc/biến thể xử lý, không dùng ảnh đã tô overlay.

### 5.3. Các biến thể hỗ trợ đọc QR

| Phương pháp | Giải thích đơn giản | Vai trò trong code |
|---|---|---|
| Grayscale | Chuyển ảnh màu thành cường độ sáng | Cơ sở cho tính toán cạnh/ngưỡng |
| Gaussian blur | Làm mượt nhiễu nhỏ | Trước phép đo focus hoặc tách contour |
| CLAHE | Tăng tương phản theo vùng, có giới hạn khuếch đại | Làm rõ chi tiết ở vùng sáng không đều |
| Unsharp mask | Cộng thêm thành phần chi tiết so với ảnh làm mượt | Hỗ trợ cạnh trong biến thể QR |
| Cubic upscale | Nội suy ảnh lên kích thước lớn hơn | Tạo đầu vào khác cho decoder |
| Otsu threshold | Chọn ngưỡng nhị phân cho toàn ảnh | Tách vùng sáng/tối |
| Adaptive Gaussian threshold | Chọn ngưỡng theo lân cận | Hỗ trợ khi sáng không đồng đều |
| Inversion | Đảo trắng/đen | Thử biến thể có cực tính khác |

Các biến thể được thử cho tới khi tìm được QR hợp lệ. Phóng to bằng nội suy không tạo lại chi tiết QR đã mất vì blur. CLAHE hoặc sharpening quá mạnh có thể khuếch đại nhiễu; ảnh gốc phải được giữ để đối chiếu. Học thêm về CLAHE tại [OpenCV histogram equalization](https://docs.opencv.org/4.x/d5/daf/tutorial_py_histogram_equalization.html).

## 6. QR, nhãn A6 và vùng kiện

### 6.1. Giải mã QR và mã vận đơn

`QrReader` ưu tiên ZXing-C++, lọc kết quả QR và fallback sang `cv2.QRCodeDetector`. Kết quả gồm payload (nội dung được mã hóa), format, biến thể đọc được và bốn góc QR quy về ảnh đầu vào.

Payload có thể là chuỗi mã, JSON hoặc URL. Parser tìm các trường như `waybill_code`/`tracking_number` rồi áp dụng quy tắc regex của dự án. Đọc được payload chưa bảo đảm đã trích được mã vận đơn phù hợp; cũng chưa chứng minh vận đơn tồn tại trên database.

API tham khảo: [ZXing-C++ Python bindings](https://github.com/zxing-cpp/zxing-cpp/blob/master/wrappers/python/README.md).

### 6.2. Chuẩn hóa phối cảnh

Nhãn nghiêng làm vị trí/kích thước logo thay đổi trên ảnh. Homography là phép biến đổi một mặt phẳng sang mặt phẳng ảnh khác; triển khai QR-anchor ánh xạ bốn góc QR tới vị trí QR đã biết trên layout nhãn.

Đầu ra mặc định là nhãn **1050×1480 pixel**, tương ứng khung A6 portrait được chuẩn hóa. Độ phân giải đầu ra là lựa chọn xử lý phần mềm, không phải phép đo kích thước thực đã hiệu chuẩn.

Điều kiện áp dụng: mặt nhãn gần phẳng, QR nhìn thấy, layout đúng với `qr_target_roi`. Đổi mẫu nhãn hoặc nhãn cong/nhăn có thể làm phép biến đổi sai. Source cũng có phương pháp tìm quadrilateral bằng contour, nhưng cấu hình mặc định chọn `qr_anchor`. Học thêm: [OpenCV homography](https://docs.opencv.org/4.x/d7/dff/tutorial_feature_homography.html).

### 6.3. Định vị kiện bằng QR-anchor và cạnh

Trình tự hiện tại:

1. Tìm QR; suy ra vùng nhãn từ vị trí QR tương đối trong layout.
2. Dùng Canny để tìm các cạnh có biến đổi sáng rõ.
3. Tính số pixel cạnh theo cột trong vùng tìm kiếm hai bên nhãn.
4. Chọn cụm cạnh trái/phải; nếu thiếu cạnh thì mở rộng theo tỷ lệ fallback.
5. Vẽ box kiện và box nhãn để giám sát.

Box là vùng **ước lượng** theo QR/nhãn/cạnh. Chiều cao và biên box có thể chưa ôm hết kiện; nhiều kiện gần nhau hoặc cạnh nền mạnh có thể gây chọn sai. Khi QR bị che, cơ chế này chưa có detector kiện độc lập để thay thế. Nếu không có QR-anchor phục vụ phối cảnh, inspection có thể dừng với quality/anchor error.

Confidence hiển thị là điểm heuristic theo thông tin cạnh tìm được, không phải xác suất nhận diện đã được kiểm chứng. Cần đánh giá riêng tình huống nhiều kiện và QR che khuất.

## 7. Nhận diện logo

### 7.1. Nguyên lý

Hệ thống so sánh **ảnh logo mẫu** với vùng tìm logo trên nhãn đã chuẩn hóa:

1. Grayscale + CLAHE chuẩn bị ảnh.
2. SIFT tìm keypoint và descriptor.
3. BFMatcher lấy hai descriptor gần nhất cho mỗi điểm template.
4. Ratio test loại các cặp match còn mơ hồ.
5. RANSAC tìm homography và xác định các cặp match phù hợp.
6. So sánh số match, tỉ lệ inlier và score với ngưỡng.

Ratio test được triển khai bằng `distance_1 < match_ratio × distance_2`. Các tham số mặc định: `match_ratio=0.76`, tối thiểu 8 good matches, `min_inlier_ratio=0.40`, `threshold=0.12`.

Score trong code là `số inlier / số keypoint template`. Ví dụ score vượt ngưỡng vẫn chưa đủ nếu thiếu số match hoặc tỉ lệ inlier yêu cầu. Score không phải accuracy hay xác suất hãng vận chuyển. Tài liệu nền tảng: [OpenCV feature matching](https://docs.opencv.org/4.x/dc/dc3/tutorial_py_matcher.html).

### 7.2. Tài nguyên hiệu chuẩn

| File | Vai trò |
|---|---|
| [spx_template.png](assets/logo/spx_template.png) | Ảnh logo mẫu hiện tại |
| [logo_calibration.json](config/calibration/logo_calibration.json) | Vùng chọn/vùng tìm kiếm và metadata hiệu chuẩn |
| [logo_calibration.py](src/machine_vision/ui/logo_calibration.py) | Cửa sổ chụp nhãn, chọn vùng logo và lưu mẫu |

Lấy mẫu bằng webcam tại setup thực giúp phản ánh ảnh in/ánh sáng thực tế. Chỉ chọn vùng logo, tránh QR và chữ khác. Khi đổi logo, layout hoặc điều kiện ảnh, cần lấy mẫu/đánh giá lại. Đây là đối chiếu template hiện có, chưa phải mô hình phân loại logo của nhiều đơn vị vận chuyển.

## 8. Kiểm tra dấu hiệu hư hỏng

### 8.1. Hình dạng và đường bao

Ảnh hiện tại được so sánh với ảnh nền trống đã chụp cùng setup. Sau làm mượt, sai khác tuyệt đối, threshold và morphology, thuật toán lấy contour (đường bao).

Morphology **open** giúp loại đốm nhỏ; **close** giúp nối/lấp khe nhỏ. Kích thước kernel quyết định mức chi tiết giữ lại. Source sử dụng các thao tác này để tạo mask trước khi tính hình dạng. [OpenCV morphology](https://docs.opencv.org/4.x/d9/d61/tutorial_py_morphological_ops.html).

| Chỉ số | Công thức/ý nghĩa | Dấu hiệu được kiểm tra |
|---|---|---|
| Rectangularity | Diện tích contour / diện tích hình chữ nhật xoay bao contour | Đường bao lệch khỏi hình chữ nhật |
| Solidity | Diện tích contour / diện tích convex hull | Vùng lõm hoặc rách cạnh |
| Vertices | Số đỉnh polygon sau xấp xỉ đường bao | Biên quá bất thường |
| Area ratio | Diện tích vùng tìm được / diện tích ROI | Loại vùng quá nhỏ để đánh giá |

Các giá trị mặc định quan trọng là `min_rectangularity=0.82`, `min_solidity=0.95` và `max_vertices=8`. Chúng gợi ý biến dạng nhìn thấy trên ảnh, chưa đo độ móp theo mm hay độ sâu 3D.

### 8.2. Điểm tối nghi lỗ thủng trên bề mặt

Trong box kiện được chọn, code che vùng nhãn để hạn chế nhầm QR/chữ đen với lỗi. Ngưỡng tối được suy ra từ median cường độ bề mặt và giới hạn trong cấu hình. Các contour tối được lọc theo diện tích, aspect ratio và mức đầy, rồi khoanh vị trí nghi vấn trên ảnh kiểm tra.

Nhánh target có thể báo dấu hiệu lỗ nhìn thấy ngay cả khi chưa đủ dữ liệu để đánh giá hình dạng. Nếu không có lỗi bề mặt và hình dạng chưa đánh giá được, kết quả damage vẫn có thể là chưa xác định.

Một vùng tối không đủ chứng minh vật liệu bị thủng xuyên. Vết in, bóng đổ và khe nắp có thể báo giả; lỗi cùng màu hoặc trên mặt khuất có thể bị bỏ sót. Cần ảnh gán nhãn và mẫu tốt đối chứng để đo hiệu quả.

### 8.3. Tài nguyên ảnh nền

| File runtime | Bối cảnh |
|---|---|
| `config/calibration/empty_bench.png` | Kiện đứng yên trên bàn/sàn |
| `config/calibration/empty_belt.png` | Băng tải trống tại setup vận hành |

Không dùng ảnh nền của một vị trí camera/đèn khác để kết luận chất lượng tại setup mới. Hướng dẫn chi tiết: [damage commissioning](docs/damage_commissioning.md).

## 9. Quyết định, GUI và Digital Twin

### 9.1. Quy tắc quyết định

Classifier hiện là tập luật, không phải mô hình học máy. Với các điều kiện bắt buộc đang bật, thứ tự đánh giá là:

| Điều kiện | Kết quả phần mềm |
|---|---|
| Damage chưa đủ hiệu chuẩn/kết quả chưa xác định | `MANUAL_REVIEW` |
| Phát hiện dấu hiệu damage | `REJECT`, rổ logic `DEFECT` |
| Logo chưa đủ điều kiện đánh giá | `MANUAL_REVIEW` |
| Logo không khớp | `REJECT` |
| Thiếu QR hoặc mã vận đơn bắt buộc | `REJECT` |
| Các điều kiện đạt trong local test | `PASS`, rổ logic `LOCAL_TEST` |
| Chế độ database | Tra cứu vận đơn và trường rổ theo repository/config |

GUI hiển thị `LOCAL PASS/FAIL/REVIEW` trong local test. “Rổ” hiện là thông tin kết quả phần mềm; chưa có lệnh tự động điều khiển cơ cấu phân loại. `QUALITY HOLD` xảy ra trước khi inspection hoàn tất, khác với kết quả `MANUAL_REVIEW`.

### 9.2. Giao diện và xử lý sự kiện

PyQt6 cung cấp widget, signal/slot và timer. Worker QThread thực hiện request UDP để thao tác mạng không chặn vòng lặp giao diện. Phần Vision inspection hiện vẫn được gọi đồng bộ từ GUI; không nên mô tả toàn bộ xử lý là bất đồng bộ.

Ảnh live giúp canh camera; snapshot giữ ảnh inspection để đối chiếu. KPI, lý do quyết định và debug images hỗ trợ truy vết. Tài liệu thư viện: [PyQt6 Reference Guide](https://www.riverbankcomputing.com/static/Docs/PyQt6/).

### 9.3. Mô hình Digital Twin

Cảnh hiện tại dùng tọa độ 3D, phép chiếu và QPainter để dựng băng tải, camera gantry, rổ và robot. Có orbit/pan/zoom, presets, layers và slider sáu khớp robot.

[Scene manifest](assets/digital_twin/scene_manifest.json) mô tả asset, transform, node và telemetry binding dự kiến. Các đường dẫn model còn trống. [QML scene template](src/machine_vision/ui/qml/DigitalTwinView.qml) chuẩn bị hướng tích hợp Qt Quick 3D, chưa phải renderer đang chạy với mesh thực.

Các binding PLC/robot trong manifest là thiết kế cho tích hợp tiếp theo, chưa chứng minh đã có dữ liệu thật. Góc robot hiện mô phỏng; băng tải hiển thị lệnh gần nhất có ACK. Quy cách asset: [3D asset handoff](docs/3d_asset_handoff.md).

## 10. Tài nguyên điều khiển ESP32

### 10.1. Nguồn thiết kế và chân kết nối

Nguồn chính là [firmware do nhóm cung cấp](firmware/sketch_sep19a.ino) và [schematic](hardware/esp32_conveyor_schematic.png). GUI tích hợp dựa trên cùng giao thức UDP của giao diện test ban đầu.

| Khối | Kết nối trong source/schematic |
|---|---|
| W5500 | MOSI GPIO23, MISO GPIO19, SCLK GPIO18, CS GPIO5, RST GPIO4 |
| BTS7960 | RPWM GPIO25, LPWM GPIO26, R_EN GPIO27, L_EN GPIO14 |
| Chân sensor trên schematic | R_S GPIO34, L_S GPIO35; firmware chưa đọc |
| Nguồn trên schematic | 24 V motor/driver; LM2596 tạo 5 V cho ESP32/logic; W5500 ghi 3,3 V; GND chung |

PWM dùng LEDC 5 kHz, độ phân giải 8 bit. Duty đặt 150/255 tương ứng khoảng 58,8% chu kỳ PWM, không đồng nghĩa motor quay 58,8% tốc độ tối đa. Firmware sử dụng API Arduino-ESP32 core 3.x. [Espressif LEDC API](https://docs.espressif.com/projects/arduino-esp32/en/latest/api/ledc.html).

### 10.2. Giao thức và xác nhận

ESP32/W5500 mặc định nghe tại `192.168.2.100:8120`; laptop cần cùng subnet, ví dụ `192.168.2.10/24`.

| Datagram gửi | Phản hồi | Ý nghĩa |
|---|---|---|
| `PING` | `PONG` | Firmware phản hồi qua UDP |
| `FWD:150` | `ACK:FWD:150 (State: FWD Speed: 150)` | Lệnh chạy thuận/PWM đã được xử lý |
| `REV:150` | ACK tương ứng | Lệnh chạy nghịch/PWM đã được xử lý |
| `STOP:0` | `ACK:STOP:0 (State: STOP Speed: 0)` | Firmware đã đặt PWM/enable về trạng thái dừng |

Client kiểm tra nguồn IP/port và nội dung ACK khớp lệnh. Timeout 600 ms làm trạng thái GUI thành `UNKNOWN`. Sau PING đầu tiên cần ACK STOP trước khi chạy; đảo chiều cần STOP; đóng ứng dụng sau lệnh chạy sẽ thử STOP. PING định kỳ 1 giây kiểm tra giao tiếp. Các thao tác được mô tả tại [esp32_contract.md](docs/esp32_contract.md); API UDP phía PC dùng [Python socket](https://docs.python.org/3/library/socket.html).

UDP/firmware gốc chưa có transaction ID và chưa bảo đảm thứ tự/giao nhận lệnh. PONG không chứa trạng thái motor. ACK phản ánh trạng thái lệnh firmware, chưa có encoder/sensor xác nhận chuyển động cơ học.

### 10.3. Giới hạn cần xử lý trước vận hành tự động

Firmware gốc chưa tự gọi stop khi mất mạng hoặc GUI ngừng gửi request. Do đó cần thử có giám sát và cơ chế dừng/ngắt nguồn động lực bằng phần cứng. STOP trên GUI là lệnh mạng.

Các hạng mục tiếp theo gồm watchdog tại ESP32, liên động, phản hồi motor và thử mất cáp/reset/mất nguồn. Chưa có điều khiển phân loại tự động bằng kết quả Vision trong bản hiện tại.

## 11. Tài nguyên dữ liệu và hiệu chuẩn

| Tài nguyên | Cách tạo/sử dụng | Nơi lưu |
|---|---|---|
| Ảnh gốc theo khoảng cách | Thu ảnh trước khi chọn khoảng làm việc/ngưỡng | `dataset/raw/`; không kèm Core |
| Logo mẫu | Chụp và chọn từ GUI hoặc script hiệu chuẩn | `assets/logo/` |
| Thông số logo | Được ghi khi lưu template | `config/calibration/logo_calibration.json` |
| Ảnh nền | Chụp cảnh trống tại setup cố định | `config/calibration/*.png` |
| Bằng chứng inspection | Lưu tự động theo cấu hình audit | `captures/<ngày>/<inspection-id>/` |
| Cấu hình trạm | Camera, ROI, ngưỡng, phân loại và controller | [default.yaml](config/default.yaml) |
| Dữ liệu vận đơn | Adapter repository; Supabase hiện tắt | [shipments.py](src/machine_vision/repositories/shipments.py) |

Một inspection có thể lưu `frame.jpg`, `label.jpg`, debug PNG và `result.json`. JSON ghi quyết định, lý do, focus metrics, payload/mã vận đơn, đánh giá logo/damage và record database nếu có. Timestamp metadata là UTC; GUI dùng đồng hồ máy.

Core Source giữ source và logo/ROI hiện tại. Private Calibration bổ sung ảnh nền/hiệu chuẩn từ setup cũ; “private” là phạm vi chia sẻ đề xuất, ZIP không có mật khẩu. Ảnh nhãn có thể chứa dữ liệu cá nhân; giữ ảnh vận hành trong Drive/thư mục nhóm được phân quyền. Không commit `.env` hoặc khóa thật.

Khi tạo tập dữ liệu mới, ghi kèm camera, khoảng cách lens–nhãn, ánh sáng, kích thước kiện, loại lỗi và nhãn ground truth. Tách tập dùng chỉnh ngưỡng khỏi tập đánh giá để tránh công bố kết quả chỉ tốt trên ảnh đã dùng hiệu chuẩn.

## 12. Công cụ sử dụng trong quá trình phát triển

| Công cụ | Công việc | Đầu vào/điều kiện |
|---|---|---|
| [capture_2k_samples.py](scripts/capture_2k_samples.py) | Thu ảnh theo khoảng cách | Webcam và bố trí đo |
| [calibrate_focus.py](scripts/calibrate_focus.py) | Xem chỉ số ảnh, ghi mẫu good/bad | Webcam; xuất CSV |
| [analyze_focus_samples.py](scripts/analyze_focus_samples.py) | Phân tích mẫu focus | CSV đã thu |
| [calibrate_logo_template.py](scripts/calibrate_logo_template.py) | Cắt template theo ROI | Ảnh nhãn đã chuẩn hóa qua `--input`; ROI qua `--roi` |
| [evaluate_logo_dataset.py](scripts/evaluate_logo_dataset.py) | Đánh giá logo theo ảnh khoảng cách | Dataset riêng; Core không có ảnh raw |
| [capture_empty_belt_reference.py](scripts/capture_empty_belt_reference.py) | Chụp nền băng tải trống | Camera tại vị trí cuối cùng |
| [render_ui.py](scripts/render_ui.py) | Render giao diện để kiểm tra bố cục | Dữ liệu demo; không xác nhận kết nối thiết bị |
| [build_windows_exe.py](scripts/build_windows_exe.py) | Build EXE | Extra `build` và môi trường Windows |
| [package_handoff.py](scripts/package_handoff.py) | Tạo gói Core và calibration khi dữ liệu có sẵn | Các file source/hiệu chuẩn được khai báo |

Chạy `--help` với các script có argparse để xem tham số trước khi thu ảnh. Hướng dẫn cài đặt/chạy GUI và test nằm trong [README.md](README.md), tránh nhầm công cụ hiệu chuẩn với luồng vận hành.

`capture_2k_samples.py` dùng tham số CLI riêng; cần kiểm tra FourCC/độ phân giải thay vì mặc định cho rằng nó kế thừa toàn bộ YAML. Script cắt logo chỉ xuất ảnh template; GUI lấy mẫu logo còn kiểm tra đặc trưng và lưu calibration JSON. Với người mới, ưu tiên quy trình hiệu chuẩn từ GUI trong README.

## 13. Kiểm chứng và cách hiểu kết quả

### 13.1. Bằng chứng kiểm thử hiện có

Mốc 05/10/2026: **47 tests passed** trên bản Core giải nén, gồm thuật toán, classifier, file paths/manifest và client/worker GUI với UDP giả lập. Screenshot offscreen đã được tạo để kiểm tra bố cục.

Đây là kiểm thử phần mềm. Trong phiên tích hợp/bàn giao chưa có xác minh motor/ESP32 thật hoặc đo độ chính xác của toàn hệ thống trên băng tải mới. Các thử nghiệm phần cứng do nhóm thực hiện cần được ghi thành biên bản riêng.

| Loại kiểm tra | Chứng minh được | Còn cần bổ sung |
|---|---|---|
| Unit/integration test | Luật và trường hợp kiểm thử đã lập trình hoạt động | Tình huống chưa mô hình hóa và dữ liệu thực |
| UDP giả lập | Request, ACK, timeout và luồng worker GUI | Firmware/mạng/motor thực |
| UI offscreen | Có thể dựng giao diện để xem bố cục | DPI, driver và tương tác tại máy vận hành |
| Pilot trên băng tải | Phát hiện đúng/sai trong setup thực | Tập dữ liệu gán nhãn và biên bản đánh giá |

### 13.2. Chỉ số nên báo cáo

| Chỉ số | Cách tính/diễn giải |
|---|---|
| QR scan success | Số inspection đọc được QR / số inspection hoàn tất; KPI hiện tại chưa tính quality hold vào mẫu số |
| Precision phát hiện lỗi | TP / (TP + FP): trong các kiện báo lỗi, bao nhiêu kiện thật sự lỗi |
| Recall phát hiện lỗi | TP / (TP + FN): trong các kiện lỗi thật, phát hiện được bao nhiêu |
| Manual review rate | Tỷ lệ mẫu cần người đánh giá; phải quy định rõ mẫu số trong báo cáo |
| Quality hold rate | Tỷ lệ lần thử không có frame đạt gate; ghi riêng với inspection hoàn tất |
| Thời gian xử lý | Median/P95 phần mềm và thời gian chu kỳ cơ khí, đo riêng |

Với bài toán **lỗi kiện là lớp positive**: TP = báo đúng lỗi; FP = báo lỗi nhầm kiện tốt; FN = bỏ sót kiện lỗi. Nếu chưa có mẫu cho một mẫu số, ghi “chưa xác định” thay vì chia hoặc suy ra độ tin cậy.

KPI `CYCLE TIME` hiện đo thời gian inspection phần mềm, gồm xử lý/lưu bằng chứng theo luồng GUI; chưa phải thời gian vận chuyển và robot hoàn tất phân loại. Score focus, logo và confidence box cũng không phải precision/recall.

### 13.3. Checklist nghiệm thu tài nguyên

1. Đo thông số camera thực và khoảng nét cho các chiều cao kiện.
2. Cố định đèn/camera, chụp nền chuẩn và xác nhận ảnh QR không chói.
3. Kiểm tra QR/layout và template logo bằng mẫu đúng, sai và che khuất.
4. Đánh giá damage với ground truth, gồm cả mẫu tốt có bóng/vết in dễ báo giả.
5. Kiểm tra UDP, chiều/PWM, mất mạng và dừng phần cứng tại trạm.
6. Ghi phiên bản thư viện thực, YAML, template và dữ liệu dùng đánh giá.
7. Xác nhận mesh/khớp robot, sensor, database và liên động trước khi bật tự động.

## 14. Danh mục tham khảo

### 14.1. Tài liệu nền tảng

| Mã | Tài liệu | Phần nên đọc và liên hệ dự án |
|---|---|---|
| R01 | [ZXing-C++ Python](https://github.com/zxing-cpp/zxing-cpp/blob/master/wrappers/python/README.md) | Đọc barcode, payload và vị trí mã; QR reader |
| R02 | [OpenCV focus measures](https://opencv.org/autofocus-using-opencv-a-comparative-study-of-focus-measures-for-sharpness-assessment/) | Laplacian/Tenengrad và giới hạn của chỉ số nét |
| R03 | [OpenCV CLAHE](https://docs.opencv.org/4.x/d5/daf/tutorial_py_histogram_equalization.html) | Tương phản toàn ảnh/cục bộ; enhancement và logo |
| R04 | [OpenCV feature matching](https://docs.opencv.org/4.x/dc/dc3/tutorial_py_matcher.html) | BFMatcher, SIFT và ratio test; logo reader |
| R05 | [OpenCV homography](https://docs.opencv.org/4.x/d7/dff/tutorial_feature_homography.html) | Biến đổi điểm/mặt phẳng và RANSAC |
| R06 | [OpenCV morphology](https://docs.opencv.org/4.x/d9/d61/tutorial_py_morphological_ops.html) | Open/close và kernel; mask damage |
| R07 | [OpenCV image processing](https://docs.opencv.org/4.x/d2/d96/tutorial_py_table_of_contents_imgproc.html) | Threshold, Canny và contours |
| R08 | [PyQt6 Reference Guide](https://www.riverbankcomputing.com/static/Docs/PyQt6/) | Widgets, signal/slot và giao diện |
| R09 | [Python socket](https://docs.python.org/3/library/socket.html) | Datagram UDP, gửi/nhận và timeout |
| R10 | [Espressif LEDC](https://docs.espressif.com/projects/arduino-esp32/en/latest/api/ledc.html) | `ledcAttach`, `ledcWrite`; PWM firmware |
| R11 | [Arduino Ethernet](https://docs.arduino.cc/libraries/ethernet/) | Ethernet library cho giao tiếp W5500 |
| R12 | [KEYENCE lighting selection](https://www.keyence.com/products/vision/resources/vision-resources/basics-of-lighting-selection.jsp) | Lựa chọn hình thức chiếu sáng theo bề mặt |
| R13 | [Cognex Lighting Guide](https://www.cognex.com/support/downloads/ns/1/11/89/1010.pdf) | Sáng cho nhãn mã và bố trí sáng khác nhau |

Các tài liệu web có thể mô tả phiên bản mới hơn phiên bản cài tại máy. Đối chiếu API với source/dependencies trước khi áp dụng ví dụ. Bảng này là tài nguyên học và tham khảo, không phải danh sách kết quả nghiệm thu.

### 14.2. Ví dụ đã được người dùng đưa vào quá trình tìm hiểu

- [Pysource — Detect when an image is blurry](https://pysource.com/2019/09/03/detect-when-an-image-is-blurry-opencv-with-python/): ví dụ blur; ngưỡng minh họa phải đo lại cho webcam/ROI thực.
- [GreenpantsDeveloper — Focus peaking](https://github.com/GreenpantsDeveloper/focus-peaking): ví dụ overlay cạnh. Project có cách giới hạn ROI và ngưỡng thích nghi riêng.

### 14.3. Hồ sơ kỹ thuật nội bộ

- [README.md](README.md): cài đặt và vận hành thử.
- [architecture.md](docs/architecture.md): thành phần và luồng dữ liệu.
- [esp32_contract.md](docs/esp32_contract.md): giao thức hiện tại và ranh giới tích hợp.
- [damage_commissioning.md](docs/damage_commissioning.md): chuẩn bị/đánh giá ảnh damage.
- [hmi_digital_twin.md](docs/hmi_digital_twin.md): thiết kế HMI và trạng thái.
- [3d_asset_handoff.md](docs/3d_asset_handoff.md): quy cách đưa mô hình thật vào hệ thống.

## 15. Hạng mục phát triển tiếp theo

| Hạng mục | Tài nguyên cần bổ sung | Cách xác nhận hoàn thành |
|---|---|---|
| Camera/đèn tại băng tải | Đồ gá, thông số camera và dữ liệu ảnh mới | Ảnh rõ cho dải chiều cao kiện đã chọn |
| Detector kiện độc lập QR | Dataset gán nhãn, model hoặc phương pháp được đánh giá | Định vị khi QR che khuất và nhiều kiện |
| Kiểm tra damage ổn định | Mẫu lỗi đa dạng và tập đánh giá riêng | Precision/recall, hold/review và lỗi bỏ sót được báo cáo |
| Liên động motor | Watchdog, tín hiệu sensor/phản hồi và dừng vật lý | Thử mất kết nối/reset và dừng tại trạm |
| Robot/Twin thật | CAD/GLB, quy ước tọa độ và dữ liệu khớp | Tỷ lệ, khớp và trạng thái được đối chiếu thực tế |
| Supabase | Schema, record thử và quyền truy cập | Tra cứu vận đơn/rổ được kiểm tra trong chế độ database |

Các hạng mục này còn cần phát triển hoặc nghiệm thu; không nên mô tả như chức năng vận hành tự động đã hoàn thành trong source 0.2.0.
