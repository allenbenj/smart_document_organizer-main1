## Microsoft Foundry Models (AI Toolkit fully supported)

Microsoft Foundry (formerly Azure AI Foundry) helps you build AI products using the latest models.
Following models are fully supported in AI Toolkit, including features like model catalog, deployment, playground, view code, build agents, evaluation, and more.

| **Name** | **DisplayName** | **Publisher** | **InputTypes** | **Input/Output Context** | **Cost** (per 1M Tokens) | **Quality** (quality index; higher is better) | **Throughput** (output tokens per second; higher is better) | **Latency** (time to first token in seconds; lower is better) | **Safety** (attack success rate; lower is better) | **LastUpdated** | **Notes** |
|--------|----------|---------------|---------------|--------------------------|---------------|---------------|---------------|---------------|---------------|----------------|--------------|
| gpt-5.2-chat | OpenAI gpt-5.2-chat (preview) | OpenAI | text, image | 200K / 100K | N/A | N/A | N/A | N/A | N/A | 2025-12 | Advanced, natural, multimodal, context-aware conversations for enterprise. |
| gpt-5.2 | OpenAI gpt-5.2 | OpenAI | text, image | 200K / 100K | N/A | N/A | N/A | N/A | N/A | 2025-12 | Engineered for enterprise agents: structured outputs, reliable tool use, governed integrations. |
| gpt-5.1-codex-max | gpt-5.1-codex-max | OpenAI | text, image | 272K / 128K | $3.4375 | 0.915806 | N/A | N/A | 0.69131% | 2025-12 | Agentic coding model for complex workflows with advanced efficiency. |
| claude-opus-4-5 | Claude Opus 4.5 | Anthropic | text, image, code | 200K / 64K | $10 | 0.927592 | 49.73 | 2.01 | 1.473963% | 2025-11 | Anthropic's most intelligent model. Leader in coding, agents, computer use, and enterprise workflows. |
| claude-sonnet-4-5 | Claude Sonnet 4.5 | Anthropic | text, image, code | 200K / 64K | $6 | 0.921449 | 42.61 | 2.69 | 2.190129% | 2025-11 | Anthropic's most capable model for complex agents, coding, and computer use. |
| gpt-5.1 | OpenAI gpt-5.1 | OpenAI | text, image | 200K / 100K | $3.4375 | 0.902956 | 75.76 | 0.66 | 0.3367% | 2025-11 | Logic-heavy, multi-step tasks. Greater consistency, adaptive reasoning, refined customization. |
| gpt-5.1-codex | gpt-5.1-codex | OpenAI | text, image | 272K / 128K | $3.4375 | 0.89866 | 32.84 | 0.25 | 0.333333% | 2025-11 | Advanced coding model: multimodal reasoning, context-aware reviews, repo-aware intelligence. |
| DeepSeek-V3.1 | DeepSeek-V3.1 | DeepSeek | text | 128K / 4K | $0.84 | 0.8548 | N/A | N/A | N/A | 2025-09 | Hybrid model that enhances tool usage, thinking efficiency, and supports both thinking and non-thinking modes via chat template switching. |
| claude-haiku-4-5 | Claude Haiku 4.5 | Anthropic | text, image | 200K / 64K | $2 | 0.840002 | 90.16 | 1.45 | 0.167333% | 2025-11 | Near-frontier performance. Fast, cost-effective for coding and scaled agents. |
| gpt-5-chat | OpenAI gpt-5-chat (preview) | OpenAI | text, image | 200K / 100K | $3.6875 | 0.8537 | 90.92 | 0.34 | N/A | 2025-08 | Advanced, natural, multimodal, context-aware conversations for enterprise apps. |
| claude-opus-4-1 | Claude Opus 4.1 | Anthropic | text, image, code | 200K / 32K | $30 | 0.901467 | 32.4 | 2.19 | 1.27738% | 2025-11 | Industry leader for coding. Sustained performance on long-running, complex tasks. |
| grok-4 | Grok 4 | xAI | text, image | 256K / 8K | $6.0 | 0.9117 | N/A | N/A | 57.8333% | 2025-09 | Latest reasoning model from xAI with advanced reasoning and tool-use capabilities, achieving new SOTA performance across challenging benchmarks. |
| gpt-5.1-chat | OpenAI gpt-5.1-chat (preview) | OpenAI | text, image | 200K / 100K | $3.4375 | 0.903285 | 75.98 | 0.65 | 0.3367% | 2025-11 | Advanced multimodal enterprise conversations. Enhanced emotional intelligence. |
| gpt-5.1-codex-mini | gpt-5.1-codex-mini | OpenAI | text, image | 272K / 128K | $0.6875 | 0.862573 | 43.12 | 0.67 | 0.333333% | 2025-11 | Lightweight gpt-5.1-codex for steerability, front-end dev, and interactivity. |
| grok-4-fast-reasoning | Grok 4 Fast Reasoning | xAI | text, image | 2M / 8K | $0.275 | 0.8856 | N/A | N/A | N/A | 2025-09 | Efficiency-focused LLM developed by xAI, pre-trained on general-purpose data and post-trained on task demonstrations and tool use, with built-in safety features. |
| gpt-5-pro | OpenAI gpt-5-pro | OpenAI | text, image | 400K / 2.72M | $41.25 | 0.9114 | 40.79 | 47.25 | 1e-7% | 2025-10 | Logic-heavy, multi-step tasks. Think harder, consistently better answers. |
| Llama-4-Maverick-17B-128E-Instruct-FP8 | Llama 4 Maverick 17B 128E Instruct FP8 | Meta | text, image | 1M / 4K | $0.615 | 0.79 | 48.53 | 0.11 | 15.3333% | 2025-04 | Great for precise image understanding & creative writing, high quality at lower price than Llama 3.3 70B. |
| gpt-5 | OpenAI gpt-5 | OpenAI | text, image | 200K / 100K | $3.6875 | 0.9058 | 68.86 | 26.86 | 4.1667% | 2025-08 | Designed for logic-heavy, multi-step tasks. |
| DeepSeek-V3-0324 | DeepSeek-V3-0324 | DeepSeek | text | 128K / 4K | $1.9975 | 0.7521 | 60.21 | 0.39 | N/A | 2025-04 | Notable improvements over DeepSeek-V3 in reasoning, function calling, and code generation. |
| gpt-4.1 | OpenAI GPT-4.1 | OpenAI | text, image | 1M / 33K | $3.5 | 0.844 | 95.2 | 0.37 | N/A | 2025-04 | Outperforms gpt-4o in coding, instruction following, and long-context understanding. |
| gpt-4.1-mini | OpenAI GPT-4.1-mini | OpenAI | text, image | 1M / 33K | $0.7 | 0.8066 | 125.04 | 0.29 | N/A | 2025-04 | Outperforms gpt-4o-mini in coding, instruction following, and long-context handling. |
| grok-4-fast-non-reasoning | Grok 4 Fast Non Reasoning | xAI | text, image | 2M / 8K | $0.275 | 0.7816 | N/A | N/A | N/A | 2025-09 | Efficiency-focused LLM developed by xAI, pre-trained on general-purpose data and post-trained on task demonstrations and tool use, with built-in safety features. |
| gpt-5-codex | gpt-5-codex | OpenAI | text, image | 272K / 128K | N/A | N/A | N/A | N/A | N/A | 2025-09 | Designed for steerability, front end development, and interactivity. |
| o3 | OpenAI o3 | OpenAI | text, image | 200K / 100K | $3.5 | 0.8991 | 62.12 | 3.45 | 2.8333% | 2025-04 | Improved quality & safety over o1 with similar or better performance. |
| gpt-5-nano | OpenAI gpt-5-nano | OpenAI | text, image | 200K / 100K | $0.1375 | 0.8262 | 223.53 | 8.16 | N/A | 2025-08 | Optimized for speed, ideal for low-latency applications. |
| gpt-5-mini | OpenAI gpt-5-mini | OpenAI | text, image | 200K / 100K | $0.6875 | 0.8914 | 126.82 | 6.7 | N/A | 2025-08 | Lightweight version for cost-sensitive applications. |
| DeepSeek-R1-0528 | DeepSeek-R1-0528 | DeepSeek | text | 128K / 4K | $2.3625 | 0.8748 | 42.54 | 1.12 | N/A | 2025-05 | Improved reasoning, reduced hallucination, better function calling & vibe coding. |
| grok-3 | Grok 3 | xAI | text | 131K / 4K | $6.0 | 0.8461 | 23.84 | 0.56 | N/A | 2025-05 | xAI's debut model, pretrained for specialized domains (finance, healthcare, law). |
| MAI-DS-R1 | MAI-DS-R1 | Microsoft | text | 128K / 4K | N/A | N/A | 92.35 | 0.32 | 32.0% | 2025-04 | Microsoft post-trained DeepSeek-R1 to fill info gaps, improve harm protection, keeping R1 reasoning. |
| o4-mini | OpenAI o4-mini | OpenAI | text, image | 200K / 100K | $1.925 | 0.8864 | 51.83 | 4 | 4.0% | 2025-04 | Improved quality & safety over o3-mini with similar or better performance. |
| gpt-4.1-nano | OpenAI GPT-4.1-nano | OpenAI | text, image | 1M / 33K | $0.175 | 0.6978 | 115.82 | 0.29 | N/A | 2025-04 | Gains in coding, instruction following, long-context handling with lower latency/cost. |
| grok-code-fast-1 | Grok Code Fast 1 | xAI | text | 256K / 8K | $0.525 | 0.8238 | N/A | N/A | N/A | 2025-09 | Fast, economical AI model for agentic coding, built from scratch with new architecture, trained on programming-rich data, and fine-tuned for real-world coding tasks. |
| o3-mini | OpenAI o3-mini | OpenAI | text | 200K / 100K | $1.925 | 0.8658 | 127.75 | 1.46 | 7.0% | 2025-01 | o1 features with significant cost-efficiencies for high-performance scenarios. |
| gpt-oss-120B | gpt-oss-120b | OpenAI | text | 131K / 131K | N/A | N/A | N/A | N/A | N/A | 2025-08 | Pushes open model frontier with GPT-OSS models under Apache 2.0 license for free use, modification, and deployment. |
| grok-3-mini | Grok 3 Mini | xAI | text | 131K / 4K | $0.505 | 0.872 | 147.54 | 0.33 | N/A | 2025-05 | Lightweight model for logic-based tasks, trained on math and science. |
| Llama-3.3-70B-Instruct | Llama-3.3-70B-Instruct | Meta | text | 128K / 4K | $0.71 | 0.6203 | 23.14 | 0.94 | N/A | 2025-06 | Enhanced reasoning, math, and instruction following, comparable to Llama 3.1 405B. |
| mistral-medium-2505 | Mistral Medium 3 (25.05) | Mistral AI | text, image | 128K / 4K | $0.8 | 0.7662 | 42.82 | 0.48 | 53.6667% | 2025-05 | Advanced LLM with SOTA reasoning, knowledge, coding, and vision. |
| codex-mini | codex-mini | OpenAI | text, image | 200K / 100K | N/A | N/A | N/A | N/A | N/A | 2025-06 | Fine-tuned o4-mini for rapid, instruction-following in CLI workflows. |
| gpt-4.5-preview | GPT-4.5 Preview | OpenAI | text, image | 131K / 16K | $93.75 | 0.7973 | N/A | N/A | N/A | 2025-02 | Largest, strongest general-purpose GPT model for diverse text/image tasks. |
| o3-pro | o3-pro | OpenAI | text, image | 200K / 100K | $35.0 | 0.9104 | 11.77 | 101.85 | N/A | 2025-06 | o3 series: RL-trained for complex reasoning. o1-pro: more compute for better answers. |
| Phi-4-reasoning | Phi-4-Reasoning | Microsoft | text | 33K / 4K | $0.2188 | 0.7579 | 28.89 | 0.3 | N/A | 2025-04 | State-of-the-art open-weight reasoning model. |
| Phi-4-mini-reasoning | Phi-4-mini-reasoning | Microsoft | text | 128K / 4K | $0.1312 | 0.691 | 28.88 | 0.83 | N/A | 2025-04 | Lightweight math reasoning model for multi-step problems. |
| Llama-4-Scout-17B-16E-Instruct | Llama 4 Scout 17B 16E Instruct | Meta | text, image | 10M / 4K | $0.345 | 0.713 | 30.46 | 0.11 | N/A | 2025-05 | Excels at multi-document summarization, parsing user activity, and reasoning over codebases. |
| cohere-command-a | Cohere Command A | Cohere | text | 131K / 4K | $4.375 | 0.7655 | 32.99 | 0.98 | 43.5% | 2025-06 | Highly efficient generative model for agentic and multilingual use cases. |
| DeepSeek-R1 | DeepSeek-R1 | DeepSeek | text | 128K / 4K | N/A | N/A | N/A | N/A | N/A | 2025-01 | Excels at reasoning (language, science, coding) via step-by-step training. |
| computer-use-preview | computer-use-preview | OpenAI | text, image | 131K / 16K | N/A | N/A | N/A | N/A | N/A | 2025-03 | Model for Computer Use Agent in Responses API to control a browser and act on a user's behalf. |
| Phi-4-mini-instruct | Phi-4-mini-instruct | Microsoft | text | 128K / 4K | $0.1312 | 0.4429 | 41.46 | 0.15 | N/A | 2025-02 | 3.8B param SLM outperforming larger models in reasoning, math, coding, and function-calling. |
| Phi-4-multimodal-instruct | Phi-4-multimodal-instruct | Microsoft | audio, image, text | 128K / 4K | N/A | 0.4301 | 21.52 | 1.45 | N/A | 2025-06 | First small multimodal model with 3 modality inputs (text, audio, image), excelling in quality and efficiency. |
| Phi-4 | Phi-4 | Microsoft | text | 16K / 16K | $0.2188 | 0.7193 | 37.94 | 0.27 | 2.0% | 2025-06 | Highly capable 14B model for low latency scenarios. |
| mistral-small-2503 | Mistral Small 3.1 | Mistral AI | text, image | 128K / 4K | $0.15 | 0.7004 | 113.29 | 1.83 | N/A | 2025-03 | Enhanced Mistral Small 3 with multimodal capabilities and 128k context. |
| o1 | OpenAI o1 | OpenAI | text, image | 200K / 100K | $26.25 | 0.8747 | 46.31 | 4.04 | 3.8333% | 2024-12 | For advanced reasoning and complex problems (math, science). Ideal for deep context and agentic workflows. |
| o1-mini | OpenAI o1-mini | OpenAI | text | 128K / 66K | $1.925 | 0.8172 | 105.88 | 1.34 | N/A | 2025-03 | Smaller, faster, 80% cheaper than o1-preview; excels at code generation and small context ops. |
| gpt-4o | OpenAI GPT-4o | OpenAI | text, image, audio | 131K / 16K | $4.375 | 0.749 | 64.67 | 1.39 | 10.6667% | 2024-12 | OpenAI's most advanced multimodal model in the gpt-4o family, handling text and image inputs. |
| gpt-4o-mini | OpenAI GPT-4o mini | OpenAI | text, image, audio | 131K / 4K | $0.2625 | 0.7193 | 73.83 | 0.89 | N/A | 2024-09 | Affordable, efficient AI for diverse text and image tasks. |
| o1-preview | OpenAI o1-preview | OpenAI | text | 128K / 33K | $26.25 | 0.7138 | 70.79 | 1.76 | N/A | 2024-09 | For advanced reasoning and complex problems (math, science). Ideal for deep context and agentic workflows. |
| tsuzumi-7b | tsuzumi-7b | NTT Data | text | N/A | N/A | N/A | N/A | N/A | N/A | 2024-11 | N/A |
| Ministral-3B | Ministral 3B | Mistral AI | text | 131K / 4K | $0.04 | 0.4503 | 98.05 | 0.8 | N/A | 2024-10 | SOTA SLM for edge/on-device apps. Low-latency, compute-efficient, ideal for standard GenAI apps. |
| gpt-4 | gpt-4 | OpenAI | text | 128K / 4K | $15.0 | 0.6556 | 34.35 | 1.04 | N/A | 2024-09 | N/A |
| Cohere-command-r-08-2024 | Cohere Command R 08-2024 | Cohere | text | 131K / 4K | N/A | N/A | N/A | N/A | N/A | 2024-10 | Scalable generative model targeting RAG and Tool Use to enable production-scale AI for enterprise. |
| Cohere-command-r-plus-08-2024 | Cohere Command R+ 08-2024 | Cohere | text | 131K / 4K | N/A | N/A | N/A | N/A | N/A | 2024-10 | SOTA RAG-optimized model for enterprise-grade workloads. |
| gpt-35-turbo | gpt-35-turbo | OpenAI | N/A | N/A | $0.75 | 0.4041 | 62.96 | 0.89 | N/A | 2024-09 | N/A |
| gpt-35-turbo-16k | gpt-35-turbo-16k | OpenAI | N/A | N/A | N/A | N/A | N/A | N/A | N/A | 2024-09 | N/A |
| gpt-35-turbo-instruct | gpt-35-turbo-instruct | OpenAI | N/A | N/A | N/A | N/A | N/A | N/A | N/A | 2024-09 | N/A |
| Codestral-2501 | Codestral 25.01 | Mistral AI | text | 256K / 4K | N/A | 0.4839 | N/A | N/A | N/A | 2025-01 | For code generation, supports 80+ languages, optimized for code completion and fill-in-the-middle. |
| gpt-4-32k | gpt-4-32k | OpenAI | N/A | N/A | $75.0 | 0.589 | 21.39 | 1.21 | N/A | 2024-09 | N/A |
| jais-30b-chat | JAIS 30b Chat | Core42 | text | 8K / 4K | N/A | N/A | N/A | N/A | N/A | 2025-02 | Auto-regressive bilingual LLM for Arabic & English with SOTA Arabic capabilities. |
| Llama-3.2-11B-Vision-Instruct | Llama-3.2-11B-Vision-Instruct | Meta | text, image, audio | 128K / 4K | $0.37 | 0.433 | 64.92 | 0.78 | N/A | 2025-07 | Excels in image reasoning on high-res images for visual understanding apps. |
| Llama-3.2-90B-Vision-Instruct | Llama-3.2-90B-Vision-Instruct | Meta | text, image, audio | 128K / 4K | N/A | N/A | N/A | N/A | N/A | 2025-05 | Advanced image reasoning for visual understanding agentic apps. |
| Meta-Llama-3.1-405B-Instruct | Meta-Llama-3.1-405B-Instruct | Meta | text | 131K / 4K | $7.9975 | 0.641 | 28.61 | 0.46 | N/A | 2024-07 | Llama 3.1 instruction-tuned text models for multilingual dialogue, outperforming many open/closed chat models. |
| Meta-Llama-3.1-8B-Instruct | Meta-Llama-3.1-8B-Instruct | Meta | text | 131K / 4K | $0.3775 | 0.3571 | 61.89 | 0.23 | N/A | 2025-03 | Llama 3.1 instruction-tuned text models for multilingual dialogue, outperforming many open/closed chat models. |
| Mistral-Large-2411 | Mistral Large 24.11 | Mistral AI | text | 128K / 4K | $3.0 | 0.7416 | 30.73 | 0.92 | N/A | 2024-12 | Enhanced system prompts, advanced reasoning, and function calling. |
| Mistral-Nemo | Mistral Nemo | Mistral AI | text | 131K / 4K | $0.15 | 0.407 | 63.86 | 0.82 | N/A | 2024-07 | SOTA reasoning, world knowledge, and coding in its size category. |
