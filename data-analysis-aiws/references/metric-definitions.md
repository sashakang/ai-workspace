# Metric Definitions

This file defines the default analytical meaning of common forecastable metrics used by `data-analysis-aiws`.

These are working defaults for forecasting and analysis. If a stakeholder or project has an explicit local definition, the local definition wins, but any override should be called out.

## Revenue

`revenue`

Default meaning:
- total monetary value of completed transactions in the selected time window

Clarify before modelling:
- gross vs net (before or after refunds, discounts, fees)
- currency and exchange-rate treatment for multi-region data
- whether recurring and one-time revenue are separated

Forecastability notes:
- typically forecastable at weekly or monthly grain
- strong seasonality in most businesses (day-of-week, month-of-year)
- regime changes (pricing updates, new product launches) can break trailing patterns

## Active Users

`active_users`

Default meaning:
- distinct users who performed a qualifying action in the selected time window

Clarify before modelling:
- definition of "active" (login, transaction, any event)
- whether the window is daily, weekly, or monthly active
- whether test or internal accounts must be excluded

Forecastability notes:
- distinct-count metric — not summable across time grains; recompute at each grain
- growth and churn dynamics make long-horizon forecasts less stable
- seasonality often differs from transaction-based metrics

## Transaction Volume

`transaction_volume`

Default meaning:
- count of completed transactions in the selected time window

Clarify before modelling:
- whether cancelled or refunded transactions are included
- whether the timestamp anchor is initiation or completion
- whether test transactions must be excluded

Forecastability notes:
- count metric — summable from daily to weekly to monthly
- typically the most stable series for forecasting
- watch for step changes from product or policy launches

## Conversion Rate

`conversion_rate`

Default meaning:
- `completed_transactions / initiated_transactions`

Rules:
- compute from aligned numerator and denominator at the same grain
- return `NULL` when denominator is zero
- flag values greater than `1.0` as a likely data-quality issue

Forecastability notes:
- ratio metric — do not forecast the ratio directly unless both components are stable
- preferred approach: forecast numerator and denominator independently, then derive the ratio
- small denominator periods can create noisy spikes

## Time Grain Aggregation Rules

When changing granularity for forecasting:
- counts are additive across time grains (daily sums to weekly)
- distinct counts are not additive — recompute at the target grain
- rates must be recomputed from component sums, not averaged
- averages of averages are only valid when group sizes are equal
