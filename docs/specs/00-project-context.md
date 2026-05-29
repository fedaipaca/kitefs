# Project Context

## Purpose

This file explains why KiteFS exists, who it serves, and what is in scope. It owns the project-level context for `docs-v2`.

## Owns

- Problem statement.
- Vision.
- Goals.
- Non-goals.
- Personas.
- Project scope.

## Does Not Own

- Detailed requirements.
- API signatures.
- Task lists.
- Glossary definitions.

## Problem Statement

KiteFS addresses the feature-management gap that appears when software teams add machine learning to existing products. The model is only one part of the system. Teams also need a reliable way to store, validate, discover, retrieve, materialize, and serve the features that feed the model.

Without a feature store, feature logic is scattered across notebooks, scripts, SQL queries, application code, and ad hoc database views. This creates different behavior between training and production, raises latency for expensive features, and makes data quality hard to enforce.

KiteFS approaches the problem as a Python library. Users compute features with their own tools, then write the results to KiteFS. KiteFS stores and serves those features through one SDK and CLI, with a local-first workflow and provider abstraction for remote storage.

## Pain Points

| ID | Pain Point | Summary |
| --- | --- | --- |
| PP-1 | Training-serving skew | Separate training and serving implementations can produce different feature values, causing silent production errors. |
| PP-2 | Logic duplication across team boundaries | The same feature logic is copied into multiple codebases and can drift independently. |
| PP-3 | Inference latency from on-the-fly computation | Expensive aggregations cannot be recomputed for every prediction request without hurting latency and database performance. |
| PP-4 | No point-in-time correctness for training data | Historical datasets can accidentally include future feature values, causing data leakage. |
| PP-5 | No feature discovery or reuse | Features are hard to find, so teams often rebuild similar features independently. |
| PP-6 | No feature governance or versioning | Feature definitions often lack change tracking, auditability, and clear ownership. |
| PP-7 | No data quality enforcement | Invalid feature values can enter training or serving flows without a clear gate. |
| PP-8 | Limited local development and experimentation | Developers lack an easy way to work locally with realistic feature data or representative production samples. |

## Vision

KiteFS makes feature management as simple and accessible as using an ORM for database work. A practitioner installs a Python library, defines features as code, and gets a working feature store locally without cloud credentials, infrastructure setup, or a separate service.

The same definitions and API should work against remote storage through configuration changes. Feature storage, serving, validation, point-in-time joins, and discovery are built-in library capabilities, not infrastructure problems the user must solve first.

## Goals

| ID | Goal | Verification |
| --- | --- | --- |
| G-1 | Eliminate training-serving skew by design. | The same registered feature definitions and stored feature values are used for historical retrieval and online serving where the feature is available. |
| G-2 | Provide point-in-time correct historical feature retrieval. | Historical retrieval returns only feature values that existed at or before each event timestamp. |
| G-3 | Deliver a zero-infrastructure local development experience. | A complete local workflow runs on a fresh machine with only Python and pip installed. |
| G-4 | Support cloud deployment with the same API. | Switching from local to remote storage requires configuration changes only; SDK calls stay the same. |
| G-5 | Apply data quality checks at the configured validation gates. | Invalid data is rejected, filtered, or allowed according to the operation-specific validation rules and selected validation mode, with actionable feedback when checks run. |
| G-6 | Generate realistic mock data from feature definitions. *(Post-MVP secondary goal.)* | Mock data generated for a feature group passes validation and can be used immediately for development. |
| G-7 | Enable local experimentation with production data through smart sampling. *(Post-MVP secondary goal.)* | A sampled subset from a remote store keeps the expected structure and is queryable through the standard SDK. |

## Non-Goals

| ID | Non-Goal | Summary |
| --- | --- | --- |
| NG-1 | Building a transformation or compute engine. | KiteFS does not manage, schedule, or execute feature computation. Users compute features with their own tools. |
| NG-2 | Streaming feature ingestion. | The MVP does not support real-time or near-real-time streaming ingestion. |
| NG-3 | Model hosting, training, or serving. | KiteFS provides features to models, but it does not host models, run inference, or manage model lifecycle. |
| NG-4 | Multi-cloud support in the MVP. | The MVP targets local and AWS providers. Other providers can be added later through the provider boundary. |
| NG-5 | Web UI for the MVP. | Feature discovery and registry inspection are provided through the CLI in the MVP. |
| NG-6 | Authentication and authorization. | KiteFS does not implement its own auth layer. Cloud access control relies on the cloud provider. |
| NG-7 | Feature drift detection or statistical monitoring. | The MVP covers type and constraint validation, not statistical drift monitoring or alerting. |

## Personas

| Persona | Needs | Primary Interface |
| --- | --- | --- |
| Data Scientist / ML Engineer | Define features, ingest computed values, build point-in-time correct training datasets, and iterate quickly. | Python SDK in notebooks or scripts. |
| Backend / Software Engineer | Retrieve precomputed feature values with low latency during real-time inference. | Python SDK in application code. |
| ML / Data Platform Engineer | Configure storage backends, automate operational workflows, and keep features validated and materialized. | CLI and project configuration. |

## Project Scope

KiteFS is a Python feature store library distributed as a pip-installable package. Its core responsibility is feature management: store, validate, retrieve, materialize, discover, and serve features through a Python SDK and CLI.

KiteFS is library-first, not service-first. It should work locally with minimal setup, then use provider configuration to target remote storage when needed. The reference example is documented separately in [01-reference-use-case.md](01-reference-use-case.md).

### MVP Scope

The MVP should avoid over-engineering. In this project, MVP means a working alpha version that demonstrates KiteFS end-to-end through a simple, minimalist, but realistic use-case project, such as a demo built on the reference use case. The goal is to prove the library works, not to polish every edge.