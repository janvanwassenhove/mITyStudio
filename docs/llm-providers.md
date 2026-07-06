# LLM providers

The chat panel plans song changes through an `LlmProvider`. Every provider
returns the same JSON operation format; the backend validates every operation
against the asset registry before applying — no provider can invent assets or
touch files/audio directly.

## Available providers

| Provider | Models | Key | Notes |
|---|---|---|---|
| `mock` | — | none | deterministic keyword planner; default, always works |
| `anthropic` | Claude (e.g. `claude-sonnet-5`) | Settings or `ANTHROPIC_API_KEY` | official `anthropic` SDK |
| `openai` | GPT (e.g. `gpt-5.2`) | Settings or `OPENAI_API_KEY` | official `openai` SDK |
| `custom` | anything | Settings or `MITY_LLM_API_KEY`; optional for local servers | **any OpenAI-compatible endpoint** via base URL |

### Custom / bring-your-own-provider examples

Set provider to *Custom*, then:

| Service | Base URL | Model example |
|---|---|---|
| OpenRouter | `https://openrouter.ai/api/v1` | `anthropic/claude-sonnet-5` |
| Groq | `https://api.groq.com/openai/v1` | `llama-3.3-70b-versatile` |
| Mistral | `https://api.mistral.ai/v1` | `mistral-large-latest` |
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` |
| Ollama (local) | `http://localhost:11434/v1` | `llama3.1` (no key needed) |
| LM Studio (local) | `http://localhost:1234/v1` | as configured (no key needed) |

The custom provider sends `response_format: json_object` when the server
supports it and falls back gracefully when it doesn't.

## Key storage

- Keys are stored **per provider** in `local_settings.json` at the workspace
  root (git-ignored). Switching providers keeps other keys intact; saving an
  empty key clears that provider's stored key.
- Environment variables work as fallback: `ANTHROPIC_API_KEY`,
  `OPENAI_API_KEY`, `MITY_LLM_API_KEY`.
- The API never returns keys — `GET /api/settings/llm` only reports
  `api_keys_set: {anthropic: bool, openai: bool, custom: bool}`.

## Endpoints

- `GET /api/settings/llm` — settings + provider list + key status
- `PUT /api/settings/llm` — save settings; `api_key` field is write-only
- `POST /api/settings/llm/test` — live connection test for the active provider

## Guarantees (tested)

- Providers returning invented asset ids get those operations rejected;
  valid operations in the same batch still apply.
- Unknown operation types are rejected at validation.
- Missing keys / missing base URL fail with a clear message, never a crash.
- The mock provider keeps the whole studio functional with zero configuration.
