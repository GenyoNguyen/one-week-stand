# Kế hoạch Phần 4 — Dashboard, UX & Triển khai

> Track: [Commercial Intelligence & Demand Forecasting](https://aitalent.genaifund.ai/tracks/retail-hospitality/commercial-demand)
> Mục tiêu quan trọng nhất: **thân thiện với người dùng vận hành hàng ngày** và **không trông như AI code**.

---

## 1. Yêu cầu (từ kế hoạch chung)

Dashboard phải có:

| Nhóm | Yêu cầu |
|---|---|
| Views | Daily Overview · Demand Forecast · Property View · Segment/Channel View · Alerts & Recommendations |
| KPIs | Occupancy, ADR, RevPAR, room nights, revenue, pickup/pace |
| So sánh | vs Budget · vs Last Year (LY) · vs On-the-books (OTB) |
| Intelligence | Cảnh báo rủi ro/cơ hội + đề xuất hành động (từ Phần 3) |
| Bàn giao | User flow, deployment plan, data upload plan, cấu trúc demo |

Tiêu chí thành công của track: *"teams acting on the system's recommendation, not merely reading its dashboard"* → view Alerts & Recommendations phải là điểm nhấn demo, không phải phần phụ.

**Bối cảnh khách hàng (từ track):** The Anam — tập đoàn resort 3 cơ sở tại Việt Nam. Hiện tại analyst mất cả buổi sáng ghép Excel từ nhiều hệ thống rời rạc. Người dùng là **commercial/revenue/reservations, operations và GM — không rành kỹ thuật**; track ghi rõ *"a clear interface matters more than any particular stack"*. UI dùng tiếng Anh (ngôn ngữ làm việc của The Anam), copy có thể localize sau.

---

## 2. Kết quả research

### 2.1. Các RMS thực tế làm gì (IDeaS G3, Duetto, Lighthouse)

- **IDeaS G3**: trang "At A Glance" với KPI có mã màu dễ đọc; "Information Manager" gom cảnh báo quan trọng lên đầu; module Business Analysis cho drill-down theo pace, lead time, nguồn booking, phân khúc.
- **Duetto**: tách sản phẩm theo việc — pricing (GameChanger) riêng, reporting (ScoreBoard) riêng. Mỗi màn hình trả lời một câu hỏi.
- **Lighthouse/RevControl**: có "Pick-Up Alert" — theo dõi pace và bắn cảnh báo khi lệch nhịp.
- **Dashboard RM tối thiểu** (chuẩn ngành): OCC/ADR/RevPAR vs LY; pace 30/60/90 ngày tới vs LY; channel mix; cancellation rate theo kênh.

**Bài học:** người làm revenue quen đọc *bảng số dày đặc* + *đường pace* + *cảnh báo lệch nhịp*. Dashboard giống công cụ họ đã dùng → cảm giác "thật". Dashboard toàn card bo tròn với gradient → cảm giác "demo AI".

### 2.2. Dashboard hiện đại được đánh giá cao (Stripe, Linear, Mercury)

- **Kiềm chế**: 5–9 thành phần chính mỗi view, "north star metric" đặt trước, mọi thứ khác cách 1 click.
- **Stripe**: mở đầu bằng 1 con số + 1 chart; màu cực tiết chế (xanh = thành công, đỏ *chỉ* cho thất bại).
- **Linear**: bảng dày nhưng "tĩnh" — hairline borders, không shadow, số tabular thẳng cột.

### 2.3. Trực quan hóa forecast

- **Fan chart / dải tin cậy**: đường trung tâm + dải 50%/80% với các bước opacity rời rạc (không gradient liên tục). Hiển thị *khoảng*, không phải *điểm* — trung thực về độ bất định.
- Luôn kèm bảng số làm fallback (accessibility + thói quen người làm revenue).

### 2.4. Vì sao UI do AI làm trông "AI" (và cách né)

Nguyên nhân: model hội tụ về mẫu phổ biến nhất trong training data ("distributional convergence"). Dấu hiệu nhận biết đã thành meme:

| Dấu hiệu "AI slop" | Thay bằng |
|---|---|
| Font Inter/Roboto/system | Font có chủ đích, pairing tương phản cao |
| Gradient tím-xanh trên nền trắng | 1 màu chủ đạo + accent sắc nét |
| Card grid đều tăm tắp, bo góc 16px, shadow mọi nơi | Layout bất đối xứng, hairline border, mật độ thay đổi theo tầm quan trọng |
| Emoji làm icon, microcopy chung chung | Icon line 1 style, copy nghiệp vụ cụ thể |
| Palette dàn đều, màu trang trí | Màu chỉ mang nghĩa (status/series), còn lại là mực + giấy |

Nguồn chính: [Claude cookbook — Prompting for frontend aesthetics](https://platform.claude.com/cookbook/coding-prompting-for-frontend-aesthetics), [AI Slop Web Design Guide](https://www.925studios.co/blog/ai-slop-web-design-guide).

---

## 3. Định hướng thiết kế

**Concept: "Sổ tay giao ban buổi sáng của revenue team" (morning briefing ledger).**
Trông như công cụ nội bộ mà một tập đoàn khách sạn đã dùng 5 năm: hơi editorial, mật độ thông tin cao nhưng bình tĩnh, mọi con số có ngữ cảnh so sánh. Không phải landing page SaaS.

### 3.1. Typography (đều hỗ trợ tiếng Việt trên Google Fonts)

| Vai trò | Font | Ghi chú |
|---|---|---|
| Display (tiêu đề view, hero number) | **Fraunces** (serif, optical size) | Chất editorial/hospitality, khác biệt ngay lập tức |
| UI & body | **IBM Plex Sans** | Kỹ thuật, chuyên nghiệp, không phải Inter |
| Số liệu trong bảng/KPI | IBM Plex Sans + `font-feature-settings: "tnum"` (hoặc IBM Plex Mono cho mã/ID) | Số tabular thẳng cột — dấu hiệu "người thật làm" |

Nguyên tắc pairing: nhảy cỡ ≥3x giữa hero và body; đậm nhạt tương phản mạnh (weight 300 vs 700), không dùng 400 vs 600.

### 3.2. Màu sắc (đã chạy validator của dataviz skill — PASS cả 4 checks)

- **Nền**: giấy ấm `#FAF8F5`, panel `#FFFFFF`, hairline `#E5E1DA`. Mực `#1A1A18`, chữ phụ `#6B6862`.
- **Categorical** (3 properties, segments, channels) — đã validate CVD-safe, thứ tự cố định, không xoay vòng:
  `#0B8A76` teal (kiêm màu brand/accent) · `#C2540A` cam đất · `#2E62B8` xanh dương · `#A03A6B` hồng đậm · `#5F8321` ô liu · `#7A52C7` tím
- **Status (chỉ dùng cho cảnh báo, không tái dùng làm series)**: good/warning/serious/critical, luôn kèm icon + label, không bao giờ chỉ dựa màu.
- **Sequential** (heatmap pickup): 1 hue teal, nhạt→đậm.
- **Diverging** (Δ vs budget/LY): teal ↔ cam đất, midpoint xám trung tính.
- Khi chốt surface cuối cùng, chạy lại: `node scripts/validate_palette.js "<hexes>" --mode light` (dataviz skill).

### 3.3. Layout & chi tiết "người thật"

- Sidebar trái hẹp (icon + label) cho 5 views; **FilterBar cố định 1 hàng trên cùng**: khoảng ngày, property, segment, channel + toggle so sánh `Budget / LY / OTB`.
- Bất đối xứng có chủ đích: hero number + chart chính chiếm ~2/3, cột phụ 1/3 cho alerts/notes.
- Hairline borders thay cho shadow; bo góc nhỏ (2–4px) và *không đồng nhất mọi nơi*.
- Footer mỗi view: `Dữ liệu đến hết 09/07 · cập nhật 06:00 · nguồn: PMS export` — dòng data-freshness là chi tiết mọi công cụ nội bộ thật đều có.
- Số âm/dương trong bảng: `▲ +4.2%` / `▼ −1.8%` bằng ký tự + màu, căn phải, tabular.
- Empty state và loading skeleton viết copy nghiệp vụ thật ("Chưa có dữ liệu OTB cho khoảng ngày này — tải file lên ở mục Data"), không lorem, **không emoji**.
- Micro-interaction: 1 lần stagger reveal khi load view (CSS animation-delay), hover crosshair trên chart. Không rải animation lung tung.

### 3.4. Bộ quy tắc UI thân thiện người dùng (ĐÃ CHỐT — soát mỗi PR)

Đúc kết từ NN/g heuristics, cognitive load theory và dashboard UX research; áp cho người dùng thương mại không rành kỹ thuật:

1. **Mỗi view = 1 câu hỏi nghiệp vụ.** Daily Overview trả lời "sáng nay có gì cần chú ý?", Forecast trả lời "phía trước ra sao?". Không trộn câu hỏi.
2. **≤7 thành phần cạnh tranh above the fold; 3–5 KPI quan trọng nhất trên cùng.** Người dùng scan theo Z-pattern và bỏ màn hình quá tải — cognitive load là lý do số 1 dashboard bị bỏ xó, không phải thẩm mỹ.
3. **Progressive disclosure 3 tầng: Summary → Context → Details.** KPI trên cùng, chart giữa, bảng chi tiết sau 1 click/expand. Không bày hết mọi thứ một lúc.
4. **Không có con số "trần".** Mọi số đều có đơn vị + so sánh (vs Budget / LY / OTB) + chiều hướng. Một con số không có ngữ cảnh là một câu hỏi chưa trả lời.
5. **Ngôn ngữ nghiệp vụ, đúng thuật ngữ họ đang dùng trong Excel:** occupancy, ADR, RevPAR, pick-up, pace, OTB. Không jargon kỹ thuật, không viết tắt tự chế.
6. **Trạng thái hệ thống luôn hiện rõ** (NN/g #1): dòng data freshness ở mọi view, loading skeleton, empty state có chỉ dẫn hành động tiếp theo.
7. **Recognition over recall** (NN/g #6): filter là preset pills và dropdown (Next 30/60/90 days, tên property), không bắt gõ; so sánh là toggle, không phải cấu hình.
8. **Mỗi cảnh báo đi kèm 1 hành động đề xuất + nút thao tác.** Người dùng quyết định, không phải suy diễn. Đây cũng chính là tiêu chí thành công của track.
9. **Glanceable:** câu trả lời chính của view đọc được trong 5 giây, kể cả từ xa (GM lướt điện thoại, máy chiếu khi demo). Hero number to, số tabular.
10. **Functional minimalism nhưng không loãng:** bỏ mọi trang trí không mang thông tin; giữ mật độ đủ cho analyst làm việc thật (dense-but-calm kiểu Linear).

---

## 4. Spec từng view

### V1 — Daily Overview (màn hình mở đầu, trả lời "sáng nay cần nhìn gì?")
- **Hero**: RevPAR toàn portfolio hôm nay (Fraunces ≥48px) + delta vs budget/LY.
- **KPI row** (stat tiles, không phải bar chart): Occupancy · ADR · Room nights · Revenue · Pickup 24h — mỗi tile: giá trị + delta + sparkline 14 ngày.
- **Chart chính**: OTB 28 ngày tới theo ngày (cột), overlay đường forecast + đường budget.
- **Cột phụ**: 3 alert nghiêm trọng nhất (link sang V5) + bảng mini 3 properties (Occ/ADR/RevPAR + delta).

> **Quyết định scope (sau review vòng 1):** so sánh "vs OTB" không phải là toggle toàn cục — OTB là *nền* của mọi view forward, nên nó thể hiện bằng đường OTB trên mọi chart + cột "Gap to forecast" trong bảng V2. Toggle toàn cục chỉ có Budget/LY.

### V2 — Demand Forecast
- **Fan chart** 30/60/90 ngày: đường forecast trung tâm, dải tin cậy 80%/50% (2 bước opacity rời rạc), OTB thực tế là đường liền đến hôm nay, forecast nét đứt từ hôm nay.
- Small multiples 3 properties (cùng 1 trục y — tuyệt đối không dual-axis).
- Bảng: ngày × {forecast, OTB, budget, LY, pickup cần thêm} — fallback dạng số cho mọi chart.

### V3 — Property View (chọn 1 trong 3 cơ sở)
- **Pace curve** (dạng *emphasis*): đường booking curve năm nay màu accent, cùng-kỳ-năm-ngoái màu xám — trả lời "đang nhanh hay chậm hơn LY?".
- **Pickup heatmap**: ngày lưu trú × tuần lead time, sequential 1 hue.
- Segment mix dạng donut (cung tách khe, bo góc, tâm hiện tổng OTB; đổi từ stacked bar theo yêu cầu owner 11/07) + KPI row của property đó.

### V4 — Segment / Channel View
- Donut chart cho mix theo từng property (5 segment, gap + bo góc, legend chung, bảng số fallback giữ nguyên; đổi từ stacked bar theo yêu cầu owner 11/07).
- Đường trend theo segment (≤6 đường, direct label, legend luôn có).
- Bảng channel: room nights, revenue, ADR, **cancellation rate**, delta vs LY.

### V5 — Alerts & Recommendations (điểm nhấn demo)
- Feed cảnh báo theo mức độ (icon + label, không chỉ màu): "Pace HN-01 tuần 32 chậm hơn LY 18%".
- Mỗi alert mở ra: **evidence** (sparkline/mini chart lấy đúng dữ liệu gây cảnh báo) + **đề xuất hành động** (từ Phần 3) + nút `Chấp nhận / Bỏ qua` với trạng thái lưu lại — demo được "team acts on recommendation".

---

## 5. Quy tắc chart (theo dataviz skill — bắt buộc)

1. Chọn *form* trước, màu sau: 1 con số → stat tile, không phải chart 1 cột.
2. Một trục y duy nhất — không bao giờ dual-axis; 2 thang đo khác nhau → 2 chart hoặc small multiples.
3. Màu theo *entity* cố định (Property A luôn teal ở mọi view), filter không được "dồn màu" lại.
4. ≥2 series luôn có legend; ≤4 series direct-label; text luôn màu mực, không nhuộm màu series.
5. Marks mảnh: line 2px, khoảng hở 2px giữa các segment stacked; grid/axes chìm.
6. Mọi chart có hover tooltip + crosshair; mọi chart có bảng số tương ứng.
7. Trước khi merge: chạy `validate_palette.js`, screenshot từng view soát label đè nhau/tràn khung.

---

## 6. Tech stack & cấu trúc

- **Svelte + Vite** (scaffold đã có, nhẹ, nhanh — hợp hackathon).
- **Chart: SVG tự dựng trong component Svelte + `d3-scale`/`d3-shape`/`d3-array`** (không dùng Chart.js/ECharts nguyên bản — look mặc định của chúng nhận ra ngay là template; SVG tự dựng cho kiểm soát 100% mark specs ở mục 5).
- Fonts self-host (tải woff2 về `frontend/public/fonts/`) — demo không phụ thuộc mạng.
- `src/lib/api.js`: gọi FastAPI backend (`/kpis`, `/forecast`, `/alerts`, `/recommendations`, `/upload`) + **mock data fallback từ JSON tĩnh** để frontend chạy demo được kể cả khi backend/Phần 2-3 chưa xong — giảm rủi ro phụ thuộc chéo trong tuần hackathon.
- `src/lib/constants.js`: design tokens (palette đã validate, spacing, thứ tự màu categorical) — một nguồn duy nhất.
- `src/lib/formatters.js`: format tiền VND/USD, %, ngày `Thg 7 10`, delta ▲▼ — dùng thống nhất mọi nơi.

---

## 7. Thứ tự build (7 ngày)

| Ngày | Việc | Kết quả kiểm chứng |
|---|---|---|
| 1 | Design tokens (`app.css`), fonts, shell layout + sidebar + FilterBar, `api.js` với mock data | Chạy `npm run dev`, shell hiển thị đúng 2 font, palette đúng token |
| 2 | `KpiCard` (stat tile + sparkline + delta) → **V1 Daily Overview** hoàn chỉnh | V1 đọc được trong 5 giây: hero → KPI → alerts |
| 3 | `ForecastChart` (fan chart + crosshair tooltip) → **V2 Demand Forecast** | Dải tin cậy đúng 2 bước opacity, bảng số khớp chart |
| 4 | Pace curve + pickup heatmap → **V3 Property**; stacked bars → **V4 Segment/Channel** | Màu property cố định xuyên view; heatmap 1 hue |
| 5 | **V5 Alerts & Recommendations** (evidence + accept/dismiss) + trang Upload data | Click accept → trạng thái đổi, demo được flow hành động |
| 6 | Polish: empty/loading states, footer freshness, stagger reveal, soát ở 1366×768 & 1920×1080 (máy chiếu) | Screenshot 5 views, đối chiếu checklist mục 8 |
| 7 | Viết `user_flow.md`, `deployment_plan.md`, `data_upload_plan.md`, `demo_script.md`; tổng duyệt demo | Chạy demo end-to-end 1 mạch không lỗi |

Ghi chú: các file docs trên đã có sẵn (rỗng) trong `docs/` — đều thuộc deliverables Phần 4.

---

## 8. Checklist "không trông như AI code" (soát trước khi nộp)

- [ ] Không Inter/Roboto/system font; Fraunces + IBM Plex Sans load đúng (kể cả tiếng Việt có dấu)
- [ ] Không gradient tím; không shadow mặc định; bo góc ≤4px
- [ ] Không emoji ở bất kỳ đâu trong UI; icon 1 bộ duy nhất (Lucide, stroke 1.5px)
- [ ] Không card grid đều nhau — layout có hierarchy 2/3–1/3
- [ ] Mọi con số: tabular, căn phải, có đơn vị, có ngữ cảnh so sánh (vs budget/LY/OTB)
- [ ] Copy nghiệp vụ cụ thể (tên property thật trong data, số thật) — không placeholder
- [ ] Dòng data-freshness luôn hiển thị (đặt ở FilterBar sticky — mọi view đều thấy; quyết định sau review vòng 1: sticky bar tốt hơn footer vì không phải cuộn xuống)
- [ ] Palette pass `validate_palette.js` (light mode, surface cuối cùng)
- [ ] Không dual-axis; màu series cố định xuyên views
- [ ] Demo chạy offline được (fonts self-host, mock data fallback)

---

## 9. Deliverables Phần 4 (khớp kế hoạch chung)

1. Dashboard hoạt động (5 views) — `frontend/`
2. User flow sử dụng hàng ngày — `docs/user_flow.md`
3. Deployment plan — `docs/deployment_plan.md`
4. Data upload/connect plan — `docs/data_upload_plan.md` (+ trang Upload trong UI)
5. Cấu trúc bài demo cuối — `docs/demo_script.md` (mở bằng V1 morning briefing → V2 forecast → V5 alert → accept recommendation → close bằng deployment slide)
