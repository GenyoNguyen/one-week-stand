# Hotel Daily Sample Data

The sample consists of three related CSV files:

data/sample/the_anam_daily_reservation_performance.csv

data/sample/the_anam_properties.csv

data/sample/the_anam_rooms.csv

Each row represents one property, one stay date, and one commercial slice defined by market segment, source, channel, and guest nationality. There are five commercial slices per property and date.

The property file contains one row per property. Cam Ranh, Khanh Hoa and Mui Ne, Binh Thuan were provided by the user. The Anam 3 remains marked TBD instead of assigning an unsupported location.

The room file contains one synthetic row per physical room. It joins to the other files through property and contains no reservation or guest identity.

The data is entirely synthetic and contains no guest names, booking references, emails, phone numbers, addresses, or other identifiable guest data.

The synthetic reporting date is 2026-07-11:

- Dates before 2026-07-11 contain finalized performance values.
- Dates from 2026-07-11 onward contain on-the-books, pace, and pick-up values.
- Budget and last-year room nights are provided for all dates.

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
| booking_pace_pct | Percent | Current OTB pace compared with the same booking point last year; 100 means equal pace |
| pickup_room_nights | Count | Net room nights added to OTB since the previous daily report; this can be negative |
| market_segment | Text | Commercial segment such as Leisure, Corporate, Group_MICE, or Wholesale |
| source | Text | Where the booking originated, such as Hotel Website or Booking.com |
| channel | Text | Broad sales channel such as Direct, OTA, Corporate, or Wholesale |
| guest_nationality | Text | Synthetic nationality category with no guest identity |
| lead_time_days | Days | Average number of days between booking and stay date for this slice |
| cancellations | Count | Number of cancelled reservations attributed to the slice |
| budget_room_nights | Count | Budgeted room nights for the same property, date, and slice |
| last_year_room_nights | Count | Final room nights for the corresponding date one year earlier |
| on_the_books_room_nights | Count | Room nights currently booked for the future stay date |

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

## Direct Calculations

- Revenue equals room nights multiplied by ADR.
- Occupancy percent equals room nights divided by property room inventory, multiplied by 100.
- RevPAR equals revenue divided by property room inventory.
- Pick-up equals current OTB room nights less the previous daily report's OTB room nights.
