import sys
import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).parent))

from db import init_db, upsert_video, get_saved
from curator import curate
from output import display, save_json
from scrapers import reddit, youtube, twitter


def load_config() -> dict:
    config_path = Path(__file__).parent.parent / "config.yaml"
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def garimpar(config: dict):
    print("[garimpador] Buscando vídeos...")

    raw: list[dict] = []
    raw += reddit.scrape(config)
    raw += youtube.scrape(config)
    raw += twitter.scrape(config)

    print(f"[garimpador] {len(raw)} vídeos encontrados antes da curadoria.")

    curated = curate(raw, config)

    for v in curated:
        upsert_video(v)

    if config.get("output", {}).get("save_json", True):
        save_json(curated)

    display(curated)


def show_saved():
    videos = get_saved()
    if not videos:
        print("Nenhum vídeo salvo ainda.")
        return
    print(f"\n📌 {len(videos)} vídeos salvos:\n")
    for i, v in enumerate(videos, 1):
        print(f"#{i} ★{v.get('hook_score','?')} [{v['source']}] {v['title']}")
        if v.get("angle"):
            print(f"   💡 {v['angle']}")
        print(f"   {v['url']}\n")


def print_help():
    print("""
Uso: python src/main.py [comando]

Comandos:
  (sem argumento)   Roda o garimpador no terminal
  bot               Inicia o bot do Telegram (fica rodando)
  salvos            Lista vídeos marcados como salvos
  help              Mostra esta mensagem
""")


def run_bot(config: dict):
    from bot.handlers import build_app
    print("[bot] Iniciando bot do Telegram... (Ctrl+C para parar)")
    app = build_app(config)
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    init_db()
    config = load_config()

    cmd = sys.argv[1] if len(sys.argv) > 1 else ""

    if cmd in ("", "garimpar"):
        garimpar(config)
    elif cmd == "bot":
        run_bot(config)
    elif cmd == "salvos":
        show_saved()
    elif cmd in ("help", "--help", "-h"):
        print_help()
    else:
        print(f"Comando desconhecido: {cmd}")
        print_help()
        sys.exit(1)
