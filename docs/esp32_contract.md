# Giao thức băng tải ESP32/W5500 đang dùng

Nguồn: firmware nhóm cung cấp tại [`../firmware/sketch_sep19a.ino`](../firmware/sketch_sep19a.ino) và sơ đồ [`../hardware/esp32_conveyor_schematic.png`](../hardware/esp32_conveyor_schematic.png). Đây là **giao thức thực tế**, thay thế bản phác thảo TCP/JSON trước đây.

## Mạng và lệnh

- ESP32/W5500 IP tĩnh `192.168.2.100/24`, UDP port `8120`. Laptop cần IP cùng subnet (ví dụ `192.168.2.10/24`); không cần Internet hay Supabase.
- Mỗi lệnh là một datagram ASCII; phản hồi về đúng source IP/port của gói vừa nhận.

| GUI gửi | ESP32 trả | Ý nghĩa |
|---|---|---|
| `PING` | `PONG` | Kiểm tra kênh UDP, **không** báo trạng thái motor |
| `FWD:150` | `ACK:FWD:150 (State: FWD Speed: 150)` | Chạy thuận, PWM 150/255 |
| `REV:150` | `ACK:REV:150 (State: REV Speed: 150)` | Chạy nghịch |
| `STOP:0` | `ACK:STOP:0 (State: STOP Speed: 0)` | Ngắt enable và PWM |

GUI xác minh IP/port người trả và ACK trùng action/speed. Timeout mặc định 600 ms; trạng thái sau timeout là `UNKNOWN`, **không** suy diễn motor đã dừng. Các thao tác dùng worker QThread để GUI vẫn phản hồi. Nút STOP vẫn nhấn được khi chưa PING hoặc có lệnh đang chờ; phản hồi cũ bị bỏ qua theo thứ tự lệnh tại GUI. PING định kỳ 1 giây chỉ kiểm tra liên lạc; firmware gốc không có watchdog từ PING.

Sau PING đầu tiên, nhấn DỪNG và đợi ACK trước khi GUI cho chạy. Đảo chiều yêu cầu STOP đã ACK. Khi có request đang chờ, STOP được ưu tiên gửi ngay sau request đó (timeout tối đa 600 ms). Địa chỉ bị khóa sau lệnh chạy cho tới ACK STOP. Khi đóng ứng dụng đã gửi lệnh chạy, GUI thử STOP và báo nếu chưa có xác nhận. UDP gốc vẫn không bảo đảm thứ tự/giao nhận ở ESP32; đây là một hạn chế giao thức cần nâng cấp.

Digital Twin chỉ phản ánh **lệnh gần nhất được ACK** (FWD/REV/STOP), không có encoder hay công tắc phản hồi để chứng minh tốc độ/trạng thái cơ học thực. Camera bật/tắt và kết quả vision không tự phát lệnh motor. Chưa có điều khiển phân loại tự động.

## Đấu nối từ schematic

| Khối | Chân |
|---|---|
| W5500 SPI | MOSI 23, MISO 19, SCLK 18, CS 5, RST 4 |
| BTS7960 | RPWM 25, LPWM 26, R_EN 27, L_EN 14 |
| BTS7960 sensor | R_S 34, L_S 35 trên sơ đồ nhưng **firmware chưa đọc** |
| Nguồn | 24 V tới BTS7960/motor; LM2596 tạo 5 V cho ESP32/BTS7960 logic; W5500 3,3 V; GND chung |

Xác minh đúng điện áp module thực tế, công suất và cực tính trước khi cấp nguồn. Không lấy 24 V trực tiếp vào ESP32 hoặc W5500. PWM trong firmware là LEDC 5 kHz, 8 bit, dùng API Arduino-ESP32 core 3.x.

## Giới hạn an toàn bắt buộc xử lý trước khi vận hành không giám sát

Firmware gốc **không tự dừng khi mất gói/đứt cáp LAN/GUI treo**; khi motor đã chạy, lệnh cũ có thể tiếp tục. Nó cũng ACK lệnh lạ mà không báo lỗi. Vì vậy đây mới là điều khiển thử nghiệm có người giám sát, không phải bộ điều khiển an toàn. Cần:

1. Nút dừng khẩn/công tắc ngắt nguồn động lực vật lý, tiếp điểm an toàn phù hợp và bảo vệ dòng.
2. Watchdog trong ESP32: chỉ duy trì chạy khi nhận heartbeat/lệnh hợp lệ từ host được cho phép; timeout hoặc link down phải gọi `stopMotor()`.
3. Thêm trạng thái/sequence ID và cơ chế kiểm tra phản hồi motor bằng sensor/encoder nếu muốn gọi là telemetry thực; test mất nguồn, mất mạng, reset ESP32.
4. Không dùng `STOP` GUI làm E-stop. Không kích hoạt auto-routing/robot cho tới khi commissioning liên động đầy đủ.

## Cách kiểm tra an toàn

Thử UDP giả lập không có động cơ trước (`tests/test_conveyor_udp.py`). Khi dùng phần cứng: tháo cơ cấu tải hoặc giữ vùng nguy hiểm trống, chuẩn bị ngắt nguồn motor vật lý, PING trước, chọn PWM thấp, chỉ nhấn FWD/REV khi giám sát trực tiếp, STOP và quan sát motor dừng thật. Mất ACK → ngắt nguồn động lực bằng phần cứng và kiểm tra tại chỗ.
