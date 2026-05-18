# AI-SaaS Week4 - API Function Specification

**OpenAI Compatible API Gateway** with Smart Routing Proxy Layer

| Property        | Value                                                                |
| --------------- | -------------------------------------------------------------------- |
| Base URL        | `http://localhost:8000`                                              |
| Auth Method     | `Bearer <api_key>`                                                   |
| Default API Key | `sk-gateway-default-key`                                             |
| Content Type    | `application/json` (non-streaming) / `text/event-stream` (streaming) |
| Spec Version    | 1.0.0                                                                |

---

## Table of Contents

1. [Authentication & Error Handling](#1-authentication--error-handling)
2. [Chat Completions](#2-chat-completions)
3. [Embeddings](#3-embeddings)
4. [Models](#4-models)
5. [Health Check](#5-health-check)
6. [Admin Dashboard](#6-admin-dashboard)
7. [Rate Limiting](#7-rate-limiting)
8. [Response Headers](#8-response-headers)
9. [Smart Routing Logic](#9-smart-routing-logic)

---

## 1. Authentication & Error Handling

### 1.1 Authentication

All endpoints (except `/health`, `/docs`, `/openapi.json`, `/redoc`, `/`, and `/admin/*`) require API key authentication via the `Authorization` header.

| Header          | Required         | Description                                                                |
| --------------- | ---------------- | -------------------------------------------------------------------------- |
| `Authorization` | Yes (most paths) | `Bearer sk-gateway-default-key`                                            |
| `X-User-ID`     | No               | User identifier for routing/cost tracking; falls back to truncated API key |

**Excluded paths (no auth required):**

- `/health`
- `/docs`, `/openapi.json`, `/redoc`
- `/`
- `/admin` and all `/admin/*` sub-paths

### 1.2 Error Response Format

All errors follow the OpenAI-compatible error format:

```json
{
  "error": {
    "message": "Human-readable error description",
    "type": "error_type",
    "code": 400
  }
}
```

| HTTP Status | Type                    | When                                              |
| ----------- | ----------------------- | ------------------------------------------------- |
| `400`       | `invalid_request_error` | Invalid JSON body, missing `model`, unknown model |
| `401`       | `authentication_error`  | Missing `Authorization` header                    |
| `403`       | `authentication_error`  | Invalid API key (wrong `Bearer` token)            |
| `404`       | `invalid_request_error` | Resource not found (model/cost user)              |
| `429`       | `rate_limit_error`      | Rate limit exceeded (default: 60 req/min per IP)  |
| `502`       | `upstream_error`        | Upstream backend unreachable or timeout           |

---

## 2. Chat Completions

### 2.1 `POST /v1/chat/completions`

OpenAI-compatible chat completions endpoint. Supports both streaming and non-streaming responses. The gateway's smart router automatically selects the best upstream model based on user identity, system health, cost budget, and load conditions.

**Request Body**

| Parameter            | Type           | Required | Default | Description                                                    |
| -------------------- | -------------- | -------- | ------- | -------------------------------------------------------------- |
| `model`              | `string`       | **Yes**  | -       | Model identifier (e.g. `vllm-local`, `gpt-3.5-turbo`, `gpt-4`) |
| `messages`           | `array`        | **Yes**  | -       | List of message objects                                        |
| `messages[].role`    | `string`       | **Yes**  | -       | `system`, `user`, `assistant`, or `function`                   |
| `messages[].content` | `string`       | **Yes**  | -       | Message text content                                           |
| `messages[].name`    | `string`       | No       | -       | Optional sender name                                           |
| `stream`             | `boolean`      | No       | `false` | Enable SSE streaming response                                  |
| `temperature`        | `number`       | No       | -       | Sampling temperature (0.0 - 2.0)                               |
| `max_tokens`         | `integer`      | No       | `256`   | Maximum completion tokens                                      |
| `top_p`              | `number`       | No       | -       | Nucleus sampling parameter                                     |
| `n`                  | `integer`      | No       | `1`     | Number of completions                                          |
| `stop`               | `string/array` | No       | -       | Stop sequences                                                 |
| `presence_penalty`   | `number`       | No       | -       | -2.0 to 2.0                                                    |
| `frequency_penalty`  | `number`       | No       | -       | -2.0 to 2.0                                                    |
| `logit_bias`         | `object`       | No       | -       | Token bias map                                                 |
| `user`               | `string`       | No       | -       | End-user identifier                                            |

**Constraints**

- `model` must be a registered model in the gateway registry (see [§ 9 Smart Routing Logic](#9-smart-routing-logic))
- `messages` must be non-empty
- `temperature` ∈ [0.0, 2.0]
- `max_tokens` must be > 0
- `stream=true` returns `text/event-stream` (SSE)

**Request Headers**

| Header          | Required | Description                                                 |
| --------------- | -------- | ----------------------------------------------------------- |
| `Authorization` | **Yes**  | `Bearer <api_key>`                                          |
| `X-User-ID`     | No       | User identifier; prioritized over API key for cost tracking |
| `X-Request-ID`  | No       | Client-provided request tracing ID                          |

### 2.1.1 Non-Streaming Response

**POST /v1/chat/completions**

```json
{
  "model": "vllm-local",
  "messages": [
    { "role": "system", "content": "You are a helpful assistant." },
    { "role": "user", "content": "What is vLLM?" }
  ],
  "temperature": 0.7,
  "max_tokens": 512
}
```

**Response 200**

```json
{
  "id": "chatcmpl-abc123",
  "object": "chat.completion",
  "created": 1700000000,
  "model": "vllm-local",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "vLLM is an open-source library for LLM inference and serving..."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 23,
    "completion_tokens": 128,
    "total_tokens": 151
  }
}
```

### 2.1.2 Streaming Response (SSE)

**POST /v1/chat/completions**

```json
{
  "model": "vllm-local",
  "messages": [{ "role": "user", "content": "Tell me a story" }],
  "stream": true
}
```

**Response 200** - `Content-Type: text/event-stream`

```
data: {"id":"chatcmpl-xyz","object":"chat.completion.chunk","created":1700000000,"model":"vllm-local","choices":[{"index":0,"delta":{"role":"assistant","content":"Once"},"finish_reason":null}]}

data: {"id":"chatcmpl-xyz","object":"chat.completion.chunk","created":1700000000,"model":"vllm-local","choices":[{"index":0,"delta":{"content":" upon"},"finish_reason":null}]}

data: {"id":"chatcmpl-xyz","object":"chat.completion.chunk","created":1700000000,"model":"vllm-local","choices":[{"index":0,"delta":{"content":" a time"},"finish_reason":null}]}

...

data: {"id":"chatcmpl-xyz","object":"chat.completion.chunk","created":1700000000,"model":"vllm-local","choices":[{"index":0,"delta":{},"finish_reason":"stop"}],"usage":{"prompt_tokens":8,"completion_tokens":42,"total_tokens":50}}

data: [DONE]
```

**Stream with fallback**: If the primary backend fails, the gateway seamlessly switches to a fallback cloud model. Content already emitted before the failure is prepended to the fallback request (as an `assistant` message) so the client sees no interruption.

**Stream Response Headers**

| Header              | Value               |
| ------------------- | ------------------- |
| `Content-Type`      | `text/event-stream` |
| `Cache-Control`     | `no-cache`          |
| `Connection`        | `keep-alive`        |
| `X-Accel-Buffering` | `no`                |
| `X-Request-ID`      | Request tracing ID  |

### 2.1.3 Error Responses

**400 - Model not found**

```json
{
  "error": {
    "message": "No healthy model found for: unknown-model",
    "type": "invalid_request_error",
    "code": 400
  }
}
```

**400 - Invalid JSON**

```json
{
  "error": {
    "message": "Invalid JSON in request body",
    "type": "invalid_request_error",
    "code": 400
  }
}
```

---

## 3. Embeddings

### 3.1 `POST /v1/embeddings`

OpenAI-compatible embeddings endpoint. Proxies requests to the best available model.

**Request Body**

| Parameter         | Type           | Required | Default | Description                                   |
| ----------------- | -------------- | -------- | ------- | --------------------------------------------- |
| `model`           | `string`       | **Yes**  | -       | Embedding model name                          |
| `input`           | `string/array` | **Yes**  | -       | Text to embed (string or array of strings)    |
| `encoding_format` | `string`       | No       | `float` | Format of the embedding (`float` or `base64`) |
| `dimensions`      | `integer`      | No       | -       | Number of embedding dimensions                |
| `user`            | `string`       | No       | -       | End-user identifier                           |

**Sample Request**

```json
{
  "model": "text-embedding-ada-002",
  "input": "The quick brown fox jumps over the lazy dog"
}
```

**Response 200**

```json
{
  "object": "list",
  "data": [
    {
      "object": "embedding",
      "index": 0,
      "embedding": [0.002, -0.001, 0.015, ...]
    }
  ],
  "model": "text-embedding-ada-002",
  "usage": {
    "prompt_tokens": 9,
    "total_tokens": 9
  }
}
```

---

## 4. Models

### 4.1 `GET /v1/models`

List all available healthy models registered in the gateway. Falls back to listing all registered models if none are healthy.

**No parameters required.**

**Sample Request**

```
GET /v1/models
Authorization: Bearer sk-gateway-default-key
```

**Response 200**

```json
{
  "object": "list",
  "data": [
    {
      "id": "gpt-3.5-turbo",
      "object": "model",
      "created": 1700000000,
      "owned_by": "openai"
    },
    {
      "id": "vllm-local",
      "object": "model",
      "created": 1700000000,
      "owned_by": "vllm"
    }
  ]
}
```

### 4.2 `GET /v1/models/{model_name:path}`

Retrieve details of a specific model by name. Supports path-style model names (e.g. `gpt-3.5-turbo`).

**Path Parameters**

| Parameter    | Type     | Required | Description      |
| ------------ | -------- | -------- | ---------------- |
| `model_name` | `string` | **Yes**  | Model identifier |

**Sample Request**

```
GET /v1/models/vllm-local
Authorization: Bearer sk-gateway-default-key
```

**Response 200**

```json
{
  "id": "vllm-local",
  "object": "model",
  "created": 1700000000,
  "owned_by": "vllm"
}
```

**Response 404**

```json
{
  "error": {
    "message": "Model not found: nonexistent-model",
    "type": "invalid_request_error",
    "code": 404
  }
}
```

---

## 5. Health Check

### 5.1 `GET /health`

Gateway health status endpoint. **No authentication required.**

**No parameters required.**

**Sample Request**

```
GET /health
```

**Response 200**

```json
{
  "status": "healthy",
  "gateway": "running",
  "models": {
    "vllm-local": {
      "status": "healthy",
      "provider": "vllm",
      "priority": 1,
      "last_checked": 1700000000.0
    },
    "gpt-3.5-turbo": {
      "status": "unknown",
      "provider": "openai",
      "priority": 10,
      "last_checked": 0.0
    }
  },
  "healthy_models": 1,
  "total_models": 2,
  "request_id": "uuid-here"
}
```

**Response Fields**

| Field                        | Type      | Description                                                        |
| ---------------------------- | --------- | ------------------------------------------------------------------ |
| `status`                     | `string`  | `"healthy"` if at least 1 model is healthy, `"degraded"` otherwise |
| `gateway`                    | `string`  | Gateway status: `"running"`                                        |
| `models`                     | `object`  | Map of model name → status info                                    |
| `models.{name}.status`       | `string`  | `healthy`, `unhealthy`, `unknown`, `degraded`                      |
| `models.{name}.provider`     | `string`  | Provider name (`vllm`, `openai`, `ollama`)                         |
| `models.{name}.priority`     | `integer` | Routing priority (lower = higher priority)                         |
| `models.{name}.last_checked` | `float`   | Unix timestamp of last health check                                |
| `healthy_models`             | `integer` | Count of healthy models                                            |
| `total_models`               | `integer` | Total registered models                                            |

---

## 6. Admin Dashboard

All admin endpoints are mounted at `/admin/*` and **do not require authentication**.

### 6.1 `GET /admin/routes`

**Main dashboard endpoint.** Returns the complete routing state: health stats, degradation status, cost data, switch statistics, and recent routing decisions.

**No parameters required.**

**Sample Request**

```
GET /admin/routes
```

**Response 200**

```json
{
  "health": {
    "is_healthy": true,
    "success_rate": 99.5,
    "p50_latency_ms": 45.0,
    "p99_latency_ms": 120.0,
    "avg_queue_depth": 2.3,
    "gpu_memory_pct": 45.2,
    "cpu_pct": 32.1,
    "gpu_pct": 68.4,
    "consecutive_5xx": 0
  },
  "degradation": {
    "is_degraded": false,
    "last_decision": {
      "should_degrade": false,
      "reason": "none",
      "detail": "",
      "timestamp": 1700000000.0
    }
  },
  "cost": {
    "total_monthly_cost": 2.3456,
    "users": [
      {
        "user_id": "user1",
        "monthly_cost_usd": 1.2345,
        "total_tokens": 15000,
        "over_budget": false
      }
    ]
  },
  "switch_stats": {
    "switch_count": 42,
    "switch_failure_count": 0,
    "switch_failure_rate": 0.0
  },
  "recent_decisions": [
    {
      "timestamp": 1700000001.0,
      "target": "vllm-local",
      "reason": "default",
      "detail": "Local vLLM healthy, routing locally",
      "switch_latency_ms": 0.35,
      "user_id": "user1",
      "model_requested": "vllm-local"
    }
  ]
}
```

### 6.2 `GET /admin/routes/dashboard`

**HTML dashboard** with auto-refresh (every 5 seconds). Visualizes health metrics, degradation status, cost data, switch statistics, and recent route decisions in a responsive grid layout with color-coded metrics (green/yellow/red).

**Sample Request**

```
GET /admin/routes/dashboard
```

**Response 200** - `Content-Type: text/html`

A complete HTML page with embedded CSS and JavaScript that fetches `/admin/routes` data and renders it as a dashboard UI.

### 6.3 `GET /admin/routes/health`

**Detailed health status** of the local endpoint. Triggers real-time degradation evaluation.

**No parameters required.**

**Sample Request**

```
GET /admin/routes/health
```

**Response 200**

```json
{
  "endpoint": "http://localhost:8000",
  "is_healthy": true,
  "stats": {
    "success_rate": 99.5,
    "p50_latency_ms": 45.0,
    "p99_latency_ms": 120.0,
    "avg_queue_depth": 2.3,
    "gpu_memory_pct": 45.2,
    "cpu_pct": 32.1,
    "gpu_pct": 68.4,
    "consecutive_5xx": 0,
    "snapshot_count": 120
  },
  "degradation": {
    "is_degraded": false,
    "reason": "none",
    "detail": ""
  }
}
```

### 6.4 `GET /admin/routes/cost`

**Cost tracking overview.** Returns per-user or aggregated cost data.

**Query Parameters**

| Parameter | Type     | Required | Description                                                 |
| --------- | -------- | -------- | ----------------------------------------------------------- |
| `user_id` | `string` | No       | Filter by user ID. Returns 404 if user has no cost records. |

**Sample Request (All Users)**

```
GET /admin/routes/cost
```

**Response 200**

```json
{
  "total_monthly_cost": 5.6789,
  "users": [
    {
      "user_id": "user1",
      "monthly_cost_usd": 3.4567,
      "total_tokens": 25000,
      "over_budget": false
    },
    {
      "user_id": "vip_user",
      "monthly_cost_usd": 1.2345,
      "total_tokens": 8000,
      "over_budget": false
    }
  ]
}
```

**Sample Request (Single User)**

```
GET /admin/routes/cost?user_id=user1
```

**Response 200**

```json
{
  "user_id": "user1",
  "monthly_cost_usd": 3.4567,
  "total_tokens": 25000,
  "over_budget": false,
  "recent_records": [
    {
      "model": "gpt-4",
      "prompt_tokens": 120,
      "completion_tokens": 45,
      "cost_usd": 0.00495,
      "timestamp": 1700000100.0
    }
  ]
}
```

**Response 404** - User has no cost records

```json
{ "error": "User unknown_user not found" }
```

### 6.5 `POST /admin/routes/vip/{user_id}`

**Add a user to the VIP list.** VIP users are always routed to GPT-4 regardless of other conditions.

**Path Parameters**

| Parameter | Type     | Required | Description                 |
| --------- | -------- | -------- | --------------------------- |
| `user_id` | `string` | **Yes**  | User ID to designate as VIP |

**Sample Request**

```
POST /admin/routes/vip/user42
```

**Response 200**

```json
{
  "status": "ok",
  "user_id": "user42",
  "is_vip": true
}
```

### 6.6 `DELETE /admin/routes/vip/{user_id}`

**Remove a user from the VIP list.**

**Path Parameters**

| Parameter | Type     | Required | Description                |
| --------- | -------- | -------- | -------------------------- |
| `user_id` | `string` | **Yes**  | User ID to remove from VIP |

**Sample Request**

```
DELETE /admin/routes/vip/user42
```

**Response 200**

```json
{
  "status": "ok",
  "user_id": "user42",
  "is_vip": false
}
```

### 6.7 `POST /admin/routes/degrade`

**Manually force degradation mode.** All subsequent non-VIP requests will be routed to the cloud fallback model. Manual degradation is not overridden by health check evaluations until manually recovered.

**No parameters required.**

**Sample Request**

```
POST /admin/routes/degrade
```

**Response 200**

```json
{
  "status": "ok",
  "degraded": true
}
```

### 6.8 `POST /admin/routes/recover`

**Manually recover from degradation mode.** Restores normal routing logic based on health checks.

**No parameters required.**

**Sample Request**

```
POST /admin/routes/recover
```

**Response 200**

```json
{
  "status": "ok",
  "degraded": false
}
```

### 6.9 `GET /admin/routes/metrics`

**Prometheus metrics endpoint.** Returns raw Prometheus-formatted metrics if enabled.

**No parameters required.**

**Sample Request**

```
GET /admin/routes/metrics
```

**Response 200**

```json
{
  "prometheus_enabled": true,
  "metrics_text": "# HELP gateway_route_decisions_total ...\n# TYPE ...\n..."
}
```

---

## 7. Rate Limiting

| Setting      | Default       | Description    |
| ------------ | ------------- | -------------- |
| Max requests | 60 per minute | Per-client-IP  |
| Window       | 60 seconds    | Sliding window |

Excluded paths: `/health`, `/docs`, `/openapi.json`, `/redoc`

### Rate Limit Response (429)

```json
{
  "error": {
    "message": "Rate limit exceeded. Please try again later.",
    "type": "rate_limit_error",
    "code": 429
  }
}
```

---

## 8. Response Headers

All responses include the following standard headers:

| Header                  | Description                                   |
| ----------------------- | --------------------------------------------- |
| `X-Request-ID`          | Unique tracing ID for the request             |
| `X-Response-Time-Ms`    | Total request processing time in milliseconds |
| `X-RateLimit-Remaining` | Remaining requests in rate limit window       |
| `X-RateLimit-Limit`     | Max requests per window                       |

Streaming responses additionally include:

| Header              | Value               |
| ------------------- | ------------------- |
| `Content-Type`      | `text/event-stream` |
| `Cache-Control`     | `no-cache`          |
| `Connection`        | `keep-alive`        |
| `X-Accel-Buffering` | `no`                |

---

## 9. Smart Routing Logic

The gateway applies the following decision tree for each chat completion request:

```
1. Is user a VIP?
   └─ YES → Route to GPT-4 (CLOUD_GPT4)
   └─ NO  → Continue to step 2

2. Is degradation active?
   └─ YES → Route to GPT-3.5-Turbo (CLOUD_GPT35)
   └─ NO  → Continue to step 3

3. Is user over monthly cost budget?
   └─ YES → Route to local vLLM (LOCAL_VLLM)
   └─ NO  → Continue to step 4

4. Is local instance overloaded? (CPU or GPU > 80%)
   └─ YES → Route to GPT-3.5-Turbo (CLOUD_GPT35)
   └─ NO  → Continue to step 5

5. Default: Route to local vLLM (LOCAL_VLLM)
```

### Degradation Triggers (auto-activate)

| Condition              | Threshold |
| ---------------------- | --------- |
| P99 latency            | > 800 ms  |
| Consecutive 5xx errors | ≥ 3       |
| GPU memory usage       | > 95%     |

### Cost Control

| Parameter            | Default            |
| -------------------- | ------------------ |
| Monthly cap per user | $10.00 USD         |
| GPT-4 cost           | $0.03 / 1K tokens  |
| GPT-3.5-Turbo cost   | $0.002 / 1K tokens |

Users exceeding their monthly cap are automatically routed to the local vLLM model.

### Load Balancing

| Condition       | Threshold              |
| --------------- | ---------------------- |
| CPU utilization | < 80% to route locally |
| GPU utilization | < 80% to route locally |

If either CPU or GPU exceeds 80%, requests are routed to the cloud fallback.

### Routing Decision Logging

Every routing decision is logged with:

- `target` - The selected model/endpoint
- `reason` - Why this target was selected (`default`, `vip_user`, `degradation`, `over_budget`, `load_balance`)
- `detail` - Human-readable explanation
- `switch_latency_ms` - Time taken to make the decision (must be < 50ms)
- `user_id` - The requesting user
- `timestamp` - Unix timestamp

---

## Quick Reference

### Endpoint Summary

| Method   | Path                          | Auth | Description                            |
| -------- | ----------------------------- | ---- | -------------------------------------- |
| `GET`    | `/`                           | No   | Service info                           |
| `POST`   | `/v1/chat/completions`        | Yes  | Chat completions (streaming supported) |
| `POST`   | `/v1/embeddings`              | Yes  | Text embeddings                        |
| `GET`    | `/v1/models`                  | Yes  | List available models                  |
| `GET`    | `/v1/models/{name}`           | Yes  | Get model details                      |
| `GET`    | `/health`                     | No   | Gateway health status                  |
| `GET`    | `/admin/routes`               | No   | Full routing dashboard (JSON)          |
| `GET`    | `/admin/routes/dashboard`     | No   | HTML dashboard                         |
| `GET`    | `/admin/routes/health`        | No   | Detailed health status                 |
| `GET`    | `/admin/routes/cost`          | No   | Cost tracking                          |
| `POST`   | `/admin/routes/vip/{user_id}` | No   | Add VIP user                           |
| `DELETE` | `/admin/routes/vip/{user_id}` | No   | Remove VIP user                        |
| `POST`   | `/admin/routes/degrade`       | No   | Force degradation                      |
| `POST`   | `/admin/routes/recover`       | No   | Recover from degradation               |
| `GET`    | `/admin/routes/metrics`       | No   | Prometheus metrics                     |

### cURL Examples

```bash
# Non-streaming chat
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer sk-gateway-default-key" \
  -H "Content-Type: application/json" \
  -H "X-User-ID: user1" \
  -d '{"model":"vllm-local","messages":[{"role":"user","content":"Hello"}]}'

# Streaming chat
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer sk-gateway-default-key" \
  -H "Content-Type: application/json" \
  -H "X-User-ID: user1" \
  -d '{"model":"vllm-local","messages":[{"role":"user","content":"Tell me a story"}],"stream":true}' \
  --no-buffer

# List models
curl http://localhost:8000/v1/models \
  -H "Authorization: Bearer sk-gateway-default-key"

# Health check
curl http://localhost:8000/health

# Admin dashboard
curl http://localhost:8000/admin/routes

# Add VIP user
curl -X POST http://localhost:8000/admin/routes/vip/user42

# Force degradation
curl -X POST http://localhost:8000/admin/routes/degrade

# Check cost
curl http://localhost:8000/admin/routes/cost?user_id=user1
```
