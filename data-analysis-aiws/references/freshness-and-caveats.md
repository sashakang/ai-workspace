# Freshness And Caveats

Do not treat extracted data as final until freshness and known caveats are understood.

## Freshness checks

Before delivery, check:
- max available date
- whether the latest day is complete
- whether there is known pipeline lag or backfill behavior

## Common caveats

- latest-day data may be provisional
- completion events may settle later than request events
- platform or city values may be null or unknown
- test or internal traffic may need exclusion
- small cells can produce misleading conversion rates

## Communication rules

Always call out caveats when they materially affect interpretation.

Examples:
- latest day incomplete
- metric definition assumed, not confirmed
- city mapping inferred from lookup table
- denominator too small for stable conversion rate

## Suppression rule

If a metric is technically computable but likely misleading because of cell size or data quality, prefer:
- `NULL`
- suppression note
- or an explicit caveat

Do not present a precise-looking number that is not trustworthy.
