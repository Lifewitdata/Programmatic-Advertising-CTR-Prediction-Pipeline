# Current feature contract

The active implementation is `src/features.py`: 11 numerical features and six
chronological categorical target encodings. It replaces the historical 84-feature
notebook. Version-1 result counts are not comparable to the new synthetic run.

History includes only fully matured 24-hour outcomes strictly before scoring.
Same-time outcomes are excluded. All historical counts use this same maturity
rule, so numerator and denominator are consistent. The declared cold-start prior
is 0.02 and is not estimated from future rows.

Training target encodings are day-block out-of-fold values using only outcomes
available before that day. Models and encoders are refitted per forward-CV fold.
Calibration, validation and test transforms use the encoder fitted on the model
fit period; boundaries purge outcomes that would not yet be known.

No IDs, outcome timestamps, latent propensity, age or gender enter the model.
The categorical fields are device, creative type, ad position, country, campaign
objective and hour bucket. The numerical fields are hour, weekday, weekend,
prior daily impressions, floor price and campaign/user matured history counts
and CTR. The floor price is not paid spend and is not used as a revenue metric.

Low feature correlation does not prove leakage is absent. Tests instead perturb
future labels and assert earlier features remain unchanged.
