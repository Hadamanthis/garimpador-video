import os
import sys
from pathlib import Path
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, ContextTypes
)
from telegram.constants import ParseMode

sys.path.insert(0, str(Path(__file__).parent.parent))

from db import init_db, upsert_video, mark_status, get_saved
from curator import curate
from downloader import download
from bot.messages import video_card_text, video_keyboard
from scrapers import reddit, youtube, twitter

# Sessão em memória: chat_id → lista de vídeos curados
_sessions: dict[int, list[dict]] = {}


def _allowed(update: Update) -> bool:
    allowed_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not allowed_id:
        return True
    return str(update.effective_chat.id) == allowed_id


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update):
        return
    await update.message.reply_text(
        "👋 Garimpador de vídeos ativo!\n\n"
        "/garimpar — buscar vídeos agora\n"
        "/salvos — ver vídeos salvos\n"
        "/ajuda — ver todos os comandos"
    )


async def cmd_ajuda(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update):
        return
    await update.message.reply_text(
        "📋 *Comandos disponíveis:*\n\n"
        "/garimpar — busca novos vídeos agora\n"
        "/salvos — lista vídeos marcados como salvos\n"
        "/ajuda — esta mensagem\n\n"
        "Nos cards de vídeo:\n"
        "⬇️ *Baixar* — baixa e envia o vídeo aqui\n"
        "⏭ *Pular* — descarta o vídeo\n"
        "🔗 *Ver relacionados* — busca vídeos do mesmo tema\n"
        "🔎 *Abrir* — abre o link original",
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_garimpar(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update):
        return
    chat_id = update.effective_chat.id
    config = ctx.bot_data["config"]

    msg = await update.message.reply_text("🔍 Garimpando vídeos...")

    raw = []
    raw += reddit.scrape(config)
    raw += youtube.scrape(config)
    raw += twitter.scrape(config)

    curated = curate(raw, config)

    if not curated:
        await msg.edit_text("😔 Nenhum vídeo novo encontrado. Tente novamente mais tarde.")
        return

    for v in curated:
        upsert_video(v)

    _sessions[chat_id] = curated
    await msg.edit_text(f"✅ {len(curated)} vídeos encontrados! Enviando cards...")

    for i, v in enumerate(curated, 1):
        text = video_card_text(v, i, len(curated))
        keyboard = video_keyboard(v["url"], i - 1)
        await update.message.reply_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
            disable_web_page_preview=False,
        )


async def cmd_salvos(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update):
        return
    videos = get_saved()
    if not videos:
        await update.message.reply_text("📭 Nenhum vídeo salvo ainda.")
        return

    await update.message.reply_text(f"📌 *{len(videos)} vídeos salvos:*", parse_mode=ParseMode.MARKDOWN)
    for i, v in enumerate(videos, 1):
        text = video_card_text(v, i, len(videos))
        keyboard = video_keyboard(v["url"], -(i))  # índice negativo = sessão de salvos
        await update.message.reply_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
            disable_web_page_preview=False,
        )


async def callback_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    chat_id = update.effective_chat.id
    data = query.data  # ex: "baixar:2", "pular:0", "relacionados:1"

    action, idx_str = data.split(":", 1)
    idx = int(idx_str)

    # índices negativos = lista de salvos
    if idx < 0:
        session = get_saved()
        video = session[(-idx) - 1] if 0 < (-idx) <= len(session) else None
    else:
        session = _sessions.get(chat_id, [])
        video = session[idx] if 0 <= idx < len(session) else None

    if video is None:
        await query.edit_message_text("⚠️ Sessão expirada. Use /garimpar novamente.")
        return

    if action == "pular":
        mark_status(video["url"], "visto")
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(f"⏭ Pulado: _{video['title'][:60]}_", parse_mode=ParseMode.MARKDOWN)

    elif action == "baixar":
        await query.edit_message_reply_markup(reply_markup=None)
        msg = await query.message.reply_text("⬇️ Baixando vídeo, aguarde...")
        path = download(video["url"])
        if path and path.exists():
            with open(path, "rb") as f:
                await ctx.bot.send_video(
                    chat_id=chat_id,
                    video=f,
                    caption=f"🎬 {video['title'][:200]}",
                    supports_streaming=True,
                )
            path.unlink(missing_ok=True)
            await msg.delete()
        else:
            await msg.edit_text(
                "❌ Não foi possível baixar o vídeo (muito grande ou formato não suportado).\n"
                f"🔗 Link direto: {video['url']}"
            )

    elif action == "relacionados":
        config = ctx.bot_data["config"]
        title_words = video.get("title", "").split()[:5]
        search_topic = " ".join(title_words)

        temp_config = dict(config)
        temp_config["topics"] = [search_topic]
        temp_config["output"] = {"top_n": 3}

        await query.message.reply_text(f"🔗 Buscando relacionados para: _{search_topic}_...", parse_mode=ParseMode.MARKDOWN)

        raw = reddit.scrape(temp_config) + youtube.scrape(temp_config)
        related = curate(raw, temp_config)

        if not related:
            await query.message.reply_text("😔 Nenhum relacionado encontrado.")
            return

        for i, v in enumerate(related, 1):
            text = video_card_text(v, i, len(related))
            keyboard = video_keyboard(v["url"], len(_sessions.get(chat_id, [])))
            _sessions.setdefault(chat_id, []).append(v)
            upsert_video(v)
            await query.message.reply_text(
                text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard,
                disable_web_page_preview=False,
            )


async def cmd_meuid(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text(
        f"Seu chat ID é: `{chat_id}`\n\nColoque esse valor no `.env`:\n`TELEGRAM_CHAT_ID={chat_id}`",
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_agenda(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update):
        return

    github_configured = all(
        os.environ.get(k) for k in ("GITHUB_TOKEN", "GITHUB_OWNER", "GITHUB_REPO")
    )
    if not github_configured:
        await update.message.reply_text(
            "⚠️ Configure `GITHUB_TOKEN`, `GITHUB_OWNER` e `GITHUB_REPO` no `.env` para usar este comando.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    from bot.github_actions import get_status, enable, disable, trigger, set_schedule

    args = ctx.args  # ex: ["ativar"] ou ["horario", "09:00"] ou ["rodar"]

    try:
        if not args:
            status = get_status()
            estado = "✅ Ativo" if status["state"] == "active" else "⏸ Pausado"
            await update.message.reply_text(
                f"📅 *Agenda do digest:*\n\n"
                f"Estado: {estado}\n"
                f"Horário: {status['horario_brt']} BRT\n\n"
                f"Comandos:\n"
                f"/agenda ativar\n"
                f"/agenda pausar\n"
                f"/agenda horario 08:00\n"
                f"/agenda rodar",
                parse_mode=ParseMode.MARKDOWN,
            )

        elif args[0] == "ativar":
            enable()
            await update.message.reply_text("✅ Digest diário *ativado*.", parse_mode=ParseMode.MARKDOWN)

        elif args[0] == "pausar":
            disable()
            await update.message.reply_text("⏸ Digest diário *pausado*.", parse_mode=ParseMode.MARKDOWN)

        elif args[0] == "rodar":
            trigger()
            await update.message.reply_text("🚀 Digest disparado! Chegará em alguns minutos.", parse_mode=ParseMode.MARKDOWN)

        elif args[0] == "horario" and len(args) > 1:
            time_str = args[1]  # ex: "08:00"
            parts = time_str.split(":")
            hour, minute = int(parts[0]), int(parts[1]) if len(parts) > 1 else 0
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                raise ValueError("Horário inválido")
            set_schedule(hour, minute)
            await update.message.reply_text(
                f"🕐 Horário atualizado para *{hour:02d}:{minute:02d} BRT*.\n"
                f"O GitHub aplicará na próxima execução.",
                parse_mode=ParseMode.MARKDOWN,
            )

        else:
            await update.message.reply_text(
                "Uso: /agenda  |  /agenda ativar  |  /agenda pausar  |  /agenda rodar  |  /agenda horario 08:00"
            )

    except Exception as e:
        await update.message.reply_text(f"❌ Erro ao comunicar com GitHub: {e}")


def build_app(config: dict) -> Application:
    init_db()
    token = os.environ["TELEGRAM_TOKEN"]
    app = Application.builder().token(token).build()
    app.bot_data["config"] = config

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("ajuda", cmd_ajuda))
    app.add_handler(CommandHandler("garimpar", cmd_garimpar))
    app.add_handler(CommandHandler("salvos", cmd_salvos))
    app.add_handler(CommandHandler("meuid", cmd_meuid))
    app.add_handler(CommandHandler("agenda", cmd_agenda))
    app.add_handler(CallbackQueryHandler(callback_handler))

    return app
