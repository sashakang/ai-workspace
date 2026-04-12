# Join And Grain Rules

Most analytical errors come from grain mistakes, not syntax mistakes.

## Core rule

Before joining anything, state the grain of each input.

Examples:
- one row per transaction
- one row per user-day
- one row per region-day-platform
- one row per product-month

## Safe join rules

- join only on keys that preserve the intended grain
- if one side is more granular, aggregate it first unless row multiplication is intended
- when in doubt, validate row counts before and after the join

## Distinct counts

Be careful with:
- users
- accounts
- sessions
- transactions if duplicated across lifecycle tables

Distinct counts should usually be computed from the rawest valid grain, not summed from rolled-up rows.

## Ratio metrics

Do not average pre-aggregated rates unless that is explicitly the business definition.

Preferred pattern:
- sum or count the numerator components
- sum or count the denominator components
- divide once at the target reporting grain

## Region and platform joins

- normalize platform values before aggregation when possible
- use a reference mapping for region names or codes if the source is not already stable
- if a mapping changes over time, call out whether you are using current or historical mapping

## Validation checks

After any meaningful join:
- compare row counts
- compare distinct primary keys
- inspect a small sample for duplicated entities
- check for impossible metric inflation
