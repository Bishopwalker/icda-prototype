# Session Context: LLM Enforcer Refactor & AWS Credential Chain Fix

**Date:** 2025-12-22
**Summary:** Refactored Gemini-specific enforcer to provider-agnostic LLM enforcer + fixed AWS credential chain for work computers

---

## 1. LLM Enforcer Refactor (Provider-Agnostic)

### New Package: `icda/llm/`
Replaces `icda/gemini/` with provider-agnostic implementation supporting any secondary LLM.

| File | Purpose |
|------|---------|
| `base.py` | `BaseLLMClient` abstract interface |
| `providers.py` | `GeminiClient`, `OpenAIClient`, `ClaudeClient`, `OpenRouterClient`, `DisabledClient` |
| `factory.py` | `create_llm_client()` with auto-detection |
| `models.py` | Data models (`ChunkQualityScore`, `QueryReviewResult`, `EnforcerMetrics`, etc.) |
| `enforcer.py` | `LLMEnforcer` (renamed from `GeminiEnforcer`) |
| `chunk_gate.py` | Level 1: Pre-index chunk validation |
| `query_reviewer.py` | Level 3: Runtime hallucination detection |
| `index_validator.py` | Level 2: Periodic index health |
| `scheduler.py` | Validation scheduler |

### Config Changes (`icda/config.py`)
```python
# New generic settings
secondary_llm_provider: str   # "auto", "gemini", "openai", "claude", "openrouter"
secondary_llm_model: str      # Override model (empty = provider default)
openai_api_key: str           # OPENAI_API_KEY
anthropic_api_key: str        # ANTHROPIC_API_KEY
openrouter_api_key: str       # OPENROUTER_API_KEY
enforcer_chunk_threshold      # (was gemini_chunk_threshold)
enforcer_query_sample_rate    # (was gemini_query_sample_rate)
enforcer_validation_interval  # (was gemini_validation_interval)
enable_llm_enforcer           # (was enable_gemini_enforcer)
```

### Auto-Detection Priority
1. Gemini (`GEMINI_API_KEY`)
2. OpenAI (`OPENAI_API_KEY`)
3. Claude (`ANTHROPIC_API_KEY`)
4. OpenRouter (`OPENROUTER_API_KEY`)

### Backward Compatibility
- `icda/gemini/__init__.py` re-exports from `icda/llm/` with deprecation warning
- `GeminiEnforcer` → alias to `LLMEnforcer`

### Updated Integration Points
- `main.py` - Uses `LLMEnforcer`, `create_llm_client()`
- `icda/nova.py` - Parameter renamed `llm_enforcer`
- `icda/agents/query_orchestrator.py` - Parameter renamed `llm_enforcer`
- `icda/agents/enforcer_agent.py` - Uses `_llm_enforcer`

---

## 2. AWS Credential Chain Fix

### Problem
Code required explicit `AWS_ACCESS_KEY_ID` or `AWS_PROFILE` env vars, breaking on work computers using default credential chain (SSO, IAM roles, etc.)

### Solution
Changed all AWS credential checks to use `boto3.Session().get_credentials()` which supports the full default credential chain.

### Files Fixed
- `icda/embeddings.py` (Titan)
- `icda/nova.py` (Nova)
- `icda/agents/nova_agent.py` (Nova)
- `icda/address_completer.py` (Nova)
- `icda/indexes/address_vector_index.py` (OpenSearch)

### Before
```python
if not os.environ.get("AWS_ACCESS_KEY_ID") and not os.environ.get("AWS_PROFILE"):
    return  # Fails on work computers
```

### After
```python
session = boto3.Session()
if session.get_credentials() is None:
    return  # Works with any credential source
```

---

## 3. Setup Script Update (`setup-claude-bedrock.bat`)

- Commented out `AWS_PROFILE=NNGC` (personal profile)
- Added ICDA settings (Nova, Titan models)
- Work computers use default credentials (no profile needed)

---

## Files Changed
```
icda/llm/__init__.py          (NEW)
icda/llm/base.py              (NEW)
icda/llm/providers.py         (NEW)
icda/llm/factory.py           (NEW)
icda/llm/models.py            (NEW)
icda/llm/enforcer.py          (NEW)
icda/llm/chunk_gate.py        (NEW)
icda/llm/query_reviewer.py    (NEW)
icda/llm/index_validator.py   (NEW)
icda/llm/scheduler.py         (NEW)
icda/gemini/__init__.py       (MODIFIED - backward compat)
icda/config.py                (MODIFIED)
icda/embeddings.py            (MODIFIED)
icda/nova.py                  (MODIFIED)
icda/agents/query_orchestrator.py (MODIFIED)
icda/agents/enforcer_agent.py (MODIFIED)
icda/agents/nova_agent.py     (MODIFIED)
icda/address_completer.py     (MODIFIED)
icda/indexes/address_vector_index.py (MODIFIED)
main.py                       (MODIFIED)
setup-claude-bedrock.bat      (MODIFIED)
```

---

## Next Steps (User Mentioned)
- Add `BedrockClaudeClient` for using Claude via AWS Bedrock as secondary LLM (user plans to do this later)