import json
import re
import os
from groq import Groq
from openai import OpenAI

from db import is_seen

# Títulos com esses termos são provavelmente vídeos de reação/opinião de outros criadores
REACTION_KEYWORDS = [
    "react", "reacts", "reacting", "reaction",
    "reação", "reagindo", "minha opinião", "my opinion",
    "i tried", "eu testei", "review", "análise",
    "ranking", "tier list", "watch me", "i asked",
    "copilot vs", "chatgpt vs", "gemini vs",
    "commentary", "breakdown", "explained by",
    "responds to", "responds", "debunking",
]

PROMPT = """\
Você é curador de conteúdo para um criador de vídeos de comentário sobre IA no cotidiano (YouTube Shorts, PT-BR).
Seu objetivo é encontrar vídeos ORIGINAIS e PRIMÁRIOS para comentar em cima — não vídeos que já são reações ou comentários de outra pessoa.

Critérios para ALTA pontuação (7-10):
- Demonstração ao vivo de uma ferramenta de IA fazendo algo surpreendente
- Notícia, anúncio ou evento real sobre IA (ex: empresa lança produto, resultado de pesquisa)
- Vídeo institucional ou corporativo sobre IA (sem edição de criador por cima)
- Clipe curto e factual que gera opinião forte

Critérios para BAIXA pontuação (1-4):
- Vídeo que já é uma reação ou comentário de outro criador
- Review/análise opinativa feita por um youtuber
- Compilação editada com narração de terceiro
- Tier list, ranking, "eu testei", "minha opinião"

Título: {title}
Descrição: {description}
Fonte: {source}

Responda SOMENTE com JSON, sem markdown, sem texto antes ou depois. Mantenha reason e angle curtos (max 80 caracteres cada):
{{"hook_score": 7, "reason": "texto curto", "angle": "texto curto"}}
"""


def _ai_client(config: dict):
    provider = config.get("ai", {}).get("provider", "groq")
    if provider == "ollama":
        base_url = config["ai"].get("ollama_base_url", "http://localhost:11434/v1")
        return "ollama", OpenAI(base_url=base_url, api_key="ollama")
    else:
        return "groq", Groq(api_key=os.environ["GROQ_API_KEY"])


def _extract_json(text: str) -> dict:
    # tenta parse direto
    try:
        return json.loads(text)
    except Exception:
        pass
    # tenta encontrar o bloco JSON dentro do texto
    match = re.search(r'\{[^{}]*"hook_score"[^{}]*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except Exception:
            pass
    return {}


def _score_video(video: dict, model: str, client, use_json_mode: bool = False) -> dict:
    prompt = PROMPT.format(
        title=video.get("title", "")[:120],
        description=video.get("description", "")[:300],
        source=video.get("source", ""),
    )
    kwargs = dict(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=300,
    )
    if use_json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    try:
        resp = client.chat.completions.create(**kwargs)
        raw = resp.choices[0].message.content.strip()
        data = _extract_json(raw)
        video["hook_score"] = int(data.get("hook_score", 5))
        video["reason"] = data.get("reason", "")
        video["angle"] = data.get("angle", "")
    except Exception as e:
        print(f"[curator] IA falhou para '{video.get('title', '')[:40]}': {e}")
        video["hook_score"] = 5
        video["reason"] = ""
        video["angle"] = ""
    return video


def _is_likely_reaction(title: str) -> bool:
    low = title.lower()
    return any(kw in low for kw in REACTION_KEYWORDS)


def curate(raw_videos: list[dict], config: dict) -> list[dict]:
    filters = config.get("filters", {})
    min_dur = filters.get("min_duration_seconds", 15)
    max_dur = filters.get("max_duration_seconds", 300)

    filtered = []
    skipped_reaction = 0
    for v in raw_videos:
        dur = v.get("duration")
        if dur is not None and (dur < min_dur or dur > max_dur):
            continue
        if is_seen(v["url"]):
            continue
        if _is_likely_reaction(v.get("title", "")):
            skipped_reaction += 1
            continue
        filtered.append(v)

    if skipped_reaction:
        print(f"[curator] {skipped_reaction} vídeos descartados por parecerem reação/review.")

    if not filtered:
        return []

    provider, client = _ai_client(config)
    model = config.get("ai", {}).get("model", "llama-3.1-8b-instant")
    use_json_mode = provider == "groq"
    print(f"[curator] avaliando {len(filtered)} vídeos com {provider}/{model}...")

    scored = [_score_video(v, model, client, use_json_mode) for v in filtered]
    scored.sort(key=lambda v: v.get("hook_score", 0), reverse=True)

    top_n = config.get("output", {}).get("top_n", 10)
    return scored[:top_n]
