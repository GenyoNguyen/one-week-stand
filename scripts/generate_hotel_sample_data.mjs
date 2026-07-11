#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const MS_PER_DAY = 24 * 60 * 60 * 1000;
const CURRENT_DATE = "2026-07-11";
const START_DATE = addDays(CURRENT_DATE, -365);
const END_DATE = addDays(CURRENT_DATE, 90); // forward-looking OTB through Oct 2026
const OTB_OBSERVATION_LEAD_DAYS = 7;

const PROPERTIES = [
  {
    code: "ACR",
    name: "The Anam Cam Ranh",
    city: "Cam Ranh",
    province: "Khanh Hoa",
    country: "Vietnam",
    propertyType: "Coastal Resort",
    rooms: 213,
    baseOccupancy: 0.68,
    baseAdrVnd: 4_700_000,
    averageGuestsPerRoom: 1.9,
    staffingCapacity: 91,
    cancellationRate: 0.035,
    segmentWeights: [0.24, 0.32, 0.08, 0.17, 0.19],
  },
  {
    code: "AMN",
    name: "The Anam Mui Ne",
    city: "Mui Ne",
    province: "Binh Thuan",
    country: "Vietnam",
    propertyType: "Beach Resort",
    rooms: 127,
    baseOccupancy: 0.64,
    baseAdrVnd: 2_650_000,
    averageGuestsPerRoom: 1.6,
    staffingCapacity: 62,
    cancellationRate: 0.03,
    segmentWeights: [0.18, 0.41, 0.04, 0.15, 0.22],
  },
  {
    code: "ANT",
    name: "The Anam Nha Trang",
    city: "Nha Trang",
    province: "Khanh Hoa",
    country: "Vietnam",
    propertyType: "City Boutique",
    rooms: 156,
    baseOccupancy: 0.71,
    baseAdrVnd: 3_350_000,
    averageGuestsPerRoom: 1.75,
    staffingCapacity: 76,
    cancellationRate: 0.045,
    segmentWeights: [0.22, 0.36, 0.11, 0.15, 0.16],
  },
];

const COMMERCIAL_SLICES = [
  {
    marketSegment: "Direct",
    source: "Brand.com",
    channel: "Brand.com",
    nationalities: ["Vietnam", "South Korea", "Australia"],
    leadTimeDays: 30,
    adrMultiplier: 1.08,
  },
  {
    marketSegment: "OTA",
    source: "Booking.com",
    channel: "Booking.com",
    nationalities: ["South Korea", "Singapore", "Germany"],
    leadTimeDays: 20,
    adrMultiplier: 1.02,
  },
  {
    marketSegment: "Corporate",
    source: "GDS",
    channel: "GDS",
    nationalities: ["Vietnam", "Singapore", "Japan"],
    leadTimeDays: 15,
    adrMultiplier: 0.9,
  },
  {
    marketSegment: "Group",
    source: "Voice / email",
    channel: "Voice / email",
    nationalities: ["Vietnam", "South Korea", "Singapore"],
    leadTimeDays: 45,
    adrMultiplier: 0.86,
  },
  {
    marketSegment: "Wholesale",
    source: "Travel agents",
    channel: "Travel agents",
    nationalities: ["Germany", "Australia", "United Kingdom"],
    leadTimeDays: 55,
    adrMultiplier: 0.82,
  },
];

const ROOM_TYPES = [
  {
    roomType: "Deluxe King",
    share: 0.3,
    bedType: "King",
    maxGuests: 2,
    sizeSqm: 42,
    rateMultiplier: 0.9,
  },
  {
    roomType: "Deluxe Twin",
    share: 0.25,
    bedType: "Twin",
    maxGuests: 2,
    sizeSqm: 42,
    rateMultiplier: 0.9,
  },
  {
    roomType: "Suite",
    share: 0.25,
    bedType: "King",
    maxGuests: 3,
    sizeSqm: 68,
    rateMultiplier: 1.25,
  },
  {
    roomType: "Villa",
    share: 0.2,
    bedType: "King",
    maxGuests: 4,
    sizeSqm: 110,
    rateMultiplier: 1.75,
  },
];

const HEADERS = [
  "date",
  "property",
  "occupancy_pct",
  "adr_vnd",
  "revpar_vnd",
  "room_nights",
  "revenue_vnd",
  "booking_pace_pct",
  "pickup_room_nights",
  "pickup_24h_room_nights",
  "market_segment",
  "source",
  "channel",
  "guest_nationality",
  "lead_time_days",
  "cancellations",
  "budget_room_nights",
  "budget_adr_vnd",
  "last_year_room_nights",
  "ly_adr_vnd",
  "on_the_books_room_nights",
  "stly_otb_room_nights",
];

function parseDate(dateString) {
  return new Date(dateString + "T00:00:00.000Z");
}

function formatDate(date) {
  return date.toISOString().slice(0, 10);
}

function addDays(dateString, days) {
  const date = parseDate(dateString);
  date.setUTCDate(date.getUTCDate() + days);
  return formatDate(date);
}

function addYears(dateString, years) {
  const date = parseDate(dateString);
  date.setUTCFullYear(date.getUTCFullYear() + years);
  return formatDate(date);
}

function daysBetween(startDate, endDate) {
  return Math.round((parseDate(endDate).getTime() - parseDate(startDate).getTime()) / MS_PER_DAY);
}

function dateRange(startDate, endDate) {
  const dates = [];
  for (let date = startDate; date <= endDate; date = addDays(date, 1)) {
    dates.push(date);
  }
  return dates;
}

function seededUnit(...parts) {
  let hash = 2_166_136_261;
  const input = parts.join("|");
  for (const character of input) {
    hash ^= character.charCodeAt(0);
    hash = Math.imul(hash, 16_777_619);
  }
  return (hash >>> 0) / 4_294_967_296;
}

function clamp(value, minimum, maximum) {
  return Math.min(Math.max(value, minimum), maximum);
}

function roundMoney(value) {
  return Math.round(value / 1_000) * 1_000;
}

function roundOneDecimal(value) {
  return Number(value.toFixed(1));
}

function seasonalAdjustment(date) {
  const month = parseDate(date).getUTCMonth();
  return [0.13, 0.15, 0.11, 0.04, 0, -0.03, -0.06, -0.12, -0.14, -0.07, 0.03, 0.15][month];
}

function holidayAdjustment(date) {
  const monthDay = date.slice(5);
  return ["01-01", "04-30", "05-01", "09-02"].includes(monthDay) ? 0.09 : 0;
}

function finalRoomNights(property, date) {
  const day = parseDate(date).getUTCDay();
  const weekendAdjustment = day === 5 || day === 6 ? 0.06 : 0;
  const noise = (seededUnit("occupancy", property.code, date) - 0.5) * 0.12;
  const occupancy = clamp(
    property.baseOccupancy + seasonalAdjustment(date) + holidayAdjustment(date) + weekendAdjustment + noise,
    0.28,
    0.96,
  );
  return Math.round(property.rooms * occupancy);
}

function budgetRoomNights(property, date) {
  const noise = (seededUnit("budget", property.code, date) - 0.5) * 0.04;
  const occupancy = clamp(
    property.baseOccupancy + seasonalAdjustment(date) * 0.8 + holidayAdjustment(date) * 0.7 + 0.01 + noise,
    0.3,
    0.93,
  );
  return Math.round(property.rooms * occupancy);
}

function bookingFraction(daysToArrival) {
  if (daysToArrival <= 0) return 0.97;
  if (daysToArrival <= 2) return 0.94;
  if (daysToArrival <= 7) return 0.87;
  if (daysToArrival <= 14) return 0.76;
  if (daysToArrival <= 30) return 0.62;
  if (daysToArrival <= 60) return 0.46;
  return 0.32;
}

function onTheBooksRoomNights(property, stayDate, reportDate) {
  const daysToArrival = daysBetween(reportDate, stayDate);
  const finalDemand = finalRoomNights(property, stayDate);
  const noise = (seededUnit("otb", property.code, stayDate, reportDate) - 0.5) * 0.08;
  return clamp(
    Math.round(finalDemand * bookingFraction(daysToArrival) * (1 + noise)),
    0,
    property.rooms,
  );
}

function normalizedWeights(property, date) {
  const rawWeights = property.segmentWeights.map((baseWeight, index) => {
    const noise = (seededUnit("segment", property.code, date, index) - 0.5) * 0.05;
    return Math.max(0.03, baseWeight + noise);
  });
  const total = rawWeights.reduce((sum, value) => sum + value, 0);
  return rawWeights.map((value) => value / total);
}

function splitInteger(total, weights) {
  const values = weights.map((weight, index) => {
    const raw = total * weight;
    return { index, value: Math.floor(raw), remainder: raw - Math.floor(raw) };
  });
  let remaining = total - values.reduce((sum, item) => sum + item.value, 0);
  values.sort((left, right) => right.remainder - left.remainder || left.index - right.index);
  for (let index = 0; index < remaining; index += 1) {
    values[index % values.length].value += 1;
  }
  values.sort((left, right) => left.index - right.index);
  return values.map((item) => item.value);
}

function sliceAdr(property, slice, date) {
  const day = parseDate(date).getUTCDay();
  const weekendAdjustment = day === 5 || day === 6 ? 0.04 : 0;
  const noise = (seededUnit("adr", property.code, slice.marketSegment, slice.source, date) - 0.5) * 0.08;
  return roundMoney(
    property.baseAdrVnd
      * slice.adrMultiplier
      * (1 + seasonalAdjustment(date) * 0.35 + weekendAdjustment + holidayAdjustment(date) * 0.5 + noise),
  );
}

function cancellationCount(property, roomNights, date, sliceIndex, isFuture) {
  const chance = seededUnit("cancellation", property.code, date, sliceIndex);
  if (isFuture) {
    if (chance < property.cancellationRate) return roomNights >= 12 ? 2 : 1;
    if (chance < property.cancellationRate * 3) return 1;
    return 0;
  }
  return Math.round(roomNights * property.cancellationRate * (0.5 + chance));
}

function guestNationality(property, slice, date) {
  const index = Math.floor(
    seededUnit("nationality", property.code, slice.marketSegment, slice.source, date)
      * slice.nationalities.length,
  );
  return slice.nationalities[index];
}

function leadTimeDays(property, slice, date) {
  return Math.max(
    1,
    Math.round(slice.leadTimeDays + (seededUnit("lead-time", property.code, slice.source, date) - 0.5) * 10),
  );
}

function guestsStaying(property, date, bookingsStaying) {
  const noise = (seededUnit("guest-density", property.code, date) - 0.5) * 0.18;
  return clamp(
    Math.round(bookingsStaying * (property.averageGuestsPerRoom + noise)),
    bookingsStaying,
    bookingsStaying * 4,
  );
}

function staffingAssessment(property, date, flow) {
  const dayOfWeek = parseDate(date).getUTCDay();
  const weekendPressure = dayOfWeek === 5 || dayOfWeek === 6 ? 1.4 : 0;
  const guestTurnover = flow.guests_checking_in + flow.guests_checking_out;
  const bookingTurnover = flow.bookings_checking_in + flow.bookings_checking_out;
  const nonlinearWorkload =
    0.8 * Math.sqrt(flow.guests_staying)
    + 0.15 * Math.pow(guestTurnover, 1.16)
    + 0.1 * Math.pow(bookingTurnover, 1.12)
    + property.rooms * 0.012
    + weekendPressure;
  const labelNoise = (seededUnit("staffing-label-noise", property.code, date) - 0.5) * 0.12;
  const staffingPressure = nonlinearWorkload / property.staffingCapacity + labelNoise;
  const riskIndex = clamp(Math.round(50 + (staffingPressure - 1) * 210), 0, 100);

  if (riskIndex >= 67) return { riskIndex, status: "Under-deployed" };
  if (riskIndex <= 25) return { riskIndex, status: "Over-deployed" };
  return { riskIndex, status: "Right amount" };
}

function buildGuestFlowRows() {
  const rows = [];
  for (const date of dateRange(START_DATE, END_DATE)) {
    const previousDate = addDays(date, -1);
    for (const property of PROPERTIES) {
      const previousBookings = finalRoomNights(property, previousDate);
      const bookingsStaying = finalRoomNights(property, date);
      const turnoverRate = 0.25 + seededUnit("turnover", property.code, date) * 0.2;
      const minimumCheckouts = Math.max(0, previousBookings - bookingsStaying);
      const bookingsCheckingOut = clamp(
        Math.max(minimumCheckouts, Math.round(previousBookings * turnoverRate)),
        0,
        previousBookings,
      );
      const bookingsCheckingIn = bookingsStaying - previousBookings + bookingsCheckingOut;

      const previousGuests = guestsStaying(property, previousDate, previousBookings);
      const currentGuests = guestsStaying(property, date, bookingsStaying);
      const guestChange = currentGuests - previousGuests;
      const minimumGuestCheckouts = Math.max(bookingsCheckingOut, bookingsCheckingIn - guestChange);
      const maximumGuestCheckouts = Math.min(
        bookingsCheckingOut * 4,
        bookingsCheckingIn * 4 - guestChange,
      );
      if (minimumGuestCheckouts > maximumGuestCheckouts) {
        throw new Error("Unable to create consistent guest flow for " + property.code + " on " + date);
      }
      const targetGuestCheckouts = Math.round(
        bookingsCheckingOut
          * (property.averageGuestsPerRoom
            + (seededUnit("departing-guest-density", property.code, date) - 0.5) * 0.18),
      );
      const guestsCheckingOut = clamp(
        targetGuestCheckouts,
        Math.ceil(minimumGuestCheckouts),
        Math.floor(maximumGuestCheckouts),
      );
      const guestsCheckingIn = guestChange + guestsCheckingOut;

      const flow = {
        date,
        property: property.code,
        bookings_checking_in: bookingsCheckingIn,
        bookings_staying: bookingsStaying,
        bookings_checking_out: bookingsCheckingOut,
        guests_checking_in: guestsCheckingIn,
        guests_staying: currentGuests,
        guests_checking_out: guestsCheckingOut,
      };
      const assessment = staffingAssessment(property, date, flow);
      flow.staffing_risk_index = assessment.riskIndex;
      flow.staffing_status = assessment.status;
      rows.push(flow);
    }
  }
  return rows;
}

function buildRows() {
  const rows = [];
  for (const date of dateRange(START_DATE, END_DATE)) {
    for (const property of PROPERTIES) {
      const weights = normalizedWeights(property, date);
      const actualRoomNights = splitInteger(finalRoomNights(property, date), weights);
      const budget = splitInteger(budgetRoomNights(property, date), weights);
      const lastYear = splitInteger(finalRoomNights(property, addYears(date, -1)), weights);
      const otbObservationDate = addDays(date, -OTB_OBSERVATION_LEAD_DAYS);
      const currentOtbTotal = onTheBooksRoomNights(property, date, otbObservationDate);
      const previousOtbTotal = onTheBooksRoomNights(property, date, addDays(otbObservationDate, -1));
      const currentOtb = splitInteger(currentOtbTotal, weights);
      const previousOtb = splitInteger(previousOtbTotal, weights);

      const lastYearStayDate = addYears(date, -1);
      const lastYearReportDate = addDays(lastYearStayDate, -OTB_OBSERVATION_LEAD_DAYS);
      const lastYearOtbTotal = onTheBooksRoomNights(property, lastYearStayDate, lastYearReportDate);
      const lastYearOtb = splitInteger(lastYearOtbTotal, weights);

      // STLY OTB: same stay date last year, observed at same lead time last year
      const stlyOtbTotal = lastYearOtbTotal;
      const stlyOtb = lastYearOtb;

      for (let index = 0; index < COMMERCIAL_SLICES.length; index += 1) {
        const slice = COMMERCIAL_SLICES[index];
        const roomNights = actualRoomNights[index];
        const adrVnd = sliceAdr(property, slice, date);
        const revenueVnd = roomNights * adrVnd;
        const pace = lastYearOtb[index] === 0
          ? 100
          : roundOneDecimal((currentOtb[index] / lastYearOtb[index]) * 100);

        const pickup7 = currentOtb[index] - previousOtb[index];
        // 24h pickup is ~1/7 of 7-day pickup with noise
        const pickup24Noise = (seededUnit("pickup24", property.code, date, index) - 0.5) * 1.2;
        const pickup24 = Math.max(0, Math.round(pickup7 / 6 + pickup24Noise));

        // Budget ADR: slightly different from actual ADR
        const budgetAdrNoise = (seededUnit("budget-adr", property.code, date, index) - 0.5) * 0.06;
        const budgetAdrVnd = roundMoney(adrVnd * (1 + budgetAdrNoise));

        // LY ADR: slightly different from actual ADR
        const lyAdrNoise = (seededUnit("ly-adr", property.code, date, index) - 0.5) * 0.06;
        const lyAdrVnd = roundMoney(adrVnd * (1 - 0.04 + lyAdrNoise));

        rows.push({
          date,
          property: property.code,
          occupancy_pct: roundOneDecimal((roomNights / property.rooms) * 100),
          adr_vnd: adrVnd,
          revpar_vnd: roundMoney(revenueVnd / property.rooms),
          room_nights: roomNights,
          revenue_vnd: revenueVnd,
          booking_pace_pct: pace,
          pickup_room_nights: pickup7,
          pickup_24h_room_nights: pickup24,
          market_segment: slice.marketSegment,
          source: slice.source,
          channel: slice.channel,
          guest_nationality: guestNationality(property, slice, date),
          lead_time_days: leadTimeDays(property, slice, date),
          cancellations: cancellationCount(property, roomNights, date, index, false),
          budget_room_nights: budget[index],
          budget_adr_vnd: budgetAdrVnd,
          last_year_room_nights: lastYear[index],
          ly_adr_vnd: lyAdrVnd,
          on_the_books_room_nights: currentOtb[index],
          stly_otb_room_nights: stlyOtb[index],
        });
      }
    }
  }
  return rows;
}

// ---- story injections (alerts reference these numbers) --------------------
function injectStories(rows) {
  const acrProperty = PROPERTIES.find((p) => p.code === "ACR");
  const amnProperty = PROPERTIES.find((p) => p.code === "AMN");
  const antProperty = PROPERTIES.find((p) => p.code === "ANT");

  for (const row of rows) {
    const d = row.date;
    const isFuture = d > CURRENT_DATE;

    // STORY 1: Cam Ranh — pace 18% behind for stays 3–9 Aug 2026
    // Reduce OTB for Direct and OTA segments so pace_pct ≈ 82
    if (
      row.property === "ACR"
      && isFuture
      && d >= "2026-08-03"
      && d <= "2026-08-09"
      && (row.market_segment === "Direct" || row.market_segment === "OTA")
    ) {
      row.on_the_books_room_nights = Math.round(row.stly_otb_room_nights * 0.82);
      row.booking_pace_pct = roundOneDecimal(
        (row.on_the_books_room_nights / Math.max(1, row.stly_otb_room_nights)) * 100,
      );
      row.pickup_room_nights = Math.round(row.pickup_room_nights * 0.5);
      row.pickup_24h_room_nights = Math.max(0, Math.round(row.pickup_24h_room_nights * 0.4));
    }

    // STORY 2: Mui Ne — cancellation spike for stays within 30 days from TODAY
    // Booking.com (OTA) cancellations 2.3× above norm
    if (
      row.property === "AMN"
      && d >= CURRENT_DATE
      && d <= addDays(CURRENT_DATE, 30)
      && row.market_segment === "OTA"
    ) {
      row.cancellations = Math.round(row.cancellations * 2.3 + 1);
    }

    // STORY 3: Nha Trang — National Day compression 1–2 Sep 2026
    // OTB at ~92% occupancy across all segments
    if (
      row.property === "ANT"
      && isFuture
      && d >= "2026-09-01"
      && d <= "2026-09-02"
    ) {
      row.on_the_books_room_nights = Math.round(antProperty.rooms * 0.92 / 5);
      row.booking_pace_pct = roundOneDecimal(
        (row.on_the_books_room_nights / Math.max(1, row.stly_otb_room_nights)) * 100,
      );
      row.pickup_room_nights = Math.max(1, row.pickup_room_nights);
    }
  }
  return rows;
}

function escapeCsv(value) {
  const text = String(value);
  return /[",\r\n]/.test(text) ? '"' + text.replaceAll('"', '""') + '"' : text;
}

function escapeMarkdown(value) {
  return String(value).replaceAll("|", "\\|").replaceAll("\r", " ").replaceAll("\n", " ");
}

function writeMarkdownFile(fileName, title, headers, rows) {
  const lines = [
    "# " + title,
    "",
    "Synthetic sample data.",
    "",
    "| " + headers.join(" | ") + " |",
    "| " + headers.map(() => "---").join(" | ") + " |",
    ...rows.map(
      (row) => "| " + headers.map((header) => escapeMarkdown(row[header])).join(" | ") + " |",
    ),
  ];
  const scriptDirectory = path.dirname(fileURLToPath(import.meta.url));
  const outputPath = path.resolve(scriptDirectory, "..", "data", fileName);
  fs.writeFileSync(outputPath, lines.join("\n") + "\n", "utf8");
  console.log("Generated " + rows.length.toLocaleString() + " rows in " + outputPath);
}

function writeCsv(rows) {
  const lines = [
    HEADERS.join(","),
    ...rows.map((row) => HEADERS.map((header) => escapeCsv(row[header])).join(",")),
  ];
  const scriptDirectory = path.dirname(fileURLToPath(import.meta.url));
  const outputPath = path.resolve(
    scriptDirectory,
    "..",
    "data",
    "sample",
    "the_anam_daily_reservation_performance.csv",
  );
  fs.writeFileSync(outputPath, lines.join("\n") + "\n", "utf8");
  console.log("Generated " + rows.length.toLocaleString() + " rows in " + outputPath);
  writeMarkdownFile(
    "the_anam_daily_reservation_performance.md",
    "The Anam Daily Reservation Performance",
    HEADERS,
    rows,
  );
}

function writePropertyCsv() {
  const headers = [
    "property",
    "city",
    "province",
    "country",
    "property_type",
    "room_count",
    "currency",
    "timezone",
  ];
  const rows = PROPERTIES.map((property) => ({
    property: property.code,
    city: property.city,
    province: property.province,
    country: property.country,
    property_type: property.propertyType,
    room_count: property.rooms,
    currency: "VND",
    timezone: "Asia/Ho_Chi_Minh",
  }));
  const lines = [
    headers.join(","),
    ...rows.map((row) => headers.map((header) => escapeCsv(row[header])).join(",")),
  ];
  const scriptDirectory = path.dirname(fileURLToPath(import.meta.url));
  const outputPath = path.resolve(scriptDirectory, "..", "data", "sample", "the_anam_properties.csv");
  fs.writeFileSync(outputPath, lines.join("\n") + "\n", "utf8");
  console.log("Generated " + rows.length + " rows in " + outputPath);
  writeMarkdownFile("the_anam_properties.md", "The Anam Properties", headers, rows);
}

function writeRoomCsv() {
  const headers = [
    "property",
    "room_id",
    "room_type",
    "floor",
    "bed_type",
    "max_guests",
    "size_sqm",
    "base_rate_vnd",
  ];
  const rows = [];
  for (const property of PROPERTIES) {
    const typeCounts = splitInteger(
      property.rooms,
      ROOM_TYPES.map((roomType) => roomType.share),
    );
    const propertyNumber = property.code;
    let roomNumber = 1;
    for (let typeIndex = 0; typeIndex < ROOM_TYPES.length; typeIndex += 1) {
      const roomType = ROOM_TYPES[typeIndex];
      for (let index = 0; index < typeCounts[typeIndex]; index += 1) {
        rows.push({
          property: property.code,
          room_id: "ANAM-" + propertyNumber + "-" + String(roomNumber).padStart(3, "0"),
          room_type: roomType.roomType,
          floor: roomType.roomType === "Villa" ? 1 : Math.floor(index / 20) + 1,
          bed_type: roomType.bedType,
          max_guests: roomType.maxGuests,
          size_sqm: roomType.sizeSqm,
          base_rate_vnd: roundMoney(property.baseAdrVnd * roomType.rateMultiplier),
        });
        roomNumber += 1;
      }
    }
  }
  const lines = [
    headers.join(","),
    ...rows.map((row) => headers.map((header) => escapeCsv(row[header])).join(",")),
  ];
  const scriptDirectory = path.dirname(fileURLToPath(import.meta.url));
  const outputPath = path.resolve(scriptDirectory, "..", "data", "sample", "the_anam_rooms.csv");
  fs.writeFileSync(outputPath, lines.join("\n") + "\n", "utf8");
  console.log("Generated " + rows.length + " rows in " + outputPath);
  writeMarkdownFile("the_anam_rooms.md", "The Anam Rooms", headers, rows);
}

function writeGuestFlowCsv(rows) {
  const headers = [
    "date",
    "property",
    "bookings_checking_in",
    "bookings_staying",
    "bookings_checking_out",
    "guests_checking_in",
    "guests_staying",
    "guests_checking_out",
    "staffing_risk_index",
    "staffing_status",
  ];
  const lines = [
    headers.join(","),
    ...rows.map((row) => headers.map((header) => escapeCsv(row[header])).join(",")),
  ];
  const scriptDirectory = path.dirname(fileURLToPath(import.meta.url));
  const outputPath = path.resolve(
    scriptDirectory,
    "..",
    "data",
    "sample",
    "the_anam_daily_guest_flow.csv",
  );
  fs.writeFileSync(outputPath, lines.join("\n") + "\n", "utf8");
  console.log("Generated " + rows.length.toLocaleString() + " rows in " + outputPath);
  writeMarkdownFile(
    "the_anam_daily_guest_flow.md",
    "The Anam Daily Guest Flow",
    headers,
    rows,
  );
}

writeCsv(injectStories(buildRows()));
writePropertyCsv();
writeRoomCsv();
writeGuestFlowCsv(buildGuestFlowRows());
