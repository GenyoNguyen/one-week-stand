# Hotel Daily Sample Data

The sample consists of four related CSV files:

```
data/sample/the_anam_daily_reservation_performance.csv
data/sample/the_anam_properties.csv
data/sample/the_anam_rooms.csv
data/sample/the_anam_daily_guest_flow.csv
```

Each row in the performance file represents one property, one stay date, and one commercial slice defined by market segment, source, channel, and guest nationality. There are five commercial slices per property and date.

The property file contains one row per property. The three properties are The Anam Cam Ranh (ACR), The Anam Mui Ne (AMN), and The Anam Nha Trang (ANT).

The room file contains one synthetic row per physical room. It joins to the other files through property and contains no reservation or guest identity.

The guest-flow file contains one row per property and date for operational staffing. It joins to the performance file using property and date. In this synthetic dataset, one in-house booking represents one occupied room.

The data is entirely synthetic and contains no guest names, booking references, emails, phone numbers, addresses, or other identifiable guest data.

## Date range

The observed period is 2025-07-11 through 2026-10-09:

- Rows through 2026-07-11 are observed historical or present records.
- Rows from 2026-07-12 onward are forward-looking on-the-books data for forecasting.
- A forecast produced from this dataset begins on 2026-07-12.
- OTB, pace, and pick-up are historical observations captured seven days before each stay date.
- Budget and last-year room nights are provided for every date.
- Three alert-able "story" scenarios are embedded in the data for demo purposes (see Story Injections below).

## Daily Data Columns (22 columns)

| Column | Unit | Meaning |
| --- | --- | --- |
| date | YYYY-MM-DD | Hotel stay date |
| property | Code | Property code: ACR, AMN, or ANT; joins to the property file |
| occupancy_pct | Percent (0–100) | Room nights for this commercial slice divided by the property's rooms; the five slices sum to total property occupancy |
| adr_vnd | VND | Average daily rate for this commercial slice |
| revpar_vnd | VND | Revenue for this slice divided by the property's rooms; the five slices sum to total property RevPAR |
| room_nights | Count | Final sold room nights for this slice (past) or on-the-books (future) |
| revenue_vnd | VND | Final room revenue for this slice |
| booking_pace_pct | Percent | OTB seven days before arrival compared with the same lead time last year; 100 means equal pace, below 100 means behind |
| pickup_room_nights | Count | Net room nights added between eight and seven days before the stay date; can be negative |
| pickup_24h_room_nights | Count | Net room nights added in the last 24 hours; approximately 1/7 of the 7-day pickup |
| market_segment | Text | Commercial segment: Direct, OTA, Corporate, Group, or Wholesale |
| source | Text | Booking source: Brand.com, Booking.com, GDS, Voice / email, or Travel agents |
| channel | Text | Distribution channel matching the source value |
| guest_nationality | Text | Synthetic nationality category with no guest identity |
| lead_time_days | Days | Average number of days between booking and stay date for this slice |
| cancellations | Count | Number of cancelled reservations attributed to the slice |
| budget_room_nights | Count | Budgeted room nights for the same property, date, and slice |
| budget_adr_vnd | VND | Budgeted ADR for the same property, date, and slice |
| last_year_room_nights | Count | Final room nights for the corresponding date one year earlier |
| ly_adr_vnd | VND | ADR for the corresponding date one year earlier |
| on_the_books_room_nights | Count | Room nights recorded on the books seven days before the stay date |
| stly_otb_room_nights | Count | Same-time-last-year on-the-books room nights; used for pace comparison |

## Property Data Columns

| Column | Unit | Meaning |
| --- | --- | --- |
| property | Code | Property code: ACR, AMN, or ANT |
| city | Text | Property city |
| province | Text | Property province |
| country | Text | Country (Vietnam) |
| property_type | Text | Resort or hotel type |
| room_count | Count | Total rooms used for occupancy and RevPAR calculations |
| currency | ISO currency | Reporting currency (VND) |
| timezone | IANA timezone | Property reporting timezone (Asia/Ho_Chi_Minh) |

## Room Data Columns

| Column | Unit | Meaning |
| --- | --- | --- |
| property | Code | Property code: ACR, AMN, or ANT |
| room_id | Text | Synthetic unique room identifier (e.g., ANAM-ACR-001) |
| room_type | Text | Room category: Deluxe King, Deluxe Twin, Suite, or Villa |
| floor | Count | Floor number |
| bed_type | Text | Primary bed configuration: King or Twin |
| max_guests | Count | Maximum guest capacity |
| size_sqm | Square metres | Room size |
| base_rate_vnd | VND | Synthetic base nightly rate before daily pricing adjustments |

## Daily Guest Flow Columns

| Column | Unit | Meaning |
| --- | --- | --- |
| date | YYYY-MM-DD | Observed hotel date |
| property | Code | Property code: ACR, AMN, or ANT |
| bookings_checking_in | Count | Bookings arriving on the date |
| bookings_staying | Count | In-house bookings occupying rooms on the date |
| bookings_checking_out | Count | Bookings departing on the date |
| guests_checking_in | Count | Guests arriving on the date |
| guests_staying | Count | Total in-house guests on the date |
| guests_checking_out | Count | Guests departing on the date |
| staffing_status | Category | Synthetic label: Under-deployed, Right amount, or Over-deployed |

## Story Injections

Three commercial scenarios are embedded in the data to support the demo's alert and recommendation flows:

1. **Cam Ranh pace gap (Aug 3–9, 2026):** On-the-books for Direct and OTA segments is set to ~82% of same-time-last-year, producing a pace_pct around 82. This triggers a "Pace behind" risk alert.

2. **Mui Ne cancellation spike (Jul 11 – Aug 10, 2026):** OTA segment cancellations are inflated to ~2.3× above baseline for AMN. This triggers a "Cancellation spike" risk alert.

3. **Nha Trang National Day compression (Sep 1–2, 2026):** OTB across all segments is set to ~92% of room inventory for ANT. This triggers an "Opportunity" alert for rate increases.

## Direct Calculations

- Revenue equals room nights multiplied by ADR.
- Occupancy percent equals room nights divided by property room inventory, multiplied by 100.
- RevPAR equals revenue divided by property room inventory.
- Booking pace percent equals (current OTB / same-time-last-year OTB) × 100.

| Column | Unit | Meaning |
| --- | --- | --- |
| date | YYYY-MM-DD | Observed hotel date |
| property | Text | Property name used to join with the other files |
| bookings_checking_in | Count | Bookings arriving on the date |
| bookings_staying | Count | In-house bookings occupying rooms on the date |
| bookings_checking_out | Count | Bookings departing on the date |
| guests_checking_in | Count | Guests arriving on the date |
| guests_staying | Count | Total in-house guests on the date |
| guests_checking_out | Count | Guests departing on the date |
| staffing_status | Category | Synthetic label: Under-deployed, Right amount, or Over-deployed |

The staffing label is generated from a nonlinear workload score using in-house guests, guest turnover, booking turnover, property size, and weekend pressure. Small deterministic noise is added before applying the three label thresholds. It is intended as sample training data, not as a real staffing policy.

## Schema Mapping (upload plan ↔ canonical)

The internal canonical schema uses 22 columns. The external upload plan (`data_upload_plan.md`) uses 17 columns. The `data_cleaner.py` service handles bidirectional mapping:

| Upload plan column | Canonical column | Direction |
| --- | --- | --- |
| `date` | `date` | same |
| `property` | `property` | same |
| `rooms_available` | (derived from property file) | upload → compute |
| `rooms_sold` | `room_nights` | rename |
| `room_revenue` | `revenue_vnd` | rename |
| `adr` | `adr_vnd` | rename |
| `occupancy` (0–1) | `occupancy_pct` (0–100) | scale × 100 |
| `market_segment` | `market_segment` | same |
| `channel` | `source` | rename |
| `guest_nationality` | `guest_nationality` | same |
| `lead_time_days` | `lead_time_days` | same |
| `cancellations` | `cancellations` | same |
| `budget_occupancy` | `budget_room_nights` | convert via room_count |
| `budget_adr` | `budget_adr_vnd` | rename |
| `ly_occupancy` | `last_year_room_nights` | convert via room_count |
| `ly_adr` | `ly_adr_vnd` | rename |
| `otb_rooms` | `on_the_books_room_nights` | rename |
| — (not in upload plan) | `revpar_vnd` | derived |
| — (not in upload plan) | `booking_pace_pct` | derived from OTB |
| — (not in upload plan) | `pickup_room_nights` | derived from OTB deltas |
| — (not in upload plan) | `pickup_24h_room_nights` | derived |
| — (not in upload plan) | `source` | upload plan uses `channel` for this |
| — (not in upload plan) | `channel` | canonical keeps both |
| — (not in upload plan) | `stly_otb_room_nights` | derived from LY OTB |

## Direct Calculations

- Revenue equals room nights multiplied by ADR.
- Occupancy percent equals room nights divided by property room inventory, multiplied by 100.
- RevPAR equals revenue divided by property room inventory.
- Pick-up equals current OTB room nights less the previous daily report's OTB room nights.
