# Kite Feature Store — Project Charter

> **Document Purpose:**
> This is the foundational document for the project. It answers three questions:
>
> 1. What problem are we solving and why does it matter?
> 2. What is our approach at the highest level?
> 3. What shared vocabulary do we use to communicate clearly?
>
> **Relationship to Other Documents:**
>
> Every subsequent document references this one. If something contradicts this document, either this document needs updating or the other one is wrong.
> - Traces forward to: [Requirements (docs-02)](docs-02-project-requirements.md), [Architecture Overview (docs-03-01)](docs-03-01-architecture-overview.md), [API Contracts (docs-03-03)](docs-03-03-api-contracts.md), [Implementation Guide (docs-04)](docs-04-implementation-guide.md)
> - Related: [Reference Use Case (docs-00-01)](docs-00-01-reference-use-case.md), [Flow Charts (docs-00-02)](docs-00-02-flow-charts.md)
>
> **Audience:** Anyone who needs to understand what this project is and why it exists — developers, reviewers, advisors, collaborators, AI agents.
>
> **Owner:** Fedai Paça
> **Status:** Draft

---

## 1. Problem Statement

When organizations add machine learning capabilities to existing software products, the ML model itself is only part of the challenge. The harder, less visible problem is managing the **data that feeds the model** — specifically, the engineered features that the model consumes during training and real-time prediction. Without a dedicated system for managing features, teams encounter a set of recurring, structural problems that degrade model accuracy, increase engineering effort, and create operational risk.

This project addresses these problems by building a lightweight feature store library with provider abstraction built in — the core logic is decoupled from any specific storage backend, and providers are pluggable implementations behind a common interface. The MVP implements local and AWS providers; the architecture enables additional providers without redesign.

### 1.1 Current Situation

Consider a typical scenario: a product team wants to add an ML-powered feature to an existing web application. The reference example for this project is an online real estate listing platform (React frontend, Node.js backend, PostgreSQL database) that wants to add a **price recommendation** — a model that estimates the current market value of a property based on its attributes and recent market conditions.
Details of use case example can be found in the [Reference Use Case Document](./docs-00-01-reference-use-case.md).

Today, teams in this situation follow an ad-hoc workflow:

- A **data scientist** explores historical data, engineers features (e.g., `avg_price_per_sqm` — the average sold price per square meter in a town for the previous calendar month), and trains a model in a notebook or script using Python and libraries like Pandas and scikit-learn.
- The data scientist hands off the trained model and feature logic to a **backend engineer**, who must replicate the feature computation inside the production application — often in a different language or framework — to serve the model in real time.
- There is no shared system for storing, versioning, or serving features. Features exist as scattered artifacts: SQL queries, notebook cells, DataFrame transformations, or ad-hoc database views.
- For features that require expensive computation (e.g., aggregating hundreds of thousands of sold listings to compute a monthly market average), there is no mechanism to pre-compute and serve them with low latency. The backend either recomputes on every request or invents a custom caching layer.

### 1.2 Pain Points

**PP-1: Training-serving skew.** When feature computation logic is implemented separately for training and for serving, subtle differences inevitably arise. The model receives different feature values in production than it saw during training, producing silently inaccurate predictions. This is the most dangerous failure mode because the system appears to work correctly.

**PP-2: Logic duplication across team boundaries.** The same feature computation exists in multiple codebases maintained by different teams. Each copy can drift independently, and fixing a bug requires coordinated changes across teams.

**PP-3: Inference latency from on-the-fly computation.** Features that require expensive aggregations (e.g., scanning all sold listings in a town for the previous month) cannot be computed in real time on every prediction request without creating database bottlenecks and unacceptable response latency. As traffic grows, performance degrades.

**PP-4: No point-in-time correctness for training data.** When building training datasets from historical data, practitioners must ensure that each record is joined only with feature values that existed at the time of the event — not future values. Violating this causes data leakage: the model looks accurate during evaluation but fails in production.

**PP-5: No feature discovery or reuse.** Features are created in isolation — inside notebooks, scripts, or application code. There is no catalog to search. Different teams working on related problems often re-derive the same features independently, wasting effort and introducing inconsistency.

**PP-6: No feature governance or versioning.** Features are data artifacts, but they lack the version control, change tracking, and audit trails that are standard for source code. When a feature definition changes (e.g., a town boundary is redrawn by regulation), there is no systematic way to track the impact on downstream models or satisfy compliance requirements.

**PP-7: No data quality enforcement.** Invalid or unexpected feature values (wrong types, out-of-range values, nulls) can silently flow into model training and serving, degrading predictions without any alert or safeguard.

**PP-8: Limited developer experience for local development and experimentation.** Setting up a local development environment with representative feature data requires either access to production systems or writing custom data generation scripts. There is no built-in mechanism to generate realistic test data from feature definitions or to pull a representative subset of production data to a local environment. This slows iteration and creates friction in the development workflow.

### 1.3 Why Existing Solutions Fall Short

The current market offers several feature store solutions, but none adequately fills the gap this project targets:

**Feast** (open-source) is the closest alternative. It provides an offline store, online store, feature registry, and serving layer. However, Feast has a steep learning curve, requires significant manual configuration to set up and operate, and its local development experience — while possible — requires understanding of its provider model and infrastructure abstractions. For a small team or individual practitioner wanting to get started quickly, the overhead is substantial. Feast also lacks built-in data quality validation, mock data generation, and smart sampling capabilities.

**Tecton, Databricks Feature Store, Hopsworks** are enterprise-grade platforms. They provide comprehensive capabilities but come with high infrastructure costs, vendor lock-in, and complexity that is disproportionate for small-to-medium projects or individual practitioners. They are designed for organizations with dedicated ML platform teams.

**AWS SageMaker Feature Store and Google Vertex AI Feature Store** are cloud-native solutions tightly coupled to their respective cloud providers. They require cloud-specific knowledge to configure and operate, and they lock users into a single cloud ecosystem. Local development and testing is limited or impossible.

**Common shortcomings across existing solutions:**

- **High barrier to entry.** Even the simplest existing solutions require understanding cloud infrastructure, provider configurations, and tool-specific concepts before writing a single line of feature management code.
- **No library-first experience.** Existing solutions are infrastructure-first: they require deploying and configuring storage backends, servers, and registries before they can be used. None offer a `pip install` → start working experience.
- **Limited local development support.** Most solutions are cloud-dependent by default. Running a fully functional feature store locally — without cloud credentials or network access — is either impossible or requires workarounds.
- **No built-in data quality validation.** Feature quality checks are either absent or require separate tooling (e.g., Great Expectations) configured independently.
- **No built-in mock data generation.** Developers must write custom scripts to create test data that conforms to feature definitions and constraints. No existing solution generates realistic mock data from feature group definitions.
- **No built-in smart sampling.** Working with a representative subset of production data locally requires manual extraction and formatting. No existing solution provides a single command to sample remote data into a local environment.

---

## 2. Project Vision

### 2.1 Vision Statement

Kite Feature Store (`kitefs`) makes feature management as simple and accessible as using an ORM for database work. A practitioner installs a Python library, defines features as code, and immediately has a working feature store — locally, with no cloud credentials, no infrastructure setup, and no learning curve beyond the Python SDK. The same definitions and API work identically when deployed to a remote cloud environment. Feature storage, serving, validation, point-in-time joins, and discovery are built-in capabilities, not infrastructure problems the user must solve.

### 2.2 Goals

**G-1: Eliminate training-serving skew by design.** Features are defined once and served through a single API for both training (offline store) and inference (online store). There is no separate serving implementation. Verification: the same feature definition produces identical values in training datasets and real-time serving.

**G-2: Provide point-in-time correct historical feature retrieval.** The offline store supports time-travel joins that automatically prevent data leakage. Verification: given a set of historical records with known event timestamps, the library returns only feature values that existed at or before each event's timestamp — never future values.

**G-3: Deliver a zero-infrastructure local development experience.** A user can `pip install kitefs`, define features, ingest data, and retrieve features for training and inference — all locally, using only the file system (Parquet files for offline store, SQLite for online store). No cloud account, no Docker, no external service required. Verification: a complete end-to-end workflow (define → ingest → materialize → retrieve for training → retrieve for serving) runs successfully on a fresh machine with only Python and pip installed.

**G-4: Support cloud deployment with the same API.** The same feature definitions and SDK calls work against remote storage (AWS S3 for offline store, DynamoDB for online store) without code changes beyond configuration. The architecture uses provider abstraction — the user specifies a provider in configuration (e.g., `local`, `aws`), and the library routes all storage operations to the corresponding backend. Verification: switch from local to remote by changing a configuration value; all SDK calls continue to work.

**G-5: Enforce data quality at every gate in the data flow.** A built-in validation engine checks feature values against user-defined type constraints and feature expectations at two points: ingestion (before data enters the offline store) and offline retrieval (before training data is returned). The validation engine supports three modes — `ERROR` (reject the entire operation if any record fails), `FILTER` (pass only valid records, report failures), and `NONE` (skip validation) — giving users control over strictness at each gate. Verification: ingesting data that violates defined constraints in `ERROR` mode is blocked with an actionable error; in `FILTER` mode, only valid records reach the store.

**G-6: Generate realistic mock data from feature definitions.** Users can generate synthetic feature data that conforms to their feature group schemas and validation rules with a single command. Verification: running the mock data command against a defined feature group populates the local store with data that passes all validation rules and is immediately usable for development and testing.

**G-7: Enable local experimentation with production data via smart sampling.** Users can pull a representative subset of features from a remote offline store to their local environment, filtered by row count, percentage, or time range. Verification: running the sampling command against a remote store populates the local offline store with a subset that preserves the data's structure and is immediately queryable through the standard SDK.

### 2.3 Non-Goals (Explicit Exclusions)

**NG-1: Building a transformation or compute engine.** Kite Feature Store does not manage, schedule, or execute feature computation logic. Users compute features using their own tools (Pandas, Spark, SQL, etc.) and write the results to the feature store. This is by design — the store does literally what its name says (stores features) and nothing more. The transformation layer is explicitly out of scope for the MVP.

**NG-2: Streaming feature ingestion.** The MVP does not support real-time or near-real-time streaming ingestion (e.g., from Kafka or Kinesis). Features are ingested via batch processes. This is appropriate for the reference use case (monthly market aggregates) and avoids the substantial complexity of stream processing infrastructure.

**NG-3: Model hosting, training, or serving.** Kite Feature Store provides features to models. It does not host models, execute inference, or manage model lifecycle. Those responsibilities belong to separate systems (model registries, serving frameworks).

**NG-4: Multi-cloud support in the MVP.** The MVP implements local and AWS (S3, DynamoDB) providers. The provider abstraction enables adding GCP, Azure, or on-premise providers later without redesign. However, only local and AWS providers are built and tested in the MVP.

**NG-5: Web UI for the MVP.** Feature discovery and registry exploration are provided via CLI in the MVP. A web application may be added in a future iteration.

**NG-6: Authentication and authorization.** The MVP does not implement its own auth layer. Access control in cloud environments relies on the underlying cloud provider's IAM (e.g., AWS IAM policies for S3 and DynamoDB). A dedicated auth layer is a future consideration.

**NG-7: Feature drift detection or statistical monitoring.** The MVP does not include automated feature drift detection, statistical distribution monitoring, or alerting. The validation engine covers type and constraint checks. Statistical monitoring is a future enhancement.

---

## 3. Project Overview

### 3.1 What Is It?

Kite Feature Store (`kitefs`) is a Python library, installed via `pip`, that provides a feature store — offline store, online store, feature registry, materialization, validation, and serving — through a simple Python SDK and a CLI. It is designed for practitioners who want to manage ML features with minimal operational overhead. Locally, it uses Parquet files (offline store) and SQLite (online store) with zero external dependencies. For production, it supports AWS S3 (offline store) and DynamoDB (online store) with the same API. Feature definitions live as code in the project repository, and the registry is a JSON file that is human-readable, Git-versionable.

### 3.2 Who Is It For?

**Persona: Data Scientist / ML Engineer**
Needs to define features, ingest computed feature values, generate point-in-time correct training datasets, and iterate quickly during experimentation. Interacts via the Python SDK within notebooks or scripts. Expects feature definitions to be straightforward code — not infrastructure configuration.

**Persona: Backend / Software Engineer**
Needs to retrieve pre-computed features at low latency during real-time inference. Interacts via the Python SDK (or in the future, an HTTP API) to fetch the latest feature values from the online store. Expects a simple key-based lookup (e.g., get the market features for `town_id` 4) that returns in milliseconds.

**Persona: ML / Data Platform Engineer**
Needs to set up and maintain the feature store infrastructure, configure remote storage backends, integrate the feature store into CI/CD pipelines, and ensure features are validated and materialized correctly. Interacts via the CLI for operations like registry sync, materialization, smart sampling, and mock data generation. Expects the system to be scriptable, automatable, and observable.

### 3.3 How Will It Be Used? (Usage Context)

Kite Feature Store is used as a Python library and CLI tool integrated into the development and production workflows of any project. The detailed, step-by-step walkthrough of every flow described below is documented in the **[Reference Use Case Document](./docs-00-01-reference-use-case.md)**. This section provides a summary of the workflow phases to establish context.

The reference use case is an online real estate listing platform operating across Istanbul and Ankara, Turkey, with ~3 million listing records (of which ~2 million are sold). The business wants to add a **price recommendation**: an ML model that estimates a property's market value based on its attributes and recent market conditions. The model requires a pre-computed market feature (`avg_price_per_sqm`) that is too expensive to calculate on every request — this is what the feature store manages.

The feature store manages two feature groups:

- **`listing_features`** (entity key: `listing_id`) — historical sold listing records stored in the offline store only. Used for training dataset generation.
- **`town_market_features`** (entity key: `town_id`) — monthly market aggregates stored in both offline and online stores. Used for training (offline) and real-time serving (online).

---

#### Phase 1: Populating the Feature Store (Initial Bootstrap)

The data scientist defines feature groups as code using the Kite SDK, computes features externally using their own tools (e.g., Pandas against the PostgreSQL database), and ingests the results into the feature store. Sold listing records (~2 million rows) go into the `listing_features` offline store. Monthly market aggregates (~72 rows, 12 months × 6 towns) go into the `town_market_features` offline store. Finally, the latest market features are materialized to the online store (6 rows — one per town). After this phase, the feature store is populated and ready for both training and serving.

---

#### Validation: The Data Quality Gate

Kite treats data quality as a first-class concern built into the library, not an afterthought requiring external tools.

**How validation is defined.** When defining a feature group, the user specifies two layers of constraints alongside each feature:

- **Type validation:** The expected data type for each feature (e.g., `integer`, `float`, `datetime`). This catches structural errors like wrong types or unexpected nulls.
- **Feature expectations:** Business-level constraints beyond type — minimum/maximum bounds, allowed values, nullability rules. These catch semantic errors where values are technically the right type but clearly wrong.

Both layers are declared in the feature group definition as code, stored in the registry, and enforced automatically.

**When validation runs.** Validation is triggered at two points in the data flow:

1. **At ingestion** — before data enters the offline store.
2. **At offline/historical retrieval** — before training data is returned via `get_historical_features`.

Materialization does not perform validation — data was already validated at ingestion.

**Validation modes.** At each gate, the user controls strictness through three modes:

- **`ERROR`:** Any validation failure rejects the entire operation. Nothing is written or returned.
- **`FILTER`:** Valid records proceed; failing records are filtered out and reported.
- **`NONE`:** Validation is skipped entirely.

The mode is configured independently at each gate (ingestion and offline retrieval), allowing different strictness levels.

---

#### Phase 2: Training the Model

Everything the training script needs is in the offline store. The production database is not involved. The data scientist calls `store.get_historical_features(...)`, specifying a base feature group via `from_=`, the desired features via `select=`, an optional time filter via `where=`, and optional joined groups via `join=`. The feature store reads the join key declarations from the feature group definitions — for example, `listing_features.town_id` → `town_market_features.town_id` — and automatically performs a point-in-time join: for each listing row, it finds the latest `town_market_features` row whose `event_timestamp` ≤ the listing's `event_timestamp`.

Because market features use the convention `event_timestamp = first day of the month after computation` (e.g., January sales → `event_timestamp = 2024-02-01`), a listing sold on April 5 is matched with the market feature from March sales (`event_timestamp = 2024-04-01`) — the most recent data actually available at the time of sale. The result is a single training-ready DataFrame. The data scientist separates features from label and trains the model.

---

#### Phase 3: Production Serving

The model is deployed. When a seller requests a price recommendation, the backend collects house attributes from user input and calls the Kite SDK to retrieve `avg_price_per_sqm` from the online store by the seller's `town_id`. The backend assembles all inputs and sends them to the model, which returns a predicted price. The entire feature retrieval is a single low-latency key-based lookup.

---

#### Phase 4: Monthly Refresh

Periodically (monthly in the reference use case), new sold listings are ingested into the offline store, new market aggregates are computed externally and ingested, and materialization updates the online store with the latest values. After this refresh, the online store serves updated market context for predictions, and the offline store contains all data needed for retraining — without touching the production database. For the MVP, this process is triggered manually.

---

#### Development Workflow: Mock Data and Smart Sampling

Two additional capabilities support the development lifecycle. **Mock data generation** allows a developer to define feature groups and immediately populate the local store with realistic synthetic data conforming to the schemas and validation rules — no production data or external services required. **Smart sampling** allows a data scientist to pull a representative subset of production feature data from a remote offline store into the local environment, filtered by row count, percentage, or time range, enabling local experimentation with real data without full downloads.

---

## 4. Domain Glossary

| Term                          | Definition                                                                                                                                                                                                                                                                                                                                                                                 | Notes / Distinctions                                                                                                  |
| ----------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------- |
| **Data Leakage**              | Using information during model training that would not be available at prediction time. Typically caused by including future feature values in historical training records.                                                                                                                                                                                                                | Prevented by point-in-time correctness.                                                                               |
| **Entity**                    | A real-world object that features describe, identified by an entity key (e.g., `listing_id`, `town_id`).                                                                                                                                                                                                                                                                                      | Not a database entity or ORM model — a domain concept that features are organized around.                             |
| **Entity Key**                | A structural column that uniquely identifies the entity a feature record belongs to. Declared as the `entity_key` parameter of a `FeatureGroup` (a single `EntityKey` instance with name and data type). Used for online store lookups and offline store joins.                                                                                                                                                | A feature group has exactly one entity key. Always returned alongside requested features in retrieval results.         |
| **Event Timestamp**           | A structural column recording when a feature value became true or was observed. Declared as the `event_timestamp` parameter of a `FeatureGroup` (a single `EventTimestamp` instance with dtype `DATETIME`). Used in the offline store to determine which values were available at a given point in time.                                                                                                               | For sold listings: the sold date. For market features: the first day of the month **after** the computation month, representing when the value became available. This convention ensures point-in-time joins naturally exclude data that would not yet exist. Dtype is always `DATETIME` — the presence of an `EventTimestamp` is enforced by the type system (required constructor parameter), but the dtype value is enforced by BB-04 during `apply()`. |
| **Feature**                   | A measurable property or computed value used as input to an ML model. Derived from raw data through feature engineering.                                                                                                                                                                                                                                                                   | Distinct from raw data: raw data is source-system output; a feature is a model-consumable value derived from it.      |
| **Feature Engineering**       | Transforming raw data into features a model can use — cleaning, encoding, aggregating, deriving new values.                                                                                                                                                                                                                                                                                | In Kite's literal architecture, this happens outside the feature store.                                               |
| **Feature Expectation**       | A business-level constraint on a feature's value beyond its data type. Defined using the `Expect` fluent builder (e.g., `Expect().not_null().gt(0).lte(1000)`). Examples: minimum/maximum bounds, allowed values, nullability rules.                                                                                                                                                       | Defined on `Feature` fields only. `EntityKey` and `EventTimestamp` do not accept expectations. Enforced by the validation engine at each gate.           |
| **Feature Group**             | A named collection of related fields sharing the same entity key, update cadence, and storage configuration. Defined with a single `entity_key` (`EntityKey`), a single `event_timestamp` (`EventTimestamp`), and a `features` list of one or more `Feature` instances. The unit of definition, ingestion, and storage.                                                                   | Examples: `listing_features` (entity key: `listing_id`), `town_market_features` (entity key: `town_id`).              |
| **Field**                     | A named, typed column in a feature group. Three kinds exist: `EntityKey` (unique identifier), `EventTimestamp` (temporal anchor), and `Feature` (model input, label, or join key). `EntityKey` and `EventTimestamp` are structural columns (separate constructor parameters); `Feature` instances are provided as a list.                                                                   | The term "field" encompasses all column types. "Feature" is a specific kind of field.                                  |
| **Feature Registry**          | A metadata catalog storing feature group definitions — names, types, entity keys, descriptions, owners, validation rules. The single source of truth for what features exist.                                                                                                                                                                                                              | Stored as a JSON file. Git-versionable (deterministic key ordering, consistent formatting). Syncable to remote storage for cross-project access.                   |
| **Feature Store**             | A centralized system for managing the lifecycle of ML features — storage, serving, validation, versioning, and discovery.                                                                                                                                                                                                                                                                  | Kite follows a literal architecture: it stores and serves features but does not compute or transform them.            |
| **Feature Validation**        | Checking feature values against defined constraints (types and feature expectations) before storage or offline retrieval. The validation engine supports three modes: `ERROR`, `FILTER`, and `NONE`.                                                                                                                                                                                               | Enforced at ingestion and offline retrieval gates.            |
| **Feature Vector**            | The complete set of feature values assembled for a single prediction request, combining inputs from multiple sources.                                                                                                                                                                                                                                                                      | In the reference use case: `{net_area, number_of_rooms, build_year, avg_price_per_sqm}`.                              |
| **Literal Architecture**      | A design philosophy where the feature store's responsibility is limited to storing, serving, and validating features. It does not manage, schedule, or execute feature computation or transformation logic. Users compute features using their own tools and write the results to the feature store. This keeps the system simple, focused, and avoids duplicating existing compute tools. | The term "literal" reflects that the store does literally what its name says — it stores features — and nothing more. |
| **Materialization**           | Syncing feature values from the offline store to the online store — typically copying the latest value per entity key, overwriting previous values.                                                                                                                                                                                                                                        | Does not perform validation — data was already validated at ingestion.                                                    |
| **Mock Data Generation**      | A Kite capability that generates realistic synthetic feature data based on feature group definitions and validation rules.                                                                                                                                                                                                                                                                 | Used for development and testing without production data.                                                             |
| **Offline Store**             | Storage for historical feature data. Optimized for high-throughput batch reads. Stores features with event timestamps for time-travel and point-in-time joins. Used for training.                                                                                                                                                                                                          | Local: Parquet files. Remote: AWS S3 (Parquet).                                                                       |
| **Online Store**              | Storage for the latest feature values. Optimized for low-latency key-based lookups. Stores only the most recent value per entity key. Used for real-time inference.                                                                                                                                                                                                                        | Local: SQLite. Remote: AWS DynamoDB.                                                                                  |
| **Point-in-Time Correctness** | A guarantee that historical feature retrieval joins each record only with feature values that existed at or before the record's event timestamp — never future values. Prevents data leakage.                                                                                                                                                                                              | Also called "time-travel joins."                                                                                      |
| **Provider**                  | A pluggable backend implementation that handles storage operations for a specific environment. Each provider implements a common interface.                                                                                                                                                                                                                                                | MVP: `local` (filesystem + SQLite), `aws` (S3 + DynamoDB).            |
| **Smart Sampling**            | A Kite capability that retrieves a representative subset of features from the remote offline store to the local environment, filtered by row count, percentage, or time range.                                                                                                                                                                                                             | Enables local experimentation with production data without full downloads.                                            |
| **Training-Serving Skew**     | A discrepancy between feature values a model sees during training and values it receives during inference. Causes silent prediction degradation.                                                                                                                                                                                                                                           | Kite prevents this by serving both training and inference from the same store through the same API.                   |
| **Validation Mode**           | The strictness level applied at a validation gate. `ERROR`: reject entire operation on any failure. `FILTER`: pass only valid records, report failures. `NONE`: skip validation.                                                                                                                                                                                                           | Configurable independently at each gate (ingestion, offline retrieval).                                      |

