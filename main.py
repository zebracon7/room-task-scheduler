from langchain_community.chat_models.gigachat import GigaChat
from langchain.prompts import ChatPromptTemplate
import config
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Определение состояний для ConversationHandler
ROOM_DESCRIPTION, TASK = 0, 1

def generate_plan(room_description: str, task:str) -> str:
    """
    Генерирует план действий на основе описания комнаты и задания

    Args:
        room_description (str): Описание комнаты.
        task (str): Задание, которое необходимо выполнить.

    Returns:
        str: Сгенерированный план действий.
    """
    # Создаем контекст для модели
    context_text = f"{room_description}\nЗадание: {task}"
    
    prompt = ChatPromptTemplate.from_template('''
    Составь подробный и конкретный план действий для выполнения следующего задания,
    обязательно учитывая особенности комнаты, описанные в контексте.
    Если комната имеет необычные или абстрактные характеристики, обязательно объясни,
    как они влияют на каждый шаг плана.

    **Требования к формату ответа:**
    - Используй нумерованный список.
    - Не используй форматирование Markdown.
    - Каждый пункт списка должен быть на отдельной строке.
    - Избегай дополнительных символов.

    **Пример:**
    Контекст:
    Комната с нулевой гравитацией, где все предметы парят в воздухе.
    Задание: Зажечь свечу.

    План действий:
    1. Закрепить себя и свечу с помощью ремней, чтобы предотвратить дрейф в невесомости.
    2. Использовать специальную зажигалку, предназначенную для условий невесомости.
    3. Аккуратно зажечь свечу, следя за тем, чтобы пламя не распространялось бесконтрольно.
    4. Наблюдать за свечой и быть готовым потушить ее в случае необходимости.

    **Твой контекст:**
    {context}

    **План действий:**
    ''')

    
    # Форматируем сообщение с подстановкой контекста
    formatted_prompt = prompt.format_messages(context=context_text)
    
    # Инициализируем модель GigaChat с использованием API-ключа из config.py
    llm = GigaChat(
        credentials=config.GIGACHAT_API_KEY,
        model='GigaChat:latest',
        verify_ssl_certs=False,
        profanity_check=False
    )
    
    response = llm(
        formatted_prompt,
        temperature=0.5,
        top_p=0.9
    )
    
    return response.content.strip()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработчик команды /start. Отправляет приветственное сообщение с кнопкой "Новая задача".

    Args:
        update (Update): Объект обновления Telegram.
        context (ContextTypes.DEFAULT_TYPE): Контекст бота.

    Returns:
        int: Конец диалога (ConversationHandler.END).
    """
    # Создаем кнопку "Новая задача"
    keyboard = [
        [InlineKeyboardButton("Новая задача", callback_data='new_task')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    # Отправляем приветственное сообщение с кнопкой
    await update.message.reply_text(
        "Здравствуйте! Нажмите кнопку ниже, чтобы начать новую задачу.",
        reply_markup=reply_markup
    )
    return ConversationHandler.END

async def new_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработчик нажатия кнопки "Новая задача". Запрашивает описание комнаты.

    Args:
        update (Update): Объект обновления Telegram.
        context (ContextTypes.DEFAULT_TYPE): Контекст бота.

    Returns:
        int: Следующее состояние (ROOM_DESCRIPTION).
    """
    query = update.callback_query
    # Подтверждаем обработку нажатия
    await query.answer()
    # Запрашиваем описание комнаты
    await query.edit_message_text(text="Пожалуйста, введите описание комнаты.")
    return ROOM_DESCRIPTION

async def room_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработчик ввода описания комнаты. Сохраняет описание и запрашивает задание.

    Args:
        update (Update): Объект обновления Telegram.
        context (ContextTypes.DEFAULT_TYPE): Контекст бота.

    Returns:
        int: Следующее состояние (TASK).
    """
    # Сохраняем описание комнаты в данных пользователя
    context.user_data['room_description'] = update.message.text
    # Просим пользователя ввести задание
    await update.message.reply_text(
        "Спасибо! Теперь введите задание, которое нужно выполнить."
    )
    return TASK

async def task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработчик ввода задания. Генерирует и отправляет план действий.

    Args:
        update (Update): Объект обновления Telegram.
        context (ContextTypes.DEFAULT_TYPE): Контекст бота.

    Returns:
        int: Конец диалога (ConversationHandler.END).
    """
    task_text = update.message.text
    room_description = context.user_data['room_description']
    
    # Генерируем план действий
    plan = generate_plan(room_description, task_text)
    # Отправляем план действий пользователю
    await update.message.reply_text("План действий:")
    await update.message.reply_text(plan)
    
    # Предлагаем начать новую задачу, отправляя кнопку "Новая задача"
    keyboard = [
        [InlineKeyboardButton("Новая задача", callback_data='new_task')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Для составления нового плана, нажмите кнопку снизу",
        reply_markup=reply_markup
    )
    
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработчик команды /cancel. Завершает диалог с пользователем.

    Args:
        update (Update): Объект обновления Telegram.
        context (ContextTypes.DEFAULT_TYPE): Контекст бота.

    Returns:
        int: Конец диалога (ConversationHandler.END).
    """
    await update.message.reply_text('Диалог завершен.')
    return ConversationHandler.END

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик ошибок. Логирует исключения, возникающие во время работы бота.

    Args:
        update (object): Объект обновления (может быть None при ошибке).
        context (ContextTypes.DEFAULT_TYPE): Контекст бота.
    """
    # Логируем информацию об ошибке
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

def main():
    """
    Основная функция, инициализирующая и запускающая Telegram-бота.
    """
    # Создаем приложение бота с использованием токена из config.py
    application = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    
    # Определяем обработчики состояний и команд
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', start),
            CallbackQueryHandler(new_task, pattern='^new_task$')
        ],
        states={
            ROOM_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, room_description)],
            TASK: [MessageHandler(filters.TEXT & ~filters.COMMAND, task)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    # Добавляем обработчики в приложение
    application.add_handler(conv_handler)
    
    # Регистрируем обработчик ошибок
    application.add_error_handler(error_handler)
    
    # Запускаем бота в режиме поллинга
    application.run_polling()

if __name__ == '__main__':
    main()
