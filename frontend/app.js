// =========================
// Slider (Header + Hero)
// =========================
function makeSlider(selector, intervalMs) {
  const slides = Array.from(document.querySelectorAll(selector));
  if (!slides.length) return;

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

// =========================
// Chatbot Widget (popup bas à droite)
// =========================
(function () {
  const openBtn = document.getElementById("open-chat");
  const closeBtn = document.getElementById("close-chat");
  const widget = document.getElementById("chat-widget");

  const form = document.getElementById("chat-widget-form");
  const input = document.getElementById("chat-input");
  const body = document.getElementById("chat-widget-body");
  const BACKEND_PORT = 8000;
  const API_PROTOCOL = window.location.protocol === "https:" ? "https" : "http";
  const API_HOST = window.location.hostname || "127.0.0.1";
  const API_BASE_URL = `${API_PROTOCOL}://${API_HOST}:${BACKEND_PORT}`;
  const SESSION_STORAGE_KEY = "epitech-chat-session-id";

  // Si tu n'as pas encore ajouté le HTML du widget, on évite les erreurs
  if (!openBtn || !closeBtn || !widget || !form || !input || !body) return;

  function getSessionId() {
    const existing = localStorage.getItem(SESSION_STORAGE_KEY);
    if (existing) return existing;
    const generated = typeof crypto !== "undefined" && crypto.randomUUID
      ? crypto.randomUUID()
      : `session-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    localStorage.setItem(SESSION_STORAGE_KEY, generated);
    return generated;
  }

  function openWidget() {
    widget.classList.add("is-open");
    widget.setAttribute("aria-hidden", "false");
    input.focus();
  }

  function closeWidget() {
    widget.classList.remove("is-open");
    widget.setAttribute("aria-hidden", "true");
    openBtn.focus();
  }

  openBtn.addEventListener("click", () => {
    if (widget.classList.contains("is-open")) closeWidget();
    else openWidget();
  });

  closeBtn.addEventListener("click", closeWidget);

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && widget.classList.contains("is-open")) closeWidget();
  });

  // Ajoute un message dans le widget
  function addMessage(who, text) {
    const msg = document.createElement("div");
    msg.classList.add("msg", who === "user" ? "msg-user" : "msg-bot");

    const bubble = document.createElement("div");
    bubble.classList.add("bubble");
    bubble.textContent = text;

    if (who === "bot") {
      const avatar = document.createElement("div");
      avatar.classList.add("avatar");
      const img = document.createElement("img");
      img.src = "images/logo-AE.png";
      img.alt = "Assistant EPITECH";
      avatar.appendChild(img);

      msg.appendChild(avatar);
      msg.appendChild(bubble);
    } else {
      const avatar = document.createElement("div");
      avatar.classList.add("avatar", "user");
      avatar.setAttribute("aria-hidden", "true");
      avatar.textContent = "Vous";

      msg.appendChild(bubble);
      msg.appendChild(avatar);
    }

    body.appendChild(msg);
    body.scrollTop = body.scrollHeight;
    return bubble;
  }

  // Envoi formulaire
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text) return;

    addMessage("user", text);
    input.value = "";

    const btn = form.querySelector("button");
    if (btn) btn.disabled = true;
    input.disabled = true;

    const thinkingBubble = addMessage("bot", "L'IA reflechit...");

    try {
      const response = await fetch(`${API_BASE_URL}/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          message: text,
          session_id: getSessionId(),
        }),
      });

      if (!response.ok) {
        throw new Error(`backend error: ${response.status}`);
      }

      const data = await response.json();
      const answer = data && data.answer ? data.answer : "Je n'ai pas de reponse pour le moment.";
      if (thinkingBubble) {
        thinkingBubble.textContent = answer;
      }
    } catch (error) {
      if (thinkingBubble) {
        thinkingBubble.textContent =
          "Impossible de joindre le backend. Verifie qu'il est demarre et que le port correspond.";
      }
    } finally {
      if (btn) btn.disabled = false;
      input.disabled = false;
      input.focus();
      body.scrollTop = body.scrollHeight;
    }
  });
})();
