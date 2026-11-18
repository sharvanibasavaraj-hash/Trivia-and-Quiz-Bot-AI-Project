const chat = document.getElementById("chat");
const form = document.getElementById("chat-form");
const input = document.getElementById("message-input");
const sendBtn = document.getElementById("send-btn");

function addMessage(text, sender) {
    const message = document.createElement("div");
    message.className = `message ${sender}-message`;

    const avatar = document.createElement("div");
    avatar.className = "avatar";
    avatar.textContent = sender === "bot" ? "🤖" : "🙂";

    const bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.textContent = text;
    bubble.style.whiteSpace = "pre-wrap";

    message.append(avatar, bubble);
    chat.appendChild(message);
    chat.scrollTop = chat.scrollHeight;

    // Return the message element so it can be removed later.
    return message;
}

// ADDED: Display the quiz question and options using existing classes.
function displayQuestion(quiz) {
    if (!quiz || !quiz.question || !Array.isArray(quiz.options)) {
        return;
    }

    const message = document.createElement("div");
    message.className = "message bot-message";

    const avatar = document.createElement("div");
    avatar.className = "avatar";
    avatar.textContent = "🤖";

    const bubble = document.createElement("div");
    bubble.className = "bubble";

    const questionText =
        `Question ${quiz.question_number} of ${quiz.total_questions}\n\n` +
        quiz.question + "\n\n" +
        quiz.options.map((option, index) =>
            `${String.fromCharCode(65 + index)}. ${option}`
        ).join("\n");

    bubble.textContent = questionText;
    bubble.style.whiteSpace = "pre-wrap";

    message.append(avatar, bubble);
    chat.appendChild(message);
    chat.scrollTop = chat.scrollHeight;
}

async function sendMessage(message) {
    const text = message.trim();

    if (!text) {
        return;
    }

    addMessage(text, "user");

    input.value = "";
    input.focus();
    sendBtn.disabled = true;

    // Show a temporary waiting message.
    const loadingMessage = addMessage(
        "🧠 Generating your response… Please wait!",
        "bot"
    );

    try {
        const response = await fetch("/api/chat", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                message: text
            })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(
                data.error || "Unable to contact TriviaBot."
            );
        }

        // Remove the waiting message before showing the answer.
        loadingMessage.remove();
addMessage(data.reply, "bot");

// Display the question returned by the backend.
if (data.quiz) {
    displayQuestion(data.quiz);
}

// Automatically load the next question after answer feedback.
if (data.auto_next) {
    setTimeout(async () => {
        try {
            const response = await fetch("/api/next", {
                method: "POST"
            });

            const nextData = await response.json();

            if (nextData.reply) {
                addMessage(nextData.reply, "bot");
            }

            if (nextData.quiz) {
                displayQuestion(nextData.quiz);
            }

        } catch (error) {
            console.error("Could not load next question:", error);
            addMessage(
                "Couldn't load the next question. Please try again.",
                "bot"
            );
        }
    }, 1500);
}

        

    } catch (error) {
        console.error(error);

        loadingMessage.remove();

        addMessage(
            "I couldn't connect to the server. Please check that Flask is running and try again.",
            "bot"
        );
    } finally {
        sendBtn.disabled = false;
        input.focus();
    }
}

form.addEventListener("submit", function (event) {
    event.preventDefault();
    sendMessage(input.value);
});

// Topic shortcuts
document.querySelectorAll(".topic-chip").forEach(button => {
    button.addEventListener("click", function () {
        sendMessage(button.dataset.message);
    });
});

// Quick-action buttons
document.getElementById("hint-btn").addEventListener("click", function () {
    sendMessage("hint");
});

document.getElementById("score-btn").addEventListener("click", function () {
    sendMessage("score");
});

document.getElementById("help-btn").addEventListener("click", function () {
    sendMessage("help");
});

document.getElementById("reset-btn").addEventListener("click", async function () {
    try {
        const response = await fetch("/api/reset", {
            method: "POST"
        });

        const data = await response.json();

        chat.replaceChildren();
        addMessage(data.reply, "bot");

    } catch (error) {
        console.error(error);

        addMessage(
            "Couldn't reset the chat. Please try again.",
            "bot"
        );
    }
});