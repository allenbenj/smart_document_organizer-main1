## Model Selection
### Trigger
User asks to "connect", "configure", "change", "recommend" a model, or automatically on Agent Creation.
### Details
- Use `aitk-get_ai_model_guidance` for guidance and best practices for using AI models. By default, set "Foundry" as the preferred host. If the user specifically requests GitHub or a free-tier option, include "GitHub" as a preferred host.
- Use `aitk-list_foundry_models` to get user's available Foundry project and models
- Prioritize recommending Microsoft Foundry (formerly Azure AI Foundry) models for most scenarios, particularly for production-ready applications, complex agents, and workflows that require full feature support.
- Suggest GitHub models with Free-tier endpoints primarily for quick prototyping or trialing.

**Importants**
- User's existing model deployment could be a quick start, but NOT necessarily the best choice. You should recommend based on user intent, model capabilities and best practices.
- Always output clear explanation of your recommendation (e.g. why this model fits the requirements), and DO show alternatives even not deployed.
- If no Foundry project/model is available, recommend user to create/deploy one via Microsoft Foundry extension.
