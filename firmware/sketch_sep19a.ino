#include <SPI.h>
#include <Ethernet.h>

// ================================================================
// 1. CẤU HÌNH PHẦN CỨNG (ESP32 DEVKIT)
// ================================================================

// Chân SPI cho W5500 trên ESP32 DevKit
#define W5500_MOSI  23
#define W5500_MISO  19
#define W5500_SCLK  18
#define W5500_CS    5

// Chân RST của W5500: 
// Đặt là 4 nếu có nối dây GPIO4. Đặt là -1 nếu bạn đã rút dây RST (khuyên dùng)
#define W5500_RST   4   

// Chân điều khiển động cơ BTS7960
#define RPWM_PIN    25
#define LPWM_PIN    26
#define R_EN_PIN    27
#define L_EN_PIN    14

// ================================================================
// 2. CẤU HÌNH MẠNG ETHERNET UDP
// ================================================================
byte mac[] = { 0xDE, 0xAD, 0xBE, 0xEF, 0xFE, 0xED };
IPAddress ip(192, 168, 2, 100);       // IP tĩnh của ESP32
IPAddress gateway(192, 168, 2, 10);   // Gateway trỏ về IP của Laptop (192.168.2.10)
IPAddress subnet(255, 255, 255, 0);   // Subnet Mask
IPAddress dns(192, 168, 2, 10);       // DNS Server trỏ về Laptop

unsigned int localPort = 8120;        // Port lắng nghe UDP

EthernetUDP Udp;

// Cấu hình PWM cho ESP32 Core v3.x
const int pwmFreq = 5000;
const int pwmResolution = 8; // 8-bit (0 - 255)

// Biến trạng thái giám sát
String currentDirection = "STOP";
int currentSpeed = 0;
unsigned long lastHeartbeat = 0;
EthernetLinkStatus lastLinkStatus = Unknown;

// Khai báo hàm
void processCommand(String cmd);
void stopMotor();
void printEthernetInfo();

// ================================================================
// 3. HÀM KHỞI TẠO (SETUP)
// ================================================================
void setup() {
  Serial.begin(115200);
  delay(1500); // Chờ cổng USB Serial trên máy tính kết nối ổn định

  Serial.println("\n==================================================");
  Serial.println("   HE THONG DIEU KHIEN BANG TAI ESP32 + W5500     ");
  Serial.println("         CHE DO: UDP SERVER & LOG MONITOR         ");
  Serial.println("==================================================");

  // 1. Thiết lập các chân điều khiển BTS7960
  Serial.println("[KHOI TAO] Thiet lap chan BTS7960...");
  pinMode(R_EN_PIN, OUTPUT);
  pinMode(L_EN_PIN, OUTPUT);
  ledcAttach(RPWM_PIN, pwmFreq, pwmResolution);
  ledcAttach(LPWM_PIN, pwmFreq, pwmResolution);
  stopMotor();
  Serial.println("  -> BTS7960: RPWM=25, LPWM=26, R_EN=27, L_EN=14 (DA DUNG DONG CO)");

  // 2. Xử lý chân Reset W5500 (nếu có dùng)
  if (W5500_RST >= 0) {
    Serial.printf("[KHOI TAO] Thuc hien Reset cung W5500 qua GPIO %d...\n", W5500_RST);
    pinMode(W5500_RST, OUTPUT);
    digitalWrite(W5500_RST, LOW);
    delay(20);
    digitalWrite(W5500_RST, HIGH);
    delay(200);
    Serial.println("  -> Da xong Reset W5500.");
  } else {
    Serial.println("[KHOI TAO] Khong dung chan RST (dung mach reset tu dong tren module).");
  }

  // 3. Khởi tạo bus SPI cho ESP32 DevKit
  Serial.printf("[KHOI TAO] SPI: SCK=%d, MISO=%d, MOSI=%d, CS=%d\n", 
                W5500_SCLK, W5500_MISO, W5500_MOSI, W5500_CS);
  SPI.begin(W5500_SCLK, W5500_MISO, W5500_MOSI, W5500_CS);
  Ethernet.init(W5500_CS);

  // 4. Khởi động mạng Ethernet với Gateway trỏ về Laptop (192.168.2.10)
  Serial.println("[KHOI TAO] Dang bat Ethernet: IP 192.168.2.100, Gateway 192.168.2.10...");
  Ethernet.begin(mac, ip, dns, gateway, subnet);

  // 5. Kiểm tra chip W5500 có phản hồi qua SPI không
  EthernetHardwareStatus hw = Ethernet.hardwareStatus();
  Serial.print("[KIEM TRA PHAN CUNG] Chip Ethernet: ");
  if (hw == EthernetW5500) {
    Serial.println("W5500 -> [OK - CHINH XAC!]");
  } else if (hw == EthernetW5100) {
    Serial.println("W5100");
  } else if (hw == EthernetW5200) {
    Serial.println("W5200");
  } else {
    Serial.println("KHONG NHAN DIEN DUOC W5500 (EthernetNoHardware)!");
  }

  // Nếu lỏng dây SPI, lặp thông báo nhắc nhở đến khi cắm lại được
  while (Ethernet.hardwareStatus() == EthernetNoHardware) {
    Serial.println("[CANH BAO NGUY HIEM] Khong tim thay W5500!");
    Serial.println("  -> Kiem tra lai: MOSI(23), MISO(19), SCK(18), CS(5), GND va Nguon 3.3V.");
    delay(3000);
  }

  // 6. Bật lắng nghe UDP Server
  Udp.begin(localPort);
  printEthernetInfo();
  Serial.println("==================================================");
  Serial.println("SANG SANG LANG NGHE LENH TU GUI QUA UDP...");
  Serial.println("==================================================\n");
}

// ================================================================
// 4. VÒNG LẶP CHÍNH (LOOP)
// ================================================================
void loop() {
  // ------------------------------------------------------------
  // A. XỬ LÝ GÓI TIN UDP ĐẾN TỪ GUI
  // ------------------------------------------------------------
  int packetSize = Udp.parsePacket();
  if (packetSize > 0) {
    char packetBuffer[128];
    int len = Udp.read(packetBuffer, sizeof(packetBuffer) - 1);
    if (len > 0) {
      packetBuffer[len] = '\0';
    }
    
    String command = String(packetBuffer);
    command.trim();

    Serial.println("\n--------------------------------------------------");
    Serial.printf("[UDP RECEIVE] Nhan goi tin tu: %s:%d | Do dai: %d bytes\n", 
                  Udp.remoteIP().toString().c_str(), 
                  Udp.remotePort(), 
                  packetSize);
    Serial.printf("[NOI DUNG LENH]: '%s'\n", command.c_str());

    // 1. Nếu là lệnh kiểm tra kết nối (PING)
    if (command == "PING") {
      Serial.println("[XU LY]: GUI gui PING -> Dang phan hoi PONG...");
      Udp.beginPacket(Udp.remoteIP(), Udp.remotePort());
      Udp.print("PONG");
      Udp.endPacket();
      Serial.println("[PHAN HOI]: Da gui thanh cong 'PONG' ve GUI!");
    } 
    // 2. Nếu là lệnh điều khiển động cơ
    else {
      processCommand(command);

      // Gửi xác nhận ACK về GUI kèm trạng thái hiện tại
      String ackMsg = "ACK:" + command + " (State: " + currentDirection + " Speed: " + String(currentSpeed) + ")";
      Udp.beginPacket(Udp.remoteIP(), Udp.remotePort());
      Udp.print(ackMsg);
      Udp.endPacket();
      Serial.printf("[PHAN HOI]: Da gui '%s' ve GUI!\n", ackMsg.c_str());
    }
    Serial.println("--------------------------------------------------");
  }

  // ------------------------------------------------------------
  // B. GIÁM SÁT TRẠNG THÁI CÁP MẠNG & HEARTBEAT (Mỗi 3 giây)
  // ------------------------------------------------------------
  unsigned long now = millis();
  if (now - lastHeartbeat >= 3000) {
    lastHeartbeat = now;
    EthernetLinkStatus link = Ethernet.linkStatus();

    // Cảnh báo ngay nếu trạng thái cắm dây mạng thay đổi
    if (link != lastLinkStatus) {
      lastLinkStatus = link;
      if (link == LinkON) {
        Serial.println("\n>>> [THONG BAO CAP MANG] CAP LAN DA DUOC KET NOI (LinkON - 100Mbps)! <<<");
      } else if (link == LinkOFF) {
        Serial.println("\n>>> [CANH BAO CAP MANG] CAP LAN BI RUT HOAC CHUA CO TIN HIEU (LinkOFF)! <<<");
        Serial.println("    -> Kiem tra: Dây mang cắm vào PC chưa? Đèn RJ45 có sáng không?");
      } else {
        Serial.println("\n>>> [THONG BAO CAP MANG] Trang thai cap: Unknown <<<");
      }
    }

    // In log định kỳ (Heartbeat)
    const char* linkStr = (link == LinkON) ? "LinkON [CAP OK]" : ((link == LinkOFF) ? "LinkOFF [CHUA CAM CAP]" : "UNKNOWN");
    Serial.printf("[MONITOR %3lus] Cap mang: %-22s | Dong co: %-4s | Toc do: %3d/255\n",
                  now / 1000,
                  linkStr,
                  currentDirection.c_str(),
                  currentSpeed);
  }
}

// ================================================================
// 5. HÀM ĐIỀU KHIỂN ĐỘNG CƠ (BTS7960)
// ================================================================
void processCommand(String cmd) {
  int sepIndex = cmd.indexOf(':');
  String action = cmd;
  int speed = 0;

  if (sepIndex != -1) {
    action = cmd.substring(0, sepIndex);
    speed = cmd.substring(sepIndex + 1).toInt();
  }

  // Giới hạn tốc độ PWM 0 - 255
  if (speed < 0) speed = 0;
  if (speed > 255) speed = 255;

  if (action == "FWD") {
    currentDirection = "FWD";
    currentSpeed = speed;
    digitalWrite(R_EN_PIN, HIGH);
    digitalWrite(L_EN_PIN, HIGH);
    ledcWrite(LPWM_PIN, 0);
    ledcWrite(RPWM_PIN, speed);
    Serial.printf("[DONG CO]: CHAY THUAN (FWD) - PWM RPWM=%d, LPWM=0, EN=HIGH\n", speed);
  } 
  else if (action == "REV") {
    currentDirection = "REV";
    currentSpeed = speed;
    digitalWrite(R_EN_PIN, HIGH);
    digitalWrite(L_EN_PIN, HIGH);
    ledcWrite(RPWM_PIN, 0);
    ledcWrite(LPWM_PIN, speed);
    Serial.printf("[DONG CO]: CHAY NGHICH (REV) - PWM RPWM=0, LPWM=%d, EN=HIGH\n", speed);
  } 
  else if (action == "STOP") {
    stopMotor();
    Serial.println("[DONG CO]: DUNG DONG CO (STOP) - RPWM=0, LPWM=0, EN=LOW");
  } else {
    Serial.printf("[CANH BAO]: Khong nhan dien duoc lenh '%s'\n", cmd.c_str());
  }
}

void stopMotor() {
  currentDirection = "STOP";
  currentSpeed = 0;
  digitalWrite(R_EN_PIN, LOW);
  digitalWrite(L_EN_PIN, LOW);
  ledcWrite(RPWM_PIN, 0);
  ledcWrite(LPWM_PIN, 0);
}

// In thông tin mạng cấu hình ra Serial
void printEthernetInfo() {
  Serial.println("[THONG TIN MANG]:");
  Serial.print("  - IP ESP32     : "); Serial.println(Ethernet.localIP());
  Serial.print("  - Subnet Mask  : "); Serial.println(Ethernet.subnetMask());
  Serial.print("  - Gateway      : "); Serial.println(Ethernet.gatewayIP());
  Serial.print("  - Port UDP     : "); Serial.println(localPort);
  
  EthernetLinkStatus link = Ethernet.linkStatus();
  Serial.print("  - Trang thai cap: ");
  if (link == LinkON) {
    Serial.println("LinkON (Da cam day mang va co tin hieu)");
  } else {
    Serial.println("LinkOFF (Chua nhan tin hieu cap mang - kiem tra lai day RJ45)");
  }
}