# Domain Forecasting Conventions

These are default forecasting conventions for the plugin. Override with project-specific knowledge when available.

## Typical seasonality patterns

- **Day-of-week:** most transaction and engagement metrics show weekly cycles; weekdays vs weekends often differ materially
- **Month-of-year:** revenue and volume metrics typically show calendar seasonality (holidays, fiscal cycles, weather)
- **Intra-month:** some metrics spike around paydays, billing cycles, or promotional calendars
- **Event-driven:** known events (holidays, product launches, marketing campaigns) should be modelled as exogenous regressors, not left as unexplained variance

## Forecast horizon conventions

- **Short-term (1–4 weeks):** trend extrapolation and recent seasonality dominate; simpler models often suffice
- **Medium-term (1–3 months):** seasonality and exogenous factors become material; validate against at least two full seasonal cycles of history
- **Long-term (3–12 months):** uncertainty grows significantly; confidence intervals should be prominently communicated; regime-change risk is high

## Common exogenous regressors

Consider including when available and relevant:
- holiday calendars (country and region-specific)
- promotional or campaign schedules
- pricing changes or policy updates
- macroeconomic indicators (for revenue or demand forecasts)
- product launches or feature rollouts

## Regime-change indicators

Flag these as potential forecast-breaking events:
- step changes in the series (sudden level shifts)
- changes in data collection or metric definition
- market entry, exit, or competitive shifts
- policy or regulatory changes affecting the metric
- infrastructure changes that alter data pipelines

When a regime change is detected, consider whether pre-change data should be excluded or down-weighted rather than treated as representative history.

## Metric cautions for forecasting

- distinct-count metrics are not additive across time grains — recompute at the forecast grain
- ratio metrics should usually be forecast as separate numerator and denominator series
- project and source freshness must be checked before using historical data for model training
