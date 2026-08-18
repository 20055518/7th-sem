# Architecture Validation

## Decision

The proposed React + FastAPI + MongoDB architecture is appropriate for the project scope. REST is suitable for registration, queue actions, QR validation, administration, and reports. WebSockets are appropriate for queue changes that must reach multiple dashboards without refresh.

Keep this as a modular monolith for the project: one React application, one FastAPI application, and one MongoDB deployment. This is easier to test, explain, and deploy than microservices while preserving clear service boundaries.

## Backend boundaries

```text
routes/        HTTP and WebSocket endpoint definitions
auth/          JWT, password hashing, current-user and RBAC dependencies
models/        Pydantic request/response schemas
services/      Queue, QR, notification, audit, and route business rules
ml/            Feature construction and regression prediction
bayesian/      Event priors, likelihoods, and posterior calculation
websocket/     Connection manager and role/queue broadcasts
utils/         Shared time, IDs, and validation helpers
```

Queue mutation is the transaction boundary. For an action such as `call-next`, the backend must update the queue state, record an audit event, recalculate affected predictions, create notifications, and then broadcast the resulting committed state. MongoDB sessions/transactions should be used when the deployment supports them; otherwise use idempotent writes and an operation ID.

WebSocket clients must authenticate with a short-lived JWT during connection setup. They should subscribe only to authorized channels: a patient can receive their own queue entry, while staff may subscribe to queues assigned to their role. REST remains the source of truth because a WebSocket message can be missed after a reconnect.

## MongoDB Design Validation

MongoDB fits the evolving queue, event, notification, and prediction documents. It does not remove the need for schema rules or indexes. Pydantic validates API data; MongoDB collection validators should be added in Phase 2 for critical status enums and required identifiers.

Use the proposed collections with these design rules:

- `users` contains credentials and role only; retain clinical/profile fields in role-specific documents where useful.
- `patients`, `doctors`, `departments`, `rooms`, and `hospital_routes` are durable reference documents.
- `appointments` records booking context. `queue_entries` records one visit/queue lifecycle and should not be overwritten for a later visit.
- `qr_tokens` stores a random opaque token hash, queue-entry ID, expiry, usage state, and purpose. The QR code contains only the opaque token or signed short URL.
- `consultations` records service start/end and outcome; `ml_predictions` records input snapshot, model version, prediction, and later actual result for evaluation.
- `notifications` is append-oriented and tracks delivery/read state. `audit_logs` is append-only.
- `system_settings` is a small, versioned singleton document with configurable next-patient threshold and notification settings.

Initial indexes for Phase 2:

```text
users:           unique(email), role
patients:        userId, medicalRecordNumber (unique only if used)
doctors:         userId (unique), departmentId
appointments:    patientId + scheduledAt, doctorId + scheduledAt
queue_entries:   unique(tokenNumber), patientId + createdAt, doctorId + status + createdAt,
                 departmentId + status + createdAt, status + createdAt
qr_tokens:       unique(tokenHash), queueEntryId, expiresAt (TTL), usedAt
notifications:   recipientUserId + createdAt, recipientUserId + readAt
consultations:   queueEntryId (unique), doctorId + startedAt
ml_predictions:  queueEntryId + createdAt, modelVersion + createdAt
audit_logs:      userId + timestamp, action + timestamp
hospital_routes: unique(departmentId + roomId)
```

Store timestamps in UTC. Store ObjectIds as ObjectIds in MongoDB and serialize them only at the API boundary. Queue position is derived during reads or refreshed atomically after a mutation; do not treat a stale stored position as authoritative.

## Security Boundaries

- QR payloads never contain patient identity, diagnoses, or credentials.
- QR tokens are high-entropy, expire, are single-purpose, and are marked used atomically for check-in.
- Patients may access only queue entries linked to their user/patient ID. Staff actions require role and assigned-doctor/department checks.
- Passwords use bcrypt. JWT keys, Mongo URI, and frontend API URL are environment variables, never source code.
- Every state-changing action creates an audit log entry.
