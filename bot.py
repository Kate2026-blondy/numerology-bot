async def main_async():
    """Асинхронная версия main для Python 3.14"""
    logger.info("🚀 Запуск бота (async)...")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("menu", menu_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    app.add_handler(CallbackQueryHandler(handle_callback))
    logger.info("✅ Бот успешно запущен!")
    await app.run_polling(allowed_updates=Update.ALL_TYPES)

def main():
    """Синхронная обёртка"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main_async())