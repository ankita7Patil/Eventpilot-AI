

// Auth check — redirect to login if not signed in
(function() {
  const name = localStorage.getItem("EP_USER_NAME");
  const email = localStorage.getItem("EP_USER_EMAIL");
  if (!name || !email) {
    window.location.href = "login.html";
  }
  // Show user in UI
  document.addEventListener("DOMContentLoaded", () => {
    const sidebar = document.querySelector(".side-panel");
    if (sidebar && name) {
      const div = document.createElement("div");
      div.style.cssText = "margin-top:12px;padding:8px 12px;background:rgba(255,255,255,0.05);border-radius:8px;font-size:13px;";
      div.innerHTML = `<span style="color:#4ade80">●</span> <strong style="color:#fff">${name}</strong><br><span style="color:#888;font-size:11px;cursor:pointer;" onclick="localStorage.removeItem('EP_USER_NAME');localStorage.removeItem('EP_USER_EMAIL');location.href='login.html'">Sign out</span>`;
      sidebar.appendChild(div);
    }
  });
})();

// Deadline notification scheduler
function scheduleDeadlineAlerts(event) {
  const deadlines = event?.briefing?.deadlines || [];
  if (!deadlines.length || Notification.permission !== "granted") return;

  // Immediate alert
  new Notification(`⚡ ${event.title || "Event"} tracked!`, {
    body: `${deadlines.length} deadline(s) found. Urgent: ${deadlines[0]?.time || "Check event page"}`,
  });

  // Parse deadline date and schedule reminder
  deadlines.forEach(dl => {
    const dateStr = dl.time;
    if (!dateStr || dateStr.toLowerCase().includes("check")) return;

    const deadlineDate = new Date(dateStr);
    if (isNaN(deadlineDate)) return;

    const now = new Date();
    const oneDayBefore = new Date(deadlineDate.getTime() - 24 * 60 * 60 * 1000);
    const oneHourBefore = new Date(deadlineDate.getTime() - 60 * 60 * 1000);

    const msTo24h = oneDayBefore - now;
    const msTo1h = oneHourBefore - now;

    if (msTo24h > 0 && msTo24h < 7 * 24 * 60 * 60 * 1000) {
      setTimeout(() => {
        new Notification(`🚨 Tomorrow: ${dl.label}`, {
          body: `Deadline: ${dl.time} — Don't forget to submit!`,
        });
      }, msTo24h);
    }

    if (msTo1h > 0 && msTo1h < 24 * 60 * 60 * 1000) {
      setTimeout(() => {
        new Notification(`🔴 1 Hour Left: ${dl.label}`, {
          body: `Deadline at ${dl.time} — Submit NOW!`,
        });
      }, msTo1h);
    }
  });
}
const API_BASE =
  window.EVENTPILOT_API_URL ||
  localStorage.getItem("EVENTPILOT_API_URL") ||
  "http://127.0.0.1:8000";

const AGENT_DEFINITIONS = [
  ["Monitor Agent", "Scrapes event pages and detects current opportunity signals."],
  ["Research Agent", "Routes scraped content through the AI briefing workflow."],
  ["Recommendation Agent", "Ranks strategies, sponsor tracks, and project ideas."],
  ["Scheduling Agent", "Builds timeline state from extracted dates and deadlines."],
  ["Alert Agent", "Creates proactive reminders from priority event actions."]
];

let activeEventId = localStorage.getItem("EVENTPILOT_ACTIVE_EVENT_ID") || "";
let activeEvent = null;

const $ = (selector) => document.querySelector(selector);

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => {
    const map = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" };
    return map[char];
  });
}

function setLoading(isLoading, message = "") {
  $("#analyzeButton").disabled = isLoading;
  $("#refreshWorkflowBtn").disabled = isLoading || !activeEvent;
  $("#analyzeButton").textContent = isLoading ? "Analyzing..." : "Analyze";
  if (message) renderStatus(message);
}

function renderStatus(message, type = "info") {
  $("#activityFeed").innerHTML = `<div class="activity-item ${type}">${escapeHtml(message)}</div>`;
}

function emptyState() {
  $("#eventTitle").textContent = "No event analyzed yet";
  $("#eventSummary").textContent = "Paste a Luma, Devfolio, Unstop, internship, or competition URL to start the autonomous workflow.";
  $("#urgencyBadge").textContent = "Waiting";
  $("#briefingList").innerHTML = "";
  $("#nextAction").innerHTML = `<div class="action-step">Add an event link to run monitor, research, recommendation, scheduling, and alert agents.</div>`;
  $("#agentGrid").innerHTML = AGENT_DEFINITIONS.map(
    ([name, detail]) => `<div class="agent-card"><strong>${name}</strong><p>${detail}</p></div>`
  ).join("");
  $("#timelineList").innerHTML = "";
  $("#strategyGrid").innerHTML = "";
  $("#activityFeed").innerHTML = `<div class="activity-item">Workflow output will appear here after the backend agents run.</div>`;
  $("#eventCount").textContent = "0";
  $("#urgentCount").textContent = "0";
  $("#agentCount").textContent = String(AGENT_DEFINITIONS.length);
  $("#deadlineClock").textContent = "None";
  $("#chatLog").innerHTML = `<div class="message ai">Analyze an event first, then ask about deadlines, tracks, preparation, or strategy.</div>`;
  $("#refreshWorkflowBtn").disabled = true;
}

function renderEvent(event) {
  activeEvent = event;
  activeEventId = event.id;
  localStorage.setItem("EVENTPILOT_ACTIVE_EVENT_ID", event.id);

  const briefing = event.briefing || {};
  const activities = event.activities || [];
  const deadlines = briefing.deadlines || [];
  const timeline = briefing.timeline || [];
  const recommendations = briefing.recommendations || [];
  const suggestions = briefing.project_suggestions || [];
  const checklist = briefing.preparation_checklist || [];
  const facts = briefing.facts || [];
  const reminders = briefing.reminders || [];

  $("#eventTitle").textContent = event.title || briefing.title || "Analyzed opportunity";
  $("#eventSummary").textContent = briefing.summary || "The backend analyzed this event, but no summary was returned.";
  $("#urgencyBadge").textContent = `${briefing.urgency || "medium"} urgency`;
  $("#eventCount").textContent = "1";
  $("#urgentCount").textContent = String(reminders.length || deadlines.length || checklist.length);
  $("#agentCount").textContent = String(AGENT_DEFINITIONS.length);
  $("#deadlineClock").textContent = deadlineLabel(deadlines, timeline);
  $("#refreshWorkflowBtn").disabled = false;

  $("#briefingList").innerHTML = facts.map(
    (item) => `<div class="info-item"><strong>${escapeHtml(item.label)}</strong><p>${escapeHtml(item.value)}</p></div>`
  ).join("") || `<div class="info-item"><strong>Source</strong><p>${escapeHtml(event.source_url)}</p></div>`;

  $("#nextAction").innerHTML = checklist.map(
    (item) => `<div class="action-step">${escapeHtml(item)}</div>`
  ).join("") || `<div class="action-step">Review the extracted timeline and choose the highest-priority reminder.</div>`;

  $("#agentGrid").innerHTML = AGENT_DEFINITIONS.map(([name, detail]) => {
    const activity = activities.find((item) => item.agent_name === name);
    const status = activity ? activity.action : detail;
    return `<div class="agent-card"><strong>${name}</strong><p>${escapeHtml(status)}</p></div>`;
  }).join("");

  $("#activityFeed").innerHTML = activities.map(
    (item) => `<div class="activity-item"><strong>${escapeHtml(item.agent_name)}</strong><br>${escapeHtml(item.action)}</div>`
  ).join("") || `<div class="activity-item">No activity logs returned.</div>`;

  $("#timelineList").innerHTML = timeline.map(
    (item) => `<div class="timeline-item"><div class="timeline-time">${escapeHtml(item.time)}</div><div><strong>${escapeHtml(item.title)}</strong><p>${escapeHtml(item.detail)}</p></div></div>`
  ).join("") || `<div class="timeline-item"><div class="timeline-time">No dates</div><div><strong>No timeline extracted</strong><p>Add a richer event page or configure an LLM provider for deeper extraction.</p></div></div>`;

  const strategyItems = [
    ...recommendations.map((item) => ({
      label: item.name,
      value: `${item.reason || ""}${item.score ? ` Score: ${item.score}` : ""}`
    })),
    ...suggestions.map((item) => ({
      label: item.name,
      value: `${item.why || ""}${item.stack ? ` Stack: ${item.stack}` : ""}`
    }))
  ];

  $("#strategyGrid").innerHTML = strategyItems.map(
    (item) => `<div class="strategy-item"><strong>${escapeHtml(item.label)}</strong><p>${escapeHtml(item.value)}</p></div>`
  ).join("") || `<div class="strategy-item"><strong>Strategy pending</strong><p>The recommendation workflow did not return strategy items.</p></div>`;

  $("#chatLog").innerHTML = `<div class="message ai">This event is tracked. Ask me what is urgent, which track to choose, or what to prepare.</div>`;
}

function deadlineLabel(deadlines, timeline) {
  const firstDeadline = deadlines.find((item) => item.time)?.time;
  if (firstDeadline) return firstDeadline;
  const firstTimeline = timeline.find((item) => item.time)?.time;
  return firstTimeline || "Unknown";
}

async function analyzeUrl(url) {
  setLoading(true, "Running autonomous workflow: scraping page, researching content, deciding priorities, and creating reminders...");
  try {
    const response = await fetch(`${API_BASE}/api/events/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        url,
        user_id: "demo-user",
        user_goal: "Manage this opportunity and recommend the best next actions."
      })
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || `API error ${response.status}`);
    }
    renderEvent(await response.json());
  } catch (error) {
    renderStatus(`Analysis failed: ${error.message}. Make sure the FastAPI backend is running and the URL is reachable.`, "error");
  } finally {
    setLoading(false);
  }
}
  // Notification
if (Notification.permission === "granted") {
  new Notification("⚡ EventPilot Alert!", {
    body: "Event analyzed! Check your deadlines."
  });
} else {
  Notification.requestPermission().then(p => {
    if (p === "granted") {
      new Notification("⚡ EventPilot Alert!", {
        body: "Event analyzed! Check your deadlines."
      });
    }
  });
}

async function loadEvent(eventId) {
  if (!eventId) return;
  try {
    const response = await fetch(`${API_BASE}/api/events/${eventId}`);
    if (response.ok) renderEvent(await response.json());
  } catch {
    emptyState();
  }
}

async function askChat(message) {
  $("#chatLog").innerHTML += `<div class="message user">${escapeHtml(message)}</div>`;
  try {
    const response = await fetch(`${API_BASE}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, event_id: activeEventId, user_id: "demo-user" })
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || `API error ${response.status}`);
    }
    const data = await response.json();
    $("#chatLog").innerHTML += `<div class="message ai">${escapeHtml(data.answer)}</div>`;
  } catch (error) {
    $("#chatLog").innerHTML += `<div class="message ai">Chat failed: ${escapeHtml(error.message)}.</div>`;
  }
  $("#chatLog").scrollTop = $("#chatLog").scrollHeight;
}

$("#eventForm").addEventListener("submit", (event) => {
  event.preventDefault();
  const url = $("#eventUrl").value.trim();
  if (!url) {
    renderStatus("Paste a full event URL first.", "error");
    return;
  }
  analyzeUrl(url);
});

$("#refreshWorkflowBtn").addEventListener("click", () => {
  const url = activeEvent?.source_url || $("#eventUrl").value.trim();
  if (url) analyzeUrl(url);
});

$("#chatForm").addEventListener("submit", (event) => {
  event.preventDefault();
  const input = $("#chatInput");
  const question = input.value.trim();
  if (!question) return;
  input.value = "";
  askChat(question);
});

emptyState();
loadEvent(activeEventId);
// ─── ALERTS / NOTIFICATIONS ───────────────────────
async function requestNotificationPermission() {
  if ("Notification" in window) {
    const permission = await Notification.requestPermission();
    return permission === "granted";
  }
  return false;
}

function sendAlert(title, body) {
  if (Notification.permission === "granted") {
    new Notification(title, {
      body: body,
      icon: "https://cdn-icons-png.flaticon.com/512/1827/1827312.png"
    });
  }
}

function scheduleDeadlineAlerts(event) {
  const deadlines = event?.briefing?.deadlines || [];
  if (Notification.permission !== "granted") {
    Notification.requestPermission().then(p => {
      if (p === "granted") scheduleDeadlineAlerts(event);
    });
    return;
  }

  // Immediate notification
  new Notification(`⚡ EventPilot: ${event.title || "Event"} tracked!`, {
    body: deadlines.length
      ? `🔴 Urgent: ${deadlines[0]?.label} — ${deadlines[0]?.time}`
      : "Event is being monitored by your agents.",
    icon: "https://cdn-icons-png.flaticon.com/512/1827/1827312.png"
  });

  // 30 second reminder (for demo)
  setTimeout(() => {
    new Notification(`🔔 EventPilot Reminder`, {
      body: `Don't miss: ${event.title} — Check your deadlines now!`,
      icon: "https://cdn-icons-png.flaticon.com/512/1827/1827312.png"
    });
  }, 30000);
}

// ─── SIMPLE USER SIGN IN ───────────────────────────
function initUserSession() {
  let userName = localStorage.getItem("EVENTPILOT_USER_NAME");
  
  if (!userName) {
    userName = prompt("👋 Welcome to EventPilot! Enter your name to get started:") || "Developer";
    localStorage.setItem("EVENTPILOT_USER_NAME", userName);
  }
  
  // Show user name in sidebar
  const sidebar = document.querySelector(".side-panel");
  if (sidebar) {
    const userDiv = document.createElement("div");
    userDiv.style.cssText = "margin-top:12px; padding:8px 12px; background:rgba(255,255,255,0.05); border-radius:8px; font-size:13px;";
    userDiv.innerHTML = `
      <span style="color:#4ade80">●</span> 
      <strong style="color:#fff">${userName}</strong>
      <span style="color:#888; font-size:11px; margin-left:4px;">signed in</span>
      <br>
      <span style="color:#888; font-size:11px; cursor:pointer;" onclick="localStorage.removeItem('EVENTPILOT_USER_NAME'); location.reload()">Sign out</span>
    `;
    sidebar.appendChild(userDiv);
  }
  
  return userName;
}

// ─── INIT ──────────────────────────────────────────
const currentUser = initUserSession();
requestNotificationPermission();

// Override renderEvent to add alerts
const _originalRenderEvent = renderEvent;
window.renderEvent = function(event) {
  _originalRenderEvent(event);
  scheduleAlerts(event);
};
scheduleDeadlineAlerts(event);

// ── FEATURE 1: Live Countdown Timer ──────────────
function startCountdown(event) {
  const deadlines = event?.briefing?.deadlines || [];
  const clockEl = document.getElementById("deadlineClock");
  if (!clockEl || !deadlines.length) return;

  const dateStr = deadlines[0]?.time;
  if (!dateStr || dateStr.toLowerCase().includes("check")) return;

  const deadline = new Date(dateStr);
  if (isNaN(deadline)) return;

  setInterval(() => {
    const now = new Date();
    const diff = deadline - now;
    if (diff <= 0) { clockEl.textContent = "DEADLINE PASSED"; return; }

    const days = Math.floor(diff / (1000 * 60 * 60 * 24));
    const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
    const mins = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
    const secs = Math.floor((diff % (1000 * 60)) / 1000);

    clockEl.textContent = `${days}d ${hours}h ${mins}m ${secs}s`;
    clockEl.style.color = diff < 3600000 ? "#ef4444" : diff < 86400000 ? "#f59e0b" : "#4ade80";
  }, 1000);
}

// ── FEATURE 2: Export to Calendar (.ics) ─────────
function exportToCalendar(event) {
  const deadlines = event?.briefing?.deadlines || [];
  const title = event?.title || "Event";

  let icsContent = `BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//EventPilot AI//EN\n`;

  deadlines.forEach((dl, i) => {
    const dateStr = dl.time;
    const d = new Date(dateStr);
    if (isNaN(d)) return;

    const fmt = d => d.toISOString().replace(/[-:]/g, "").split(".")[0] + "Z";
    const end = new Date(d.getTime() + 3600000);

    icsContent += `BEGIN:VEVENT\nUID:eventpilot-${i}@ai\nSUMMARY:${title} — ${dl.label}\nDTSTART:${fmt(d)}\nDTEND:${fmt(end)}\nDESCRIPTION:Tracked by EventPilot AI\nBEGIN:VALARM\nTRIGGER:-PT24H\nACTION:DISPLAY\nDESCRIPTION:Reminder: ${dl.label}\nEND:VALARM\nEND:VEVENT\n`;
  });

  icsContent += `END:VCALENDAR`;

  const blob = new Blob([icsContent], { type: "text/calendar" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `${title.replace(/\s+/g, "_")}_deadlines.ics`;
  a.click();
}

// ── FEATURE 3: Add Export Button to UI ───────────
function addExportButton(event) {
  const existing = document.getElementById("exportCalBtn");
  if (existing) existing.remove();

  const btn = document.createElement("button");
  btn.id = "exportCalBtn";
  btn.textContent = "📅 Export to Calendar";
  btn.style.cssText = `
    margin-top: 12px; width: 100%; padding: 10px 16px;
    background: rgba(99,102,241,0.15); border: 1px solid rgba(99,102,241,0.4);
    border-radius: 10px; color: #818cf8; font-size: 13px; font-weight: 500;
    cursor: pointer; transition: background 0.2s;
  `;
  btn.onmouseover = () => btn.style.background = "rgba(99,102,241,0.25)";
  btn.onmouseout = () => btn.style.background = "rgba(99,102,241,0.15)";
  btn.onclick = () => exportToCalendar(event);

  const nextAction = document.getElementById("nextAction");
  if (nextAction) nextAction.after(btn);
}

// ── HOOK INTO renderEvent ─────────────────────────
const _origRender = renderEvent;
window.renderEvent = function(event) {
  _origRender(event);
  scheduleDeadlineAlerts(event);
  startCountdown(event);
  addExportButton(event);
};
