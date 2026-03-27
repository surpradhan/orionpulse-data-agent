# Prediction Playbook

Default model: Holt-Winters additive trend + seasonality.

Guidelines:

- Use monthly series with at least 18 points (target >= 24)
- Return point forecast and assumptions
- Mention uncertainty and potential external drivers not in dataset
- Pair forecast with anomaly scan for risk commentary
