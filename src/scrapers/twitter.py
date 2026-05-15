"""
Twitter/X scraper — desabilitado por padrão.

snscrape não é mais mantido e está bloqueado pela API do X.
Alternativas futuras:
  - Nitter RSS feeds (instâncias públicas, instáveis)
  - API oficial do X (Basic tier: US$100/mês)

Para habilitar, defina sources.twitter.enabled: true no config.yaml
e implemente um dos métodos acima aqui.
"""


def scrape(config: dict) -> list[dict]:
    cfg = config.get("sources", {}).get("twitter", {})
    if not cfg.get("enabled", False):
        return []

    print("[twitter] scraper não implementado. Desabilite no config.yaml ou implemente uma fonte.")
    return []
