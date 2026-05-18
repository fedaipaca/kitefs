# Glossary

## Purpose

This file defines domain terms, abbreviations, and short definitions used across `docs`. It is the only place where glossary definitions live.

## Owns

- All domain terms used across `docs`.
- Abbreviations used across `docs`.
- Definitions used across `docs`.

## Does Not Own

- Detailed explanations of concepts.

## Content

| Term | Definition |
| --- | --- |
| Acceptance Criteria | Testable conditions that show a requirement has been met. |
| API | Application programming interface exposed by KiteFS for code-level use. |
| Apply | Operation that regenerates the local working registry from current feature definitions without publishing to provider registry storage. |
| AP-X | Stable ID prefix for architecture principles. |
| AWS | Amazon Web Services, the cloud environment targeted by the remote provider. |
| AWS Provider | Provider implementation that stores offline data in S3 and online data in DynamoDB. |
| Batch Ingestion | Loading computed feature values into KiteFS in discrete batches rather than as a stream. |
| BB-XX | Stable ID prefix for architecture building blocks. |
| CLI | Command-line interface exposed through the `kitefs` command. |
| Cloud Provider | External cloud platform that supplies storage and access-control services. |
| Configuration | Project settings that tell KiteFS which provider and storage locations to use. |
| CON-XXX | Stable ID prefix for project constraints. |
| Data Leakage | Using information during model training that would not have been available at prediction time. |
| Data Quality Gate | Validation point that checks data before it enters or leaves a store. |
| DynamoDB | AWS key-value database used by the AWS provider for online feature storage. |
| Entity | Real-world object that features describe, identified by an entity key. |
| Entity Key | Structural field that identifies the entity a feature record belongs to. |
| `EntityKey` | Public definition type used to declare a feature group's entity key. |
| Event Timestamp | Structural field that records when a feature value became true or was observed. |
| `EventTimestamp` | Public definition type used to declare a feature group's event timestamp. |
| `Expect` | Public builder used to define feature expectations. |
| Feature | Model-consumable value derived from raw data. |
| `Feature` | Public definition type used to declare a feature field. |
| Feature Definition | Code declaration that describes a feature group and its fields. |
| Feature Discovery | Finding registered feature groups and their metadata. |
| Feature Drift | Change in feature distributions or behavior over time. |
| Feature Engineering | Transforming raw data into model-consumable feature values. This happens outside KiteFS. |
| Feature Expectation | Business-level constraint on a feature value, such as bounds, allowed values, or nullability. |
| Feature Governance | Ownership, change tracking, and auditability for feature definitions. |
| Feature Group | Named collection of related fields that share an entity key, event timestamp, and storage configuration. |
| `FeatureGroup` | Public definition type used to declare a feature group as code. |
| Feature Registry | Generated metadata catalog that stores feature group definitions and runtime metadata. |
| Feature Store | System for managing feature storage, serving, validation, versioning, and discovery. |
| Feature Validation | Checking feature values against declared types and expectations. |
| Feature Vector | Complete set of feature values assembled for one prediction request. |
| `FeatureStore` | Public SDK entry point for KiteFS operations. |
| `FeatureType` | Public enum for supported feature data types. |
| Field | Named typed column in a feature group. Entity keys, event timestamps, and features are fields. |
| FR-XXX | Stable ID prefix for functional requirements. |
| G-X | Stable ID prefix for project goals. |
| Hive-Style Partitioning | Directory layout that stores partition values in path segments such as `year=YYYY/month=MM`. |
| IAM | Cloud identity and access management used for provider-level permissions. |
| Inference | Using a trained model to make a prediction. |
| Ingestion | Writing computed feature values into KiteFS. |
| Ingestion Gate | Validation point that runs before data enters the offline store. |
| JSON | Text data format used for the feature registry. |
| Join Key | Field that links one feature group to another feature group's entity key. |
| `JoinKey` | Public definition type used to declare a relationship between feature groups. |
| KiteFS | Python feature store library documented by this repository. |
| `kitefs` | Package name and command name used by the KiteFS library. |
| `kitefs.yaml` | Project configuration file used by KiteFS. |
| KTD-X | Stable ID prefix for KiteFS technical decisions. |
| Literal Architecture | Design philosophy that limits KiteFS to storing, serving, retrieving, materializing, discovering, and validating features. |
| Local Provider | Provider implementation that uses the local filesystem, Parquet, and SQLite. |
| Local Working Registry | Generated registry file in the local working environment, used for development, validation, inspection, and local workflows. |
| Machine Learning | Building systems that learn from data to make predictions or decisions. |
| Materialization | Syncing feature values from the offline store to the online store. |
| `Metadata` | Public definition type used to attach description, owner, and tags to a feature group. |
| Mock Data Generation | Capability that creates synthetic feature data from feature group definitions and validation rules. |
| MVP | Minimum viable product scope for the first usable version of KiteFS. |
| NFR-XXX | Stable ID prefix for non-functional requirements. |
| NG-X | Stable ID prefix for non-goals. |
| Offline Retrieval | Reading historical feature data from the offline store. |
| Offline Retrieval Gate | Validation point that runs before historical feature data is returned. |
| Offline Store | Storage for historical feature data used for training and batch retrieval. |
| Online Feature Serving | Reading latest feature values from the online store for inference. |
| Online Store | Storage for latest feature values used for low-latency inference lookups. |
| ORM | Object-relational mapper, used as an analogy for a simple developer experience. |
| Pandas DataFrame | Tabular Python data structure accepted or returned by KiteFS data operations. |
| Parquet | Columnar file format used by the offline store. |
| Point-in-Time Correctness | Guarantee that historical retrieval uses only feature values available at or before each event timestamp. |
| PIT | Short form of point-in-time. |
| PP-X | Stable ID prefix for pain points. |
| Project Root | Directory that contains the KiteFS project configuration. |
| Provider | Backend implementation that handles storage operations for a specific environment. |
| Provider Abstraction | Boundary that lets KiteFS route storage operations through a common provider interface. |
| Provider ABC | Abstract provider interface that concrete providers implement. |
| Provider Registry Location | Configured registry destination for the active provider, such as a local provider registry path or an AWS S3 registry object. |
| Publish | Operation that regenerates and validates the registry from current definitions, writes the local working registry, and promotes the same registry to the configured provider registry location. |
| PyArrow | Python library used for reading and writing Parquet data. |
| Raw Data | Source-system data before feature engineering. |
| Registry | Short name for the feature registry. |
| Remote Store | Storage backend outside the local filesystem, such as AWS storage. |
| S3 | AWS object storage used by the AWS provider for offline feature data and registry storage. |
| SDK | Python software development kit exposed by KiteFS for programmatic use. |
| Smart Sampling | Capability that copies a representative subset of remote feature data into a local environment. |
| SQLite | Local relational database used by the local provider for online feature storage. |
| Statistical Monitoring | Tracking statistical changes in feature data over time. |
| Storage Root | Configured directory or prefix where KiteFS stores managed artifacts. |
| Storage Target | Feature group setting that controls whether data is offline-only or can also be materialized online. |
| `StorageTarget` | Public enum for supported storage target values. |
| Structural Column | Required non-feature field that is always part of a feature group, such as entity key or event timestamp. |
| Time-Travel Join | Historical join that selects feature values according to event time to preserve point-in-time correctness. |
| Training-Serving Skew | Difference between feature values used during training and feature values used during inference. |
| Validation Gate | Point in a data flow where feature values are checked before proceeding. |
| Validation Mode | Strictness setting for validation behavior. |
| `ValidationMode` | Public enum for validation modes such as `ERROR`, `FILTER`, and `NONE`. |
| Validation Report | Summary of validation results, including counts and failure details. |
| YAML | Human-readable configuration format used for `kitefs.yaml`. |