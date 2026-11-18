import os
import json
import random
import re

from flask import Flask, request, jsonify, session, send_from_directory
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv(
    "FLASK_SECRET_KEY",
    "local-development-key"
)

api_key = os.getenv("GROQ_API_KEY")
client = Groq(api_key=api_key) if api_key else None

MODEL = "openai/gpt-oss-20b"

DEFAULT_COUNT = 10
MAX_QUESTIONS = 50


QUESTION_BANK = {
    "python": [
        {
            "question": "Which keyword defines a function in Python?",
            "options": ["function", "def", "fun", "define"],
            "answer": 1,
            "hint": "It is a three-letter keyword."
        },
        {
            "question": "Which data type stores True or False?",
            "options": ["int", "str", "bool", "list"],
            "answer": 2,
            "hint": "Its name comes from Boolean logic."
        },
        {
            "question": "Which symbol starts a comment in Python?",
            "options": ["//", "#", "/*", "--"],
            "answer": 1,
            "hint": "Look for the hash symbol."
        },
        {
            "question": "Which collection stores key-value pairs?",
            "options": ["List", "Tuple", "Set", "Dictionary"],
            "answer": 3,
            "hint": "It maps keys to values."
        }
    ],
    "computer science": [
        {
            "question": "What does CPU stand for?",
            "options": [
                "Central Processing Unit",
                "Computer Personal Unit",
                "Central Program Utility",
                "Control Processing User"
            ],
            "answer": 0,
            "hint": "It is often called the brain of a computer."
        },
        {
            "question": "Which data structure follows FIFO?",
            "options": ["Stack", "Queue", "Tree", "Graph"],
            "answer": 1,
            "hint": "The first element added is removed first."
        },
        {
            "question": "Which language is commonly used for web page structure?",
            "options": ["HTML", "SQL", "C", "Assembly"],
            "answer": 0,
            "hint": "It uses tags such as <p> and <h1>."
        },
        {
            "question": "What does RAM stand for?",
            "options": [
                "Read Access Memory",
                "Random Access Memory",
                "Rapid Action Module",
                "Run Access Machine"
            ],
            "answer": 1,
            "hint": "It is temporary working memory."
        }
    ],
    "space": [
        {
            "question": "Which planet is known as the Red Planet?",
            "options": ["Venus", "Mars", "Jupiter", "Mercury"],
            "answer": 1,
            "hint": "Its surface contains iron oxide."
        },
        {
            "question": "Which star is closest to Earth?",
            "options": ["Sirius", "Polaris", "The Sun", "Vega"],
            "answer": 2,
            "hint": "We see it during the daytime."
        },
        {
            "question": "Which planet has the most prominent ring system?",
            "options": ["Mars", "Saturn", "Earth", "Mercury"],
            "answer": 1,
            "hint": "Its rings are made largely of ice and rock."
        },
        {
            "question": "What is Earth's natural satellite?",
            "options": ["Titan", "Europa", "The Moon", "Phobos"],
            "answer": 2,
            "hint": "It orbits Earth."
        }
    ],
    "general knowledge": [
        {
            "question": "What is the capital of Japan?",
            "options": ["Seoul", "Beijing", "Tokyo", "Bangkok"],
            "answer": 2,
            "hint": "It is Japan's largest city."
        },
        {
            "question": "How many sides does a hexagon have?",
            "options": ["Five", "Six", "Seven", "Eight"],
            "answer": 1,
            "hint": "The prefix 'hexa' means six."
        },
        {
            "question": "Which is the largest ocean on Earth?",
            "options": [
                "Atlantic Ocean",
                "Indian Ocean",
                "Arctic Ocean",
                "Pacific Ocean"
            ],
            "answer": 3,
            "hint": "It lies between Asia and the Americas."
        },
        {
            "question": "Which planet is the largest in our solar system?",
            "options": ["Earth", "Jupiter", "Neptune", "Venus"],
            "answer": 1,
            "hint": "It is a gas giant."
        }
    ]
}


# --------------------------------------------------
# QUIZ HELPERS
# --------------------------------------------------

def reset_quiz():
    session["quiz_active"] = False
    session["questions"] = []
    session["current_index"] = 0
    session["score"] = 0
    session["answered"] = False
    session.pop("topic", None)
    session.pop("difficulty", None)


def get_current_question():
    questions = session.get("questions", [])
    index = session.get("current_index", 0)

    if 0 <= index < len(questions):
        return questions[index]

    return None


def format_question(question, index, total):
    return {
        "question_number": index + 1,
        "total_questions": total,
        "question": question["question"],
        "options": question["options"],
        "hint": question.get("hint", "Think carefully!")
    }


def extract_question_count(message):
    patterns = [
        r"\b(\d+)\s*(?:questions?|qs)\b",
        r"\b(?:questions?|qs)\s*(?:of|=|:)?\s*(\d+)\b"
    ]

    for pattern in patterns:
        match = re.search(pattern, message, re.IGNORECASE)

        if match:
            return max(1, min(int(match.group(1)), MAX_QUESTIONS))

    return DEFAULT_COUNT


def extract_difficulty(message):
    message = message.lower()

    if re.search(r"\b(easy|beginner|simple)\b", message):
        return "easy"

    if re.search(r"\b(hard|difficult|advanced|challenging)\b", message):
        return "hard"

    return "medium"


def extract_topic(message):
    topic = message.strip()

    topic = re.sub(
        r"\b(start|begin|give|create|make|generate|prepare|"
        r"conduct|take|ask|play|do|launch)\b",
        " ",
        topic,
        flags=re.IGNORECASE
    )

    topic = re.sub(
        r"\b(a|an|the|me|my|please|for me|about|on|"
        r"quiz|trivia|test me|questions?|question|"
        r"easy|medium|hard|beginner|advanced|challenging|"
        r"simple|difficult|with|of|topic|topics)\b",
        " ",
        topic,
        flags=re.IGNORECASE
    )

    topic = re.sub(r"\b\d+\b", " ", topic)
    topic = re.sub(r"\s+", " ", topic).strip(" .,!?-:")

    return topic or "General Knowledge"


# --------------------------------------------------
# GROQ API
# --------------------------------------------------

def ask_groq(prompt, system_message=None, max_tokens=5000):
    if not client:
        raise RuntimeError(
            "GROQ_API_KEY is missing from your .env file."
        )

    messages = []

    if system_message:
        messages.append({
            "role": "system",
            "content": system_message
        })

    messages.append({
        "role": "user",
        "content": prompt
    })

    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=0.4,
        max_tokens=max_tokens
    )

    content = response.choices[0].message.content

    if not content:
        raise RuntimeError("The AI returned an empty response.")

    return content.strip()


# --------------------------------------------------
# GENERATE QUESTIONS ON ANY TOPIC
# --------------------------------------------------

def generate_questions(topic, difficulty, count):
    prompt = f"""
Create exactly {count} multiple-choice quiz questions.

Topic: {topic}
Difficulty: {difficulty}

Support any requested topic.

Each question must have exactly four options and one correct answer.
The answer must be an integer from 0 to 3.
Include a short hint.
Avoid duplicates.

Return ONLY valid JSON:

{{
  "questions": [
    {{
      "question": "Question text?",
      "options": ["Option A", "Option B", "Option C", "Option D"],
      "answer": 0,
      "hint": "A short hint."
    }}
  ]
}}
"""

    raw = ask_groq(
        prompt,
        system_message=(
            "You are a quiz generator. Return valid JSON only."
        ),
        max_tokens=12000
    )

    raw = re.sub(
        r"^\s*```(?:json)?\s*",
        "",
        raw,
        flags=re.IGNORECASE
    )
    raw = re.sub(r"\s*```\s*$", "", raw)

    start = raw.find("{")
    end = raw.rfind("}")

    if start == -1 or end == -1:
        raise ValueError("The AI did not return valid JSON.")

    data = json.loads(raw[start:end + 1])
    questions = data.get("questions", [])

    validated = []

    for item in questions:
        if not isinstance(item, dict):
            continue

        question = item.get("question")
        options = item.get("options")
        answer = item.get("answer")

        if not isinstance(question, str) or not question.strip():
            continue

        if not isinstance(options, list) or len(options) != 4:
            continue

        if not all(isinstance(option, str) for option in options):
            continue

        if not isinstance(answer, int) or isinstance(answer, bool):
            continue

        if answer not in range(4):
            continue

        validated.append({
            "question": question.strip(),
            "options": options,
            "answer": answer,
            "hint": str(item.get("hint", "Think carefully!"))
        })

    if len(validated) < count:
        raise ValueError(
            f"Only {len(validated)} valid questions were generated."
        )

    return validated[:count]


# --------------------------------------------------
# START QUIZ
# --------------------------------------------------

def start_quiz(topic, difficulty, count):
    try:
        questions = generate_questions(topic, difficulty, count)

    except Exception as error:
        print("QUESTION GENERATION ERROR:", repr(error))

        fallback = QUESTION_BANK.get(topic.lower().strip(), [])

        if len(fallback) >= count:
            questions = random.sample(fallback, count)
        else:
            return {
                "reply": (
                    "I couldn't generate the quiz right now. "
                    "Please try again or check your Groq API setup."
                )
            }

    random.shuffle(questions)

    session["quiz_active"] = True
    session["questions"] = questions
    session["current_index"] = 0
    session["score"] = 0
    session["answered"] = False
    session["topic"] = topic
    session["difficulty"] = difficulty

    return {
        "reply": (
            f"Your {difficulty} quiz on {topic} is ready! "
            f"You have {count} questions. Good luck!"
        ),
        "quiz": format_question(questions[0], 0, count)
    }


# --------------------------------------------------
# ANSWER QUESTION
# --------------------------------------------------

def process_answer(message):
    question = get_current_question()

    if not question:
        return {"reply": "There is no active question."}

    if session.get("answered", False):
        return {
            "reply": "You've already answered this question."
        }

    message = message.strip().lower()
    selected_index = None

    match = re.fullmatch(
        r"(?:option\s*)?([a-d1-4])(?:[.)])?",
        message
    )

    if match:
        choice = match.group(1)

        if choice in "abcd":
            selected_index = ord(choice) - ord("a")
        else:
            selected_index = int(choice) - 1

    else:
        for index, option in enumerate(question["options"]):
            if message == option.strip().lower():
                selected_index = index
                break

    if selected_index is None:
        return {
            "reply": (
                "Please answer with A, B, C, or D, "
                "or type the full answer option."
            )
        }

    correct_index = question["answer"]
    correct_option = question["options"][correct_index]

    is_correct = selected_index == correct_index

    if is_correct:
        session["score"] = session.get("score", 0) + 1
        reply = "Correct! 🎉"
    else:
        reply = f"Incorrect. The correct answer is: {correct_option}"

    session["answered"] = True

    return {
        "reply": reply,
        "correct": is_correct,
        "correct_answer": correct_option,
        "score": session.get("score", 0),
        "total": len(session.get("questions", [])),
        "auto_next": True
    }


# --------------------------------------------------
# NEXT QUESTION
# --------------------------------------------------

def next_question():
    questions = session.get("questions", [])

    if not questions:
        return {"reply": "No active quiz. Start a new quiz!"}

    if not session.get("answered", False):
        return {"reply": "Answer the current question first."}

    index = session.get("current_index", 0) + 1

    if index >= len(questions):
        score = session.get("score", 0)
        total = len(questions)
        percentage = round(score / total * 100)

        if percentage >= 80:
            feedback = "Excellent work! 🌟"
        elif percentage >= 50:
            feedback = "Good effort! Keep practising."
        else:
            feedback = "Keep learning! You'll improve with practice."

        topic = session.get("topic", "your quiz")

        reset_quiz()

        return {
            "reply": (
                f"Quiz completed!\n"
                f"Topic: {topic}\n"
                f"Final score: {score}/{total}\n"
                f"Percentage: {percentage}%\n"
                f"{feedback}"
            ),
            "quiz_finished": True,
            "score": score,
            "total": total,
            "percentage": percentage
        }

    session["current_index"] = index
    session["answered"] = False

    return {
        "reply": "",
        "quiz": format_question(
            questions[index],
            index,
            len(questions)
        )
    }


# --------------------------------------------------
# FRONTEND
# --------------------------------------------------

@app.route("/")
def home():
    return send_from_directory(".", "index.html")


@app.route("/<path:filename>")
def frontend_files(filename):
    if filename in {"style.css", "script.js"}:
        return send_from_directory(".", filename)

    return "Not found", 404


# --------------------------------------------------
# CHAT API
# --------------------------------------------------

@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    message = str(data.get("message", "")).strip()

    if not message:
        return jsonify({"reply": "Please type a message."})

    lower_message = message.lower()

    print("CHAT REQUEST RECEIVED:", message)

    # Help must work during an active quiz.
    if lower_message in {"help", "what can you do?", "what can you do"}:
        return jsonify({
            "reply": (
                "I'm TriviaBot! You can ask me questions or start a quiz "
                "on any topic. You can also check your score or ask for a hint."
            )
        })

    # Score must be checked before processing answers.
    if re.search(
        r"\b(score|my score|show score|current score)\b",
        lower_message
    ):
        if session.get("quiz_active"):
            return jsonify({
                "reply": (
                    f"Your current score is "
                    f"{session.get('score', 0)}/"
                    f"{len(session.get('questions', []))}."
                ),
                "score": session.get("score", 0),
                "total": len(session.get("questions", []))
            })

        return jsonify({
            "reply": "There is no active quiz. Start a quiz to track your score."
        })

    # Hint must work during an active quiz.
    if re.search(r"\b(hint|clue)\b", lower_message):
        question = get_current_question()

        if session.get("quiz_active") and question:
            return jsonify({
                "reply": question.get("hint", "Think carefully!")
            })

        return jsonify({"reply": "Start a quiz first to receive hints."})

    # Stop quiz.
    if re.search(
        r"\b(stop quiz|quit quiz|end quiz|cancel quiz)\b",
        lower_message
    ):
        reset_quiz()
        return jsonify({"reply": "Quiz stopped."})

    # Start a new quiz.
    if re.search(r"\b(quiz|trivia|test me)\b", lower_message):
        topic = extract_topic(message)
        count = extract_question_count(message)
        difficulty = extract_difficulty(message)

        return jsonify(start_quiz(topic, difficulty, count))

    # Manual next command remains available.
    if re.fullmatch(
        r"(next|next question|continue|continue quiz|next one|go ahead|proceed)",
        lower_message
    ):
        if session.get("quiz_active"):
            return jsonify(next_question())

        return jsonify({"reply": "Start a quiz first."})

    # Greetings.
    if re.fullmatch(
        r"(hi|hello|hey|hii|hiii|good morning|good evening)[!. ]*",
        lower_message
    ):
        return jsonify({
            "reply": (
                "Hey! 👋 Welcome to TriviaBot. "
                "Ask me anything or start a quiz on any topic!"
            )
        })

    # Process answers only after commands have been checked.
    if session.get("quiz_active"):
        return jsonify(process_answer(message))

    # General AI assistant.
    try:
        answer = ask_groq(
            message,
            system_message=(
                "You are TriviaBot, a friendly and helpful AI assistant. "
                "Answer questions clearly and accurately."
            ),
            max_tokens=1500
        )

        return jsonify({"reply": answer})

    except Exception as error:
        print("ASSISTANT ERROR:", repr(error))

        return jsonify({
            "reply": (
                "I'm having trouble connecting to the AI service. "
                "Please check your Groq API key and internet connection."
            )
        })


# --------------------------------------------------
# AUTO-NEXT API
# --------------------------------------------------

@app.route("/api/next", methods=["POST"])
def auto_next():
    if not session.get("quiz_active"):
        return jsonify({"reply": "The quiz has ended."})

    return jsonify(next_question())


# --------------------------------------------------
# RESET API
# --------------------------------------------------

@app.route("/api/reset", methods=["POST"])
def reset():
    reset_quiz()
    return jsonify({"reply": "Quiz reset successfully."})


if __name__ == "__main__":
    app.run(debug=True)