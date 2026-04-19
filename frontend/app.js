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
  const promptButtons = Array.from(document.querySelectorAll("[data-prompt]"));

  // ── URL du backend ──────────────────────────────────────────
  // ⚠️  Remplace cette URL par celle fournie par Render après déploiement
  const RENDER_BACKEND_URL = "https://epitech-chatbot.onrender.com";

  // Auto-détection : localhost → backend local, sinon → Render
  const isLocal = ["localhost", "127.0.0.1", ""].includes(window.location.hostname);
  const API_BASE_URL = isLocal
    ? "http://127.0.0.1:8000"
    : RENDER_BACKEND_URL;
  const SESSION_STORAGE_KEY = "epitech-chat-session-id";
  let isSending = false;

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

  function setPromptButtonsDisabled(disabled) {
    promptButtons.forEach((btn) => {
      btn.disabled = disabled;
    });
  }

  function applyPrompt(prompt, { autoSend = true } = {}) {
    if (!prompt) return;
    if (isSending) return;
    if (!widget.classList.contains("is-open")) openWidget();
    input.value = prompt;
    input.focus();
    if (autoSend) {
      if (typeof form.requestSubmit === "function") form.requestSubmit();
      else form.dispatchEvent(new Event("submit", { cancelable: true }));
    }
  }

  promptButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      const prompt = btn.getAttribute("data-prompt");
      applyPrompt(prompt, { autoSend: true });
    });
  });

  openBtn.addEventListener("click", () => {
    if (widget.classList.contains("is-open")) closeWidget();
    else openWidget();
  });

  closeBtn.addEventListener("click", closeWidget);

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && widget.classList.contains("is-open")) closeWidget();
  });

  function escapeHtml(text) {
    return text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function renderMarkdown(text) {
    let safe = escapeHtml(text);
    safe = safe.replace(/^###\s+(.+)$/gm, '<div class="chat-md-h3">$1</div>');
    safe = safe.replace(/^##\s+(.+)$/gm, '<div class="chat-md-h2">$1</div>');
    safe = safe.replace(/^#\s+(.+)$/gm, '<div class="chat-md-h1">$1</div>');
    safe = safe.replace(/`([^`]+)`/g, "<code>$1</code>");
    safe = safe.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
    safe = safe.replace(/\n/g, "<br>");
    return safe;
  }

  // Ajoute un message dans le widget
  function addMessage(who, text) {
    const msg = document.createElement("div");
    msg.classList.add("msg", who === "user" ? "msg-user" : "msg-bot");

    const bubble = document.createElement("div");
    bubble.classList.add("bubble");
    if (who === "bot") bubble.innerHTML = renderMarkdown(text);
    else bubble.textContent = text;

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

  function appendFeedbackButtons(bubbleElement, questionText, answerText, sessionId) {
    const feedbackDiv = document.createElement("div");
    feedbackDiv.className = "chat-feedback";
    feedbackDiv.style.display = "flex";
    feedbackDiv.style.gap = "8px";
    feedbackDiv.style.marginTop = "4px";
    feedbackDiv.style.justifyContent = "flex-end";
    
    feedbackDiv.innerHTML = `
      <button type="button" class="btn-feedback" data-thumb="1" style="background:none;border:none;cursor:pointer;opacity:0.6;font-size:14px;transition:0.2s;" title="Bonne réponse">👍</button>
      <button type="button" class="btn-feedback" data-thumb="0" style="background:none;border:none;cursor:pointer;opacity:0.6;font-size:14px;transition:0.2s;" title="Mauvaise réponse">👎</button>
    `;
    
    const btns = feedbackDiv.querySelectorAll(".btn-feedback");
    btns.forEach(b => {
      b.addEventListener("mouseover", () => { if(!b.disabled) b.style.opacity = "1"; });
      b.addEventListener("mouseout", () => { if(!b.disabled) b.style.opacity = "0.6"; });
      
      b.addEventListener("click", async () => {
        const thumb = parseInt(b.getAttribute("data-thumb"), 10);
        btns.forEach(btn => btn.disabled = true);
        b.style.opacity = "1";
        b.style.transform = "scale(1.2)";
        const otherBtn = thumb === 1 ? btns[1] : btns[0];
        otherBtn.style.opacity = "0.2";
        
        try {
          await fetch(`${API_BASE_URL}/feedback`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              session_id: sessionId,
              question: questionText,
              answer: answerText,
              thumb: thumb
            })
          });
        } catch(e) {
          console.error("Feedback error", e);
        }
      });
    });
    
    // On l'ajoute dans le conteneur du message
    bubbleElement.parentElement.appendChild(feedbackDiv);
  }

  // Envoi formulaire
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (isSending || input.disabled) return;
    const text = input.value.trim();
    if (!text) return;
    isSending = true;

    addMessage("user", text);
    input.value = "";

    const btn = form.querySelector("button");
    if (btn) btn.disabled = true;
    input.disabled = true;
    setPromptButtonsDisabled(true);

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

      if (thinkingBubble) {
        thinkingBubble.innerHTML = "";
      }
      let fullText = "";
      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        fullText += chunk;
        if (thinkingBubble) {
          thinkingBubble.innerHTML = renderMarkdown(fullText);
        }
        body.scrollTop = body.scrollHeight;
      }
      
      if (thinkingBubble && fullText.trim().length > 0) {
        appendFeedbackButtons(thinkingBubble, text, fullText, getSessionId());
      }
      
    } catch (error) {
      if (thinkingBubble) {
        thinkingBubble.innerHTML = renderMarkdown(
          "Impossible de joindre le backend. Verifie qu'il est demarre et que le port correspond."
        );
      }
    } finally {
      isSending = false;
      if (btn) btn.disabled = false;
      input.disabled = false;
      setPromptButtonsDisabled(false);
      input.focus();
      body.scrollTop = body.scrollHeight;
    }
  });
})();
