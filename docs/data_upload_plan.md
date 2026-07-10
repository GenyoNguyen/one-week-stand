# Data Upload / Connect Plan

> Đề bài: "Integration: read structured daily exports from property management and reservation systems. A direct connector is welcome, but a scheduled file export is acceptable."

## Ba đường đưa dữ liệu vào (cùng một pipeline validate)

| # | Phương án | Khi nào dùng | Trạng thái |
|---|---|---|---|
| 1 | **Scheduled file export** (khuyến nghị) | Vận hành hàng ngày — PMS/CRS drop CSV vào SFTP/thư mục chia sẻ lúc 05:30, ingest job tự nạp, 06:00 dashboard sẵn sàng. Không thao tác tay. | Thiết kế xong, cần Phần 1 |
| 2 | **Manual upload** (trang Data trong UI) | Bổ sung/sửa dữ liệu, backfill lịch sử, hoặc khi đường tự động trục trặc | **Đã có UI + validate client-side** |
| 3 | **Direct PMS/CRS connector** (Opera Cloud / SynXis API) | Sau pilot, khi có credentials — bỏ hẳn bước file | Giai đoạn 3 |

Cả ba đường đổ về cùng một validation trước khi ghi: sai schema thì từ chối cả file và báo lỗi cụ thể, không nạp nửa vời.

## Schema file CSV hàng ngày (17 cột bắt buộc)

Mỗi dòng = một tổ hợp `ngày lưu trú × property × segment × channel`. File có thể chứa nhiều ngày (backfill) hoặc một ngày (daily).

| Cột | Kiểu | Ví dụ | Ghi chú |
|---|---|---|---|
| `date` | YYYY-MM-DD | 2026-07-09 | Ngày lưu trú (stay date) |
| `property` | mã | ACR / AMN / ANT | Cam Ranh, Mui Ne, Nha Trang |
| `rooms_available` | int | 213 | Số phòng khả dụng |
| `rooms_sold` | int | 196 | Phòng đã bán (quá khứ) / OTB (tương lai) |
| `room_revenue` | number | 41160 | USD |
| `adr` | number | 210.00 | |
| `occupancy` | 0–1 | 0.92 | |
| `market_segment` | text | OTA / Direct / Corporate / Group / Wholesale | |
| `channel` | text | Booking.com / Brand.com / GDS... | |
| `guest_nationality` | ISO-2 | KR | Mức quốc tịch — không có dữ liệu định danh khách |
| `lead_time_days` | int | 21 | |
| `cancellations` | int | 3 | Room nights hủy trong ngày báo cáo |
| `budget_occupancy` | 0–1 | 0.89 | |
| `budget_adr` | number | 205.00 | |
| `ly_occupancy` | 0–1 | 0.87 | Cùng kỳ năm trước |
| `ly_adr` | number | 198.00 | |
| `otb_rooms` | int | 180 | On-the-books tại thời điểm export |

Template mẫu: nút **"Download CSV template"** ngay trên trang Data (sinh đúng header + 2 dòng ví dụ). Đây cũng là hợp đồng dữ liệu giữa Phần 1 (ingest) và Phần 4 (dashboard) — đổi schema phải cập nhật cả hai + file này.

## Validate — hai lớp

**Lớp 1 — client-side (đã chạy trong UI, không cần backend):**
- Đúng đuôi `.csv`, đọc được, có dòng dữ liệu.
- Đủ 17 cột bắt buộc (thiếu cột nào báo đúng cột đó); cột thừa được liệt kê và bỏ qua.
- Tóm tắt trước khi Import: số dòng, khoảng ngày, danh sách property — người dùng xác nhận đúng file rồi mới nạp.

**Lớp 2 — server-side (Phần 1, khi backend nối vào):**
- Kiểu dữ liệu từng cột, occupancy ∈ [0,1], `rooms_sold ≤ rooms_available`.
- Liên tục ngày theo property (cảnh báo nếu thủng ngày); trùng khóa `date×property×segment×channel` → lấy bản mới nhất.
- Ghi log ingest: file, người/nguồn nạp, số dòng nhận/loại, thời điểm — hiển thị ngược lên bảng "Ingest status" của trang Data.

## Xử lý sự cố dữ liệu

| Tình huống | Hành vi hệ thống |
|---|---|
| 06:00 thiếu file của 1 property | Dashboard vẫn lên với 2 property còn lại; banner + dòng freshness ghi rõ property nào đang dùng dữ liệu cũ; alert cho admin |
| File sai schema | Từ chối cả file, không nạp nửa vời; lỗi hiển thị ở trang Data + log |
| Nạp lại cùng ngày (số điều chỉnh) | Upsert theo khóa — bản mới ghi đè, có log phiên bản |
| Backfill lịch sử | Cùng schema, một file nhiều ngày; khuyến nghị ≤ 1 năm/file |

## Trạng thái hiện tại

- Trang **Data** (`#data`): bảng ingest status (mock), dropzone + validate 17 cột client-side, template download, mô tả 2 phương án kết nối — **hoạt động được ngay, không cần backend**.
- Nút Import hiện dừng ở "Queued" (mock). Khi Phần 1 sẵn sàng: đổi 1 hàm trong `frontend/src/lib/api.js` để POST `/api/upload` — UI không đổi.
