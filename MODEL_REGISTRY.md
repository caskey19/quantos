# Model registry

No production model is registered.

`quantos.ml.baseline.fit_linear_baseline` fits an ordinary least-squares map from residual return to a research label on a training window and scores R² on a later window. The returned record sets `promoted` to false. A model is kept only if a later, costed, purged comparison beats the rank rule. That comparison has not been accepted.

Stored fields when a fit is run: version, training time, features, hyperparameters, coefficients, validation R², calibration note, and the refusal reason.

Nothing in the order pipeline loads this record.
