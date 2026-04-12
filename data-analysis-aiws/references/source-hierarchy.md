# Source Hierarchy

Use the highest-quality source that can answer the request at the required grain and freshness.

## Preferred order

### 1. Curated business metrics tables

Use first when available.

Good for:
- stakeholder reporting
- repeated KPI pulls
- daily or weekly summary metrics

Strengths:
- stable definitions
- lower query complexity
- easier stakeholder alignment

Risks:
- may lag behind raw operational data
- may hide edge-case exclusions

### 2. Curated product or funnel tables

Use when the request is about conversion, request flow, or stage-level drop-offs.

Good for:
- funnel analysis
- platform/source segmentation
- request-to-completion analysis

Risks:
- stage definitions may drift across teams
- not always suitable for operational transaction accounting

### 3. Operational fact tables

Use when curated tables do not have the needed grain, freshness, or dimensions.

Good for:
- detailed transaction or event extraction
- debugging discrepancies
- custom segmentation

Risks:
- more complex joins
- more data-quality pitfalls
- easier to miscount because of grain mistakes

## Selection rules

- prefer curated metrics over raw facts when they answer the question cleanly
- prefer source consistency over clever joins across many layers
- if two layers disagree, do not merge silently; identify the authoritative layer first
- if freshness matters more than definitional stability, call that tradeoff out explicitly

## Escalation rule

If no source can answer the request at the required grain, freshness, and trust level:
- say so
- narrow the scope
- or propose a staged answer
