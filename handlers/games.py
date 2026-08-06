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

HANGMAN_WORDS = ["python", "oracle", "midnight", "telegram", "mystery", "shadow"]

TRIVIA_CATEGORIES = {
    "movies": [
        {"q": "Which movie features the line 'I'll be back'?", "options": ["Terminator", "Predator", "Rambo", "RoboCop"], "correct": 0},
    ],
    "cricket": [
        {"q": "Which country has won the most Cricket World Cups?", "options": ["India", "Australia", "West Indies", "England"], "correct": 1},
    ],
    "general": [
        {"q": "What year was Telegram launched?", "options": ["2011", "2013", "2015", "2017"], "correct": 1},
    ],
}

WORDLE_WORDS = ["oracle", "midnight", "mystery", "shadow", "friend"]

# {chat_id: {"word": str, "guessed": set, "wrong": int}}
active_hangman = {}

# {chat_id: {"board": [None]*9, "players": [id1, id2], "turn": id, "names": {id: name}}}
active_ttt = {}

# {chat_id: {"chain": [words], "last_player": user_id}}
active_wordchain = {}

# {chat_id: {"word": str, "date": str}}
active_wordle = {}

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


# ---- Hangman ----
def _hangman_display(word: str, guessed: set) -> str:
    return " ".join(c if c in guessed else "_" for c in word)


async def hangman(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    word = random.choice(HANGMAN_WORDS)
    active_hangman[chat_id] = {"word": word, "guessed": set(), "wrong": 0}
    await update.message.reply_text(
        f"🪢 Hangman started: {_hangman_display(word, set())}\n"
        f"Wrong guesses: 0/6\nGuess with /hangmanguess [letter]"
    )


async def hangman_guess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in active_hangman:
        await update.message.reply_text("No active hangman game — start one with /hangman")
        return
    if not context.args or len(context.args[0]) != 1:
        await update.message.reply_text("Usage: /hangmanguess [single letter]")
        return

    game = active_hangman[chat_id]
    letter = context.args[0].lower()
    game["guessed"].add(letter)

    if letter not in game["word"]:
        game["wrong"] += 1

    display = _hangman_display(game["word"], game["guessed"])

    if "_" not in display:
        _record_win(chat_id, update.effective_user.id, update.effective_user.first_name)
        await update.message.reply_text(f"🎉 Solved! The word was '{game['word']}'")
        del active_hangman[chat_id]
    elif game["wrong"] >= 6:
        await update.message.reply_text(f"💀 Out of guesses! The word was '{game['word']}'")
        del active_hangman[chat_id]
    else:
        await update.message.reply_text(f"{display}\nWrong guesses: {game['wrong']}/6")


# ---- Tic Tac Toe ----
def _ttt_render(board):
    symbols = {None: "⬜", "X": "❌", "O": "⭕"}
    rows = ["".join(symbols[board[i]] for i in range(r * 3, r * 3 + 3)) for r in range(3)]
    return "\n".join(rows)


def _ttt_winner(board):
    lines = [(0,1,2), (3,4,5), (6,7,8), (0,3,6), (1,4,7), (2,5,8), (0,4,8), (2,4,6)]
    for a, b, c in lines:
        if board[a] and board[a] == board[b] == board[c]:
            return board[a]
    return None


async def tictactoe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("Reply to someone's message with /tictactoe to challenge them")
        return
    chat_id = update.effective_chat.id
    p1 = update.effective_user
    p2 = update.message.reply_to_message.from_user
    active_ttt[chat_id] = {
        "board": [None] * 9,
        "players": {p1.id: "X", p2.id: "O"},
        "turn": p1.id,
        "names": {p1.id: p1.first_name, p2.id: p2.first_name},
    }
    await update.message.reply_text(
        f"⭕❌ {p1.first_name} vs {p2.first_name}\n\n{_ttt_render([None]*9)}\n\n"
        f"{p1.first_name}'s turn (❌) — play with /ttt [1-9]"
    )


async def ttt_move(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in active_ttt:
        await update.message.reply_text("No active game — start one with /tictactoe (reply to challenge someone)")
        return
    game = active_ttt[chat_id]
    user_id = update.effective_user.id
    if user_id not in game["players"]:
        await update.message.reply_text("You're not in this game.")
        return
    if user_id != game["turn"]:
        await update.message.reply_text("Not your turn!")
        return
    if not context.args or not context.args[0].isdigit() or not (1 <= int(context.args[0]) <= 9):
        await update.message.reply_text("Usage: /ttt [1-9]")
        return

    pos = int(context.args[0]) - 1
    if game["board"][pos] is not None:
        await update.message.reply_text("That spot's taken!")
        return

    symbol = game["players"][user_id]
    game["board"][pos] = symbol
    winner_symbol = _ttt_winner(game["board"])

    if winner_symbol:
        _record_win(chat_id, user_id, game["names"][user_id])
        await update.message.reply_text(f"{_ttt_render(game['board'])}\n\n🎉 {game['names'][user_id]} wins!")
        del active_ttt[chat_id]
        return
    if None not in game["board"]:
        await update.message.reply_text(f"{_ttt_render(game['board'])}\n\n🤝 It's a draw!")
        del active_ttt[chat_id]
        return

    other_id = [pid for pid in game["players"] if pid != user_id][0]
    game["turn"] = other_id
    await update.message.reply_text(f"{_ttt_render(game['board'])}\n\n{game['names'][other_id]}'s turn")


# ---- Word Chain ----
async def wordchain_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    starter = random.choice(["apple", "tiger", "ocean", "mirror", "dream"])
    active_wordchain[chat_id] = {"chain": [starter], "last_player": None}
    await update.message.reply_text(
        f"🔗 Word chain started with: *{starter}*\n"
        f"Next word must start with '{starter[-1].upper()}' — submit with /chainword [word]",
        parse_mode="Markdown",
    )


async def chain_word(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in active_wordchain:
        await update.message.reply_text("No active word chain — start one with /wordchain")
        return
    if not context.args:
        await update.message.reply_text("Usage: /chainword [word]")
        return

    game = active_wordchain[chat_id]
    word = context.args[0].lower()
    last_word = game["chain"][-1]

    if update.effective_user.id == game["last_player"]:
        await update.message.reply_text("Wait for someone else to go before playing again!")
        return
    if word[0] != last_word[-1]:
        await update.message.reply_text(f"❌ Must start with '{last_word[-1].upper()}'")
        return
    if word in game["chain"]:
        await update.message.reply_text("❌ That word was already used")
        return

    game["chain"].append(word)
    game["last_player"] = update.effective_user.id
    await update.message.reply_text(f"✅ {word} — next word starts with '{word[-1].upper()}'")


# ---- Trivia by category ----
async def trivia_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or context.args[0].lower() not in TRIVIA_CATEGORIES:
        cats = ", ".join(TRIVIA_CATEGORIES.keys())
        await update.message.reply_text(f"Usage: /trivia [category]\nAvailable: {cats}")
        return
    category = context.args[0].lower()
    q = random.choice(TRIVIA_CATEGORIES[category])
    await context.bot.send_poll(
        chat_id=update.effective_chat.id,
        question=f"[{category.title()}] {q['q']}",
        options=q["options"],
        type="quiz",
        correct_option_id=q["correct"],
        is_anonymous=False,
    )


# ---- Wordle (daily, shared per group) ----
async def wordle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import datetime
    chat_id = update.effective_chat.id
    today = str(datetime.date.today())
    if chat_id not in active_wordle or active_wordle[chat_id]["date"] != today:
        # Deterministic word per day so everyone in the group gets the same one
        day_index = datetime.date.today().toordinal() % len(WORDLE_WORDS)
        active_wordle[chat_id] = {"word": WORDLE_WORDS[day_index], "date": today}
    await update.message.reply_text(
        f"🟩 Today's word is {len(active_wordle[chat_id]['word'])} letters. Guess with /wordleguess [word]"
    )


async def wordle_guess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import datetime
    chat_id = update.effective_chat.id
    today = str(datetime.date.today())
    if chat_id not in active_wordle or active_wordle[chat_id]["date"] != today:
        await update.message.reply_text("No active word today — start with /wordle first")
        return
    if not context.args:
        await update.message.reply_text("Usage: /wordleguess [word]")
        return

    target = active_wordle[chat_id]["word"]
    guess = context.args[0].lower()
    if len(guess) != len(target):
        await update.message.reply_text(f"Word must be {len(target)} letters")
        return

    feedback = ""
    for i, letter in enumerate(guess):
        if letter == target[i]:
            feedback += "🟩"
        elif letter in target:
            feedback += "🟨"
        else:
            feedback += "⬛"

    if guess == target:
        _record_win(chat_id, update.effective_user.id, update.effective_user.first_name)
        await update.message.reply_text(f"{feedback}\n🎉 Correct! Today's word was '{target}'")
    else:
        await update.message.reply_text(feedback)
