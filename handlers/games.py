import random
from telegram import Update
from telegram.ext import ContextTypes

TRUTHS = [
    "What's the most embarrassing thing you've done in this group?",
    "Who do you secretly agree with the most here?",
    "What's a lie you've told recently?",
]

DARES = [
    "Send your last selfie in the group.",
    "Type your reply using only emojis for the next message.",
    "Compliment the person above you in the chat.",
]

WYR = [
    "Would you rather always be 10 minutes late or 20 minutes early?",
    "Would you rather lose all your photos or all your contacts?",
    "Would you rather have unlimited money or unlimited time?",
]

QUIZ_QUESTIONS = [
    {"q": "What year was Telegram launched?", "options": ["2011", "2013", "2015", "2017"], "correct": 1},
]


async def quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = random.choice(QUIZ_QUESTIONS)
    await context.bot.send_poll(
        chat_id=update.effective_chat.id,
        question=q["q"],
        options=q["options"],
        type="quiz",
        correct_option_id=q["correct"],
        is_anonymous=False,
    )


async def truth(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"🎯 Truth: {random.choice(TRUTHS)}")


async def dare(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"🔥 Dare: {random.choice(DARES)}")


async def would_you_rather(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"🤔 {random.choice(WYR)}")


async def rock_paper_scissors(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /rps rock|paper|scissors")
        return
    choices = ["rock", "paper", "scissors"]
    user_choice = context.args[0].lower()
    if user_choice not in choices:
        await update.message.reply_text("Choose: rock, paper, or scissors")
        return
    bot_choice = random.choice(choices)
    if user_choice == bot_choice:
        result = "It's a tie! 🤝"
    elif (
        (user_choice == "rock" and bot_choice == "scissors")
        or (user_choice == "paper" and bot_choice == "rock")
        or (user_choice == "scissors" and bot_choice == "paper")
    ):
        result = "You win! 🎉"
    else:
        result = "I win! 😎"
    await update.message.reply_text(f"You: {user_choice} | Me: {bot_choice}\n{result}")
