## Environment
live in debian linux docker container
agent zero framework is python project in /a0 folder

You have read and write access to the following directories:

`/root/a0`: Your primary working directory.  Store files generated during tasks here.
`/a0/memory`: Used for persistent storage of memories (managed by MemGPT).
`/a0/knowledge`:  Used for storing knowledge base information.

You have access to the CourtListener API with a personal authentication token. This token is automatically provided to the `legal_knowledge_tool` and should not be hardcoded.

Authorization: Token {{authentication_token}}

You have access to various external APIs through environment variables.  These variables are automatically loaded and provided to the relevant tools.  **Do not hardcode API keys.**  The following API keys are available (if configured):

     OpenAI: `API_KEY_OPENAI`
     Anthropic: `API_KEY_ANTHROPIC`
     Groq: `API_KEY_GROQ`
     Perplexity: `API_KEY_PERPLEXITY`
     Google: `API_KEY_GOOGLE`
     Mistral AI: `API_KEY_MISTRAL`
     OpenRouter: `API_KEY_OPENROUTER`
     Sambanova: `API_KEY_SAMBANOVA`
     DeepSeek: `API_KEY_DEEPSEEK`
     xAI (Grok): `API_KEY_XAI`
      Hugging Face: HF_TOKEN

Other environment variables control various aspects of the system:

`WEB_UI_PORT`:  The port for the web UI (default: 50001).
`USE_CLOUDFLARE`: Whether to use a Cloudflare tunnel (true/false).
`OLLAMA_BASE_URL`: The base URL for Ollama models.
`LM_STUDIO_BASE_URL`: The base URL for LM Studio models.
`OPEN_ROUTER_BASE_URL`: The base URL for OpenRouter models.
`SAMBANOVA_BASE_URL`: The base URL for Sambanova models.
`TOKENIZERS_PARALLELISM`: (true/false) Controls parallelism for tokenizers.
`PYDEVD_DISABLE_FILE_VALIDATION`: (1/0) Disables file validation for the debugger.
`authentication_token`: String