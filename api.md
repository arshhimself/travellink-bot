# AeroCRS v5 API Reference

Base URL: `https://api.aerocrs.com/v5`

---

## Common Request Headers

| Header          | Value                          |
|-----------------|--------------------------------|
| `Content-Type`  | `application/json`             |
| `auth_id`       | `$AUTHID` (from `.env`)        |
| `auth_password` | `$AUTHPASSSWORD` (from `.env`) |

---

## Booking Flow

```
getDestinations
      ↓
getSchedule
      ↓
getAvailability + getFares  (can run in parallel)
      ↓
getDeepLink  (outbound)
getDeepLink  (inbound — round-trip only)
      ↓
createBooking
      ↓
getAncillaries → createAncillary  (optional)
      ↓
confirmBooking → confirmExtrasReservation  (optional)
```

---

## 1. Get Destinations

**`GET /getDestinations`**
Fetch all available airports/cities. Use this first to validate city names and resolve IATA codes before any search.

**Request**
No body. Headers only.

**Response**
```json
{
  "aerocrs": {
    "destinations": {
      "destination": [
        {
          "code": "JRO",
          "name": "Kilimanjaro",
          "iatacode": "JRO"
        }
      ]
    }
  }
}
```

| Field      | Type   | Description              |
|------------|--------|--------------------------|
| `code`     | string | Internal airport code    |
| `name`     | string | City / airport full name |
| `iatacode` | string | IATA code                |

---

## 2. Get Schedule

**`POST /getSchedule`**
Fetch the flight schedule (routes and dates that have flights). Call after resolving IATA codes, before checking availability.

**Request Body**
```json
{
  "aerocrs": {
    "parms": {
      "dates": {
        "start": "YYYY/MM/DD",
        "end": "YYYY/MM/DD"
      }
    }
  }
}
```

| Field         | Type   | Description                        |
|---------------|--------|------------------------------------|
| `dates.start` | string | Start of schedule window `YYYY/MM/DD` |
| `dates.end`   | string | End of schedule window `YYYY/MM/DD`   |

**Response** — Raw AeroCRS schedule data.

---

## 3. Get Availability

**`POST /getAvailability`**
Check how many flights are available in a date range. Use this to confirm flights exist before calling `getDeepLink`.

**Request Body**
```json
{
  "aerocrs": {
    "parms": {
      "dates": {
        "start": "YYYY/MM/DD",
        "end": "YYYY/MM/DD"
      }
    }
  }
}
```

| Field         | Type   | Description                           |
|---------------|--------|---------------------------------------|
| `dates.start` | string | Start of search window `YYYY/MM/DD`   |
| `dates.end`   | string | End of search window `YYYY/MM/DD`     |

**Response**
```json
{
  "aerocrs": {
    "flights": {
      "count": 3
    }
  }
}
```

| Field   | Type    | Description                             |
|---------|---------|-----------------------------------------|
| `count` | integer | Number of available flights; `0` = none |

---

## 4. Get Fares

**`POST /getFares`**
Fetch available fares for a date range. Run in parallel with `getAvailability`.

**Request Body**
```json
{
  "aerocrs": {
    "parms": {
      "dates": {
        "start": "YYYY/MM/DD",
        "end": "YYYY/MM/DD"
      }
    }
  }
}
```

| Field         | Type   | Description                       |
|---------------|--------|-----------------------------------|
| `dates.start` | string | Start of fare window `YYYY/MM/DD` |
| `dates.end`   | string | End of fare window `YYYY/MM/DD`   |

**Response** — Raw AeroCRS fares list.

---

## 5. Get Deep Link (Flight Details)

**`GET /getDeepLink`**
Retrieve detailed flight options with pricing and fare classes. Call once for outbound, and again for inbound if round-trip.

**Request** — Query Parameters
```
GET /getDeepLink?from=JRO&to=DAR&start=2026/03/01&adults=1&child=0&infant=0
GET /getDeepLink?from=DAR&to=JRO&start=2026/03/10&adults=1&child=0&infant=0  ← inbound (RT only)
```

| Param    | Type    | Required | Description                                |
|----------|---------|----------|--------------------------------------------|
| `from`   | string  | Yes      | Departure IATA code                        |
| `to`     | string  | Yes      | Arrival IATA code                          |
| `start`  | string  | Yes      | Departure date `YYYY/MM/DD`                |
| `adults` | integer | Yes      | Number of adult passengers                 |
| `child`  | integer | Yes      | Number of child passengers                 |
| `infant` | integer | Yes      | Number of infant passengers                |
| `end`    | string  | No       | Return date `YYYY/MM/DD` (round-trip only) |

**Response**
```json
{
  "aerocrs": {
    "flights": {
      "flight": [
        {
          "flightcode": "QA101",
          "fltnum": "101",
          "flighttype": "Direct",
          "direction": "outbound",
          "STD": "2026-03-01T08:00:00",
          "STA": "2026-03-01T09:30:00",
          "via": null,
          "classes": {
            "Economy": {
              "fare": {
                "adultFare": "120.00",
                "tax": "20.00"
              },
              "freeseats": 45,
              "fareid": 789,
              "flightid": 456
            }
          }
        }
      ]
    }
  }
}
```

| Field            | Type    | Description                                   |
|------------------|---------|-----------------------------------------------|
| `flightcode`     | string  | Flight code                                   |
| `fltnum`         | string  | Flight number                                 |
| `flighttype`     | string  | e.g. `"Direct"`, `"Via"`                      |
| `direction`      | string  | `"outbound"` or `"inbound"`                   |
| `STD`            | string  | Scheduled departure datetime                  |
| `STA`            | string  | Scheduled arrival datetime                    |
| `via`            | string  | Stopover city, or `null` if direct            |
| `classes`        | object  | Keyed by class name (e.g. `"Economy"`)        |
| `fare.adultFare` | string  | Adult base fare                               |
| `fare.tax`       | string  | Tax amount                                    |
| `freeseats`      | integer | Available seats in this class                 |
| `fareid`         | integer | Fare ID — required for `createBooking`        |
| `flightid`       | integer | Flight ID — required for `createBooking`      |

---

## 6. Create Booking

**`POST /createBooking`**
Create a booking for a selected flight and fare class. Use `flightid` and `fareid` from `getDeepLink`.

**Request Body**
```json
{
  "aerocrs": {
    "parms": {
      "triptype": "OW",
      "adults": 1,
      "child": 0,
      "infant": 0,
      "bookflight": [
        {
          "fromcode": "JRO",
          "tocode": "DAR",
          "flightid": 456,
          "fareid": 789
        }
      ]
    }
  }
}
```

| Field                   | Type    | Description                             |
|-------------------------|---------|-----------------------------------------|
| `triptype`              | string  | `"OW"` (one-way) or `"RT"` (round-trip)|
| `adults`                | integer | Number of adults                        |
| `child`                 | integer | Number of children                      |
| `infant`                | integer | Number of infants                       |
| `bookflight[].fromcode` | string  | Origin IATA code                        |
| `bookflight[].tocode`   | string  | Destination IATA code                   |
| `bookflight[].flightid` | integer | Flight ID from `getDeepLink`            |
| `bookflight[].fareid`   | integer | Fare class ID from `getDeepLink`        |

**Response**
```json
{
  "aerocrs": {
    "booking": {
      "bookingid": 789,
      "pnrref": "ABC123",
      "items": {
        "flight": [
          { "flightid": 456, "error": null }
        ]
      }
    }
  }
}
```

| Field                    | Type        | Description                                        |
|--------------------------|-------------|----------------------------------------------------|
| `bookingid`              | integer     | Booking ID — used for all subsequent calls         |
| `pnrref`                 | string      | PNR reference — used in `confirmExtrasReservation` |
| `items.flight[].error`   | string/null | Non-null if that leg failed                        |

---

## 7. Get Ancillaries

**`POST /getAncillaries`**
Fetch available add-ons (baggage, meals, seats) for a booking. Call immediately after `createBooking`.

**Request Body**
```json
{
  "aerocrs": {
    "parms": {
      "bookingid": 789,
      "flightid": 456,
      "currency": "USD"
    }
  }
}
```

| Field       | Type    | Description             |
|-------------|---------|-------------------------|
| `bookingid` | integer | Booking ID              |
| `flightid`  | integer | Flight ID               |
| `currency`  | string  | Currency code (`"USD"`) |

**Response**
```json
{
  "aerocrs": {
    "success": true,
    "ancillaries": [
      {
        "itemid": 11,
        "name": "Extra Baggage 20kg",
        "price": "35.00"
      }
    ]
  }
}
```

| Field         | Type    | Description                                   |
|---------------|---------|-----------------------------------------------|
| `success`     | boolean | Whether the request succeeded                 |
| `ancillaries` | array   | List of available add-ons; empty `[]` if none |
| `itemid`      | integer | Item ID — used in `createAncillary`           |
| `name`        | string  | Add-on display name                           |
| `price`       | string  | Add-on price                                  |

---

## 8. Create Ancillary *(optional)*

**`POST /createAncillary`**
Attach a selected add-on to a booking. Only call if the user wants an extra.

**Request Body**
```json
{
  "aerocrs": {
    "parms": {
      "ancillaries": {
        "ancillary": [
          {
            "paxnum": 0,
            "itemid": 11,
            "bookingid": 789,
            "flightid": 456
          }
        ]
      }
    }
  }
}
```

| Field       | Type    | Description                             |
|-------------|---------|-----------------------------------------|
| `paxnum`    | integer | Passenger index (`0` = first passenger) |
| `itemid`    | integer | Item ID from `getAncillaries`           |
| `bookingid` | integer | Booking ID                              |
| `flightid`  | integer | Flight ID                               |

**Response** — Raw AeroCRS confirmation object.

---

## 9. Confirm Booking

**`POST /confirmBooking`**
Finalize the booking with full passenger details. Only call once you have all required fields.

**Request Body**
```json
{
  "aerocrs": {
    "parms": {
      "bookingid": 789,
      "agentconfirmation": "apiconnector",
      "confirmationemail": "passenger@example.com",
      "passenger": [
        {
          "paxtitle": "Mr.",
          "firstname": "John",
          "lastname": "Doe",
          "paxage": null,
          "paxnationailty": "US",
          "paxdoctype": "PP",
          "paxdocnumber": "9919239123",
          "paxdocissuer": "US",
          "paxdocexpiry": "2028/12/31",
          "paxbirthdate": "1990/06/15",
          "paxphone": "+1234567890",
          "paxemail": "passenger@example.com"
        }
      ]
    }
  }
}
```

| Field                        | Type    | Description                                    |
|------------------------------|---------|------------------------------------------------|
| `bookingid`                  | integer | Booking ID                                     |
| `agentconfirmation`          | string  | Always `"apiconnector"`                        |
| `confirmationemail`          | string  | Email to receive confirmation receipt          |
| `passenger[].paxtitle`       | string  | Title (e.g. `"Mr."`, `"Ms."`)                  |
| `passenger[].firstname`      | string  | Passenger first name                           |
| `passenger[].lastname`       | string  | Passenger last name                            |
| `passenger[].paxage`         | null    | Always `null`                                  |
| `passenger[].paxnationailty` | string  | Nationality code (e.g. `"US"`)                 |
| `passenger[].paxdoctype`     | string  | Document type — `"PP"` (passport)              |
| `passenger[].paxdocnumber`   | string  | Passport number                                |
| `passenger[].paxdocissuer`   | string  | Issuing country code                           |
| `passenger[].paxdocexpiry`   | string  | Passport expiry `YYYY/MM/DD`                   |
| `passenger[].paxbirthdate`   | string  | Date of birth `YYYY/MM/DD`                     |
| `passenger[].paxphone`       | string  | Contact phone number                           |
| `passenger[].paxemail`       | string  | Contact email                                  |

**Response** — Raw AeroCRS confirmation response indicating success or failure.

---

## 10. Confirm Extras Reservation *(optional)*

**`POST /confirmExtrasReservation`**
Confirm seat assignments and ancillaries per passenger per flight. Call after `createAncillary` if seats or extras were selected.

**Request Body**
```json
{
  "aerocrs": {
    "parms": {
      "bookingid": "36720213",
      "pnrref": "28804C52",
      "companycode": "DS",
      "firstname": "Kevin",
      "lastname": "Klitrik",
      "confirmationemail": "test@test.com",
      "flights": [
        {
          "flightnumber": "A100",
          "flightdate": "YYYY/MM/DD",
          "passengers": [
            {
              "type": "ADT",
              "firstname": "Kevin",
              "lastname": "Klitrik",
              "seat": "10A",
              "ancillaries": "6955,7073"
            }
          ]
        }
      ]
    }
  }
}
```

| Field                      | Type   | Description                                                         |
|----------------------------|--------|---------------------------------------------------------------------|
| `bookingid`                | string | Booking ID from `createBooking`                                     |
| `pnrref`                   | string | PNR reference from `createBooking`                                  |
| `companycode`              | string | Airline/company code                                                |
| `firstname`                | string | Lead passenger first name                                           |
| `lastname`                 | string | Lead passenger last name                                            |
| `confirmationemail`        | string | Email to send confirmation to                                       |
| `flights[].flightnumber`   | string | Flight number                                                       |
| `flights[].flightdate`     | string | Flight date `YYYY/MM/DD`                                            |
| `passengers[].type`        | string | Passenger type: `"ADT"` (adult), `"CHD"` (child), `"INF"` (infant) |
| `passengers[].firstname`   | string | Passenger first name                                                |
| `passengers[].lastname`    | string | Passenger last name                                                 |
| `passengers[].seat`        | string | Selected seat number (e.g. `"10A"`)                                 |
| `passengers[].ancillaries` | string | Comma-separated item IDs from `getAncillaries` (e.g. `"6955,7073"`) |

**Response** — Raw AeroCRS confirmation of the extras reservation.
