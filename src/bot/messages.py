from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def _fmt_duration(secs: int | None) -> str:
    if secs is None:
        return "?"
    m, s = divmod(secs, 60)
    return f"{m}m{s:02d}s"


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
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M {label}"
    if n >= 1000:
        return f"{n / 1000:.1f}k {label}"
    return f"{n} {label}"


def video_card_text(v: dict, index: int, total: int) -> str:
    source = v.get("source", "")
    star = v.get("hook_score", "?")
    lines = [
        f"🎯 *Gancho {index}/{total}* — {source}",
        "",
        f"*{v.get('title', 'sem título')}*",
        "",
        f"⏱ {_fmt_duration(v.get('duration'))}  |  "
        f"👍 {_fmt_score(v.get('score'), source)}  |  "
        f"📅 há {_fmt_age(v.get('age_hours'))}  |  ★{star}",
    ]
    angle = v.get("angle", "")
    if angle:
        lines += ["", f"💡 _{angle}_"]
    return "\n".join(lines)


def video_keyboard(url: str, idx: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⬇️ Baixar", callback_data=f"baixar:{idx}"),
            InlineKeyboardButton("⏭ Pular", callback_data=f"pular:{idx}"),
        ],
        [
            InlineKeyboardButton("🔗 Ver relacionados", callback_data=f"relacionados:{idx}"),
            InlineKeyboardButton("🔎 Abrir", url=url),
        ],
    ])
