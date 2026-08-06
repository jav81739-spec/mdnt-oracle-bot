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

NHIE = [
    "Never have I ever stalked someone's profile at 3 AM.",
    "Never have I ever lied about being busy to avoid plans.",
    "Never have I ever pretended to like a gift I hated.",
]

RIDDLES = [
    {"q": "I speak without a mouth and hear without ears. What am I?", "a": "echo"},
    {"q": "The more you take, the more you leave behind. What am I?", "a": "footsteps"},
    {"q": "What has keys but can't open locks?", "a": "piano"},
]

SCRAMBLE_WORDS = ["telegram", "midnight", "oracle", "mystery", "friendship"]

# {chat_id: {user_id: wins}}
leaderboard = {}


def _record_win(chat_id: int, user_id: int, name: str):
    leaderboard.setdefault(chat_id, {})
    if user_id not in leaderboard[chat_id]:
        leaderboard[chat_id][user_id] = {"name": name, "wins": 0}
    leaderboard[chat_id][user_id]["wins"] += 1


# {chat_id: {"word": str, "hint_shown": bool}}
active_riddles = {}
active_scrambles = {}


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
        _record_win(update.effective_chat.id, context.bot.id, "Bot")
    if "You win" in result:
        _record_win(update.effective_chat.id, update.effective_user.id, update.effective_user.first_name)
    await update.message.reply_text(f"You: {user_choice} | Me: {bot_choice}\n{result}")


async def never_have_i_ever(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"🙊 {random.choice(NHIE)}")


async def riddle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    r = random.choice(RIDDLES)
    active_riddles[chat_id] = r["a"]
    await update.message.reply_text(f"🧩 Riddle: {r['q']}\n\nReply with /riddleanswer [your guess]")


async def riddle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in active_riddles:
        await update.message.reply_text("No active riddle — start one with /riddle")
        return
    guess = " ".join(context.args).lower().strip()
    answer = active_riddles[chat_id]
    if guess == answer:
        _record_win(chat_id, update.effective_user.id, update.effective_user.first_name)
        del active_riddles[chat_id]
        await update.message.reply_text(f"✅ Correct! It was '{answer}'")
    else:
        await update.message.reply_text("❌ Not quite, try again")


async def scramble(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    word = random.choice(SCRAMBLE_WORDS)
    scrambled = "".join(random.sample(word, len(word)))
    active_scrambles[chat_id] = word
    await update.message.reply_text(f"🔤 Unscramble: {scrambled.upper()}\n\nReply with /unscramble [your guess]")


async def unscramble(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in active_scrambles:
        await update.message.reply_text("No active scramble — start one with /scramble")
        return
    guess = " ".join(context.args).lower().strip()
    word = active_scrambles[chat_id]
    if guess == word:
        _record_win(chat_id, update.effective_user.id, update.effective_user.first_name)
        del active_scrambles[chat_id]
        await update.message.reply_text(f"✅ Correct! It was '{word}'")
    else:
        await update.message.reply_text("❌ Not quite, try again")


async def guess_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Simple 1-20 number guess, single message reveal (lightweight version)."""
    if not context.args:
        await update.message.reply_text("Usage: /guess [1-20]")
        return
    try:
        user_guess = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Send a number between 1 and 20")
        return
    target = random.randint(1, 20)
    if user_guess == target:
        _record_win(update.effective_chat.id, update.effective_user.id, update.effective_user.first_name)
        await update.message.reply_text(f"🎯 Correct! It was {target}!")
    else:
        hint = "higher" if target > user_guess else "lower"
        await update.message.reply_text(f"❌ Nope, it was {target}. Try {hint} next time!")


async def leaderboard_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    scores = leaderboard.get(chat_id, {})
    if not scores:
        await update.message.reply_text("No wins recorded yet — play some games first!")
        return
    ranked = sorted(scores.values(), key=lambda x: x["wins"], reverse=True)[:10]
    lines = [f"{i+1}. {p['name']} — {p['wins']} wins" for i, p in enumerate(ranked)]
    await update.message.reply_text("🏆 Leaderboard\n\n" + "\n".join(lines))


async def dice_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_dice(update.effective_chat.id, emoji="🎲")


async def darts_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_dice(update.effective_chat.id, emoji="🎯")


async def basketball_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_dice(update.effective_chat.id, emoji="🏀")


async def bowling_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_dice(update.effective_chat.id, emoji="🎳")


async def football_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_dice(update.effective_chat.id, emoji="⚽")


async def slot_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_dice(update.effective_chat.id, emoji="🎰")
