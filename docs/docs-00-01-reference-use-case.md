# Kite Feature Store — Reference Use Case

**Purpose of This Document:**
This document describes a single, concrete use case that serves as the reference example across all project documentation, code examples, demos, and tests. Every abstraction in Kite maps to something tangible in this use case.

This is not a toy example. It is deliberately simplified, but it represents a realistic production pattern: pre-computing expensive aggregate features, storing them for low-latency serving, and providing point-in-time correct historical features for model training.

---

## 1. Business Context

An online real estate listing platform operates across two major cities in Turkey: **Istanbul** and **Ankara**. The platform runs on a standard web stack: React frontend, Node.js backend, PostgreSQL database.

The database contains approximately **3 million listing records** for homes listed between 2024-01-01 and 2024-12-31. Of these, **2 million are sold** (have a non-null `sold_at` date). The remaining 1 million are still active.

The dataset covers **6 towns** across the two cities:

| City     | Towns                    |
| -------- | ------------------------ |
| Istanbul | Kadıköy, Beşiktaş, Tuzla |
| Ankara   | Çankaya, Keçiören, Mamak |

Listings are fairly distributed across all 6 towns. Assume **today is 2025-01-01**.

---

## 2. Source Database Schema

The application database (PostgreSQL) has three tables. These are the authoritative source for all data that flows into the feature store.

**`cities`**

| Column | Type    | Description                   |
| ------ | ------- | ----------------------------- |
| `id`   | integer | Primary key.                  |
| `name` | string  | City name (e.g., "Istanbul"). |

Sample data:

| id  | name     |
| --- | -------- |
| 1   | Istanbul |
| 2   | Ankara   |

**`towns`**

| Column    | Type    | Description                  |
| --------- | ------- | ---------------------------- |
| `id`      | integer | Primary key.                 |
| `city_id` | integer | Foreign key → `cities.id`.   |
| `name`    | string  | Town name (e.g., "Kadikoy"). |

Sample data:

| id  | city_id | name     |
| --- | ------- | -------- |
| 1   | 1       | Kadikoy  |
| 2   | 1       | Besiktas |
| 3   | 1       | Tuzla    |
| 4   | 2       | Cankaya  |
| 5   | 2       | Kecioren |
| 6   | 2       | Mamak    |

**`listings`**

| Column            | Type     | Description                                                                      |
| ----------------- | -------- | -------------------------------------------------------------------------------- |
| `id`              | integer  | Primary key. Unique listing identifier.                                          |
| `town_id`         | integer  | Foreign key → `towns.id`. The town where the property is located.                |
| `net_area`        | integer  | Usable area of the house in square meters (e.g., 130).                           |
| `number_of_rooms` | integer  | Number of rooms (e.g., 3).                                                       |
| `build_year`      | integer  | Year the building was constructed (e.g., 2015).                                  |
| `asking_price`    | float    | The price set by the seller in TL. Becomes the sold price when `sold_at` is set. |
| `created_at`      | datetime | When the listing was first created.                                              |
| `updated_at`      | datetime | When the listing was last modified.                                              |
| `sold_at`         | datetime | When the listing was marked as sold. `NULL` if still active.                     |

**Key business rule:** A listing is considered **sold** when `sold_at IS NOT NULL`. The sold price is whatever `asking_price` is at the time `sold_at` is set.

Sample data:

| id   | town_id | net_area | number_of_rooms | build_year | asking_price | created_at          | updated_at          | sold_at             |
| ---- | ------- | -------- | --------------- | ---------- | ------------ | ------------------- | ------------------- | ------------------- |
| 1001 | 2       | 75       | 2               | 2020       | 2250000.00   | 2024-01-10 10:00:00 | 2024-03-15 11:00:00 | 2024-03-15 11:00:00 |
| 1002 | 1       | 130      | 3               | 2015       | 3400000.00   | 2024-02-20 09:30:00 | 2024-04-05 14:00:00 | 2024-04-05 14:00:00 |
| 1003 | 6       | 85       | 2               | 2002       | 1050000.00   | 2024-01-25 14:00:00 | 2024-03-18 14:30:00 | 2024-03-18 14:30:00 |
| 1004 | 4       | 110      | 3               | 2010       | 2100000.00   | 2024-03-01 11:00:00 | 2024-05-22 16:00:00 | 2024-05-22 16:00:00 |
| 1005 | 3       | 140      | 4               | 2008       | 2050000.00   | 2024-04-10 08:30:00 | 2024-06-11 10:15:00 | 2024-06-11 10:15:00 |
| 1006 | 5       | 95       | 2               | 2017       | 1400000.00   | 2024-05-15 12:00:00 | 2024-07-03 13:45:00 | 2024-07-03 13:45:00 |
| 1007 | 2       | 60       | 1               | 2019       | 1850000.00   | 2024-06-20 09:00:00 | 2024-08-20 09:30:00 | 2024-08-20 09:30:00 |
| 1008 | 1       | 105      | 3               | 2000       | 2800000.00   | 2024-07-05 16:00:00 | 2024-09-14 15:00:00 | 2024-09-14 15:00:00 |
| 1009 | 4       | 120      | 3               | 2012       | 2400000.00   | 2024-10-01 10:00:00 | 2024-11-15 11:00:00 | NULL                |
| 1010 | 3       | 90       | 2               | 2016       | 1250000.00   | 2024-01-05 09:00:00 | 2024-01-20 17:00:00 | 2024-01-20 17:00:00 |

Listing 1009 is still active (`sold_at` is `NULL`). Listing 1010 was sold in January 2024, which makes it a boundary case for point-in-time joins (see Section 7.3). The remaining 8 listings were sold between March and September 2024.

---

## 3. How the Application Works Today

The platform operates as a straightforward listing website:

1. A seller creates an account and fills out a form to list their house. They provide:
   **town**: filtered based on the selected city, then selected from town dropdown, stored as `town_id`,
   **net area**: square meters, integer, e.g., 130, stored as `net_area`,
   **number of rooms**: integer, e.g., 3, stored as `number_of_rooms`,
   **build year**: integer, e.g., 2015, stored as `build_year`,
   **asking price**: TL, float, e.g., 2,500,000.00. The seller sets this based on their own judgment. Stored as `asking_price`.

2. The listing appears on the platform. Buyers browse active listings.

3. Buyers and sellers communicate through the platform's messaging system. When a deal is reached, the seller marks the listing as sold. The `asking_price` at the time of marking becomes the sold price, and `sold_at` is set to the current timestamp.

4. Sold listings are no longer visible to buyers. The record remains in the database.

5. While a listing is active, the seller can update property details and asking price from their dashboard.

**What is missing:** There is no price guidance. Sellers set their asking price based on their own judgment. Some overprice, some underprice, and buyers have no way to assess whether a price is fair.

---

### 3.1. Listing Lifecycle Rules

These rules govern how listings behave on the platform. They determine how data flows through the system and into the feature store.

**Rule 1: One listing, one sale attempt.** Each listing has a unique `id` and tracks one house through one sale process.

**Rule 2: Sold listings are permanently archived.** When marked as sold, `sold_at` is set and the listing is archived. It cannot be reactivated.

**Rule 3: Not possible to relist the sold property.** User must create a new listing record, even if they want to sell the same house again in the future. This ensures a clean, immutable record of each sale.

**Rule 4: Only sold listings contribute to market calculations.** Active listings reflect seller expectations. Sold listings reflect actual market prices. Market features (`avg_price_per_sqm`) are computed exclusively from sold listings.

---

## 4. What the Business Wants to Add

The business wants to add a **price recommendation** feature: a machine learning model that estimates the current market value of a property based on its attributes and recent market conditions.

### 4.1. When Does the Recommendation Appear?

At two points in the user journey:

1. **Creating a new listing.** After the seller fills in property details, and asks for a price recommendation, the system shows a recommended price before the listing goes live.

2. **Updating an existing listing.** If a seller wants to adjust their asking price, and asks for a price recommendation, the system shows a fresh recommendation reflecting current market conditions.

### 4.2. What Does the User See?

A single number: **"Recommended market price: 2,450,000 TL"**.

The seller can follow or ignore the recommendation. It is guidance, not a constraint.

---

## 5. What Inputs Does the Model Need?

The model needs two categories of information:

- **House attributes:** Physical characteristics of the property (net area, number of rooms, build year). These come from what the seller entered in the form.

- **Market context:** What are recent price trends in this town? Specifically, the average sold price per square meter in the listing's town for the previous calendar month. This must be pre-computed from historical sales data because it is too expensive to calculate on every request.

---

## 6. Features Needed for Price Prediction

### 6.1. Model Features

The model receives **4 numeric features** and predicts a price. No categorical encoding or feature transformations are involved — all features are passed as raw numeric values.

| Feature             | Data Type | Source at Training Time                            | Source at Prediction Time             | Description                                                                                             |
| ------------------- | --------- | -------------------------------------------------- | ------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| `net_area`          | integer   | Offline store (`listing_features.net_area`)        | Seller form input                     | Usable area of the house in sqm.                                                                        |
| `number_of_rooms`   | integer   | Offline store (`listing_features.number_of_rooms`) | Seller form input                     | Number of rooms.                                                                                        |
| `build_year`        | integer   | Offline store (`listing_features.build_year`)      | Seller form input                     | Year the building was constructed.                                                                      |
| `avg_price_per_sqm` | float     | Offline store (`town_market_features`, joined)     | Online store (looked up by `town_id`) | Average sold price per sqm in this town last month. Captures both location value and market conditions. |

**Why there is no location categorical feature (no `town_id`, `town_name`, or `town_label` in the model):**

The `avg_price_per_sqm` feature already encodes the location signal. It tells the model "houses in this area are currently selling at X TL per sqm." Two towns with similar market conditions will have similar `avg_price_per_sqm` values, and the model treats them similarly — which is correct behavior. This approach scales to any number of locations without introducing high-cardinality categorical encoding problems.

**Trade-off acknowledged:** This is a deliberate simplification. Using `avg_price_per_sqm` as a proxy for location captures overall price levels but not location-specific effects — for example, the value of an extra room may differ between a luxury district and an affordable one, even at similar price-per-sqm levels. Adding an explicit categorical location feature would let the model learn these differences, but it would require categorical encoding in the model pipeline and architectural decision for how to manage it. That is a modeling concern, not a feature store concern — the feature store stores and serves numeric values regardless. This trade-off is acceptable for the MVP scope.

### 6.2. Label (Training Only)

| Name         | Data Type | DB Source                                                                | Description                                                                                                     |
| ------------ | --------- | ------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------- |
| `sold_price` | float     | `listings.asking_price` (only rows where `listings.sold_at IS NOT NULL`) | The actual sold price in TL. The target variable the model learns to predict. Not available at prediction time. |

### 6.3. What the Model Receives

**At training time:**

**Features (X):**

- net_area (integer)
- number_of_rooms (integer)
- build_year (integer)
- avg_price_per_sqm (float)

**Target (y):**

- sold_price (float)

4 numeric features → 1 numeric target.

**At prediction time:**

```
From seller form:                          From online store:
  net_area = 130                             avg_price_per_sqm = 27200.00
  number_of_rooms = 3                              (looked up by town_id)
  build_year = 2015
         │                                           │
         └──────────────┬────────────────────────────┘
                        ▼
                  Model predicts
                        ▼
                  sold_price = 3,450,000 TL
```

---

## 7. What the Feature Store Stores

The feature store organizes data into **feature groups**. A feature group is a logical collection of related features that share the same entity key, the same event timestamp, and the same update cadence.

The feature store has two storage layers:

- **Offline store:** Historical feature data on disk (e.g., Parquet on S3). Used for generating training datasets.
- **Online store:** Latest feature values in a low-latency key-value store (e.g., DynamoDB, SQLite). Used for real-time prediction serving.

**Important principle:** The feature store stores exactly what it receives during ingestion. It does not run queries against source databases, transform raw data, or apply business logic. The SQL queries shown in the subsections below represent the user's data preparation step — they run outside the feature store, producing data that is then passed to the feature store's ingestion API.

---

### 7.1. Feature Group: `listing_features` (Offline Store Only)

**What:** Historical sold listing records with their attributes and sold price.

**Entity key:** `listing_id` (one row per sold listing)

**Event timestamp:** `event_timestamp` — the date the listing was sold. Used for point-in-time joins and time-range filtering.

**Why offline only:** At prediction time, house attributes come from the seller form. There is no need for low-latency feature store lookups for these values. But during training, we need historical listing data joined with point-in-time correct market features. Storing listing features in the offline store enables this join and decouples training from the production database.

**Relationship to other feature groups:** The `town_id` field in this feature group is the join key to `town_market_features`. This relationship is declared in the feature group definition and enables the feature store to automatically perform point-in-time joins when both feature groups are requested together.

**Fields stored and their database origins:**

| Feature Store Field | Type     | DB Source                                                  | Role          | Description                                            |
| ------------------- | -------- | ---------------------------------------------------------- | ------------- | ------------------------------------------------------ |
| `listing_id`        | integer  | `listings.id`                                              | Entity key    | Unique listing identifier.                             |
| `town_id`           | integer  | `listings.town_id`                                         | Join key      | Links to `town_market_features`. Not a model feature.  |
| `net_area`          | integer  | `listings.net_area`                                        | Model feature | Usable area in sqm.                                    |
| `number_of_rooms`   | integer  | `listings.number_of_rooms`                                 | Model feature | Number of rooms.                                       |
| `build_year`        | integer  | `listings.build_year`                                      | Model feature | Year the building was constructed.                     |
| `sold_price`        | float    | `listings.asking_price` (only where `sold_at IS NOT NULL`) | Label         | The sold price. Training target.                       |
| `event_timestamp`   | datetime | `listings.sold_at`                                         | Structural    | When the listing was sold. Drives point-in-time joins. |

**Ingestion query:**

```sql
SELECT
    l.id              AS listing_id,
    l.town_id         AS town_id,
    l.net_area        AS net_area,
    l.number_of_rooms AS number_of_rooms,
    l.build_year      AS build_year,
    l.asking_price    AS sold_price,
    l.sold_at         AS event_timestamp
FROM listings l
WHERE l.sold_at IS NOT NULL
```

**Storage:** Offline only — not stored in the online store.

**Update cadence:** Monthly batch. Each run picks up newly sold listings from the previous month and appends them to the offline store.

**Data volume:** Approximately 2 million rows initially (all historical sold listings). Grows by roughly 150K–200K rows per month as new listings sell.

**Sample data (corresponding to the sold listings from Section 2):**

| listing_id | town_id | net_area | number_of_rooms | build_year | sold_price | event_timestamp     |
| ---------- | ------- | -------- | --------------- | ---------- | ---------- | ------------------- |
| 1010       | 3       | 90       | 2               | 2016       | 1250000.00 | 2024-01-20 17:00:00 |
| 1001       | 2       | 75       | 2               | 2020       | 2250000.00 | 2024-03-15 11:00:00 |
| 1003       | 6       | 85       | 2               | 2002       | 1050000.00 | 2024-03-18 14:30:00 |
| 1002       | 1       | 130      | 3               | 2015       | 3400000.00 | 2024-04-05 14:00:00 |
| 1004       | 4       | 110      | 3               | 2010       | 2100000.00 | 2024-05-22 16:00:00 |
| 1005       | 3       | 140      | 4               | 2008       | 2050000.00 | 2024-06-11 10:15:00 |
| 1006       | 5       | 95       | 2               | 2017       | 1400000.00 | 2024-07-03 13:45:00 |
| 1007       | 2       | 60       | 1               | 2019       | 1850000.00 | 2024-08-20 09:30:00 |
| 1008       | 1       | 105      | 3               | 2000       | 2800000.00 | 2024-09-14 15:00:00 |

Listing 1009 is not included because it has not been sold (`sold_at IS NULL`). Listing 1010 is included — it was sold in January 2024 and will be affected by the boundary condition described in Section 7.3.

---

### 7.2. Feature Group: `town_market_features` (Offline Store + Online Store)

**What:** The average sold price per square meter for each town for each month.

**Entity key:** `town_id` (unique town identifier, not town name — town names are not guaranteed unique across cities)

**Event timestamp:** `event_timestamp` — set to the **first day of the month after** the month the data was computed from. This represents when the value became available (the batch job computes it after the month ends). This convention ensures the standard point-in-time join (`event_timestamp ≤ listing sold date`) automatically prevents data leakage without requiring special offset logic.

**Why both stores:**

- **Offline store:** Each historical listing must be joined with the market feature that was available at the time of sale (point-in-time correctness for training).
- **Online store:** At prediction time, the backend retrieves the latest market feature for a town with low latency.

**Fields stored and their computation origins:**

| Feature Store Field | Type     | Source                                                                                       | Role          | Description                                                                                       |
| ------------------- | -------- | -------------------------------------------------------------------------------------------- | ------------- | ------------------------------------------------------------------------------------------------- |
| `town_id`           | integer  | `towns.id` (the grouping key)                                                                | Entity key    | Unique town identifier. Lookup key.                                                               |
| `avg_price_per_sqm` | float    | `AVG(listings.asking_price / listings.net_area)` for sold listings in a given town and month | Model feature | Average sold price per sqm.                                                                       |
| `event_timestamp`   | datetime | Derived: first day of the month **after** the computation month                              | Structural    | When this value became available. Stored in both offline and online stores. Useful for debugging. |

**Computation query (example for January 2024 sales):**

```sql
SELECT
    l.town_id                               AS town_id,
    AVG(l.asking_price / l.net_area)        AS avg_price_per_sqm,
    '2024-02-01'::timestamp                 AS event_timestamp
FROM listings l
WHERE l.sold_at IS NOT NULL
  AND l.sold_at >= '2024-01-01'
  AND l.sold_at < '2024-02-01'
GROUP BY l.town_id
```

This query produces 6 rows (one per town) with `event_timestamp = 2024-02-01`, meaning "these values were computed from January 2024 sales and became available on February 1."

**Storage:** Both offline and online stores.

**Update cadence:** Monthly. The batch job runs on the first of each month, computes aggregates from the previous month's sales, and ingests them into the offline store (append). A separate `materialize()` call then reads all offline data, extracts the latest value per entity key, and fully overwrites the online store.

**Data volume:** 6 rows per month (one per town). After 12 months: 72 rows in the offline store. 6 rows in the online store (latest only).

**Sample data (offline store — full history):**

| town_id | avg_price_per_sqm | event_timestamp |
| ------- | ----------------- | --------------- |
| 1       | 24500.00          | 2024-02-01      |
| 2       | 28200.00          | 2024-02-01      |
| 3       | 14100.00          | 2024-02-01      |
| 4       | 18500.00          | 2024-02-01      |
| 5       | 14200.00          | 2024-02-01      |
| 6       | 11800.00          | 2024-02-01      |
| 1       | 25100.00          | 2024-03-01      |
| 2       | 28800.00          | 2024-03-01      |
| 3       | 14300.00          | 2024-03-01      |
| 4       | 18700.00          | 2024-03-01      |
| 5       | 14300.00          | 2024-03-01      |
| 6       | 11900.00          | 2024-03-01      |
| 1       | 25400.00          | 2024-04-01      |
| 2       | 29100.00          | 2024-04-01      |
| 3       | 14500.00          | 2024-04-01      |
| 4       | 18800.00          | 2024-04-01      |
| 5       | 14400.00          | 2024-04-01      |
| 6       | 12000.00          | 2024-04-01      |
| ...     | ...               | ...             |

Each row with `event_timestamp = 2024-02-01` was computed from **January 2024** sales data. Each row with `event_timestamp = 2024-03-01` was computed from **February 2024** sales data, and so on.

**Note:** Above table presentation is for simplicity. Even if the table shows the newly created rows as appended, the table above shows rows conceptually. The physical storage layout is an implementation detail may be different, for example a new file may be created by following the Hive style partitioning convention.

**Sample data (online store — latest value per town only):**

| town_id | avg_price_per_sqm | event_timestamp |
| ------- | ----------------- | --------------- |
| 1       | 27200.00          | 2025-01-01      |
| 2       | 31500.00          | 2025-01-01      |
| 3       | 15800.00          | 2025-01-01      |
| 4       | 19200.00          | 2025-01-01      |
| 5       | 14800.00          | 2025-01-01      |
| 6       | 12100.00          | 2025-01-01      |

These values were computed from **December 2024** sales (event_timestamp = 2025-01-01). The `event_timestamp` field is stored alongside the feature value and can be retrieved by callers for debugging.

---

### 7.3. How Point-in-Time Joins Work Between the Two Feature Groups

When the feature store is asked for features from both `listing_features` and `town_market_features`, it joins them automatically.

**Join key:** `listing_features.town_id` = `town_market_features.town_id`

**Temporal condition:** `town_market_features.event_timestamp` ≤ `listing_features.event_timestamp`, take the latest matching row.

**This relationship is declared at the feature group definition level**, not at query time. The `listing_features` definition specifies that its `town_id` field is a join key to `town_market_features`. The feature store uses this metadata to resolve joins automatically when features from both groups are requested.

**Worked example:**

Listing 1002: town_id = 1, event_timestamp = 2024-04-05 14:00:00 (sold April 5)

Feature store looks for town_market_features WHERE:
town_id = 1 AND event_timestamp ≤ 2024-04-05

Available matches:
town_id=1, event_timestamp=2024-02-01, avg_price_per_sqm=24500.00 (from Jan sales) [match]
town_id=1, event_timestamp=2024-03-01, avg_price_per_sqm=25100.00 (from Feb sales) [match]
town_id=1, event_timestamp=2024-04-01, avg_price_per_sqm=25400.00 (from Mar sales) [match] ← latest, selected
town_id=1, event_timestamp=2024-05-01 (from Apr sales) [excluded — not yet available on Apr 5]

Result: Listing 1002 gets avg_price_per_sqm = 25400.00 (from March 2024 sales for town_id 1).

**Boundary condition:** Listings sold in January 2024 (such as listing 1010, sold on 2024-01-20) cannot be matched with any market feature because the earliest `event_timestamp` is `2024-02-01` (from January 2024 sales, available February 1). Since `2024-02-01 > any date in January`, no match exists. These listings get `NULL` for `avg_price_per_sqm` and are excluded from training. This affects approximately one month of data and is an acceptable trade-off for the first model with this limited dataset.

---

### 7.4. What Is NOT in the Feature Store

| Item                                                | Where It Lives                       | Why Not in the Feature Store                                            |
| --------------------------------------------------- | ------------------------------------ | ----------------------------------------------------------------------- |
| Raw database tables (`listings`, `towns`, `cities`) | PostgreSQL application database      | The feature store stores curated features, not raw operational data.    |
| House attributes at serving time                    | Seller form input                    | Immediately available from the request. No pre-computation needed.      |
| Town names, city names                              | Application database                 | Not model features. Location signal is captured by `avg_price_per_sqm`. |
| The trained model itself                            | Model registry / model serving infra | The feature store provides features to models. It does not host models. |

---

## 8. Real Life Example Cases

### 8.1. Case 1 - Training Flow - Initial Training (No Feature Store Yet)

**Situation:** The platform has been running for a year. Today is 2025-01-01. There are 3 million listing records in the database, 2 million of which are sold. No feature store exists yet. No model has been trained. We want to train the first model and bootstrap the feature store.

**Step 1: Compute historical market features from raw data.**

Since the feature store does not exist yet, we compute `avg_price_per_sqm` directly from the database for all historical months.

```
For each month M in [January 2024 ... December 2024]:
  For each town_id T in [1, 2, 3, 4, 5, 6]:
    avg_price_per_sqm(T, M) = AVG(listings.asking_price / listings.net_area)
      WHERE listings.town_id = T
        AND listings.sold_at IS NOT NULL
        AND listings.sold_at falls within month M

    event_timestamp = first day of month M+1
```

This produces **72 rows** (12 months × 6 towns).

**Step 2: Bootstrap the feature store.**

Load the computed data into the feature store:

- **Offline store — `town_market_features`:** Load all 72 rows of historical market features.
- **Offline store — `listing_features`:** Load all ~2 million sold listing records (via the ingestion query in Section 7.1).
- **Online store — `town_market_features`:** Materialize the latest month's values only (6 rows, one per town, computed from December 2024 sales).

**Step 3: Generate the training dataset from the feature store.**

```python
training_df = store.get_historical_features(
    from_="listing_features",
    join=["town_market_features"],
    select={
        "listing_features": ["net_area", "number_of_rooms", "build_year", "sold_price"],
        "town_market_features": ["avg_price_per_sqm"],
    },
    where={
        "event_timestamp": {
            "gte": datetime(2024, 2, 1),
            "lte": datetime(2024, 12, 31, 23, 59, 59),
        },
    },
)
```

**Note on event_timestamp boundaries:** The first training run uses ~11 months due to the bootstrap boundary condition; subsequent runs use the full 12-month window.

**Note on datetime precision in `where` filters:** Datetime comparisons in Kite are timestamp-precise — the full value including the time component is compared. Writing `"lte": datetime(2024, 12, 31)` without explicit time arguments is equivalent to `"lte": datetime(2024, 12, 31, 0, 0, 0)` — which means "at or before midnight at the start of December 31." This would exclude any listing sold later on December 31 (e.g., `2024-12-31 15:00:00`). To include the full day, either specify the time explicitly as shown above (`datetime(2024, 12, 31, 23, 59, 59)`) or use the half-open interval pattern with `lt` and the first moment of the next period: `"lt": datetime(2025, 1, 1)`. Both approaches are equivalent. This document uses explicit time for readability; choose whichever convention fits your project.


The feature store:

1. Reads `listing_features` (the `from_` group) from the offline store, filtered to Feb–Dec 2024 (excluding January due to the boundary condition). Note: the `where` filter applies exclusively to the base feature group (`from_`). Joined groups are not filtered by `where` — their temporal scope is determined by the point-in-time join condition.
2. Identifies that `town_market_features` is declared in `join` and that specific features are requested from it via `select`.
3. From the feature group definition, knows that `listing_features.town_id` joins to `town_market_features.town_id`.
4. Performs the point-in-time join for each listing row.
5. Returns the merged DataFrame with only the selected columns plus structural columns (`listing_id`, `event_timestamp`).

**Result (showing the sample listings from Section 2 — the full dataset contains ~2 million rows):**

| listing_id | event_timestamp     | net_area | number_of_rooms | build_year | sold_price | avg_price_per_sqm |
| ---------- | ------------------- | -------- | --------------- | ---------- | ---------- | ----------------- |
| 1001       | 2024-03-15 11:00:00 | 75       | 2               | 2020       | 2250000.00 | 28800.00          |
| 1003       | 2024-03-18 14:30:00 | 85       | 2               | 2002       | 1050000.00 | 11900.00          |
| 1002       | 2024-04-05 14:00:00 | 130      | 3               | 2015       | 3400000.00 | 25400.00          |
| 1004       | 2024-05-22 16:00:00 | 110      | 3               | 2010       | 2100000.00 | 19000.00          |
| 1005       | 2024-06-11 10:15:00 | 140      | 4               | 2008       | 2050000.00 | 14900.00          |
| 1006       | 2024-07-03 13:45:00 | 95       | 2               | 2017       | 1400000.00 | 14600.00          |
| 1007       | 2024-08-20 09:30:00 | 60       | 1               | 2019       | 1850000.00 | 30200.00          |
| 1008       | 2024-09-14 15:00:00 | 105      | 3               | 2000       | 2800000.00 | 26800.00          |
| ...        | ...                 | ...      | ...             | ...        | ...        | ...               |

Listing 1010 (sold January 20) is excluded — it falls outside the `gte: 2024-02-01` filter. Even if it were included, the point-in-time join would find no matching market feature (see Section 7.3 boundary condition).

**Step 4: Train the model.**

```python
feature_columns = ["net_area", "number_of_rooms", "build_year", "avg_price_per_sqm"]
label_column = "sold_price"

X = training_df[feature_columns]
y = training_df[label_column]

model.fit(X, y)
```

**X (features passed to model):**

| net_area | number_of_rooms | build_year | avg_price_per_sqm |
| -------- | --------------- | ---------- | ----------------- |
| 75       | 2               | 2020       | 28800.00          |
| 85       | 2               | 2002       | 11900.00          |
| 130      | 3               | 2015       | 25400.00          |
| 110      | 3               | 2010       | 19000.00          |
| 140      | 4               | 2008       | 14900.00          |
| 95       | 2               | 2017       | 14600.00          |
| 60       | 1               | 2019       | 30200.00          |
| 105      | 3               | 2000       | 26800.00          |
| ...      | ...             | ...        | ...               |

**y (target):**

| sold_price |
| ---------- |
| 2250000.00 |
| 1050000.00 |
| 3400000.00 |
| 2100000.00 |
| 2050000.00 |
| 1400000.00 |
| 1850000.00 |
| 2800000.00 |
| ...        |

**Step 5: Deploy the model.**

The trained model is saved and made available to the backend for serving predictions.

---

### 8.2. Case 2 - Training Flow - Monthly Retraining (Feature Store Populated)

**Situation:** The model and feature store have been running in production. Today is 2025-02-01. The January 2025 batch job has just completed. We want to retrain the model with updated data.

**What the monthly batch job did (before retraining):**

1. Queried the PostgreSQL database for listings newly sold in January 2025.
2. Ingested those sold listings into the offline store's `listing_features`, adds as new data.
3. Computed `avg_price_per_sqm` for each town from January 2025 sales.
4. Ingested the results into the offline store's `town_market_features`, adds 6 rows with `event_timestamp = 2025-02-01` as new data.
5. Materialized `town_market_features` to the online store — `store.materialize()` reads all offline data, extracts the latest value per entity key, and fully overwrites the online store (6 rows, one per town).

**After this job completes, the offline store contains everything needed for retraining. The production database is not involved in training.**

**Step 1: Generate the training dataset from the feature store.**

This use case uses a **rolling 12-month window**: only sold listings from the past 12 months are included. Real estate markets shift over time — pricing patterns from years ago may not reflect current conditions.

```python
training_df = store.get_historical_features(
    from_="listing_features",
    join=["town_market_features"],
    select={
        "listing_features": ["net_area", "number_of_rooms", "build_year", "sold_price"],
        "town_market_features": ["avg_price_per_sqm"],
    },
    where={
        "event_timestamp": {
            "gte": datetime(2024, 2, 1),
            "lte": datetime(2025, 1, 31, 23, 59, 59),
        },
    },
)
```

The feature store reads, joins, and returns the complete training DataFrame — same mechanics as Step 3 in Case 1.

Note: All features from the `from_` group can be retrieved via the `"*"` wildcard in `select` without needing to specify the exact fields. For example:

```python
training_df = store.get_historical_features(
    from_="listing_features",
    join=["town_market_features"],
    select={
        "listing_features": "*",
        "town_market_features": ["avg_price_per_sqm"],
    },
    where={
        "event_timestamp": {
            "gte": datetime(2024, 2, 1),
            "lte": datetime(2025, 1, 31, 23, 59, 59),
        },
    },
)
```

The `"*"` wildcard returns all fields from `listing_features` — entity key (`listing_id`), event timestamp (`event_timestamp`), and all features (`net_area`, `number_of_rooms`, `build_year`, `sold_price`, `town_id`) — plus the joined `avg_price_per_sqm` from `town_market_features`.

When `"*"` is used for a joined group as well, the joined group's features and `event_timestamp` are included. The joined group's entity key is not duplicated — it is the join key already present from the `from_` group. Column name conflicts are resolved by prefixing the conflicting joined column with the joined group's name (FR-OFF-010). For example:

```python
training_df = store.get_historical_features(
    from_="listing_features",
    join=["town_market_features"],
    select={
        "listing_features": "*",
        "town_market_features": "*",
    },
    where={
        "event_timestamp": {
            "gte": datetime(2024, 2, 1),
            "lte": datetime(2025, 1, 31, 23, 59, 59),
        },
    },
)
```

The resulting DataFrame has these columns:

| Column | Source | Notes |
| --- | --- | --- |
| `listing_id` | `listing_features` (entity key) | Structural — always included |
| `event_timestamp` | `listing_features` (event timestamp) | Structural — always included, unprefixed (base group) |
| `town_id` | `listing_features` (join key) | Present once — the join key is not duplicated |
| `net_area` | `listing_features` (feature) | No conflict |
| `number_of_rooms` | `listing_features` (feature) | No conflict |
| `build_year` | `listing_features` (feature) | No conflict |
| `sold_price` | `listing_features` (feature) | No conflict |
| `avg_price_per_sqm` | `town_market_features` (feature) | No conflict — keeps original name |
| `town_market_features_event_timestamp` | `town_market_features` (event timestamp) | Prefixed — conflicts with base `event_timestamp` |

The `event_timestamp` from `town_market_features` is always included (structural column) and is always prefixed because it invariably conflicts with the base group's `event_timestamp`. The `avg_price_per_sqm` column has no naming conflict and keeps its original name.

**Step 2: Train and deploy.**

```python
X = training_df[["net_area", "number_of_rooms", "build_year", "avg_price_per_sqm"]]
y = training_df["sold_price"]

model.fit(X, y)
```

The trained model replaces the previous one in the serving infrastructure.

---

### 8.3. Case 3 - User Flow - New Listing with Price Recommendation

A seller wants to list a house and get a price recommendation. **Current date: 2025-06-05.**

1. Seller opens the "Create Listing" page.

2. Seller fills in the form:
   - Town: Kadikoy (dropdown selection, stored as town_id = 1)
   - Net area: 130 sqm
   - Number of rooms: 3
   - Build year: 2015

3. Seller clicks "Get Price Recommendation."

4. Backend receives the form data and assembles the model input:

   a. From the form:
   - net_area = 130
   - number_of_rooms = 3
   - build_year = 2015

   b. Retrieves the market feature from the feature store online store:
   - Calls: get_online_features(
     from_="town_market_features",
     select=["avg_price_per_sqm"],
     where={"town_id": {"eq": 1}},
     )
   - Receives: {"town_id": 1, "event_timestamp": "2025-06-01T00:00:00", "avg_price_per_sqm": 27800.00}
     (Computed from May 2025 sales. The June batch job has not
     run yet because June is not over.)
     The caller accesses result["avg_price_per_sqm"] to get the value.

   c. Sends all inputs to the model:

   ```
     {
       net_area: 130,
       number_of_rooms: 3,
       build_year: 2015,
       avg_price_per_sqm: 27800.00
     }
   ```

   d. Model returns predicted price: 3,650,000 TL.

5. Backend returns the recommendation to the frontend.

6. Seller sees: "Recommended market price: 3,650,000 TL"

7. Seller decides on their asking price and publishes the listing.

### 8.4. Case 4 - User Flow - Updating an Existing Listing

A seller listed a house a month ago. It has not sold. They want a fresh recommendation. **Current date: 2025-07-05.**

1. Seller opens their dashboard and selects their active listing.
   The listing details are in the application database:
   - id: 50001
   - town_id: 5
   - net_area: 95 sqm
   - number_of_rooms: 2
   - build_year: 2008

2. Seller clicks "Get Price Recommendation."

3. Backend follows the same process as "Case 3 - User Flow - New Listing with Price Recommendation":

   a. From the database record:
   - net_area = 95
   - number_of_rooms = 2
   - build_year = 2008

   b. Online store lookup:
   - get_online_features(
     from_="town_market_features",
     select=["avg_price_per_sqm"],
     where={"town_id": {"eq": 5}},
     )
   - Receives: {"town_id": 5, "event_timestamp": "2025-07-01T00:00:00", "avg_price_per_sqm": 15200.00}
     (Computed from June 2025 sales. July batch job hasn't run yet.)
     The caller accesses result["avg_price_per_sqm"] to get the value.
   - This value may differ from last month's because the July 1
     batch job updated the online store with June's data.

   c. Model input:

   ```
     {
       net_area: 95,
       number_of_rooms: 2,
       build_year: 2008,
       avg_price_per_sqm: 15200.00
     }
   ```

   d. Model predicts: 1,450,000 TL.

4. Seller sees the recommendation and decides whether to adjust their price.

### 8.5. Case 5 - User Flow - A House Gets Sold

A buyer and seller agree on a deal. **Current date: 2025-09-05.**

1. Seller marks listing 50001 as sold on their dashboard.

2. The application updates the database:
   - listings.sold_at = 2025-09-05 14:30:00
   - listings.asking_price remains 1,400,000 TL (the sold price)

3. The listing is no longer visible to buyers.

4. This record will be picked up by the next monthly batch job
   (runs October 1):
   - The batch job queries the database for listings sold in September 2025.
   - This listing is ingested into the offline store's listing_features.
   - Its sold price (1,400,000 TL) and net_area (95 sqm) contribute to
     the computation of avg_price_per_sqm for town_id 5 for September.
   - The computed value is ingested into the offline store's
     `town_market_features` (event_timestamp = 2025-10-01).
   - A subsequent `materialize()` then updates the online store by
     reading all offline data, extracting the latest value per entity
     key, and fully overwriting the existing online entries.

---

## 9. Summary: The Feature Store's Role

**The feature store does:**

- Store pre-computed market features (`avg_price_per_sqm` per town per month) in the offline store for training.
- Serve the latest market features from the online store for real-time prediction requests.
- Store historical sold listing records in the offline store for training dataset generation.
- Perform point-in-time correct joins when generating training datasets, ensuring each listing is matched with the market conditions that existed at the time of sale.
- Provide an ORM-like interface: declare feature groups and their relationships once, then query across them using `from_`, `select`, `where`, and `join` parameters — similar to how ORMs express queries.

**The feature store does not:**

- Serve house attributes at prediction time (those come from the seller form or application database).
- Run the ML model or host model artifacts.
- Handle feature transformations of any kind (all features are raw numeric values).
- Replace the application database as the system of record.

**At a glance:**

```
                                      Offline Store       Online Store
                                      ─────────────       ────────────

listing_features
  ├─ listing_id  (entity key)             Yes                 No
  ├─ town_id     (join key)               Yes                 No
  ├─ net_area    (model feature)          Yes                 No
  ├─ number_of_rooms   (model feature)    Yes                 No
  ├─ build_year  (model feature)          Yes                 No
  ├─ sold_price  (label)                  Yes                 No
  └─ event_timestamp                      Yes                 No

town_market_features
  ├─ town_id     (entity key)             Yes                 Yes
  ├─ avg_price_per_sqm (feature)          Yes (full history)  Yes (latest only)
  └─ event_timestamp                      Yes                 Yes (latest only, optional to use)
```
