# Hotel Daily Sample Data

The sample consists of four related CSV files:

data/sample/the_anam_daily_reservation_performance.csv

data/sample/the_anam_properties.csv

data/sample/the_anam_rooms.csv

data/sample/the_anam_daily_guest_flow.csv

Each row represents one property, one stay date, and one commercial slice defined by market segment, source, channel, and guest nationality. There are five commercial slices per property and date.

The property file contains one row per property. The locations provided by the user are Cam Ranh, Khanh Hoa; Mui Ne, Binh Thuan; and Ho Chi Minh City.

The room file contains one synthetic row per physical room. It joins to the other files through property and contains no reservation or guest identity.

The guest-flow file contains one row per property and date for operational staffing. It joins to the performance file using property and date. In this synthetic dataset, one in-house booking represents one occupied room.

The data is entirely synthetic and contains no guest names, booking references, emails, phone numbers, addresses, or other identifiable guest data.

The observed period is 2025-07-11 through 2026-07-11:

- Every row is an observed historical or present record.
- No date after 2026-07-11 is included.
- A forecast produced from this dataset should begin on 2026-07-12.
- OTB, pace, and pick-up are historical observations captured seven days before each stay date.
- Budget and last-year room nights are provided for every date.

## Daily Data Columns

| Column | Unit | Meaning |
| --- | --- | --- |
| date | YYYY-MM-DD | Hotel stay date |
| property | Text | Sample property name; joins to the property file |
| occupancy_pct | Percent | Room nights for this commercial slice divided by the property's rooms; the five slices sum to total property occupancy |
| adr_vnd | VND | Average daily rate for this commercial slice |
| revpar_vnd | VND | Revenue for this slice divided by the property's rooms; the five slices sum to total property RevPAR |
| room_nights | Count | Final sold room nights for this slice |
| revenue_vnd | VND | Final room revenue for this slice |
| booking_pace_pct | Percent | OTB seven days before arrival compared with the same lead time last year; 100 means equal pace |
| pickup_room_nights | Count | Net room nights added between eight and seven days before the stay date; this can be negative |
| market_segment | Text | Commercial segment such as Leisure, Corporate, Group_MICE, or Wholesale |
| source | Text | Where the booking originated, such as Hotel Website or Booking.com |
| channel | Text | Broad sales channel such as Direct, OTA, Corporate, or Wholesale |
| guest_nationality | Text | Synthetic nationality category with no guest identity |
| lead_time_days | Days | Average number of days between booking and stay date for this slice |
| cancellations | Count | Number of cancelled reservations attributed to the slice |
| budget_room_nights | Count | Budgeted room nights for the same property, date, and slice |
| last_year_room_nights | Count | Final room nights for the corresponding date one year earlier |
| on_the_books_room_nights | Count | Room nights recorded on the books seven days before the stay date |

## Property Data Columns

| Column | Unit | Meaning |
| --- | --- | --- |
| property | Text | Property name used to join with the daily data |
| city | Text | Synthetic sample city |
| province | Text | Synthetic sample province |
| country | Text | Country |
| property_type | Text | Broad hotel or resort type |
| room_count | Count | Total rooms used for occupancy and RevPAR calculations |
| currency | ISO currency | Reporting currency |
| timezone | IANA timezone | Property reporting timezone |

## Room Data Columns

| Column | Unit | Meaning |
| --- | --- | --- |
| property | Text | Property name used to join with the other files |
| room_id | Text | Synthetic unique room identifier |
| room_type | Text | Synthetic room category |
| floor | Count | Sample floor number |
| bed_type | Text | Primary bed configuration |
| max_guests | Count | Maximum sample guest capacity |
| size_sqm | Square metres | Sample room size |
| base_rate_vnd | VND | Synthetic base nightly rate before daily pricing adjustments |

## Daily Guest Flow Columns

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

## Direct Calculations

- Revenue equals room nights multiplied by ADR.
- Occupancy percent equals room nights divided by property room inventory, multiplied by 100.
- RevPAR equals revenue divided by property room inventory.
- Pick-up equals current OTB room nights less the previous daily report's OTB room nights.
