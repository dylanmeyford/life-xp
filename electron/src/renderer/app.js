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

// ── Goal graph helpers ───────────────────────────────────────────────

function isDailyGoal(goal) {
  const text = (goal.title + " " + (goal.description || "") + " " + (goal.category || "")).toLowerCase();
  return /per day|daily|every day|each day/.test(text);
}

function parseTargetNum(str) {
  if (!str) return null;
  const m = str.replace(/,/g, "").match(/[\d.]+/);
  const n = m ? parseFloat(m[0]) : NaN;
  return isNaN(n) ? null : n;
}

// 365-day GitHub-style dot grid for daily habits
function renderDotGraph(readings, target) {
  const DAYS = 365, COLS = Math.ceil(DAYS / 7), CELL = 10, GAP = 2, STEP = CELL + GAP;
  const W = COLS * STEP - GAP, H = 7 * STEP - GAP;

  const byDate = {};
  (readings || []).forEach((r) => {
    const v = parseFloat(r.value);
    if (!isNaN(v)) byDate[r.date] = Math.max(byDate[r.date] || 0, v);
  });

  const vals = Object.values(byDate);
  const maxVal = target || (vals.length ? Math.max(...vals) : 1) || 1;
  const todayStr = new Date().toISOString().slice(0, 10);

  let rects = "";
  for (let i = 0; i < DAYS; i++) {
    const d = new Date();
    d.setDate(d.getDate() - (DAYS - 1 - i));
    const dateStr = d.toISOString().slice(0, 10);
    const col = Math.floor(i / 7);
    const row = i % 7;
    const x = col * STEP, y = row * STEP;
    const val = byDate[dateStr];
    const isFuture = dateStr > todayStr;

    let fill;
    if (isFuture) {
      fill = "transparent";
    } else if (val === undefined) {
      fill = "var(--elevated)";
    } else if (target && val >= target) {
      fill = "#22c55e";
    } else if (val > 0) {
      const ratio = Math.min(val / maxVal, 1);
      fill = `rgba(34,197,94,${(0.15 + ratio * 0.75).toFixed(2)})`;
    } else {
      fill = "var(--elevated)";
    }

    const label = val !== undefined ? Number(val).toLocaleString() : "—";
    rects += `<rect x="${x}" y="${y}" width="${CELL}" height="${CELL}" rx="2" fill="${fill}"><title>${dateStr}: ${label}</title></rect>`;
  }

  // Month labels along the top
  let monthLabels = "";
  const months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  let lastMonth = -1;
  for (let col = 0; col < COLS; col++) {
    const d = new Date();
    d.setDate(d.getDate() - (DAYS - 1 - col * 7));
    const m = d.getMonth();
    if (m !== lastMonth) {
      monthLabels += `<text x="${col * STEP}" y="-5" font-size="9" fill="var(--text-3)" font-family="-apple-system,sans-serif">${months[m]}</text>`;
      lastMonth = m;
    }
  }

  return `<svg viewBox="0 0 ${W} ${H + 14}" width="${W}" height="${H + 14}" style="display:block;overflow:visible;margin-top:10px">
    <g transform="translate(0,14)">${monthLabels}${rects}</g>
  </svg>`;
}

// Area sparkline for progress-over-time goals
function renderSparkline(readings) {
  const pts = (readings || [])
    .map((r) => ({ date: r.date, v: parseFloat(r.value) }))
    .filter((p) => !isNaN(p.v))
    .sort((a, b) => a.date.localeCompare(b.date));

  if (pts.length < 2) return null;

  const W = 500, H = 60, PT = 10, PB = 4;
  const iH = H - PT - PB;
  const minV = Math.min(...pts.map((p) => p.v));
  const maxV = Math.max(...pts.map((p) => p.v));
  const rangeV = maxV - minV || 1;

  const mapped = pts.map((p, i) => ({
    x: (i / (pts.length - 1)) * W,
    y: PT + (1 - (p.v - minV) / rangeV) * iH,
  }));

  const line = mapped.map((p, i) => `${i ? "L" : "M"}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ");
  const area = `${line} L${W},${PT + iH} L0,${PT + iH} Z`;
  const gid = `sg${Math.random().toString(36).slice(2, 6)}`;

  return `<svg viewBox="0 0 ${W} ${H}" width="100%" height="${H}" style="display:block">
    <defs>
      <linearGradient id="${gid}" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#3b82f6" stop-opacity="0.2"/>
        <stop offset="100%" stop-color="#3b82f6" stop-opacity="0"/>
      </linearGradient>
    </defs>
    <path d="${area}" fill="url(#${gid})"/>
    <path d="${line}" fill="none" stroke="#3b82f6" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
  </svg>`;
}

window.toggleSubGoals = function (goalId, count) {
  const el = document.getElementById(`rest-${goalId}`);
  const label = document.getElementById(`toggle-label-${goalId}`);
  const open = el.style.display !== "none";
  el.style.display = open ? "none" : "block";
  label.textContent = open
    ? `${count} more milestone${count !== 1 ? "s" : ""}`
    : "Show less";
};

// ── Goals page ──────────────────────────────────────────────────────

async function refreshGoals() {
  const page = document.getElementById("page-goals");

  try {
    const goals = await api("/api/goals?status=active");

    // Fetch daily readings for all goals in parallel
    const readingsArr = await Promise.all(
      goals.map((g) => api(`/api/goals/${g.id}/readings/daily?days=365`).catch(() => []))
    );
    const readingsMap = {};
    goals.forEach((g, i) => { readingsMap[g.id] = readingsArr[i]; });

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
          <h2>No active goals</h2>
          <p>Type a goal above and the AI coach will help you plan and track it automatically.</p>
        </div>
      `;
    } else {
      for (const goal of goals) {
        const readings = readingsMap[goal.id] || [];
        const target = parseTargetNum(goal.target);
        const daily = isDailyGoal(goal);

        // Graph
        let graphHtml = "";
        if (daily) {
          graphHtml = renderDotGraph(readings, target);
        } else {
          graphHtml = renderSparkline(readings) || "";
        }

        // Today's value
        const todayStr = new Date().toISOString().slice(0, 10);
        const todayReading = readings.find((r) => r.date === todayStr);
        const todayVal = todayReading ? parseFloat(todayReading.value) : null;
        const progressLabel = todayVal !== null
          ? `<span class="today-val">${Number(todayVal).toLocaleString()}${target ? `<span class="today-target"> / ${Number(target).toLocaleString()}</span>` : ""}</span>`
          : "";

        // Sub-goals: first visible, rest collapsed
        const subGoals = goal.sub_goals || [];
        const mkItem = (sg) => `
          <li class="sub-goal-item ${sg.status === "completed" ? "completed" : ""}">
            <div class="sub-goal-check">${sg.status === "completed" ? "✓" : ""}</div>
            <span>${sg.title}</span>
            <span class="badge badge-${sg.status}" style="margin-left:auto">${sg.xp_reward} XP</span>
          </li>`;

        const firstSG = subGoals[0];
        const restSG = subGoals.slice(1);

        const subGoalsHtml = firstSG ? `
          <ul class="sub-goals-list">
            ${mkItem(firstSG)}
          </ul>
          ${restSG.length ? `
            <ul class="sub-goals-list" id="rest-${goal.id}" style="display:none">
              ${restSG.map(mkItem).join("")}
            </ul>
            <button class="sub-goals-toggle" onclick="toggleSubGoals(${goal.id}, ${restSG.length})">
              <svg width="11" height="11" viewBox="0 0 11 11" fill="none" style="flex-shrink:0"><path d="M2 4l3.5 3.5L9 4" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/></svg>
              <span id="toggle-label-${goal.id}">${restSG.length} more milestone${restSG.length !== 1 ? "s" : ""}</span>
            </button>` : ""}` : "";

        // Sensor pill
        const sensorLabel = { swift_health: "Apple Health", api: "API", cli: "CLI", manual: "Manual" };
        const sensorHtml = (goal.sensors || [])
          .filter((s) => s.status === "active")
          .map((s) => `<span class="sensor-pill">📡 ${sensorLabel[s.sensor_type] || s.sensor_type}</span>`)
          .join("");

        html += `
          <div class="card" data-goal-id="${goal.id}">
            <div class="card-header">
              <div class="card-title">${goal.title}</div>
              <div style="display:flex;align-items:center;gap:10px">
                ${progressLabel}
                <span class="badge badge-active">${goal.status}</span>
              </div>
            </div>
            ${graphHtml ? `<div class="goal-graph">${graphHtml}</div>` : ""}
            ${subGoalsHtml}
            <div class="card-footer">
              <div style="display:flex;gap:6px;flex-wrap:wrap">${sensorHtml}</div>
              <button class="btn btn-secondary" onclick="openGoalChat(${goal.id})">Coach</button>
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

// ── Deep-link / OAuth handlers ───────────────────────────────────────

if (window.lifeXP?.onDeepLink) {
  window.lifeXP.onDeepLink((url) => {
    // Show a transient "completing auth…" banner while the main process
    // calls /api/oauth/exchange in the background.
    if (url.includes("oauth/callback")) {
      showToast("Completing authentication…", "info");
    }
  });
}

if (window.lifeXP?.onOAuthResult) {
  window.lifeXP.onOAuthResult(async (result) => {
    if (result.ok) {
      showToast("Connected! Sensor is now active.", "success");
      await refreshGoals();
      await refreshStats();
    } else {
      showToast(`OAuth failed: ${result.error || result.detail || "Unknown error"}`, "error");
    }
  });
}

function showToast(message, type = "info") {
  const el = document.createElement("div");
  el.className = `toast toast-${type}`;
  el.textContent = message;
  document.body.appendChild(el);
  // Trigger animation
  requestAnimationFrame(() => el.classList.add("toast-visible"));
  setTimeout(() => {
    el.classList.remove("toast-visible");
    setTimeout(() => el.remove(), 300);
  }, 3500);
}

// ── Init ────────────────────────────────────────────────────────────

async function init() {
  await refreshStats();
  await refreshGoals();
}

init();
