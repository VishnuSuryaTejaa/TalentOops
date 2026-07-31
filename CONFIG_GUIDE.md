# TalentOps Configuration Guide

This guide details the configuration management system for TalentOps, an AI-powered multi-agent hiring and evaluation platform.

All configuration settings are managed centrally using `pydantic-settings` in [`app/config.py`](file:///Users/apple/TalentOops/app/config.py). Settings are loaded automatically from environment variables or a local `.env` file with strict type validation and default fallback values.

---

## Configuration Architecture

TalentOps uses Pydantic's `BaseSettings` for type-safe, validated, and self-documenting configuration management.

```python
from app.config import settings, get_settings

# Access configuration settings via the singleton instance
supabase_url = settings.SUPABASE_URL
is_offline = settings.is_offline_mode
origins = settings.cors_origins_list
```

### Key Architectural Benefits
- **Type Safety & Auto-Coercion**: String inputs from `.env` are automatically converted to float, int, or boolean.
- **Environment Fallbacks**: Default values ensure non-production testing functions out of the box without requiring every key.
- **Computed Helper Properties**: Utility properties handle dynamic operations like parsing comma-separated CORS origins or determining offline status.
- **Singleton Access**: `get_settings()` provides a thread-safe singleton instance across supervisor, agent, and API layers.

---

## Environment Variables Reference

### 1. Database & Persistence

| Variable | Type | Default | Description & Usage | Example |
|----------|------|---------|---------------------|---------|
| `SUPABASE_URL` | `str` | `""` | Supabase project API URL for pgvector and table storage. | `https://xyz.supabase.co` |
| `SUPABASE_KEY` | `str` | `""` | Supabase anon/public API key for client authentication. | `eyJhbGciOi...` |

### 2. AI & LLM Provider Services

| Variable | Type | Default | Description & Usage | Example |
|----------|------|---------|---------------------|---------|
| `GEMINI_API_KEY` | `str` | `""` | Google Gemini API key for multimodal/audio and LLM capabilities. | `AIzaSy...` |
| `GROQ_API_KEY` | `str` | `""` | Groq Cloud API key for ultra-low latency LLM inference. | `gsk_...` |
| `GROQ_API_KEY4` | `str` | `""` | Groq unified API key for multi-model access. | `sk-or-v1-...` |
| `LLM_PROVIDER` | `str` | `"groq"` | Selected LLM provider backend (`groq`, `groq`, `gemini`, `mock`). | `groq` |
| `LLM_MODEL` | `str` | `"meta-llama/llama-3.3-70b-instruct"` | Default model identifier for remote completion calls. | `meta-llama/llama-3.3-70b-instruct` |

### 3. Vector Embedding Engine

| Variable | Type | Default | Description & Usage | Example |
|----------|------|---------|---------------------|---------|
| `EMBED_PROVIDER` | `str` | `"mock"` | Vector embedding generator provider (`mock`, `sentence_transformers`, `openai`, `groq`, `groq`). | `mock` |
| `EMBED_DIM` | `int` | `384` | Vector dimension size for candidate resume and job description embeddings. | `384` |

### 4. WebRTC Client Infrastructure

| Variable | Type | Default | Description & Usage | Example |
|----------|------|---------|---------------------|---------|
| `WEBRTC_API_BASE` | `str` | `"http://localhost:18056"` | Base HTTP URL for the WebRTC headless bot container service. | `http://localhost:18056` |
| `WEBRTC_API_KEY` | `str` | `""` | API key/token for authenticating with the WebRTC client service. | `vxa_bot_...` |

### 5. Integrations & Service Providers

| Variable | Type | Default | Description & Usage | Example |
|----------|------|---------|---------------------|---------|
| `EMAIL_PROVIDER` | `str` | `"mock"` | Email service dispatch engine (`mock`, `smtp`). | `smtp` |
| `CALENDAR_PROVIDER` | `str` | `"mock"` | Google Calendar integration mode (`mock`, `google`). | `google` |
| `GOOGLE_TOKEN_PATH` | `str` | `"token.json"` | Relative path to local Google OAuth credentials file. | `token.json` |
| `FROM_ADDRESS` | `str` | `"noreply@talentops.ai"` | Default sender email address for automated communications. | `noreply@talentops.ai` |

### 6. Outbound SMTP Email Service

| Variable | Type | Default | Description & Usage | Example |
|----------|------|---------|---------------------|---------|
| `SMTP_SERVER` | `str` | `""` | Outbound SMTP host server address. | `smtp.gmail.com` |
| `SMTP_PORT` | `int` | `587` | Outbound SMTP server connection port. | `587` |
| `SMTP_USERNAME` | `str` | `""` | Authentication username/email for SMTP server. | `user@example.com` |
| `SMTP_PASSWORD` | `str` | `""` | Authentication password or App Password for SMTP server. | `secret-app-password` |
| `SMTP_FROM_EMAIL` | `str` | `""` | Specific sender email address used in SMTP message envelopes. | `notifications@example.com` |
| `SMTP_USE_TLS` | `bool` | `True` | Enable STARTTLS encryption for SMTP connections. | `true` |

### 7. Security & CORS Configuration

| Variable | Type | Default | Description & Usage | Example |
|----------|------|---------|---------------------|---------|
| `CORS_ORIGINS` | `str` | `"http://localhost:5173"` | Comma-separated list of allowed origins for cross-origin browser requests. | `http://localhost:5173,https://app.talentops.ai` |

### 8. Agent Evaluation, Telemetry & Guardrails

| Variable | Type | Default | Description & Usage | Example |
|----------|------|---------|---------------------|---------|
| `CONFIDENCE_THRESHOLD` | `float` | `0.6` | Minimum confidence score ($0.0 - 1.0$) required for automated decision validation. | `0.6` |
| `TELEMETRY_MAX_RTT_MS` | `float` | `400.0` | Maximum acceptable round-trip audio latency limit in milliseconds. | `400.0` |
| `TELEMETRY_MAX_JITTER_MS` | `float` | `100.0` | Maximum acceptable network audio jitter limit in milliseconds. | `100.0` |
| `K_ANONYMITY` | `int` | `5` | Minimum demographic cohort size ($k \ge 5$) required for fairness reporting. | `5` |
| `SANDBOX_MAX_SEC` | `int` | `120` | Maximum allowed duration in seconds for sandbox execution calibrations. | `120` |

### 9. Logging, Environment & Offline Controls

| Variable | Type | Default | Description & Usage | Example |
|----------|------|---------|---------------------|---------|
| `LOG_LEVEL` | `str` | `"INFO"` | System logging verbosity level (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`). | `INFO` |
| `IS_PRODUCTION` | `bool` | `False` | Toggle flag for enabling production operational mode. | `true` |
| `OFFLINE_MODE` | `str` | `"false"` | Run application without external network API calls (uses mocks for testing). | `true` |

---

## Computed Properties & Helper Methods

The `Settings` class in [`app/config.py`](file:///Users/apple/TalentOops/app/config.py) exposes convenient computed properties:

```python
# Check if Supabase credentials are configured
if settings.supabase_configured:
    # Initialize Supabase client
    ...

# Get parsed list of allowed CORS origin strings
origins: list[str] = settings.cors_origins_list
# Returns: ["http://localhost:5173", "https://app.talentops.ai"]

# Check if application is running in offline testing mode
if settings.is_offline_mode:
    # Use deterministic mock responses
    ...
```

---

## Environment Setup & Deployment Scenarios

### 1. Local Development (Default)

Copy `.env.example` to `.env` and fill in your development keys:

```bash
cp .env.example .env
```

Minimal `.env` file for local development:
```env
SUPABASE_URL="https://your-project.supabase.co"
SUPABASE_KEY="your-anon-key"
GROQ_API_KEY4="sk-or-v1-your-key"
WEBRTC_API_BASE="http://localhost:18056"
CORS_ORIGINS="http://localhost:5173"
```

### 2. Offline / Unit Testing Mode

To run tests or run locally without making paid external API calls:

```env
OFFLINE_MODE=true
EMBED_PROVIDER=mock
LLM_PROVIDER=mock
EMAIL_PROVIDER=mock
CALENDAR_PROVIDER=mock
```

### 3. Production Deployment

In production environments (e.g. Docker, Kubernetes, Render, AWS ECS):

```env
IS_PRODUCTION=true
LOG_LEVEL=INFO
CORS_ORIGINS="https://talentops.example.com,https://dashboard.example.com"
LLM_PROVIDER=groq
LLM_MODEL=meta-llama/llama-3.3-70b-instruct
EMAIL_PROVIDER=smtp
SMTP_SERVER="smtp.sendgrid.net"
SMTP_PORT=587
SMTP_USERNAME="apikey"
SMTP_PASSWORD="your-sendgrid-api-key"
SMTP_FROM_EMAIL="notifications@talentops.example.com"
```

---

## Security Best Practices

1. **Never Commit `.env` Files**: `.env` and `token.json` are listed in `.gitignore` to prevent credential leaks.
2. **Use Environment Variables in CI/CD**: Provide secrets securely via deployment platform secret stores (e.g., GitHub Secrets, AWS Secrets Manager).
3. **Least Privilege API Keys**: Use restricted/scoped API keys for third-party services in production.
4. **CORS Hardening**: Never set `CORS_ORIGINS="*"` in production. Always specify exact allowed domain origins.
5. **K-Anonymity & Privacy**: Maintain `K_ANONYMITY >= 5` to ensure candidate cohort metrics remain anonymized and compliant with privacy standards.

---

## Configuration Verification & Testing

### Programmatic Check

Verify current settings via Python CLI:

```bash
python -c "from app.config import settings; print('CORS Origins:', settings.cors_origins_list); print('Offline Mode:', settings.is_offline_mode)"
```

### Run Configuration Test Suite

*(Note: Automated configuration tests are not yet implemented. Please verify configuration manually.)*