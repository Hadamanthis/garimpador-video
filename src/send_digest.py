"""
Script standalone para o digest do GitHub Actions.
Roda scraper + curator e envia cards direto na API do Telegram (sem bot polling).
"""
import sys
import os
from pathlib import Path

import yaml
import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).parent))

from db import init_db, upsert_video
from curator import curate
from scrapers import reddit, youtube, twitter


def tg_send(token: str, chat_id: str, text: str):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    resp = requests.post(url, json={
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": False,
    }, timeout=10)
    if not resp.ok:
        print(f"[telegram] ERRO ao enviar mensagem: {resp.status_code} {resp.text}")


def fmt_card(v: dict, i: int, total: int) -> str:
    source = v.get("source", "")
    dur = v.get("duration")
    dur_str = f"{dur // 60}m{dur % 60:02d}s" if dur else "?"
    score = v.get("score", 0)
    score_str = f"{score / 1000:.1f}k" if score >= 1000 else str(score)
    label = "views" if "youtube" in source else "pts"
    age = v.get("age_hours")
    age_str = f"{age:.0f}h" if age and age < 24 else (f"{age / 24:.1f}d" if age else "?")
    star = v.get("hook_score", "?")

    lines = [
        f"🎯 *Gancho {i}/{total}* — {source}",
        "",
        f"*{v.get('title', '')}*",
        "",
        f"⏱ {dur_str}  |  👍 {score_str} {label}  |  📅 há {age_str}  |  ★{star}",
    ]
    if v.get("angle"):
        lines += ["", f"💡 _{v['angle']}_"]
    lines += ["", f"🔗 {v.get('url', '')}"]
    return "\n".join(lines)


def main():
    required = ["TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID", "GROQ_API_KEY"]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        print(f"ERRO: variáveis não encontradas no ambiente: {', '.join(missing)}")
        print("Valores recebidos:")
        for k in required:
            val = os.environ.get(k, "")
            print(f"  {k} = {'(vazio)' if not val else '(ok, ' + str(len(val)) + ' chars)'}")
        sys.exit(1)

    init_db()
    config_path = Path(__file__).parent.parent / "config.yaml"
    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    token = os.environ["TELEGRAM_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]

    print("[digest] Buscando vídeos...")
    raw = reddit.scrape(config) + youtube.scrape(config) + twitter.scrape(config)
    print(f"[digest] {len(raw)} vídeos brutos encontrados.")

    curated = curate(raw, config)
    if not curated:
        tg_send(token, chat_id, "😔 *Digest diário*: nenhum vídeo novo encontrado hoje.")
        return

    for v in curated:
        upsert_video(v)

    tg_send(token, chat_id, f"📬 *Digest diário — {len(curated)} ganchos novos*\nUse /garimpar no bot para ver com botões de download.")

    for i, v in enumerate(curated, 1):
        tg_send(token, chat_id, fmt_card(v, i, len(curated)))
        print(f"[digest] enviado {i}/{len(curated)}: {v.get('title', '')[:50]}")

    print("[digest] Concluído.")


if __name__ == "__main__":
    main()
