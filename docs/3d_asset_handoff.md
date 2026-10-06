# Quy ước bàn giao mô hình 3D cho Digital Twin

## Định dạng và cấu trúc

- Ưu tiên **GLB (glTF 2.0 binary)** vì mesh, vật liệu và texture nằm trong một file. GLTF cũng được hỗ trợ; OBJ chỉ nên dùng cho vật thể tĩnh không cần PBR hoặc animation.
- Tách thành ba file: `conveyor.glb`, `robot-6dof.glb`, `vision-cell.glb`. Việc tách file giúp thay thế, hiệu chỉnh tọa độ và cập nhật telemetry độc lập.
- Đơn vị phải là **meter**. Chọn Y-up khi xuất file; nếu phần mềm CAD bắt buộc Z-up thì ghi đúng `upAxis` trong manifest.
- Gốc tọa độ của robot đặt tại tâm đế; gốc băng tải đặt ở tâm mặt sàn đầu vào. Freeze/apply transform trước khi xuất.

## Tên node bắt buộc

Robot cần giữ hierarchy và pivot quay đúng trục:

```text
Robot
├─ J1
│  └─ J2
│     └─ J3
│        └─ J4
│           └─ J5
│              └─ J6
│                 └─ Tool
```

Băng tải và cell nên có các node: `Conveyor/Belt`, `Conveyor/Sensor_S1`,
`Vision/Camera_2K`, `Bins/Pass`, `Bins/Defect`, `Bins/Review`.

Tên thực tế có thể khác, nhưng phải ánh xạ lại trong
`assets/digital_twin/scene_manifest.json`.

## Chuẩn vật liệu và hiệu năng

- Dùng PBR base color / metallic / roughness; đóng gói texture cùng GLB.
- Texture 1K–2K là đủ cho HMI; tránh texture 4K nếu không cần đọc chi tiết bề mặt.
- Xóa chi tiết CAD rất nhỏ, phần bên trong và fastener không nhìn thấy. Mục tiêu tổng thể dưới khoảng 300k triangles cho một cell nhỏ.
- Tên mesh cần có ý nghĩa, không dùng hàng loạt `Object001`, `Object002`.

## Cách đưa file vào project

1. Chép file đã kiểm tra vào `assets/digital_twin/models/`.
2. Điền đường dẫn tương đối vào trường `file` của từng asset trong
   `assets/digital_twin/scene_manifest.json`.
3. Kiểm tra lại translation, rotation, scale và node bindings.
4. Gửi ba file và manifest để thực hiện bước commissioning: kiểm tra pivot J1–J6,
   căn tọa độ với camera/băng tải, rồi mới chuyển viewer từ `placeholder` sang
   `quick3d`. Không bật viewer thật trước khi hoàn thành bước này.

Chỉ nạp file 3D từ nguồn tin cậy. Runtime loader không phải là sandbox và không
nên dùng để mở file tùy ý nhận từ người dùng bên ngoài.
