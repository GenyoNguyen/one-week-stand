# Demo Script — Cấu trúc bài trình bày cuối

> Thời lượng mục tiêu: **6 phút demo + 2 phút Q&A**. Đường click dưới đây đã được kiểm chứng end-to-end qua "judge dry-run" (review vòng 3–4, không dead end). Mọi con số nói to đều có nguồn thứ hai trên màn hình — cột "Nếu bị hỏi lại" là chỗ để trỏ vào.

## Chuẩn bị trước khi lên sân khấu

- [ ] `npm run dev --prefix frontend` chạy sẵn, mở `http://localhost:5173/#daily`, filter **All properties · vs Budget**
- [ ] Refresh trang để reset trạng thái Accept/Dismiss về ban đầu
- [ ] Máy chiếu 1280×860 hoặc 1920×1080 (cả hai đã kiểm tra không vỡ layout); demo chạy **offline được** (fonts self-host, mock data)
- [ ] Chuẩn bị 1 file CSV mẫu đúng schema + 1 file sai (thiếu cột) cho phần Data

## Mạch chuyện: "Từ 3 giờ ghép Excel → 10 phút quyết định"

### 0. Hook — vấn đề (30 giây, chưa mở dashboard)

> "Mỗi sáng, analyst của The Anam mất phần lớn buổi sáng ghép dữ liệu từ nhiều hệ thống rời rạc vào Excel — cho từng resort, lặp lại mỗi ngày. Insight đến muộn, forecast theo cảm tính và mỗi nơi một kiểu. Chúng tôi thay buổi sáng đó bằng 10 phút này."

### 1. Daily Overview — buổi giao ban sáng (90 giây)

| Làm | Nói | Nếu bị hỏi lại |
|---|---|---|
| Mở `#daily`, chỉ dòng freshness trên FilterBar | "06:00 sáng, dữ liệu ba resort đã tự tổng hợp xong." | Dòng "Data to 06:00 · PMS + CRS daily export" |
| Chỉ hero | "Cả portfolio đêm nay: RevPAR **$204**, cao hơn budget ~5%, hơn năm ngoái ~14–19% tùy chỉ số." | Hàng **Portfolio** cuối bảng: 91% · $224 · $204 — trùng từng số |
| Quét 4 KPI | "Occupancy **91%**, pickup 24h qua, doanh thu OTB 30 ngày — mỗi số đều kèm so sánh, không có số trần." | Delta ngay dưới mỗi KPI |
| Chỉ chart outlook | "30 ngày tới: đường đen là đã đặt, nét đứt là forecast kèm dải tin cậy 50/80% — chúng tôi trung thực về độ bất định." | "View as table" ngay dưới chart |

### 2. Alert → Hành động — cao trào (2 phút, tiêu chí thành công của track)

| Làm | Nói | Nếu bị hỏi lại |
|---|---|---|
| Chỉ "Needs attention", click card **"Pace 18% behind for stays 3–9 Aug"** | "Hệ thống không chỉ báo cáo — nó chỉ ra chỗ cần hành động. Tuần đầu tháng 8 ở Cam Ranh đang chậm hơn cùng kỳ **18%**." | Mở đúng alert đó, evidence sparkline pickup 14 ngày |
| Đọc Recommended action | "Đề xuất cụ thể: mở BAR khuyến mãi midweek 3–7/8 trên Brand.com và OTA, giữ giá cuối tuần. Ước tính **$38K** nếu pace về quỹ đạo năm ngoái." | Khối action viền xanh + impact |
| **Bấm Accept** | "Một click — việc được gán cho Revenue team. Đây chính là tiêu chí của đề bài: *đội ngũ hành động theo đề xuất, không chỉ đọc dashboard*." | Card chuyển "Accepted · sent to Revenue" trong Resolved today; subtitle đếm "1 accepted today" |
| Mở tiếp alert Mui Ne | "Spike hủy phòng: **114** room nights trong 7 ngày, gấp **2.6×** bình thường — Booking.com nhảy từ **8% lên 19%**." | Segments & channels: hàng Booking.com "19% (8%)"; Property view Mui Ne: KPI "114 rm · vs trailing norm (2.6×)" |

### 3. Forecast — một con số chung cho cả 3 resort (60 giây)

| Làm | Nói | Nếu bị hỏi lại |
|---|---|---|
| Sang `#forecast`, đổi 30d → 60d, hover crosshair | "Một forecast nhất quán theo ngày và theo resort — thay cho ba bảng đoán khác nhau. Hover là thấy OTB, forecast, dải tin cậy, budget từng ngày." | Bảng "Forecast detail by stay date" + "Show all 60 days" |
| Chỉ 1–2/9 trên chart/bảng | "Lễ 2/9 ở Nha Trang: đã đặt **92%**, forecast đóng ở **97%** → hệ thống đề xuất tăng BAR 12–15% và minimum stay 2 đêm — cơ hội, không chỉ rủi ro." | Alert "National Day compression" khớp đúng 92%→97% |

### 4. Property drill-down (45 giây)

| Làm | Nói |
|---|---|
| Về `#daily`, click hàng Cam Ranh trong bảng | "Từ tổng quan xuống chi tiết một click. Pace curve: màu là năm nay, xám là cùng kỳ — thấy ngay gap tuần đầu tháng 8 vừa nói. Heatmap là pickup 7 ngày theo ngày lưu trú." |

### 5. Data & triển khai — khép vòng (45 giây)

| Làm | Nói |
|---|---|
| Sang `#data`, kéo file CSV mẫu vào | "Dữ liệu vào bằng scheduled export mỗi sáng — không thao tác tay. Cần bổ sung thì kéo-thả: hệ thống validate **17 cột** tại chỗ, sai là chỉ đúng cột thiếu." (thả file lỗi nếu còn thời gian) |
| Câu chốt | "Stack tối giản — static frontend + FastAPI, một VM in-region là chạy, tuân thủ bảo vệ dữ liệu cá nhân VN vì chỉ nhận dữ liệu tổng hợp. Pilot 4 tuần." |

### 6. Kết (15 giây)

> "Buổi sáng của commercial team giờ bắt đầu bằng quyết định, không phải bằng Excel. Cảm ơn."

## Q&A dự kiến

| Câu hỏi | Trả lời + trỏ vào đâu |
|---|---|
| "Số này lấy đâu ra?" | Mọi số nói to có nguồn thứ hai: hàng Portfolio, bảng detail, channel table (đã liệt kê ở cột "Nếu bị hỏi lại") |
| "Forecast chính xác đến đâu?" | Dashboard hiển thị dải tin cậy thay vì một con số — trung thực về độ bất định; backtest thuộc Phần 2 (MiroFish) |
| "Dữ liệu thật chưa?" | Demo dùng mock cùng schema với export thật (17 cột — mở trang Data); mọi cấu phần UI giữ nguyên khi nối backend |
| "Bảo mật dữ liệu khách?" | Chỉ nhận dữ liệu tổng hợp/ẩn danh, quốc tịch mức ISO-2, hạ tầng in-region — xem `deployment_plan.md` |
| "Triển khai mất bao lâu?" | Pilot 1 property trong 4 tuần với 1 VM; go-live 3 properties tuần 5–8 |

## Phân vai đề xuất (nếu demo theo nhóm)

- 1 người nói (theo script) + 1 người cầm chuột (thuộc đường click) — tránh vừa nói vừa tìm nút.
- Tổng duyệt ít nhất 2 lần với đúng máy chiếu; lần cuối bấm giờ.
