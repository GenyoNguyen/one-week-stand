# Dashboard Indicators for Commercial Intelligence and Demand Forecasting

This document defines recommended dashboard indicators for The Anam's commercial intelligence and demand forecasting system.

The forecasting engine should return foundational measures and metadata. The dashboard should then derive ratios, changes, probabilities, and decision signals from those outputs. An indicator should be displayed only when it helps a commercial, revenue, reservations, operations, or leadership user make a decision.

## 1. Minimum output contract

| Output area | Required content |
| --- | --- |
| Data status | As-of time, freshness per property, accepted and rejected rows, and missing feeds |
| Performance read | Occupancy, ADR, RevPAR, room nights, and revenue versus budget and last year |
| Forecast | Stay date x property x segment; currently booked rooms, expected final room nights, ADR and revenue, budget and last-year comparisons, and rooms still needed to reach budget |
| Risks and opportunities | Trigger, threshold, evidence window, affected dates, property, segment and channel, and confidence |
| Commercial action | Exact scope, recommendation, rationale, impact range, assumptions, owner, deadline, and status |
| Model and data checks | Typical historical forecast error, tendency to forecast high or low, last successful run, and missing or late feeds |

## 2. Main dashboard indicators

Use plain-language labels on the dashboard. Hotel terms may appear secondarily in tooltips.

| Dashboard label | Hotel term | Unit | Meaning and decision supported |
| --- | --- | --- | --- |
| Revenue risk | Revenue Risk Index | 0-100 and VND | Shows the percentage by which forecast revenue is below budget and the corresponding revenue gap. |
| Currently booked | OTB | Rooms and occupancy percent | Shows confirmed bookings currently recorded for the selected future stay dates. |
| Forecast versus budget | Forecast variance | Rooms, occupancy points, and VND | Shows whether expected final performance is above or below the commercial target. |
| Bookings versus the same time last year | Pace versus STLY | Percent and rooms | Compares current bookings with last year's bookings at the same number of days before arrival. |
| New bookings, last 7 days | Net pickup | Rooms | Shows the net change in booked rooms during the last seven days, after cancellations and reductions. |
| Rooms still needed for budget | Budget gap | Rooms | Shows how many additional booked rooms are needed to reach budget. |
| Cancelled rooms, last 7 days | Cancellation movement | Rooms and change versus normal | Shows whether recent cancellations are materially above the comparable historical level. |
| Forecast change since yesterday | Forecast revision | Rooms and VND | Shows whether the expected result has recently improved or deteriorated. |
| Revenue below budget | Revenue at risk | VND | Gives the monetary value of the forecast shortfall. |

These nine indicators are sufficient for the main commercial dashboard. Segment, channel, source-market, and lead-time diagnostics should appear only when a user opens a supporting detail view.

## 3. Revenue Risk Index

Keep the Risk Index simple: it is the forecast revenue shortfall as a percentage of budget. It does not combine pace, cancellations, confidence, or other unrelated measures.

Calculate it for a defined scope such as `stay date x property`, with optional segment drill-down:

```text
Revenue below budget = max(budget revenue - forecast revenue, 0)

Revenue Risk Index =
min(revenue below budget / budget revenue x 100, 100)
```

The score explains itself:

- `0` means forecast revenue is on or above budget.
- `8` means forecast revenue is 8% below budget.
- `25` means forecast revenue is 25% below budget.

Use the following display bands:

| Score | Label | Meaning |
| --- | --- | --- |
| 0-4 | Low | Forecast revenue is within 5% of budget or above it. |
| 5-9 | Watch | Forecast revenue is 5-9% below budget. |
| 10-19 | High | Forecast revenue is 10-19% below budget and needs commercial review. |
| 20-100 | Critical | Forecast revenue is at least 20% below budget and needs an immediate response. |

Never show the score by itself. Display it with:

- Revenue below budget in VND
- Affected property and stay-date range
- A plain-language reason such as bookings behind last year, high cancellations, or a weak segment
- Data-freshness status
- Recommended action, owner, and response deadline

Important guardrails:

- Do not use missing data as a zero-risk value; show the Risk Index as unavailable.
- Do not include upside opportunities in the downside Risk Index.
- Keep forecast reliability and data quality separate from commercial risk.
- Use one consistent budget period when comparing properties.
- Always show the VND revenue gap next to the score.

## 4. Indicator formulas

```text
Currently booked occupancy = currently booked rooms / available rooms x 100

Forecast versus budget = forecast revenue - budget revenue

Bookings versus the same time last year =
(currently booked rooms - last-year rooms at the same lead time)
/ last-year rooms at the same lead time x 100

New bookings, last 7 days =
currently booked rooms - booked rooms seven days ago

Rooms still needed for budget = max(budget rooms - currently booked rooms, 0)

Forecast change since yesterday = current forecast - yesterday's forecast

Revenue below budget = max(budget revenue - forecast revenue, 0)
```

`New bookings, last 7 days` is net movement. It can be negative when cancellations or booking reductions are greater than new bookings.

## 5. Recommended morning dashboard

Keep the opening dashboard focused on approximately six headline indicators:

1. Data freshness and property coverage
2. Revenue Risk Index with the VND revenue gap
3. Currently booked occupancy
4. Forecast occupancy and revenue versus budget
5. Bookings versus the same time last year
6. New bookings and cancelled rooms during the last seven days

Alongside these indicators, display:

- The top three risks and separately identified opportunities
- Rooms still needed for budget
- Recommended action, owner, and deadline
- Open, accepted, and overdue action counts as workflow status, not as commercial performance scores

Detailed segment, channel, stay-date, and forecast-reliability information should remain available one level deeper.

## 6. Operational indicators

Operations teams can use the demand forecast to derive:

- Expected occupied rooms by date
- Forecast guests in-house
- Expected arrivals and departures
- Housekeeping room turns
- Required staffing hours or headcount by department
- Peak-load dates
- Understaffing and overstaffing risk

Use staffing hours or headcount rather than an unexplained "staffing demand index." Historical guest-flow data alone is not sufficient for these future indicators. Future arrivals, departures, guest counts, workload, and staffing productivity standards are required.

## 7. Indicators requiring additional data

| Indicator | Additional data required |
| --- | --- |
| Net channel profitability | Commission, marketing cost, transaction cost, and payment cost |
| Defensible rate-change percentage | Historical rates, availability, booking response, and preferably competitor rates |
| Unconstrained demand | Turnaways, denials, closed inventory, and sell-out history |
| Group displacement risk | Group blocks, cutoff dates, rooming lists, and transient demand |
| Length-of-stay pressure | Arrival and departure dates or length of stay |
| Room-type compression | Inventory and OTB by room type |
| Market share and competitive position | Competitor rates or market-demand data |
| Promotion effectiveness | Campaign exposure, campaign cost, and resulting bookings |

Without these inputs, the system should not present unsupported exact instructions such as "raise BAR 12-15%" or "move 60% of inventory." It should instead recommend that the user consider an action and label it clearly as rule-based.

## 8. Indicators deliberately excluded

Do not add indicators that compress unrelated facts into an impressive-looking number without a defensible calculation. Excluded examples include:

- Sell-out probability and soft-date probability until the forecast intervals are proven reliable
- Expected revenue shortfall calculated from a full probability distribution
- Cancellation exposure in VND without reservation-level cancellation terms
- Median lead-time change as a headline KPI
- Channel-mix, momentum, opportunity, health, or generic performance indexes
- A single opaque "AI confidence score"
- A staffing demand index without staffing hours, headcount, or a documented capacity standard
- Action-count or dashboard-engagement scores presented as commercial performance
- Traffic-light statuses with no visible threshold or monetary impact

Raw metrics may still appear in drill-down views when they provide evidence. They should not be promoted to headline indicators unless they lead to a specific decision.

## 9. Model and data checks

Keep technical model measurements away from the main commercial dashboard. An administrator view should show only:

- Typical historical forecast error, expressed in rooms and percent
- Whether the model usually forecasts too high or too low
- Last successful forecast run
- Missing, late, or rejected property feeds
- A clear warning when there is not enough data to trust a forecast

Technical names such as WAPE, MAE, bias, and interval coverage may appear in administrator tooltips, but they should not be headline indicators for commercial users.

## 10. Recommended decision hierarchy

The dashboard should help the user answer four questions in order:

1. **What changed?** Currently booked rooms, new bookings, cancellations, and forecast change since yesterday.
2. **Why does it matter?** Revenue Risk Index, VND revenue gap, and rooms still needed for budget.
3. **What should we do?** A scoped recommendation with evidence, assumptions, owner, and deadline.
4. **Did anyone act?** Accepted, dismissed, overdue, and completed action status with an audit trail.

This hierarchy supports the problem statement's success criterion: commercial, revenue, reservations, and operations teams should act on the system's recommendations rather than merely read the dashboard.
