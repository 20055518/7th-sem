# DHQPM Research Methodology

## Research Position

DHQPM is a proposed engineering model, not a proven clinical model. Its research question is whether dynamic event-aware corrections improve remaining waiting-time estimates compared with a linear-regression baseline. Results must be reported only after experiments on clearly identified real or synthetic data.

## Prediction Unit And Target

One observation is a queue-entry snapshot at prediction time `t`. The target is:

```text
actual_remaining_wait_minutes = consultation_started_at - t
```

For a patient waiting in queue, this is the remaining time until that patient's consultation starts. At initial queue entry, `t` is the arrival/check-in time. For dynamic retraining, take additional snapshots after material events without using information that occurred after `t`.

Exclude cancelled, invalid, and still-unresolved observations from supervised target labels. No-shows should be modelled as queue events, not assigned a fabricated wait target.

## Linear Regression Features

All features must be available at the snapshot time.

```text
patients_ahead                 integer; waiting plus currently served patients ahead
active_queue_length            integer; all waiting and in-service patients for the doctor
mean_service_minutes_trailing  mean completed consultation duration for same doctor, trailing window
doctor_id                      categorical, one-hot encoded
department_id                  categorical, one-hot encoded
hour_sin, hour_cos             cyclic transformation of local appointment hour
day_of_week                    categorical or one-hot encoded
current_consult_elapsed        minutes; 0 when no active consultation
historical_wait_trailing       trailing mean wait for doctor/department/time bucket
service_rate_trailing          completed consultations per available hour, trailing window
declared_delay_minutes         observed doctor-declared delay remaining at snapshot
checked_in_ahead_count         count of ahead patients already confirmed present
```

The target is `actual_remaining_wait_minutes`. Do not use future completion duration, final queue position, future emergencies, or a historical aggregate that includes the observation's own outcome. Fit preprocessing and encoders on the training partition only.

## Probability And Bayesian Module

Estimate each event prior from labelled historical sessions with Laplace smoothing:

```text
P(E) = (count(E) + 1) / (session_count + 2)
```

Calculate likelihoods from labelled historic data for observable evidence bins, also smoothed:

```text
P(evidence_bin | E) = (count(evidence_bin and E) + 1) / (count(E) + bin_count)
```

For conditionally independent evidence bins, use a naive-Bayes posterior in odds form:

```text
posterior_odds(E) = prior_odds(E) * product(P(e_k | E) / P(e_k | not E))
P(E | evidence) = posterior_odds / (1 + posterior_odds)
```

Use the following observable labels and evidence:

```text
doctor_delay: declared delay or consultation overrun beyond expected threshold
evidence: current consultation elapsed/expected ratio, declared-delay flag, doctor historical delay bucket

patient_no_show: scheduled patient fails to check in by configured grace period
evidence: check-in state, minutes relative to appointment, patient historical attendance bucket

emergency_arrival: emergency queue entry added during a defined prediction horizon
evidence: department, hour bucket, weekday, recent emergency arrivals

queue_congestion: queue length/service capacity exceeds a documented threshold
evidence: active queue length, trailing service rate, room/doctor availability
```

Use only real historical labels or a dataset explicitly marked synthetic. Sparse doctors/departments should fall back to a department-level prior with the fallback recorded in the prediction document.

## Hybrid Fusion

The originally proposed formula is directionally reasonable, but raw probabilities cannot be added directly to a result in minutes. Convert every correction into expected minutes first:

```text
D = P(delay | evidence) * expected_remaining_delay_minutes
N = sum(P(no_show_j | evidence) * expected_service_minutes_j) for ahead scheduled patients
E = P(emergency | evidence) * expected_emergency_service_burden_minutes
C = max(0, active_queue_length / expected_capacity_for_horizon - 1) * mean_service_minutes_trailing

W_hybrid = max(0, W_LR + alpha*D - beta*N + gamma*E + delta*C)
```

`D`, `N`, `E`, and `C` are all minutes. `alpha`, `beta`, `gamma`, and `delta` are dimensionless non-negative calibration weights. This keeps the formula interpretable: delays, emergencies, and congestion increase waits; expected no-shows reduce them.

Fit the weights after fitting the linear-regression baseline. On a validation set, solve a non-negative regularized least-squares problem for the residual `actual_wait - W_LR`, using correction columns `[D, -N, E, C]`. Tune regularization and bounds with time-ordered cross-validation. Refit once on train plus validation only after selecting settings, then evaluate one untouched test period. Never hand-pick final weights from the test set.

## Baselines And Evaluation

Compare at minimum:

```text
Traditional queue estimate: patients_ahead * trailing mean service minutes
Historical average:         trailing doctor/department/time-bucket mean wait
Linear regression:          specified feature pipeline without Bayesian corrections
DHQPM:                      linear regression plus calibrated event corrections
```

Split chronologically, for example earliest 70% train, next 15% validation, latest 15% test. If the data spans multiple doctors, report overall and per-department metrics. Prevent duplicate snapshots of the same future outcome from crossing split boundaries where this would leak outcomes.

Report MAE, RMSE, and R-squared on the untouched test set. Also report prediction-event quality: Brier score and calibration plots for probabilities, and confidence intervals from bootstrap resampling for the difference in MAE between Linear Regression and DHQPM. Do not claim improvement unless this comparison supports it.

For real-time evaluation, timestamp queue action receipt, database commit, broadcast send, and client render. Measure API response, queue update, WebSocket delivery, notification delivery, and QR verification latency over repeated runs. Report median, p95, sample size, hardware/network context, and whether the environment is local or deployed.

## Known Limitations And Practical Controls

- Linear regression can underfit nonlinear waits. Start with it for interpretability; compare residuals before considering a more complex model.
- Naive Bayes assumes evidence independence. Document this assumption and use few, meaningfully distinct evidence bins.
- Emergency arrivals and no-shows are inherently uncertain. Present a prediction interval or confidence band later, not false precision.
- Small or synthetic datasets limit clinical generalization. Label synthetic data clearly and frame results as prototype evaluation.
- Queue state can change between prediction and display. Store the snapshot timestamp and show its age in every patient-facing prediction.
