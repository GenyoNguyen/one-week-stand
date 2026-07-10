# Deployment Plan

> Yêu cầu từ đề bài: cloud hoặc hybrid đều chấp nhận, không bắt buộc on-premise, ưu tiên cloud phổ biến để dễ hỗ trợ. Không dùng dữ liệu khách thật trong giai đoạn build; pilot trên dữ liệu thật cần tuân thủ bảo vệ dữ liệu cá nhân Việt Nam và giữ dữ liệu trong khu vực.

## Kiến trúc tổng thể

```
PMS / CRS (Opera, SynXis...)
   │  export CSV hàng ngày 05:30 (SFTP / shared folder)   ← Giai đoạn 1
   │  (API connector trực tiếp                             ← Giai đoạn 3)
   ▼
Ingest service (Phần 1 — FastAPI job): validate schema 17 cột → làm sạch → lưu
   ▼
Forecast engine (Phần 2 — MiroFish) + Intelligence (Phần 3 — alerts/recommendations)
   ▼
REST API (FastAPI): /kpis /forecast /alerts /recommendations /upload
   ▼
Dashboard (Phần 4 — Svelte, static build ~500KB kể cả fonts self-host)
```

Frontend là static files — không có secret, không gọi dịch vụ ngoài (fonts đã self-host), chỉ nói chuyện với API qua một origin.

## Ba giai đoạn triển khai

### Giai đoạn 0 — Demo hackathon (hiện tại)
- Chạy local: `npm run dev --prefix frontend` (mock data, offline được).
- Không cần hạ tầng. Đây là trạng thái đã được review sign-off 27/27.

### Giai đoạn 1 — Pilot 1 property (tuần 1–4 sau hackathon)
- **Hạ tầng:** 1 VM nhỏ (2 vCPU / 4GB) chạy Docker Compose: `nginx` (serve static + reverse proxy) + `api` (FastAPI) + `postgres`. Một máy là đủ cho 3 properties × vài năm dữ liệu daily.
- **Region:** ưu tiên trong nước (VNG Cloud, FPT Cloud, Viettel Cloud) hoặc AWS `ap-southeast-1` (Singapore) nếu tập đoàn đã có sẵn — thỏa yêu cầu "data remaining in-region would be preferred".
- **Dữ liệu vào:** scheduled CSV export qua SFTP 05:30 (không đụng hệ thống PMS production). Upload tay qua trang Data làm đường dự phòng.
- **Truy cập:** HTTPS + SSO của tập đoàn (hoặc basic auth cho pilot); chỉ mạng nội bộ/VPN.

### Giai đoạn 2 — Cả 3 properties + go-live (tuần 5–8)
- Bật đủ 3 nguồn export; backfill 2 năm lịch sử để pace/LY chính xác.
- Đào tạo: 1 buổi 45 phút cho commercial team (đi theo `user_flow.md`), 15 phút cho GM.
- Chạy song song với quy trình Excel 2 tuần → so số → cắt Excel.

### Giai đoạn 3 — Connector trực tiếp (sau pilot, tùy chọn)
- API pull từ Opera Cloud / SynXis thay file export. Schema không đổi nên dashboard và forecast không phải sửa.

## Tuân thủ & bảo mật dữ liệu

| Yêu cầu | Cách đáp ứng |
|---|---|
| Không dữ liệu khách thật khi build | Toàn bộ build/demo dùng mock + sample ẩn danh |
| Nghị định 13/2023/NĐ-CP (PDPD) | Pilot chỉ nhận dữ liệu đã tổng hợp/ẩn danh: không tên khách, không số phòng, không liên lạc. `guest_nationality` giữ ở mức quốc tịch (không định danh) |
| Dữ liệu trong khu vực | Region VN/SG như trên; không dịch vụ SaaS thứ ba nhận dữ liệu |
| Phân quyền | Pilot: 1 role xem tất; go-live: role theo property nếu tập đoàn yêu cầu |

## Vận hành & giám sát

- **Health:** `GET /api/health` + uptime ping 5 phút/lần.
- **Ingest guard:** nếu 06:00 chưa nhận đủ 3 file → email/Zalo cho admin + banner trên dashboard hiện dữ liệu cũ kèm ngày (không bao giờ hiện số cũ như số mới — nguyên tắc data freshness).
- **Backup:** pg_dump hàng đêm, giữ 30 ngày. Dữ liệu gốc là file export nên luôn re-ingest lại được.
- **Rollback:** static frontend + docker tag theo version — rollback = đổi tag, <5 phút.

## Chi phí ước tính (pilot)

1 VM 4GB in-region ≈ $25–40/tháng + domain/TLS. Không phí license — toàn bộ stack open-source.
