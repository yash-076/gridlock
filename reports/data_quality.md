# Data Quality Report - Gridlock / Bengaluru Traffic Events

**Total rows after cleaning:** 8,173
**Active (right-censored, duration unknown):** 1,007  (12.3%)
**Resolved / Closed (duration known):** 7,166  (87.7%)

## Missing values (% per retained column)

| Column | % Missing |
|--------|-----------|
| address | 0.0% |
| closed_datetime | 61.6% |
| created_date | 0.0% |
| description | 16.6% |
| duration_minutes | 56.6% |
| end_datetime | 94.2% |
| endlatitude | 91.6% |
| endlongitude | 91.6% |
| event_end_time | 55.3% |
| junction | 69.3% |
| priority | 0.0% |
| resolved_datetime | 99.1% |
| start_datetime | 1.4% |
| veh_no | 40.2% |
| veh_type | 40.2% |
| zone | 57.9% |

## event_cause distribution

| Cause | Count |
|-------|-------|
| vehicle_breakdown | 4,929 |
| pot_holes | 537 |
| construction | 510 |
| others | 502 |
| water_logging | 468 |
| accident | 368 |
| tree_fall | 290 |
| road_conditions | 170 |
| congestion | 136 |
| public_event | 84 |
| procession | 72 |
| tyre_puncture | 33 |
| signal_failure | 21 |
| vip_movement | 20 |
| protest | 15 |
| debris | 13 |
| test_demo | 3 |
| fog_/_low_visibility | 2 |

## Notes
- `end_datetime` was populated for <3% of rows; `event_end_time` falls back to `closed_datetime` then `resolved_datetime`.
- `endlatitude`/`endlongitude` == 0 treated as missing.
- `corridor` imputed via 3-NN on (lat, lon) for rows without a corridor label.
- `others` event_cause sub-classified via regex keyword tagger (English + transliterated Kannada).
- `active`-status rows excluded from duration model training (right-censored).