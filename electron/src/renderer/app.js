// ── Life XP — Frontend App ──────────────────────────────────────────
// Vanilla JS — no build step needed. Talks to the Python FastAPI backend.

const API = (window.lifeXP && window.lifeXP.apiBase) || "http://127.0.0.1:5175";

// ── State ───────────────────────────────────────────────────────────

let currentPage = "goals";
let currentGoalId = null;
let chatGoalId = null;

// ── API helpers ─────────────────────────────────────────────────────

async function api(path, options = {}) {
  const url = `${API}${path}`;
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });
  if (!res.ok) throw new Error(`API ${res.status}: ${await res.text()}`);
  return res.json();
}

// ── Navigation ──────────────────────────────────────────────────────

document.querySelectorAll(".nav-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelector(".nav-btn.active")?.classList.remove("active");
    btn.classList.add("active");
    const page = btn.dataset.page;
    document.querySelector(".page.active")?.classList.remove("active");
    document.getElementById(`page-${page}`).classList.add("active");
    currentPage = page;
    refreshPage(page);
  });
});

// ── Player stats ────────────────────────────────────────────────────

async function refreshStats() {
  try {
    const stats = await api("/api/stats");
    document.getElementById("player-level").textContent = `Lv ${stats.level}`;
    document.getElementById("player-title").textContent = stats.title;
    document.getElementById("xp-bar-fill").style.width = `${stats.progress * 100}%`;
    document.getElementById("xp-bar-text").textContent =
      `${stats.xp_current_level} / ${stats.xp_next_level} XP`;
    document.getElementById("total-xp").textContent = `${stats.total_xp} XP`;
  } catch (e) {
    console.error("Failed to fetch stats:", e);
  }
}

// ── XP popup ────────────────────────────────────────────────────────

function showXPPopup(amount) {
  const popup = document.createElement("div");
  popup.className = "xp-popup";
  popup.textContent = `+${amount} XP`;
  document.body.appendChild(popup);
  setTimeout(() => popup.remove(), 2400);
}

// ── Goals page ──────────────────────────────────────────────────────

async function refreshGoals() {
  const page = document.getElementById("page-goals");

  try {
    const goals = await api("/api/goals?status=active");
    let html = `
      <div class="new-goal-area">
        <input class="goal-input" id="new-goal-input"
               placeholder="What's your next goal? e.g. 'Lose weight to 80kg' or 'Read 20 books this year'"
               autocomplete="off" />
      </div>
    `;

    if (goals.length === 0) {
      html += `
        <div class="empty-state">
          <h2>No active goals yet</h2>
          <p>Type a goal above and the AI coach will help you plan and track it automatically.</p>
        </div>
      `;
    } else {
      for (const goal of goals) {
        const subGoalHtml = (goal.sub_goals || [])
          .map(
            (sg) => `
          <li class="sub-goal-item ${sg.status === "completed" ? "completed" : ""}">
            <div class="sub-goal-check">${sg.status === "completed" ? "✓" : ""}</div>
            <span>${sg.title}</span>
            <span class="badge badge-${sg.status}" style="margin-left:auto">${sg.xp_reward} XP</span>
          </li>`
          )
          .join("");

        const sensorLabel = { swift_health: "Apple Health", api: "API", cli: "CLI", manual: "Manual" };
        const sensorHtml = (goal.sensors || [])
          .filter((s) => s.status === "active")
          .map((s) => {
            const label = sensorLabel[s.sensor_type] || s.sensor_type;
            const val = s.last_value && !s.last_value.startsWith("{") && !s.last_value.includes("error")
              ? ` · ${s.last_value}` : "";
            return `<span class="sensor-pill badge-active">📡 ${label}${val}</span>`;
          })
          .join("");

        html += `
          <div class="card" data-goal-id="${goal.id}">
            <div style="display:flex;justify-content:space-between;align-items:start">
              <div>
                <div class="card-title">${goal.title}</div>
                ${goal.target ? `<div class="goal-target">Target: ${goal.target}</div>` : ""}
              </div>
              <span class="badge badge-active">${goal.status}</span>
            </div>
            ${goal.description ? `<div class="card-subtitle">${goal.description}</div>` : ""}
            ${subGoalHtml ? `<ul class="sub-goals-list">${subGoalHtml}</ul>` : ""}
            ${sensorHtml ? `<div class="sensor-pills">${sensorHtml}</div>` : ""}
            <div style="margin-top:12px;display:flex;gap:8px">
              <button class="btn btn-secondary" onclick="openGoalChat(${goal.id})">Chat with Coach</button>
            </div>
          </div>
        `;
      }
    }

    page.innerHTML = html;

    // Bind new goal input
    const input = document.getElementById("new-goal-input");
    if (input) {
      input.addEventListener("keydown", async (e) => {
        if (e.key === "Enter" && input.value.trim()) {
          const text = input.value.trim();
          input.value = "";
          input.disabled = true;
          input.placeholder = "Creating goal and planning with AI coach...";

          try {
            // Create the goal
            const result = await api("/api/goals", {
              method: "POST",
              body: JSON.stringify({
                title: text,
                description: "",
                target: "",
                category: "",
              }),
            });

            // Immediately run the agent to plan it
            const chatResult = await api("/api/chat", {
              method: "POST",
              body: JSON.stringify({
                message: `I just created a new goal: "${text}". Please plan out sub-goals for this, discover the best way to track it automatically, and set up sensors. Ask me questions if you need more info.`,
                goal_id: result.id,
              }),
            });

            // Refresh and switch to chat view for this goal
            await refreshGoals();
            chatGoalId = result.id;
            document.querySelector(".nav-btn.active")?.classList.remove("active");
            document.querySelector('[data-page="chat"]').classList.add("active");
            document.querySelector(".page.active")?.classList.remove("active");
            document.getElementById("page-chat").classList.add("active");
            currentPage = "chat";
            refreshChat(chatResult.messages);

          } catch (err) {
            console.error("Goal creation failed:", err);
            input.disabled = false;
            input.placeholder = `Error: ${err.message}. Try again.`;
          }

          await refreshStats();
        }
      });
    }
  } catch (e) {
    page.innerHTML = `
      <div class="new-goal-area">
        <input class="goal-input" id="new-goal-input" placeholder="What's your next goal?" />
      </div>
      <div class="empty-state">
        <h2>Cannot connect to server</h2>
        <p>Make sure the Life XP server is running: <code>life-xp serve</code></p>
      </div>
    `;
  }
}

function openGoalChat(goalId) {
  chatGoalId = goalId;
  document.querySelector(".nav-btn.active")?.classList.remove("active");
  document.querySelector('[data-page="chat"]').classList.add("active");
  document.querySelector(".page.active")?.classList.remove("active");
  document.getElementById("page-chat").classList.add("active");
  currentPage = "chat";
  refreshChat();
}

// ── Chat page ───────────────────────────────────────────────────────

async function refreshChat(initialMessages = null) {
  const page = document.getElementById("page-chat");

  let messages = initialMessages;
  if (!messages) {
    try {
      const history = await api(`/api/chat/history?limit=50${chatGoalId ? `&goal_id=${chatGoalId}` : ""}`);
      messages = history
        .filter((m) => m.role !== "system")
        .map((m) => ({
          role: m.role,
          content: m.content,
          tool: m.tool_use ? JSON.parse(m.tool_use) : null,
        }));
    } catch {
      messages = [];
    }
  }

  const msgsHtml = messages
    .map((m) => {
      if (m.role === "tool_use") {
        return `
          <div class="chat-msg tool_use">
            <div class="msg-bubble">⚡ ${m.tool}(${JSON.stringify(m.input).slice(0, 100)}...)</div>
          </div>`;
      }
      if (m.role === "question") {
        const opts = (m.options || [])
          .map((o) => `<button class="question-option" onclick="answerQuestion('${o.replace(/'/g, "\\'")}')">${o}</button>`)
          .join("");
        return `
          <div class="chat-msg question">
            <div class="msg-bubble">
              ${m.question}
              ${opts ? `<div class="question-options">${opts}</div>` : ""}
            </div>
          </div>`;
      }
      return `
        <div class="chat-msg ${m.role}">
          <div class="msg-bubble">${formatMessage(m.content || "")}</div>
        </div>`;
    })
    .join("");

  page.innerHTML = `
    <div class="chat-container">
      ${chatGoalId ? `<div style="margin-bottom:12px;color:var(--text-muted);font-size:13px">Coaching goal #${chatGoalId}</div>` : ""}
      <div class="chat-messages" id="chat-messages">${msgsHtml}</div>
      <div class="chat-input-bar">
        <input class="chat-input" id="chat-input" placeholder="Ask your coach anything..." autocomplete="off" />
        <button class="btn btn-primary" id="chat-send">Send</button>
      </div>
    </div>
  `;

  // Scroll to bottom
  const msgsEl = document.getElementById("chat-messages");
  msgsEl.scrollTop = msgsEl.scrollHeight;

  // Bind events
  const input = document.getElementById("chat-input");
  const sendBtn = document.getElementById("chat-send");

  async function sendMessage() {
    const text = input.value.trim();
    if (!text) return;
    input.value = "";

    // Add user message immediately
    appendChatMsg("user", text);

    // Show loading
    const loadingId = appendChatMsg("loading", "");

    try {
      const result = await api("/api/chat", {
        method: "POST",
        body: JSON.stringify({ message: text, goal_id: chatGoalId }),
      });

      // Remove loading
      document.getElementById(loadingId)?.remove();

      // Add response messages
      for (const msg of result.messages || []) {
        if (msg.role === "user" && msg.content === text) continue; // skip echo
        if (msg.role === "tool_use") {
          appendChatMsg("tool_use", `⚡ ${msg.tool}(…)`);
        } else if (msg.role === "question") {
          appendQuestion(msg.question, msg.options || []);
        } else if (msg.role === "assistant") {
          appendChatMsg("assistant", msg.content);
        }
      }

      await refreshStats();
    } catch (err) {
      document.getElementById(loadingId)?.remove();
      appendChatMsg("assistant", `Error: ${err.message}`);
    }
  }

  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") sendMessage();
  });
  sendBtn.addEventListener("click", sendMessage);
}

function appendChatMsg(role, content) {
  const msgsEl = document.getElementById("chat-messages");
  const id = `msg-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;

  if (role === "loading") {
    msgsEl.insertAdjacentHTML(
      "beforeend",
      `<div id="${id}" class="loading-msg"><div class="loading"></div> Thinking...</div>`
    );
  } else {
    msgsEl.insertAdjacentHTML(
      "beforeend",
      `<div class="chat-msg ${role}" id="${id}"><div class="msg-bubble">${formatMessage(content)}</div></div>`
    );
  }
  msgsEl.scrollTop = msgsEl.scrollHeight;
  return id;
}

function appendQuestion(question, options) {
  const msgsEl = document.getElementById("chat-messages");
  const opts = options
    .map((o) => `<button class="question-option" onclick="answerQuestion('${o.replace(/'/g, "\\'")}')">${o}</button>`)
    .join("");
  msgsEl.insertAdjacentHTML(
    "beforeend",
    `<div class="chat-msg question">
      <div class="msg-bubble">
        ${formatMessage(question)}
        ${opts ? `<div class="question-options">${opts}</div>` : ""}
      </div>
    </div>`
  );
  msgsEl.scrollTop = msgsEl.scrollHeight;
}

async function answerQuestion(answer) {
  const input = document.getElementById("chat-input");
  if (input) {
    input.value = answer;
    input.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter" }));
  }
}
// Make it globally accessible
window.answerQuestion = answerQuestion;
window.openGoalChat = openGoalChat;

function formatMessage(text) {
  if (!text) return "";
  // Basic markdown-like formatting
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/\n/g, "<br>");
}

// ── XP page ─────────────────────────────────────────────────────────

async function refreshXP() {
  const page = document.getElementById("page-xp");
  try {
    const history = await api("/api/xp/history?limit=50");
    if (history.length === 0) {
      page.innerHTML = `<div class="empty-state"><h2>No XP earned yet</h2><p>Create a goal and start achieving things!</p></div>`;
      return;
    }

    const entries = history
      .map(
        (e) => `
        <div class="xp-entry">
          <div>
            <span class="xp-amount">+${e.amount}</span>
            <span class="xp-reason">${e.reason || e.source_type}</span>
          </div>
          <span class="xp-time">${new Date(e.created_at).toLocaleString()}</span>
        </div>`
      )
      .join("");

    page.innerHTML = `<h2 style="margin-bottom:20px;font-size:16px;font-weight:600;letter-spacing:-0.01em">XP History</h2><div class="card" style="padding:0">${entries}</div>`;
  } catch {
    page.innerHTML = `<div class="empty-state"><p>Cannot load XP history.</p></div>`;
  }
}

// ── Settings page ───────────────────────────────────────────────────

async function refreshSettings() {
  const page = document.getElementById("page-settings");
  let settings = {};
  try {
    settings = await api("/api/settings");
  } catch {}

  page.innerHTML = `
    <h2 style="margin-bottom:20px">Settings</h2>
    <div class="settings-group">
      <h3>API Configuration</h3>
      <div class="setting-row">
        <span class="setting-label">Anthropic API Key</span>
        <input class="setting-input" type="password" id="setting-api-key"
               value="${settings.anthropic_api_key || ""}"
               placeholder="sk-ant-..." />
      </div>
      <div class="setting-row">
        <span class="setting-label">Model</span>
        <input class="setting-input" id="setting-model"
               value="${settings.model || "claude-sonnet-4-20250514"}"
               placeholder="claude-sonnet-4-20250514" />
      </div>
    </div>
    <div class="settings-group">
      <h3>Sensor Polling</h3>
      <div class="setting-row">
        <span class="setting-label">Poll interval (minutes)</span>
        <input class="setting-input" type="number" id="setting-poll-interval"
               value="${settings.poll_interval || "60"}" />
      </div>
      <div class="setting-row">
        <span class="setting-label">Swift Health Helper</span>
        <button class="btn btn-secondary" id="compile-swift-btn">Compile Helper</button>
      </div>
    </div>
    <div style="margin-top:20px">
      <button class="btn btn-primary" id="save-settings-btn">Save Settings</button>
    </div>
  `;

  document.getElementById("save-settings-btn").addEventListener("click", async () => {
    const keys = [
      ["anthropic_api_key", "setting-api-key"],
      ["model", "setting-model"],
      ["poll_interval", "setting-poll-interval"],
    ];
    for (const [key, id] of keys) {
      const value = document.getElementById(id).value;
      if (value) {
        await api("/api/settings", {
          method: "PUT",
          body: JSON.stringify({ key, value }),
        });
      }
    }
    alert("Settings saved!");
  });
}

// ── Page refresh router ─────────────────────────────────────────────

function refreshPage(page) {
  switch (page) {
    case "goals": return refreshGoals();
    case "chat": return refreshChat();
    case "xp": return refreshXP();
    case "settings": return refreshSettings();
  }
}

// ── Init ────────────────────────────────────────────────────────────

async function init() {
  await refreshStats();
  await refreshGoals();
}

init();
