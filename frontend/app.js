function makeSlider(selector, intervalMs) {
  const slides = Array.from(document.querySelectorAll(selector));
  if (slides.length === 0) return;

  let i = 0;
  slides.forEach((s, idx) => s.classList.toggle("active", idx === 0));

  setInterval(() => {
    slides[i].classList.remove("active");
    i = (i + 1) % slides.length;
    slides[i].classList.add("active");
  }, intervalMs);
}

makeSlider(".header-bg-slide", 3200);
makeSlider(".hero-bg-slide", 4500);

const BACKEND_PORT = 8000;
const API_PROTOCOL = window.location.protocol === "https:" ? "https" : "http";
const API_HOST = window.location.hostname || "127.0.0.1";
const API_BASE_URL = `${API_PROTOCOL}://${API_HOST}:${BACKEND_PORT}`;

const chatWindow = document.querySelector(".chat-window");
const chatForm = document.querySelector(".chat-form");
const chatInput = document.querySelector("#chat-input");
const chatButton = document.querySelector("#chat-submit");
const chatStatus = document.querySelector("#chat-status");
const chatDot = document.querySelector(".chat-dot");
const assistantAvatarSrc = "images/logo-AE.png";
const SESSION_STORAGE_KEY = "epitech-chat-session-id";

function getSessionId() {
  const existing = localStorage.getItem(SESSION_STORAGE_KEY);
  if (existing) return existing;
  const generated = typeof crypto !== "undefined" && crypto.randomUUID
    ? crypto.randomUUID()
    : `session-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  localStorage.setItem(SESSION_STORAGE_KEY, generated);
  return generated;
}

function setStatus(online, text) {
  if (chatStatus) {
    chatStatus.textContent = text;
  }
  if (chatDot) {
    chatDot.classList.toggle("offline", !online);
  }
}

async function checkHealth() {
  if (!chatStatus) return;
  try {
    const resp = await fetch(`${API_BASE_URL}/health`);
    if (!resp.ok) throw new Error("health check failed");
    setStatus(true, "Connecte");
  } catch (error) {
    setStatus(false, "Backend indisponible");
  }
}

function appendMessage(role, text) {
  if (!chatWindow) return null;

  const msg = document.createElement("div");
  msg.className = `msg ${role === "user" ? "msg-user" : "msg-bot"}`;

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = text;

  if (role === "user") {
    msg.appendChild(bubble);
    const avatar = document.createElement("div");
    avatar.className = "avatar user";
    avatar.setAttribute("aria-hidden", "true");
    avatar.textContent = "Vous";
    msg.appendChild(avatar);
  } else {
    const avatar = document.createElement("div");
    avatar.className = "avatar";
    const img = document.createElement("img");
    img.src = assistantAvatarSrc;
    img.alt = "Assistant EPITECH";
    avatar.appendChild(img);
    msg.appendChild(avatar);
    msg.appendChild(bubble);
  }

  chatWindow.appendChild(msg);
  chatWindow.scrollTop = chatWindow.scrollHeight;
  return bubble;
}

function syncButtonState() {
  if (!chatButton || !chatInput) return;
  chatButton.disabled = chatInput.disabled || chatInput.value.trim().length === 0;
}

if (chatForm && chatInput && chatButton && chatWindow) {
  const sessionId = getSessionId();

  chatInput.addEventListener("input", syncButtonState);
  syncButtonState();
  checkHealth();

  chatForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const message = chatInput.value.trim();
    if (!message) return;

    appendMessage("user", message);
    chatInput.value = "";
    syncButtonState();

    chatInput.disabled = true;
    chatButton.disabled = true;
    const pendingBubble = appendMessage("bot", "L'assistant reflechit...");

    try {
      const response = await fetch(`${API_BASE_URL}/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          message,
          session_id: sessionId,
        }),
      });

      if (!response.ok) {
        throw new Error(`backend error: ${response.status}`);
      }

      const data = await response.json();
      const answer = data && data.answer ? data.answer : "Je n'ai pas de reponse pour le moment.";
      if (pendingBubble) {
        pendingBubble.textContent = answer;
      }
      setStatus(true, "Connecte");
    } catch (error) {
      if (pendingBubble) {
        pendingBubble.textContent =
          "Impossible de joindre le backend. Verifie qu'il est demarre et que le port correspond.";
      }
      setStatus(false, "Backend indisponible");
    } finally {
      chatInput.disabled = false;
      syncButtonState();
      chatInput.focus();
    }
  });
}
