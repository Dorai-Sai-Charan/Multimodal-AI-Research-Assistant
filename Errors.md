# Fixed Errors Log

This document tracks significant errors encountered during development and how they were resolved.

---

## 1. Model Settings: 400 Bad Request on Reasoning Models

### Issue
When selecting **Qwen3 32B** or **Groq Compound Mini** from the model settings panel, any query (Chat, Compare, etc.) failed with a `400 Bad Request` error from the Groq API.

**Error Messages:**
- *Qwen3*: `Error code: 400 - {'error': {'message': 'reasoning_effort is not supported with this model'}}`
- *Groq Compound Mini*: `Error code: 400 - {'error': {'message': 'reasoning_effort is not supported with this model'}}`

### Why it occurred
The backend was configured to send the `reasoning_effort` parameter (defaulting to `medium`) to these models because they were listed in the `REASONING_MODELS` whitelist. However:
1.  **Qwen3 32B** on Groq does not support the `reasoning_effort` parameter at all.
2.  **Groq Compound Mini** likewise reports that the parameter is not supported via the API.

### How it was resolved
The issue was resolved by implementing a **Model-Specific Parameter Mapping** in the backend (`src/generation/llm_client.py`). 

To maintain a consistent UI state across all reasoning models while respecting API constraints, the following logic was applied:

1.  **For Qwen & Groq Mini Models**: The `reasoning_effort` parameter is now automatically **omitted** before the request is sent to Groq, as the API reports it is not supported for these specific model IDs.
2.  **For GPT-OSS Models**: The parameter is passed through normally (low/medium/high).

This hybrid approach allows these models to remain in the "Reasoning Models" category in the frontend (reflecting their true capabilities) while guaranteeing that the underlying API calls never fail due to invalid parameter configurations.
