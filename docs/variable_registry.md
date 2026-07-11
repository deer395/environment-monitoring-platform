# Variable Registry

## Purpose

`src/variable_registry.py` is the single source of truth for V1 variable metadata.

The registry keeps variable-specific decisions out of loaders, metrics, plotting, and report modules.

## V1 Variables

V1 supports:

1. `depth`
2. `temperature`

No water-quality variables are included in V1.

## Registry Responsibilities

Each variable entry should describe:

1. Variable key.
2. Display name.
3. Unit.
4. Accepted Excel datetime column names.
5. Accepted Excel value column names.
6. Quality-control placeholders.
7. Resampling requirements.
8. Metric requirements.
9. Plot requirements.

## V1 Registry Design

`depth` should include:

1. Excel datetime aliases.
2. Excel value aliases.
3. Unit placeholder.
4. Daily maximum variation amplitude metric.
5. Raw hourly plus daily mean plot.
6. Intra-day anomaly plot.

`temperature` should include:

1. Excel datetime aliases.
2. Excel value aliases.
3. Unit placeholder.
4. Mean, max, min, monthly mean, monthly standard deviation metrics.
5. Raw hourly plus daily mean plot.
6. Intra-day anomaly plot.

## V2 Registry Candidates

V2 may extend the registry with:

1. MAT source metadata.
2. Salinity.
3. Water-quality variables.
4. Harmonic-analysis settings.
5. AI report section templates based on computed statistics.
