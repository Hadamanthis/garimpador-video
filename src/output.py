import json
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich import box

from db import mark_status

console = Console()
DATA_DIR = Path(__file__).parent.parent / "data"


def _fmt_duration(secs: int | None) -> str:
    if secs is None:
        return "?"
    m, s = divmod(secs, 60)
    return f"{m}m {s:02d}s"


def _fmt_age(hours: float | None) -> str:
    if hours is None:
        return "?"
    if hours < 1:
        return f"{int(hours * 60)}min"
    if hours < 24:
        return f"{hours:.0f}h"
    return f"{hours / 24:.1f}d"


def _fmt_score(n: int | None, source: str) -> str:
    if n is None:
        return "?"
    label = "views" if "youtube" in source else "pts"
    if n >= 1000:
        return f"{n / 1000:.1f}k {label}"
    return f"{n} {label}"


def display(videos: list[dict]):
    if not videos:
        console.print("\n[yellow]Nenhum vídeo novo encontrado.[/yellow]")
        return

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    console.print(f"\n[bold cyan]🎯 Top {len(videos)} Ganchos — {now}[/bold cyan]\n")

    for i, v in enumerate(videos, 1):
        star = v.get("hook_score", "?")
        source = v.get("source", "")
        console.print(
            f"[bold]#{i}[/bold]  \[{source}] [yellow]★{star}[/yellow]  "
            f"[bold white]{v.get('title', 'sem título')}[/bold white]"
        )
        console.print(
            f"    ⏱ {_fmt_duration(v.get('duration'))}  |  "
            f"👍 {_fmt_score(v.get('score'), source)}  |  "
            f"📅 há {_fmt_age(v.get('age_hours'))}"
        )
        if v.get("angle"):
            console.print(f"    [green]💡 {v['angle']}[/green]")
        console.print(f"    [blue]{v.get('url', '')}[/blue]")
        console.print()

    _interactive(videos)


def _interactive(videos: list[dict]):
    console.print("[dim]Comandos: s <n> salvar  |  v <n> visto  |  q sair[/dim]")
    console.print("[dim]Exemplo:  s 1  → salva o vídeo #1  |  v 3  → marca #3 como visto[/dim]\n")

    while True:
        try:
            cmd = console.input("[bold]> [/bold]").strip().lower()
        except (EOFError, KeyboardInterrupt):
            break

        if cmd in ("q", "quit", "sair", ""):
            break

        parts = cmd.split()
        if len(parts) == 2 and parts[0] in ("s", "v") and parts[1].isdigit():
            idx = int(parts[1]) - 1
            if 0 <= idx < len(videos):
                status = "salvo" if parts[0] == "s" else "visto"
                mark_status(videos[idx]["url"], status)
                label = "Salvo ✅" if status == "salvo" else "Marcado como visto"
                console.print(f"[green]{label}: {videos[idx]['title'][:60]}[/green]")
            else:
                console.print(f"[red]Número inválido. Use 1–{len(videos)}[/red]")
        else:
            console.print("[dim]Comandos válidos: s <n>  |  v <n>  |  q[/dim]")


def save_json(videos: list[dict]):
    DATA_DIR.mkdir(exist_ok=True)
    path = DATA_DIR / "last_run.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(videos, f, ensure_ascii=False, indent=2)
    console.print(f"[dim]💾 Salvo em {path}[/dim]")
