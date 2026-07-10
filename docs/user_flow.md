# User Flow — Sử dụng hàng ngày

> Nguyên tắc thiết kế: mỗi view trả lời một câu hỏi nghiệp vụ. Người dùng không "khám phá dashboard" — họ đi theo thói quen buổi sáng đã có sẵn, chỉ là nhanh hơn Excel.

## Nhịp dữ liệu

```
05:30  PMS/CRS xuất file CSV hàng ngày → thư mục chia sẻ / SFTP
05:35  Ingest job (Phần 1) validate + nạp dữ liệu
05:45  Forecast (Phần 2) + Intelligence (Phần 3) chạy lại
06:00  Dashboard sẵn sàng — dòng "Data to 06:00" trên FilterBar xác nhận
```

Nếu 06:15 mà FilterBar vẫn hiện ngày hôm trước → dữ liệu chưa về, liên hệ admin (xem `deployment_plan.md`, mục giám sát).

## Flow 1 — Giao ban sáng của Revenue/Commercial Analyst (07:30, ~10 phút)

Đây là flow chính, thay thế 2–3 giờ ghép Excel mỗi sáng.

```
Mở dashboard (#daily)
 │  Đọc hero RevPAR tonight + delta vs Budget/LY   (30 giây: hôm nay tốt hay xấu?)
 │  Quét 4 KPI: Occupancy · ADR · Pickup 24h · Revenue OTB 30d
 │  Liếc "Occupancy outlook — next 30 days": có hố nào phía trước không?
 │
 ├─ Cột "Needs attention" (tối đa 3 cảnh báo nặng nhất)
 │   └─ Click một cảnh báo → mở ĐÚNG alert đó trong Alerts & actions
 │       │  Đọc evidence (sparkline) + Recommended action + impact
 │       ├─ Accept → tự gán owner (Revenue/Sales/Distribution/Reservations)
 │       │           → card chuyển "Resolved today", nói lại trong stand-up
 │       └─ Dismiss → nêu lý do miệng trong stand-up (Undo nếu bấm nhầm)
 │
 └─ Bảng "By property — tonight" + hàng Portfolio
     └─ Property nào lệch nhiều → click hàng → Property view (Flow 3)
```

**Kết thúc giao ban:** mọi alert trong queue đã Accept hoặc Dismiss. Câu đo thành công của track: *đội ngũ hành động theo đề xuất, không chỉ đọc dashboard.*

## Flow 2 — GM / Group Commercial lướt nhanh (bất kỳ lúc nào, ~2 phút)

```
#daily  → hero + 2 dòng delta là đủ trả lời "đêm nay thế nào?"
#forecast → fan chart: forward book so với budget; dải tin cậy hẹp = chắc chắn
#alerts → đếm "x accepted today" ở subtitle: đội có đang hành động không?
```

GM không cần thao tác gì — mọi con số nói to được đều có nguồn thứ hai trên màn hình (hàng Portfolio, bảng chi tiết) khi bị hỏi lại.

## Flow 3 — Revenue Manager đào sâu một property (khi có alert hoặc thứ Hai hàng tuần)

```
#property (từ drill-down hoặc chọn tab Cam Ranh / Mui Ne / Nha Trang)
 │  KPI row: Occ · ADR · Pickup 7d (vs pace needed) · Cancellations (vs norm)
 │  Booking pace curve: đường màu = năm nay, xám = cùng kỳ năm ngoái
 │     → đang nhanh hay chậm hơn LY? Gap ở đầu đường = tuần có vấn đề
 │  Pickup heatmap: ô đậm = ngày đang hút booking; hàng nhạt bất thường = soi
 │  Segment mix: cơ cấu OTB 30 ngày tới, legend có % chính xác
 └─ Quyết định rate/inventory → thực hiện trong RMS/PMS (ngoài hệ thống này)
```

## Flow 4 — Reservations/Distribution khi có biến động kênh

```
#segments
 │  Bảng "By channel": cột "Cxl rate (prev)" — số đỏ đậm = spike
 │  Ví dụ demo: Booking.com 19% (8%) ← đúng con số alert Mui Ne trích dẫn
 │  Segment mix theo property + "View as table"
 └─ Top source markets: thị trường nào tăng/giảm vs LY (KR +34%...)
```

## Flow 5 — Operations lập kế hoạch nhân sự (chiều, cho tuần tới)

```
#forecast → chọn 30d → đọc bảng "Forecast detail by stay date"
   Cột Forecast + 80% band theo từng ngày = số phòng dự kiến để xếp ca
   Cuối tuần (nền đậm) và ngày lễ nổi bật ngay trong bảng
```

## Flow 6 — Nạp dữ liệu (admin / analyst, khi cần)

```
#data
 │  Bảng "Ingest status": 3 property × lần nhận cuối × số dòng × trạng thái
 ├─ Bình thường: không phải làm gì (scheduled export tự chạy)
 └─ Bất thường / bổ sung: kéo-thả CSV vào "Manual upload"
     → validate tại chỗ (17 cột bắt buộc, khoảng ngày, property)
     → Ready → Import;  lỗi → báo đúng cột thiếu, tải template mẫu
```

Chi tiết schema và các phương án kết nối: `data_upload_plan.md`.

## Vòng đời một cảnh báo

```
Intelligence (Phần 3) sinh alert ──▶ Queue (#alerts, xếp theo Risk > Watch > Opportunity)
        │ hiện tối đa 3 trên #daily "Needs attention"
        ▼
   Analyst mở (1 card một lúc — progressive disclosure)
        ├─ Accept  ──▶ "Resolved today" + gán owner ──▶ nhắc lại trong stand-up
        └─ Dismiss ──▶ "Resolved today" (kèm lý do miệng)
              └─ Undo bất kỳ lúc nào trong ngày → quay lại queue
```

Trạng thái accept/dismiss hiện lưu trong phiên (mock). Khi backend nối vào, trạng thái + owner + timestamp sẽ ghi qua API để làm báo cáo "acted on" hàng tuần — đúng tiêu chí thành công của track.
