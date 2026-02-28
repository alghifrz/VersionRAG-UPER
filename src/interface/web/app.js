const chatEl = document.getElementById("chat");
const chatForm = document.getElementById("chatForm");
const messageInput = document.getElementById("messageInput");
const sendBtn = document.getElementById("sendBtn");
const clearBtn = document.getElementById("clearBtn");

const modelSelect = document.getElementById("modelSelect");
const modelDropdownEl = document.getElementById("modelDropdown");
const modelTriggerEl = document.getElementById("modelTrigger");
const modelMenuEl = document.getElementById("modelMenu");
const modelItemEls = document.querySelectorAll(".model-item");
const mainEl = document.getElementById("main");
const emptyStateEl = document.getElementById("emptyState");
const emptyComposerHostEl = document.getElementById("emptyComposerHost");
const composerEl = document.querySelector(".composer");

let _composerOriginalParent = null;
let _composerOriginalNextSibling = null;

const indexBaselineBtn = document.getElementById("indexBaselineBtn");
const indexVersionBtn = document.getElementById("indexVersionBtn");
const indexStatusEl = document.getElementById("indexStatus");
const indexLogsEl = document.getElementById("indexLogs");
const indexLogsWrapEl = document.getElementById("indexLogsWrap");
const indexProgressWrapEl = document.getElementById("indexProgressWrap");
const indexProgressFillEl = document.getElementById("indexProgressFill");
const copyrightYearEl = document.getElementById("copyrightYear");
const themeToggleEl = document.getElementById("themeToggle");
const brandLogoEl = document.getElementById("brandLogo");

let indexPollTimer = null;
let activeIndexJobId = null;

function scrollToBottom() {
  chatEl.scrollTop = chatEl.scrollHeight;
}

function el(tag, className, text) {
  const e = document.createElement(tag);
  if (className) e.className = className;
  if (text !== undefined) e.textContent = text;
  return e;
}

function addMessage(role, text, metaText) {
  const wrap = el("div", `msg msg-${role}`);
  if (role === "user") {
    // User: bubble on the right, no avatar
    const bubble = el("div", "bubble user");
    bubble.textContent = text;
    wrap.appendChild(bubble);
  } else {
    // Assistant: plain text on the left, no bubble, no avatar
    const content = el("div", "assistant-text");
    content.textContent = text;
    wrap.appendChild(content);

    if (metaText) {
      const details = el("details", "assistant-meta");
      const summary = el("summary", "assistant-meta-summary", "Context (debug)");
      const pre = el("pre", "assistant-meta-pre", metaText);
      details.appendChild(summary);
      details.appendChild(pre);
      wrap.appendChild(details);
    }
  }

  chatEl.appendChild(wrap);
  setEmptyState(false);
  scrollToBottom();
  return wrap;
}

function addTypingDots() {
  const wrap = el("div", "msg msg-assistant");
  const content = el("div", "assistant-text");
  const dots = el("span", "typing-dots");
  content.appendChild(dots);
  wrap.appendChild(content);
  chatEl.appendChild(wrap);
  setEmptyState(false);
  scrollToBottom();
  return { wrap, content };
}

function setEmptyState(isEmpty) {
  if (!mainEl) return;
  mainEl.classList.toggle("is-empty", isEmpty);
  if (emptyStateEl) emptyStateEl.style.display = isEmpty ? "" : "";

  // Move the composer (chat input) into the center on empty state, like ChatGPT.
  if (!composerEl) return;
  if (isEmpty) {
    if (emptyComposerHostEl && composerEl.parentElement !== emptyComposerHostEl) {
      _composerOriginalParent = composerEl.parentElement;
      _composerOriginalNextSibling = composerEl.nextSibling;
      emptyComposerHostEl.appendChild(composerEl);
    }
  } else {
    if (_composerOriginalParent && composerEl.parentElement !== _composerOriginalParent) {
      if (_composerOriginalNextSibling) {
        _composerOriginalParent.insertBefore(composerEl, _composerOriginalNextSibling);
      } else {
        _composerOriginalParent.appendChild(composerEl);
      }
    }
  }
}

function setBusy(isBusy) {
  sendBtn.disabled = isBusy;
  messageInput.disabled = isBusy;
  if (!isBusy) messageInput.focus();
}

function setActiveModelLabel() {
  // no header label; keep for future hooks
  document.title = `LexUP - Universitas Pertamina Legal & Regulation Assistant`;
}

modelSelect.addEventListener("change", () => {
  setActiveModelLabel();
});

function setModelUI(value) {
  // sync native select
  if (modelSelect && modelSelect.value !== value) modelSelect.value = value;

  // sync trigger label
  if (modelTriggerEl) {
    const opt = [...modelSelect.options].find((o) => o.value === value);
    const label = opt ? opt.textContent : value;
    // keep caret span
    modelTriggerEl.childNodes[0].textContent = label + " ";
  }

  // sync selected item styling
  modelItemEls.forEach((el) => {
    el.classList.toggle("is-selected", el.dataset.value === value);
  });
}

function closeModelMenu() {
  if (!modelMenuEl || !modelTriggerEl) return;
  modelMenuEl.classList.add("hidden");
  modelTriggerEl.setAttribute("aria-expanded", "false");
}

function toggleModelMenu() {
  if (!modelMenuEl || !modelTriggerEl) return;
  const isOpen = !modelMenuEl.classList.contains("hidden");
  if (isOpen) closeModelMenu();
  else {
    modelMenuEl.classList.remove("hidden");
    modelTriggerEl.setAttribute("aria-expanded", "true");
  }
}

if (modelTriggerEl) {
  modelTriggerEl.addEventListener("click", () => toggleModelMenu());
}

modelItemEls.forEach((btn) => {
  btn.addEventListener("click", () => {
    const v = btn.dataset.value;
    if (!v) return;
    setModelUI(v);
    modelSelect.dispatchEvent(new Event("change"));
    closeModelMenu();
  });
});

// close on outside click / ESC
document.addEventListener("click", (e) => {
  if (!modelDropdownEl || !modelMenuEl) return;
  if (!modelDropdownEl.contains(e.target)) closeModelMenu();
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeModelMenu();
});

if (clearBtn) {
  clearBtn.addEventListener("click", () => {
    chatEl.innerHTML = "";
    setEmptyState(true);
    messageInput.value = "";
    messageInput.style.height = "auto";
    messageInput.focus();
  });
}

async function apiChat(model, message) {
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ model, message }),
  });
  if (!res.ok) {
    // Prefer FastAPI's JSON error shape: { detail: "..." }
    try {
      const j = await res.json();
      const detail = j && (j.detail || j.message);
      throw new Error(detail || JSON.stringify(j));
    } catch (_) {
      const t = await res.text();
      throw new Error(t || `HTTP ${res.status}`);
    }
  }
  return await res.json();
}

function stripAnswerPrefix(text) {
  if (!text) return text;
  const s = String(text).trim();
  const lower = s.toLowerCase();
  const prefixes = ["answer:", "answer -", "answer—", "jawaban:", "jawaban -", "jawaban—"];
  for (const p of prefixes) {
    if (lower.startsWith(p)) return s.slice(p.length).trimStart();
  }
  return s;
}

chatForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const msg = messageInput.value.trim();
  if (!msg) return;

  const model = modelSelect.value;
  setEmptyState(false);
  addMessage("user", msg);
  messageInput.value = "";
  messageInput.style.height = "auto";

  setBusy(true);
  const typing = addTypingDots();

  try {
    const data = await apiChat(model, msg);
    // Replace typing dots with final answer (no "Answer:" prefix)
    typing.content.textContent = stripAnswerPrefix((data.answer || "").trim()) || "(no answer)";
    const metaText = data.context ? `Context (debug):\n${data.context}` : "";
    if (metaText) {
      const details = el("details", "assistant-meta");
      const summary = el("summary", "assistant-meta-summary", "Context (debug)");
      const pre = el("pre", "assistant-meta-pre", metaText);
      details.appendChild(summary);
      details.appendChild(pre);
      typing.wrap.appendChild(details);
    }
  } catch (err) {
    typing.content.textContent = `Error: ${err.message || err}`;
  } finally {
    setBusy(false);
  }
});

messageInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    chatForm.requestSubmit();
  }
});

messageInput.addEventListener("input", () => {
  // auto grow textarea
  messageInput.style.height = "auto";
  messageInput.style.height = Math.min(messageInput.scrollHeight, 180) + "px";
});

async function apiStartIndex(model) {
  const res = await fetch("/api/index", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ model }),
  });
  if (!res.ok) {
    const t = await res.text();
    throw new Error(t || `HTTP ${res.status}`);
  }
  return await res.json();
}

async function apiIndexStatus(jobId) {
  const res = await fetch(`/api/index/${jobId}`);
  if (!res.ok) {
    const t = await res.text();
    throw new Error(t || `HTTP ${res.status}`);
  }
  return await res.json();
}

function setIndexBusy(isBusy) {
  indexBaselineBtn.disabled = isBusy;
  indexVersionBtn.disabled = isBusy;
}

function showIndexUI({ running }) {
  if (indexProgressWrapEl) indexProgressWrapEl.classList.toggle("hidden", !running);
  if (indexLogsWrapEl) indexLogsWrapEl.classList.toggle("hidden", !running);
  if (indexStatusEl) indexStatusEl.classList.add("hidden");
  if (indexProgressFillEl) {
    indexProgressFillEl.classList.add("indeterminate");
    indexProgressFillEl.style.width = "";
    indexProgressFillEl.style.transform = "";
  }
}

function showFinalIndexStatus(text, ok) {
  if (indexProgressWrapEl) indexProgressWrapEl.classList.add("hidden");
  if (indexLogsWrapEl) indexLogsWrapEl.classList.remove("hidden"); // keep logs accessible after finish
  if (indexStatusEl) {
    indexStatusEl.textContent = text;
    indexStatusEl.classList.remove("hidden");
    indexStatusEl.style.color = ok ? "rgba(55, 214, 183, 0.9)" : "rgba(255, 91, 106, 0.95)";
  }
  if (indexProgressFillEl) {
    indexProgressFillEl.classList.remove("indeterminate");
    indexProgressFillEl.style.width = ok ? "100%" : "100%";
  }
}

function stopPolling() {
  if (indexPollTimer) {
    clearInterval(indexPollTimer);
    indexPollTimer = null;
  }
}

function startPolling(jobId) {
  stopPolling();
  indexPollTimer = setInterval(async () => {
    try {
      const st = await apiIndexStatus(jobId);
      if (indexLogsEl) indexLogsEl.textContent = st.logs_tail || "";

      if (indexProgressFillEl && indexProgressWrapEl && !indexProgressWrapEl.classList.contains("hidden")) {
        // indeterminate bar; no percentage
        indexProgressFillEl.classList.add("indeterminate");
      }

      if (st.status === "done") {
        showFinalIndexStatus("Indexing selesai ✅", true);
        setIndexBusy(false);
        stopPolling();
      } else if (st.status === "error") {
        showFinalIndexStatus(`Indexing gagal ❌ ${st.error || ""}`, false);
        setIndexBusy(false);
        stopPolling();
      }
    } catch (e) {
      showFinalIndexStatus(`Error polling: ${e.message || e}`, false);
      setIndexBusy(false);
      stopPolling();
    }
  }, 1200);
}

async function runIndex(model) {
  setIndexBusy(true);
  showIndexUI({ running: true });
  if (indexLogsEl) indexLogsEl.textContent = "";
  if (indexLogsWrapEl) indexLogsWrapEl.open = false; // start hidden
  try {
    const start = await apiStartIndex(model);
    activeIndexJobId = start.job_id;
    startPolling(start.job_id);
  } catch (e) {
    showFinalIndexStatus(`Gagal mulai indexing ❌ ${e.message || e}`, false);
    setIndexBusy(false);
  }
}

indexBaselineBtn.addEventListener("click", () => runIndex("Baseline"));
indexVersionBtn.addEventListener("click", () => runIndex("VersionRAG"));

// initial UI
setActiveModelLabel();
setEmptyState(true);
messageInput.focus();

// initialize model UI from native select default
setModelUI(modelSelect.value || "Baseline");

// footer year
if (copyrightYearEl) {
  copyrightYearEl.textContent = String(new Date().getFullYear());
}

// theme (dark/light)
function applyTheme(theme) {
  const isLight = theme === "light";
  document.body.classList.toggle("theme-light", isLight);
  if (themeToggleEl) themeToggleEl.checked = isLight;
  if (brandLogoEl) {
    brandLogoEl.src = isLight ? "/static/logoH.png" : "/static/logo.png";
  }
}

function initTheme() {
  const saved = localStorage.getItem("lexup_theme");
  if (saved === "light" || saved === "dark") {
    applyTheme(saved);
    return;
  }
  // default: follow system preference
  const prefersLight = window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches;
  applyTheme(prefersLight ? "light" : "dark");
}

initTheme();

if (themeToggleEl) {
  themeToggleEl.addEventListener("change", () => {
    const theme = themeToggleEl.checked ? "light" : "dark";
    localStorage.setItem("lexup_theme", theme);
    applyTheme(theme);
  });
}


