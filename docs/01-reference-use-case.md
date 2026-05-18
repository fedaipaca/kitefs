# Reference Use Case

## Purpose

This file describes the Turkish real estate reference use case as the concrete example for KiteFS. Other files may link here when they need an example without redefining it.

## Owns

- Turkish real estate example.
- Source database schema.
- Business rules.
- Feature group examples.
- Expected workflow walkthrough.

## Does Not Own

- Generic system requirements.
- Architecture.

## Content

This use case follows an online real estate listing platform in Turkey. It shows what KiteFS stores, how the stored data is prepared, and how the same feature definitions support training and serving.

KiteFS does not compute the feature values in this example. The platform team prepares data with SQL, Pandas, or another tool, then writes the prepared feature rows into KiteFS.

## Business Context

The platform operates in two cities: İstanbul and Ankara. It has a React frontend, a Python-based FastAPI REST API backend, and a PostgreSQL application database.

For the MVP scope, KiteFS supports only the Python programming language and is used in Python environments.

The database contains about 3 million listings for homes listed between 2024-01-01 and 2024-12-31. About 2 million listings are sold, which means `sold_at` is not null. The remaining 1 million listings are still active.

The dataset covers 6 towns. PostgreSQL stores city and town names.

| City | Towns |
| --- | --- |
| İstanbul | Kadıköy, Beşiktaş, Tuzla |
| Ankara | Çankaya, Keçiören, Mamak |

Assume the starting date for the first training workflow is `2025-01-01 00:00:00`.

All timestamps in this document are UTC for simplicity. The application database, batch preparation logic, and KiteFS examples use UTC directly and do not apply any time conversion.

## Source Database Schema

The application database has three source tables. They remain the system of record for operational data.

### `cities`

| Column | Type | Description |
| --- | --- | --- |
| `id` | integer | Primary key. |
| `name` | string | City name. |

Sample data:

| id | name |
| --- | --- |
| 1 | İstanbul |
| 2 | Ankara |

### `towns`

| Column | Type | Description |
| --- | --- | --- |
| `id` | integer | Primary key. |
| `city_id` | integer | Foreign key to `cities.id`. |
| `name` | string | Town name. |

Sample data:

| id | city_id | name |
| --- | --- | --- |
| 1 | 1 | Kadıköy |
| 2 | 1 | Beşiktaş |
| 3 | 1 | Tuzla |
| 4 | 2 | Çankaya |
| 5 | 2 | Keçiören |
| 6 | 2 | Mamak |

### `listings`

| Column | Type | Description |
| --- | --- | --- |
| `id` | integer | Primary key. Unique listing identifier. |
| `town_id` | integer | Foreign key to `towns.id`. |
| `net_area` | integer | Usable area of the house in square meters. |
| `number_of_rooms` | integer | Number of rooms. |
| `build_year` | integer | Year the building was constructed. |
| `asking_price` | float | Price set by the seller in TL. Becomes the sold price when `sold_at` is set. |
| `created_at` | datetime | When the listing was first created. |
| `updated_at` | datetime | When the listing was last modified. |
| `sold_at` | datetime | When the listing was marked as sold. `NULL` if the listing is still active. |

A listing is sold when `sold_at IS NOT NULL`. The sold price is the `asking_price` at the time `sold_at` is set.

Sample data:

| id | town_id | net_area | number_of_rooms | build_year | asking_price | created_at | updated_at | sold_at |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1001 | 2 | 75 | 2 | 2020 | 2250000.00 | 2024-01-10 10:00:00 | 2024-03-15 11:00:00 | 2024-03-15 11:00:00 |
| 1002 | 1 | 130 | 3 | 2015 | 3400000.00 | 2024-02-20 09:30:00 | 2024-04-05 14:00:00 | 2024-04-05 14:00:00 |
| 1003 | 6 | 85 | 2 | 2002 | 1050000.00 | 2024-01-25 14:00:00 | 2024-03-18 14:30:00 | 2024-03-18 14:30:00 |
| 1004 | 4 | 110 | 3 | 2010 | 2100000.00 | 2024-03-01 11:00:00 | 2024-05-22 16:00:00 | 2024-05-22 16:00:00 |
| 1005 | 3 | 140 | 4 | 2008 | 2050000.00 | 2024-04-10 08:30:00 | 2024-06-11 10:15:00 | 2024-06-11 10:15:00 |
| 1006 | 5 | 95 | 2 | 2017 | 1400000.00 | 2024-05-15 12:00:00 | 2024-07-03 13:45:00 | 2024-07-03 13:45:00 |
| 1007 | 2 | 60 | 1 | 2019 | 1850000.00 | 2024-06-20 09:00:00 | 2024-08-20 09:30:00 | 2024-08-20 09:30:00 |
| 1008 | 1 | 105 | 3 | 2000 | 2800000.00 | 2024-07-05 16:00:00 | 2024-09-14 15:00:00 | 2024-09-14 15:00:00 |
| 1009 | 4 | 120 | 3 | 2012 | 2400000.00 | 2024-10-01 10:00:00 | 2024-11-15 11:00:00 | NULL |
| 1010 | 3 | 90 | 2 | 2016 | 1250000.00 | 2024-01-05 09:00:00 | 2024-01-20 17:00:00 | 2024-01-20 17:00:00 |

Listing 1009 is still active. Listing 1010 was sold in January 2024, which makes it the boundary case for the point-in-time join example.

## Listing Lifecycle Rules

1. One listing tracks one sale attempt for one house.
2. When a listing is marked as sold, `sold_at` is set and the listing is archived.
3. A sold listing cannot be reactivated. Selling the same property again requires a new listing record.
4. Only sold listings contribute to market calculations. Active listings reflect seller expectations, not actual market prices.

## Price Recommendation Goal

The business wants to add a price recommendation feature. A machine learning model estimates the current market value of a property from its attributes and recent market conditions.

The recommendation appears when a seller creates a new listing or updates an existing listing. The seller sees one number, such as `Recommended market price: 2,450,000 TL`. The recommendation is guidance, not a constraint.

## Model Inputs

The model receives 4 numeric features and predicts a price.

| Feature | Data Type | Source at Training Time | Source at Prediction Time | Description |
| --- | --- | --- | --- | --- |
| `net_area` | integer | Offline store, `listing_features.net_area` | Seller form input | Usable area of the house in square meters. |
| `number_of_rooms` | integer | Offline store, `listing_features.number_of_rooms` | Seller form input | Number of rooms. |
| `build_year` | integer | Offline store, `listing_features.build_year` | Seller form input | Year the building was constructed. |
| `avg_price_per_sqm` | float | Offline store, joined from `town_market_features` | Online store lookup by `town_id` | Average sold price per square meter in the town, computed only from sold listings whose `sold_at` falls in the previous calendar month. |

The training label is `sold_price`, which comes from `listings.asking_price` for rows where `sold_at IS NOT NULL`. It is available only during training.

The model does not receive `town_id` as a categorical feature in this example. `town_id` is a structural join key that KiteFS uses to connect `listing_features` to `town_market_features`. The location signal is carried by `avg_price_per_sqm`. In the joined historical retrieval result, this value is returned as `town_market_features_avg_price_per_sqm` because joined group columns are prefixed in the MVP output.

## Feature Groups

The reference use case has two feature groups:

| Feature Group | Storage | Entity Key | Event Timestamp | Purpose |
| --- | --- | --- | --- | --- |
| `listing_features` | Offline only | `listing_id` | `sold_at` from `listings.sold_at` | Historical sold listing records for training. |
| `town_market_features` | Offline and online | `town_id` | First moment of the next month at `00:00:00` | Monthly town-level market aggregate for training and serving. |

The SQL in this section represents user-owned data preparation outside KiteFS. KiteFS stores the prepared rows it receives.

### `listing_features` Definition

`listing_features` stores sold listing attributes and the training label. It is offline only because prediction-time house attributes come from the seller form or application database.

```python
# definitions/listing_features.py

from kitefs import FeatureGroup, Feature, EntityKey, EventTimestamp
from kitefs import FeatureType, StorageTarget, Expect
from kitefs import JoinKey, ValidationMode, Metadata

listing_features = FeatureGroup(
    name="listing_features",
    storage_target=StorageTarget.OFFLINE,
    entity_key=EntityKey(
        name="listing_id",
        dtype=FeatureType.INTEGER,
        description="Unique identifier for each listing",
    ),
    event_timestamp=EventTimestamp(
        name="sold_at",
        description="When the listing was sold",
    ),
    features=[
        Feature(name="net_area", dtype=FeatureType.INTEGER,
                description="Usable area in sqm",
                expect=Expect().not_null().gt(0)),
        Feature(name="number_of_rooms", dtype=FeatureType.INTEGER,
                description="Number of rooms",
                expect=Expect().not_null().gt(0)),
        Feature(name="build_year", dtype=FeatureType.INTEGER,
                description="Year the building was constructed",
                expect=Expect().not_null().gte(1900).lte(2030)),
        Feature(name="sold_price", dtype=FeatureType.FLOAT,
                description="Sold price in TL (training label)",
                expect=Expect().not_null().gt(0)),
    ],
    join_keys=[
        JoinKey(
            name="town_id",
            dtype=FeatureType.INTEGER,
            referenced_group="town_market_features",
            description="Join key to town_market_features",
        ),
    ],
    ingestion_validation=ValidationMode.ERROR,
    offline_retrieval_validation=ValidationMode.NONE,
    metadata=Metadata(
        description="Historical sold listing attributes and prices",
        owner="data-science-team",
        tags={"domain": "real-estate", "cadence": "monthly"},
    ),
)
```

Fields stored:

| Field | Type | Source | Role | Description |
| --- | --- | --- | --- | --- |
| `listing_id` | integer | `listings.id` | Entity key, Structural | Unique listing identifier. |
| `town_id` | integer | `listings.town_id` | Join key, Structural | Links to `town_market_features`. Not a model feature. |
| `net_area` | integer | `listings.net_area` | Model feature | Usable area in square meters. |
| `number_of_rooms` | integer | `listings.number_of_rooms` | Model feature | Number of rooms. |
| `build_year` | integer | `listings.build_year` | Model feature | Year the building was constructed. |
| `sold_price` | float | `listings.asking_price` for sold rows | Label | Training target. |
| `sold_at` | datetime | `listings.sold_at` | Event timestamp, Structural | Sale time used for time filtering and point-in-time joins. |


Preparation query:

```sql
SELECT
    l.id              AS listing_id,
    l.town_id         AS town_id,
    l.net_area        AS net_area,
    l.number_of_rooms AS number_of_rooms,
    l.build_year      AS build_year,
    l.asking_price    AS sold_price,
    l.sold_at         AS sold_at
FROM listings l
WHERE l.sold_at IS NOT NULL
```

The prepared data is ingested monthly. The first run loads about 2 million sold listings. Later monthly runs append newly sold listings.

Sample `listing_features` rows from the source listing sample:

| listing_id | town_id | net_area | number_of_rooms | build_year | sold_price | sold_at |
| --- | --- | --- | --- | --- | --- | --- |
| 1010 | 3 | 90 | 2 | 2016 | 1250000.00 | 2024-01-20 17:00:00 |
| 1001 | 2 | 75 | 2 | 2020 | 2250000.00 | 2024-03-15 11:00:00 |
| 1003 | 6 | 85 | 2 | 2002 | 1050000.00 | 2024-03-18 14:30:00 |
| 1002 | 1 | 130 | 3 | 2015 | 3400000.00 | 2024-04-05 14:00:00 |
| 1004 | 4 | 110 | 3 | 2010 | 2100000.00 | 2024-05-22 16:00:00 |
| 1005 | 3 | 140 | 4 | 2008 | 2050000.00 | 2024-06-11 10:15:00 |
| 1006 | 5 | 95 | 2 | 2017 | 1400000.00 | 2024-07-03 13:45:00 |
| 1007 | 2 | 60 | 1 | 2019 | 1850000.00 | 2024-08-20 09:30:00 |
| 1008 | 1 | 105 | 3 | 2000 | 2800000.00 | 2024-09-14 15:00:00 |

Listing 1009 is not present because it has no `sold_at` value.

### `town_market_features` Definition

`town_market_features` stores the average sold price per square meter for each town and month. It is stored offline for historical joins and online for low-latency serving.

```python
# definitions/town_market_features.py

from kitefs import FeatureGroup, Feature, EntityKey, EventTimestamp
from kitefs import FeatureType, StorageTarget, Expect
from kitefs import ValidationMode, Metadata

town_market_features = FeatureGroup(
    name="town_market_features",
    storage_target=StorageTarget.OFFLINE_AND_ONLINE,
    entity_key=EntityKey(
        name="town_id",
        dtype=FeatureType.INTEGER,
        description="Unique town identifier",
    ),
    event_timestamp=EventTimestamp(
        name="event_timestamp",
        description="When this value became available",
    ),
    features=[
        Feature(name="avg_price_per_sqm", dtype=FeatureType.FLOAT,
                description="Average sold price per sqm from sold listings in this town during the previous calendar month",
                expect=Expect().not_null().gt(0)),
    ],
    ingestion_validation=ValidationMode.ERROR,
    offline_retrieval_validation=ValidationMode.NONE,
    metadata=Metadata(
        description="Monthly town-level market aggregate",
        owner="data-science-team",
        tags={"domain": "real-estate", "cadence": "monthly"},
    ),
)
```

Fields stored:

| Field | Type | Source | Role | Description |
| --- | --- | --- | --- | --- |
| `town_id` | integer | `towns.id` | Entity key | Unique town identifier. |
| `avg_price_per_sqm` | float | `AVG(listings.asking_price / listings.net_area)` for sold listings in one town and one calendar month | Model feature | Average sold price per square meter, computed only from sold listings. |
| `event_timestamp` | datetime | First moment of the next month at `00:00:00` | Structural | When the aggregate became available in UTC. |

Preparation query for January 2024 sales:

`avg_price_per_sqm` is calculated only from sold listings. For the January 2024 aggregate, the batch job uses rows with `sold_at` in the half-open UTC interval `[2024-01-01 00:00:00, 2024-02-01 00:00:00)`. The resulting feature row becomes available at `event_timestamp = 2024-02-01 00:00:00`, which is the first moment of the next month.

```sql
SELECT
    l.town_id                               AS town_id,
    AVG(l.asking_price / l.net_area)        AS avg_price_per_sqm,
    '2024-02-01 00:00:00'::timestamp        AS event_timestamp
FROM listings l
WHERE l.sold_at IS NOT NULL
  AND l.sold_at >= '2024-01-01 00:00:00'::timestamp
  AND l.sold_at < '2024-02-01 00:00:00'::timestamp
GROUP BY l.town_id
```

In the small source listing sample above, January 2024 has one sold listing: listing `1010`, sold at `2024-01-20 17:00:00`. Using only that small sample row, the January aggregate for `town_id = 3` is `1250000.00 / 90 = 13888.89`, and the stored feature row gets `event_timestamp = 2024-02-01 00:00:00`.

For the full dataset, this monthly job produces one row per town with sales in that month. If a town has multiple sold listings in the interval, the query averages all of them. The representative sample rows below reflect full-dataset monthly outputs, not the single-row toy calculation above.

The `event_timestamp` is the first moment after the computation month. A value computed from January 2024 sales has `event_timestamp = 2024-02-01 00:00:00`, meaning it became available at the start of `2024-02-01`.

Sample offline rows:

| town_id | avg_price_per_sqm | event_timestamp |
| --- | --- | --- |
| 1 | 24500.00 | 2024-02-01 00:00:00 |
| 2 | 28200.00 | 2024-02-01 00:00:00 |
| 3 | 14100.00 | 2024-02-01 00:00:00 |
| 4 | 18500.00 | 2024-02-01 00:00:00 |
| 5 | 14200.00 | 2024-02-01 00:00:00 |
| 6 | 11800.00 | 2024-02-01 00:00:00 |
| 1 | 25100.00 | 2024-03-01 00:00:00 |
| 2 | 28800.00 | 2024-03-01 00:00:00 |
| 3 | 14300.00 | 2024-03-01 00:00:00 |
| 4 | 18700.00 | 2024-03-01 00:00:00 |
| 5 | 14300.00 | 2024-03-01 00:00:00 |
| 6 | 11900.00 | 2024-03-01 00:00:00 |
| 1 | 25400.00 | 2024-04-01 00:00:00 |
| 2 | 29100.00 | 2024-04-01 00:00:00 |
| 3 | 14500.00 | 2024-04-01 00:00:00 |
| 4 | 18800.00 | 2024-04-01 00:00:00 |
| 5 | 14400.00 | 2024-04-01 00:00:00 |
| 6 | 12000.00 | 2024-04-01 00:00:00 |
| ... | ... | ... |

Sample online rows after materializing values computed from December 2024 sales:

| town_id | avg_price_per_sqm | event_timestamp |
| --- | --- | --- |
| 1 | 27200.00 | 2025-01-01 00:00:00 |
| 2 | 31500.00 | 2025-01-01 00:00:00 |
| 3 | 15800.00 | 2025-01-01 00:00:00 |
| 4 | 19200.00 | 2025-01-01 00:00:00 |
| 5 | 14800.00 | 2025-01-01 00:00:00 |
| 6 | 12100.00 | 2025-01-01 00:00:00 |

## Point-in-Time Join Example

When training data requests both feature groups, KiteFS uses the structural join key declared in `listing_features`: `listing_features.town_id` joins to `town_market_features.town_id`.

For each listing row, the joined market row must satisfy:

```text
town_market_features.town_id = listing_features.town_id
town_market_features.event_timestamp <= listing_features.sold_at
```

KiteFS selects the latest matching market row.

### Worked Example: Listing 1002

Listing 1002 has:

| Field | Value |
| --- | --- |
| `town_id` | 1 |
| `sold_at` | 2024-04-05 14:00:00 |

Matching `town_market_features` rows for `town_id = 1`:

| town_id | event_timestamp | avg_price_per_sqm | Outcome |
| --- | --- | --- | --- |
| 1 | 2024-02-01 00:00:00 | 24500.00 | Match; available before sale. |
| 1 | 2024-03-01 00:00:00 | 25100.00 | Match; available before sale. |
| 1 | 2024-04-01 00:00:00 | 25400.00 | Latest match; selected. |
| 1 | 2024-05-01 00:00:00 | Not shown | Excluded; not available on April 5. |

Result: listing 1002 gets `town_market_features_avg_price_per_sqm = 25400.00` in the joined training result, computed from March 2024 sales for town 1 in the interval `[2024-03-01 00:00:00, 2024-04-01 00:00:00)`.

### Boundary Example: Listing 1010

Listing 1010 was sold on `2024-01-20 17:00:00`. The earliest market feature timestamp is `2024-02-01 00:00:00`, computed from January sales in `[2024-01-01 00:00:00, 2024-02-01 00:00:00)` and available at the start of February 1.

Because `2024-02-01 00:00:00` is after `2024-01-20 17:00:00`, listing 1010 has no matching market feature. In a real system, the feature engineering team might still include this row by applying an agreed fallback, imputation, or business-specific default for `avg_price_per_sqm`. For this reference use case, KiteFS keeps the example simple: listing 1010 gets `NULL` for `town_market_features_avg_price_per_sqm` and is excluded from the first training dataset.

## What KiteFS Does Not Store

| Item | Where It Lives | Why It Is Not in KiteFS |
| --- | --- | --- |
| Raw `cities`, `towns`, and `listings` tables | PostgreSQL application database | KiteFS stores curated features, not raw operational data. |
| House attributes at serving time | Seller form or application database | They are immediately available in the prediction request. |
| Town and city names | Application database | The model uses `avg_price_per_sqm` as the location signal in this example. |
| Trained model artifact | Model registry or model serving system | KiteFS provides features to the model. It does not host the model. |

## Workflow Walkthrough

This walkthrough shows how the same reference use case exercises the main KiteFS workflow. The snippets are examples for this use case, not the authoritative SDK reference.

### 1. Define Feature Groups

The data scientist writes the two feature definition files shown above under the project `definitions/` directory.

### 2. Apply Definitions

The registry is generated from the definition files.

```python
from kitefs import FeatureStore

store = FeatureStore()
store.apply()
```

After this step, KiteFS knows the entity keys, event timestamps, storage targets, validation modes, and join relationship between `listing_features` and `town_market_features`.

### 3. Bootstrap Historical Data

On `2025-01-01 00:00:00`, the platform has a year of source data and no feature store yet.

The team prepares historical market features outside KiteFS:

```text
For each month M in January 2024 through December 2024:
    month_start_utc = first day of month M at 00:00:00 UTC
    next_month_start_utc = first day of month M + 1 at 00:00:00 UTC

    For each town_id T in 1 through 6:
        avg_price_per_sqm(T, M) = AVG(listings.asking_price / listings.net_area)
            WHERE listings.town_id = T
                AND listings.sold_at IS NOT NULL
                AND month_start_utc <= listings.sold_at < next_month_start_utc

        event_timestamp = next_month_start_utc
```

This produces 72 rows for `town_market_features` in the full dataset: 12 months times 6 towns.

The team also prepares all sold listing rows with the `listing_features` query above.

```python
store.ingest("town_market_features", historical_market_df)
store.ingest("listing_features", sold_listing_df)
store.materialize("town_market_features")
```

The `ingest` calls take the prepared DataFrames produced outside KiteFS, validate them against the target feature group definitions, and write the accepted rows into KiteFS offline storage. The `materialize` call computes the latest market row for each town and writes those rows into the online store.

After materialization, the online store contains the latest market row for each town. For the `2025-01-01 00:00:00` example, those are the 6 rows computed from December 2024 sales with `event_timestamp = 2025-01-01 00:00:00`.

### 4. Retrieve Training Features

The first training run reads historical listing rows from `2024-02-01 00:00:00` through `2024-12-31 23:59:59`. For brevity, January sold listings are excluded because they cannot join to a market feature that was already available at their sale time.

```python
from datetime import datetime, timezone

training_df = store.get_historical_features(
    from_="listing_features",
    join=["town_market_features"],
    select={
        "listing_features": ["net_area", "number_of_rooms", "build_year", "sold_price"],
        "town_market_features": ["avg_price_per_sqm"],
    },
    where={
        "sold_at": {
            "gte": datetime(2024, 2, 1, 0, 0, 0, tzinfo=timezone.utc),
            "lte": datetime(2024, 12, 31, 23, 59, 59, tzinfo=timezone.utc),
        },
    },
)
```

The `where` filter uses `sold_at` because `sold_at` is the physical column declared as the event timestamp role for `listing_features`. For the MVP, `get_historical_features` accepts filtering only on the base group's event timestamp column.

The returned training rows include base structural columns, selected base features, prefixed joined structural columns, and prefixed selected joined features. Base structural columns include the entity key, event timestamp, and join keys. All joined structural columns are returned with the joined feature group prefix. The sample result below uses the same listing IDs and feature names defined earlier. Market values for later months come from the omitted continuation of the monthly market table.

| listing_id | sold_at | town_id | net_area | number_of_rooms | build_year | sold_price | town_market_features_town_id | town_market_features_event_timestamp | town_market_features_avg_price_per_sqm |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1001 | 2024-03-15 11:00:00 | 2 | 75 | 2 | 2020 | 2250000.00 | 2 | 2024-03-01 00:00:00 | 28800.00 |
| 1003 | 2024-03-18 14:30:00 | 6 | 85 | 2 | 2002 | 1050000.00 | 6 | 2024-03-01 00:00:00 | 11900.00 |
| 1002 | 2024-04-05 14:00:00 | 1 | 130 | 3 | 2015 | 3400000.00 | 1 | 2024-04-01 00:00:00 | 25400.00 |
| 1004 | 2024-05-22 16:00:00 | 4 | 110 | 3 | 2010 | 2100000.00 | 4 | 2024-05-01 00:00:00 | 19000.00 |
| 1005 | 2024-06-11 10:15:00 | 3 | 140 | 4 | 2008 | 2050000.00 | 3 | 2024-06-01 00:00:00 | 14900.00 |
| 1006 | 2024-07-03 13:45:00 | 5 | 95 | 2 | 2017 | 1400000.00 | 5 | 2024-07-01 00:00:00 | 14600.00 |
| 1007 | 2024-08-20 09:30:00 | 2 | 60 | 1 | 2019 | 1850000.00 | 2 | 2024-08-01 00:00:00 | 30200.00 |
| 1008 | 2024-09-14 15:00:00 | 1 | 105 | 3 | 2000 | 2800000.00 | 1 | 2024-09-01 00:00:00 | 26800.00 |

Listing 1010 is excluded by the `gte` filter. If it were included, its joined `town_market_features_avg_price_per_sqm` would be `NULL` because no market feature was available on `2024-01-20 17:00:00`.

The model then trains on these columns:

```python
feature_columns = [
    "net_area",
    "number_of_rooms",
    "build_year",
    "town_market_features_avg_price_per_sqm",
]
label_column = "sold_price"

X = training_df[feature_columns]
y = training_df[label_column]

model.fit(X, y)
```

### 5. Retrain Monthly

On `2025-02-01 00:00:00`, the January 2025 batch job has completed.

The batch job:

1. Queries listings sold in January 2025.
2. Ingests those rows into `listing_features`.
3. Computes January 2025 `avg_price_per_sqm` by town.
4. Ingests 6 rows into `town_market_features` with `event_timestamp = 2025-02-01 00:00:00`.
5. Materializes `town_market_features` so the online store has the latest row per town.

The retraining query uses a rolling 12-month window:

```python
training_df = store.get_historical_features(
    from_="listing_features",
    join=["town_market_features"],
    select={
        "listing_features": ["net_area", "number_of_rooms", "build_year", "sold_price"],
        "town_market_features": ["avg_price_per_sqm"],
    },
    where={
        "sold_at": {
            "gte": datetime(2024, 2, 1, 0, 0, 0, tzinfo=timezone.utc),
            "lte": datetime(2025, 1, 31, 23, 59, 59, tzinfo=timezone.utc),
        },
    },
)
```

The source database is no longer involved in building the training dataset. The offline store contains the needed listing and market features.

### 6. Serve a New Listing Recommendation

A seller creates a new listing on `2025-06-05 10:00:00`.

The seller enters:

| Input | Value |
| --- | --- |
| Town | Kadıköy, stored as `town_id = 1` |
| `net_area` | 130 |
| `number_of_rooms` | 3 |
| `build_year` | 2015 |

The backend uses the form values and retrieves the latest market feature for town 1:

```python
result = store.get_online_features(
    from_="town_market_features",
    select=["avg_price_per_sqm"],
    where={"town_id": {"eq": 1}},
)
```

Example result:

```python
{
    "town_id": 1,
    "event_timestamp": "2025-06-01T00:00:00Z",
    "avg_price_per_sqm": 27800.00,
}
```

The `event_timestamp` is `2025-06-01 00:00:00` because the value was computed from May 2025 sales in `[2025-05-01 00:00:00, 2025-06-01 00:00:00)`. The June batch has not run yet.

The backend maps the online feature value to the same model input name used during training:

```python
{
    "net_area": 130,
    "number_of_rooms": 3,
    "build_year": 2015,
    "town_market_features_avg_price_per_sqm": 27800.00,
}
```

The model predicts `3,650,000 TL`. The seller sees `Recommended market price: 3,650,000 TL` and chooses their asking price.

### 7. Serve an Existing Listing Recommendation

A seller updates an active listing on `2025-07-05 11:00:00`.

The application database already has:

| Field | Value |
| --- | --- |
| `id` | 50001 |
| `town_id` | 5 |
| `net_area` | 95 |
| `number_of_rooms` | 2 |
| `build_year` | 2008 |

The backend retrieves the latest market feature for town 5:

```python
result = store.get_online_features(
    from_="town_market_features",
    select=["avg_price_per_sqm"],
    where={"town_id": {"eq": 5}},
)
```

Example result:

```python
{
    "town_id": 5,
    "event_timestamp": "2025-07-01T00:00:00Z",
    "avg_price_per_sqm": 15200.00,
}
```

The backend maps the online feature value to the same model input name used during training:

```python
{
    "net_area": 95,
    "number_of_rooms": 2,
    "build_year": 2008,
    "town_market_features_avg_price_per_sqm": 15200.00,
}
```

The model predicts `1,450,000 TL`.

### 8. Ingest a Sold Listing

On `2025-09-05 14:30:00`, listing 50001 is sold.

The application updates the source database:

| Field | Value |
| --- | --- |
| `listings.sold_at` | 2025-09-05 14:30:00 |
| `listings.asking_price` | 1400000.00 |

The next monthly batch job runs on `2025-10-01 00:00:00`.

It:

1. Queries listings sold in September 2025.
2. Ingests listing 50001 into `listing_features`.
3. Uses its sold price and `net_area` in the September market aggregate for `town_id = 5`.
4. Ingests the aggregate into `town_market_features` with `event_timestamp = 2025-10-01 00:00:00`.
5. Materializes `town_market_features` so online serving uses the latest available market rows.

## Storage Summary

| Feature Group | Field | Offline Store | Online Store |
| --- | --- | --- | --- |
| `listing_features` | `listing_id` | Yes | No |
| `listing_features` | `town_id` | Yes | No |
| `listing_features` | `net_area` | Yes | No |
| `listing_features` | `number_of_rooms` | Yes | No |
| `listing_features` | `build_year` | Yes | No |
| `listing_features` | `sold_price` | Yes | No |
| `listing_features` | `sold_at` | Yes | No |
| `town_market_features` | `town_id` | Yes | Yes |
| `town_market_features` | `avg_price_per_sqm` | Yes, full history | Yes, latest only |
| `town_market_features` | `event_timestamp` | Yes | Yes, latest only |

## Example Consistency Notes

- `listing_features` contains only rows where `listings.sold_at IS NOT NULL`.
- `listing_features.sold_price` equals `listings.asking_price` for sold rows.
- `listing_features.sold_at` equals `listings.sold_at`.
- `listing_features.town_id` is a structural join key declared in `join_keys`, not a model feature.
- `town_market_features.event_timestamp` is the first moment after the month used for the aggregate, always at `00:00:00` UTC.
- Historical retrieval examples select only feature fields; structural fields are returned automatically, and joined output columns are prefixed with the joined group name.
- Online serving examples retrieve only `avg_price_per_sqm` from `town_market_features`; house attributes come from the request or application database.

