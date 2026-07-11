#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const MS_PER_DAY = 24 * 60 * 60 * 1000;
const CURRENT_DATE = "2026-07-11";
const START_DATE = addDays(CURRENT_DATE, -365);
const END_DATE = CURRENT_DATE;
const OTB_OBSERVATION_LEAD_DAYS = 7;

const PROPERTIES = [
  {
    name: "The Anam 1",
    city: "Cam Ranh",
    province: "Khanh Hoa",
    country: "Vietnam",
    propertyType: "Coastal Resort",
    rooms: 120,
    baseOccupancy: 0.68,
    baseAdrVnd: 4_700_000,
    cancellationRate: 0.035,
    segmentWeights: [0.25, 0.24, 0.14, 0.17, 0.20],
  },
  {
    name: "The Anam 2",
    city: "Mui Ne",
    province: "Binh Thuan",
    country: "Vietnam",
    propertyType: "Beach Resort",
    rooms: 85,
    baseOccupancy: 0.64,
    baseAdrVnd: 2_650_000,
    cancellationRate: 0.03,
    segmentWeights: [0.18, 0.18, 0.30, 0.18, 0.16],
  },
  {
    name: "The Anam 3",
    city: "Ho Chi Minh City",
    province: "Ho Chi Minh City",
    country: "Vietnam",
    propertyType: "TBD",
    rooms: 64,
    baseOccupancy: 0.71,
    baseAdrVnd: 3_350_000,
    cancellationRate: 0.045,
    segmentWeights: [0.28, 0.23, 0.10, 0.18, 0.21],
  },
];

const COMMERCIAL_SLICES = [
  {
    marketSegment: "Leisure",
    source: "Hotel Website",
    channel: "Direct",
    nationalities: ["Vietnam", "South Korea", "Australia"],
    leadTimeDays: 30,
    adrMultiplier: 1.08,
  },
  {
    marketSegment: "Leisure",
    source: "Booking.com",
    channel: "OTA",
    nationalities: ["South Korea", "Singapore", "Germany"],
    leadTimeDays: 20,
    adrMultiplier: 1.02,
  },
  {
    marketSegment: "Corporate",
    source: "Corporate Contract",
    channel: "Corporate",
    nationalities: ["Vietnam", "Singapore", "Japan"],
    leadTimeDays: 15,
    adrMultiplier: 0.9,
  },
  {
    marketSegment: "Group_MICE",
    source: "Group Sales",
    channel: "Direct",
    nationalities: ["Vietnam", "South Korea", "Singapore"],
    leadTimeDays: 45,
    adrMultiplier: 0.86,
  },
  {
    marketSegment: "Wholesale",
    source: "Travel Agent",
    channel: "Wholesale",
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
  "market_segment",
  "source",
  "channel",
  "guest_nationality",
  "lead_time_days",
  "cancellations",
  "budget_room_nights",
  "last_year_room_nights",
  "on_the_books_room_nights",
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
  const noise = (seededUnit("occupancy", property.name, date) - 0.5) * 0.12;
  const occupancy = clamp(
    property.baseOccupancy + seasonalAdjustment(date) + holidayAdjustment(date) + weekendAdjustment + noise,
    0.28,
    0.96,
  );
  return Math.round(property.rooms * occupancy);
}

function budgetRoomNights(property, date) {
  const noise = (seededUnit("budget", property.name, date) - 0.5) * 0.04;
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
  const noise = (seededUnit("otb", property.name, stayDate, reportDate) - 0.5) * 0.08;
  return clamp(
    Math.round(finalDemand * bookingFraction(daysToArrival) * (1 + noise)),
    0,
    property.rooms,
  );
}

function normalizedWeights(property, date) {
  const rawWeights = property.segmentWeights.map((baseWeight, index) => {
    const noise = (seededUnit("segment", property.name, date, index) - 0.5) * 0.05;
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
  const noise = (seededUnit("adr", property.name, slice.marketSegment, slice.source, date) - 0.5) * 0.08;
  return roundMoney(
    property.baseAdrVnd
      * slice.adrMultiplier
      * (1 + seasonalAdjustment(date) * 0.35 + weekendAdjustment + holidayAdjustment(date) * 0.5 + noise),
  );
}

function cancellationCount(property, roomNights, date, sliceIndex, isFuture) {
  const chance = seededUnit("cancellation", property.name, date, sliceIndex);
  if (isFuture) {
    if (chance < property.cancellationRate) return roomNights >= 12 ? 2 : 1;
    if (chance < property.cancellationRate * 3) return 1;
    return 0;
  }
  return Math.round(roomNights * property.cancellationRate * (0.5 + chance));
}

function guestNationality(property, slice, date) {
  const index = Math.floor(
    seededUnit("nationality", property.name, slice.marketSegment, slice.source, date)
      * slice.nationalities.length,
  );
  return slice.nationalities[index];
}

function leadTimeDays(property, slice, date) {
  return Math.max(
    1,
    Math.round(slice.leadTimeDays + (seededUnit("lead-time", property.name, slice.source, date) - 0.5) * 10),
  );
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

      for (let index = 0; index < COMMERCIAL_SLICES.length; index += 1) {
        const slice = COMMERCIAL_SLICES[index];
        const roomNights = actualRoomNights[index];
        const adrVnd = sliceAdr(property, slice, date);
        const revenueVnd = roomNights * adrVnd;
        const pace = lastYearOtb[index] === 0
          ? 100
          : roundOneDecimal((currentOtb[index] / lastYearOtb[index]) * 100);

        rows.push({
          date,
          property: property.name,
          occupancy_pct: roundOneDecimal((roomNights / property.rooms) * 100),
          adr_vnd: adrVnd,
          revpar_vnd: roundMoney(revenueVnd / property.rooms),
          room_nights: roomNights,
          revenue_vnd: revenueVnd,
          booking_pace_pct: pace,
          pickup_room_nights: currentOtb[index] - previousOtb[index],
          market_segment: slice.marketSegment,
          source: slice.source,
          channel: slice.channel,
          guest_nationality: guestNationality(property, slice, date),
          lead_time_days: leadTimeDays(property, slice, date),
          cancellations: cancellationCount(
            property,
            roomNights,
            date,
            index,
            false,
          ),
          budget_room_nights: budget[index],
          last_year_room_nights: lastYear[index],
          on_the_books_room_nights: currentOtb[index],
        });
      }
    }
  }
  return rows;
}

function escapeCsv(value) {
  const text = String(value);
  return /[",\r\n]/.test(text) ? '"' + text.replaceAll('"', '""') + '"' : text;
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
    property: property.name,
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
    const propertyNumber = property.name.slice(-1);
    let roomNumber = 1;
    for (let typeIndex = 0; typeIndex < ROOM_TYPES.length; typeIndex += 1) {
      const roomType = ROOM_TYPES[typeIndex];
      for (let index = 0; index < typeCounts[typeIndex]; index += 1) {
        rows.push({
          property: property.name,
          room_id: "ANAM" + propertyNumber + "-" + String(roomNumber).padStart(3, "0"),
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
}

writeCsv(buildRows());
writePropertyCsv();
writeRoomCsv();
