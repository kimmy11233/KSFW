// --- Configurable endpoints ---
const API_BASE = "/api";

// --- DOM Elements ---
const messagesDiv = document.getElementById("messages");
const agentList = document.getElementById("agent-list");
const lastResponseTime = document.getElementById("last-response-time");
const storyImage = document.getElementById("story-image");
const promptForm = document.getElementById("prompt-form");
const promptInput = document.getElementById("prompt-input");
const promptSend = document.getElementById("prompt-send");
const promptRestore = document.getElementById("prompt-restore");
const storyTitleDiv = document.getElementById("story-title");
const turnValueSpan = document.getElementById("turn-value");
const plannerThinking = document.getElementById("planner-thinking");

// If for whatever reason (missing image) we can't load an image, just hide it
storyImage.addEventListener('load', () => { storyImage.style.display = ''; });
storyImage.addEventListener('error', () => { storyImage.style.display = 'hidden'; });

// Example: updateStoryInfo('My Story', 5)
function updateStoryInfo(title, turn) {
    if (storyTitleDiv) storyTitleDiv.textContent = title;
    if (turnValueSpan) turnValueSpan.textContent = (turn + '').padStart(1, ' ');
}


// Handle Enter/Shift+Enter for textarea
promptInput.addEventListener("keydown", function(e) {
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        promptForm.requestSubmit();
    }
});

// --- State ---
let lastTimestamp = null;
let isStreaming = false;
// Track agent status for disabling send
let agentStatus = [];
// Stagger counter for diff insert animations — reset each correction
let diffInsertIndex = 0;

// --- Fetch Functions ---
async function fetchMessages() {
    try {
        const res = await fetch(`${API_BASE}/messages`);
        if (!res.ok) return [];
        return await res.json();
    } catch (e) {
        console.error("fetchMessages error", e);
        return [];
    }
}

async function fetchAgents() {
    try {
        const res = await fetch(`${API_BASE}/agents`);
        if (!res.ok) return [];
        return await res.json();
    } catch (e) {
        console.error("fetchAgents error", e);
        return [];
    }
}

async function fetchImage() {
    try {
        const res = await fetch(`${API_BASE}/image`);
        if (!res.ok) return "";
        const data = await res.json();
        return data.image_url;
    } catch (e) {
        console.error("fetchImage error", e);
        return "";
    }
}

// --- Render Functions ---
function renderMessages(data) {
    const messages = data.messages;
    const _ = data.memory;
    const title = data.title;
    const turn_number = data.turn_number;

    updateStoryInfo(title, turn_number);

    messagesDiv.innerHTML = "";
    if (!messages || messages.length === 0) {
        return;
    }
    for (let i = 0; i < messages.length; i++) {
        const msg = messages[i];
        if (!msg) continue;
        let msgDiv, contentDiv;
        if (msg.agent_name === "User") {
            // User message
            msgDiv = document.createElement("div");
            msgDiv.className = "message user-message";
            contentDiv = document.createElement("div");
            contentDiv.className = "message-content";
            contentDiv.textContent = msg.content;
            msgDiv.appendChild(contentDiv);
        } else {
            // System message with pink vertical bar
            msgDiv = document.createElement("div");
            msgDiv.className = "message system-message";
            contentDiv = document.createElement("div");
            contentDiv.className = "message-content";
            contentDiv.textContent = msg.content;
            msgDiv.appendChild(contentDiv);
        }
        messagesDiv.appendChild(msgDiv);
        // Grey horizontal bar below every message
        let greyBarDiv = document.createElement("div");
        greyBarDiv.className = "horizontal-bar grey";
        messagesDiv.appendChild(greyBarDiv);
    }
}

function renderAgents(agents) {
    agentList.innerHTML = "";
    agentStatus = agents;
    if (!Array.isArray(agents) || agents.length === 0) { return; }
    agents.forEach(agent => {
        const li = document.createElement("li");
        li.className = "agent-item";
 
        // Status dot
        const dot = document.createElement("span");
        dot.className = `agent-dot ${agent.status}`;
        li.appendChild(dot);
 
        // Agent name + response time
        const timeText = agent.last_response_time ? ` - ${parseFloat(agent.last_response_time).toFixed(2)}s` : "";
        const nameSpan = document.createElement("span");
        nameSpan.className = "agent-name";
        nameSpan.textContent = `${agent.name}${timeText}`;
        li.appendChild(nameSpan);
 
        // Token usage row (only shown after first response)
        if (agent.last_usage) {
            const { prompt_tokens, completion_tokens, total_tokens, context_pct } = agent.last_usage;
            const pct = context_pct ?? 0;
 
            const tokenRow = document.createElement("div");
            tokenRow.className = "agent-token-row";
 
            // Circle filled proportionally to context usage via conic-gradient
            const ctxCircle = document.createElement("span");
            ctxCircle.className = "agent-ctx-circle";
            ctxCircle.title = `${pct}% of context window used`;
            ctxCircle.style.background =
                `conic-gradient(var(--accent) ${pct}%, var(--bar) ${pct}%)`;
            tokenRow.appendChild(ctxCircle);
 
            // "1,234 tokens (2.4%)"
            const tokenText = document.createElement("span");
            tokenText.className = "agent-token-text";
            tokenText.textContent = `${total_tokens.toLocaleString()} tokens (${pct}%)`;
            tokenText.title = `Prompt: ${prompt_tokens.toLocaleString()}  Completion: ${completion_tokens.toLocaleString()}`;
            tokenRow.appendChild(tokenText);
 
            li.appendChild(tokenRow);
        }
 
        li.dataset.agentId = agent.id;
        agentList.appendChild(li);
    });
    updatePromptSendState(agentStatus);
    updatePlannerIndicator(agentStatus);
}

function updatePromptSendState(agentStatus) {
    if (!storyReady) return; // keep locked until story is selected
    // Disable if any critical agent is busy or errored
    let disable = false;
    if (Array.isArray(agentStatus)) {
        for (const agent of agentStatus) {
            if ((agent.status === "busy" || agent.status === "errored")) {
                disable = true;
                break;
            }
        }
    }
    if (typeof promptSend !== 'undefined' && promptSend) {
        promptSend.disabled = disable;
        promptSend.style.opacity = disable ? 0.5 : 1;
    }
    if (typeof promptRestore !== 'undefined' && promptRestore) {
        promptRestore.disabled = disable;
    }
}


function updatePlannerIndicator(agentStatus) {
    if (!plannerThinking || !Array.isArray(agentStatus)) return;
    const isBusy = agentStatus.some(a => a.status === "busy");
    const showPlanning = !isStreaming && isBusy;
    plannerThinking.classList.toggle("planner-hidden", !showPlanning);
}


function renderImage(url) {
    storyImage.src = url || "";
}

async function pollAll() {
    
    const [messages, agents, imageUrl] = await Promise.all([
        fetchMessages(),
        fetchAgents(),
        fetchImage(),
    ]);
    
    renderAgents(agents);
    renderImage(imageUrl);

    updateStoryInfo(messages.title, messages.turn_number);
        
}

// --- Story selection gate ---
// Polling and input are blocked until a story is confirmed loaded/created.
let storyReady = false;
let pollInterval = null;

function startPolling() {
    if (pollInterval) return; // already running
    storyReady = true;
    pollAll();
    pollInterval = setInterval(pollAll, 2000);
    // Unlock the prompt form
    promptSend.disabled = false;
    promptSend.style.opacity = 1;
    promptInput.disabled = false;
    promptRestore.disabled = false;
}

// Lock prompt form until a story is ready
promptSend.disabled = true;
promptSend.style.opacity = 0.5;
promptInput.disabled = true;
promptRestore.disabled = true;

// Open the Manage Stories modal immediately on load
window.addEventListener("DOMContentLoaded", () => {
    openModal("modal-stories");
    // Trigger the load tab fetch via the existing IIFE logic
    document.getElementById("btn-stories").dispatchEvent(new Event("_autoopen"));
});

// Apply as many complete newline-delimited JSON diff events as are in buf.
// Returns the remaining incomplete line.
function applyDiffLines(buf, container) {
    const lines = buf.split("\n");
    const remaining = lines.pop();
    for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) continue;
        let event;
        try { event = JSON.parse(trimmed); } catch { continue; }
        applyDiffEvent(event, container);
    }
    return remaining;
}

// Apply a single diff event. Deletes are silently dropped — the corrected
// text is shown via inserts only. Equal ops render as plain text.
function applyDiffEvent(event, container) {
    if (event.op === "equal") {
        const span = document.createElement("span");
        span.textContent = event.text;
        container.appendChild(span);
    } else if (event.op === "insert") {
        const span = document.createElement("span");
        span.textContent = event.text;
        span.className = "diff-insert";
        // Stagger each insert token so corrections animate in sequentially
        span.style.animationDelay = `${diffInsertIndex * 25}ms`;
        container.appendChild(span);
        diffInsertIndex++;
    }
    // delete ops are intentionally ignored — removed text simply disappears
}

promptForm.addEventListener("submit", async (e) => {
    e.preventDefault();

    const prompt = promptInput.value.trim();
    if (!prompt) return;
    if (promptSend.disabled) return;

    isStreaming = true;

    // Show planner indicator immediately — don't wait for first poll
    if (plannerThinking) plannerThinking.classList.remove("planner-hidden");

    // Add user message (no tag, left justified)
    const userDiv = document.createElement("div");
    userDiv.className = "message user-message";
    const userContent = document.createElement("div");
    userContent.className = "message-content";
    userContent.textContent = prompt;
    userDiv.appendChild(userContent);

    // Ensure a bottom spacer exists and is tall enough that even the last message
    // in the list has room to scroll up to the top of the viewport.
    let spacer = document.getElementById("messages-bottom-spacer");
    if (!spacer) {
        spacer = document.createElement("div");
        spacer.id = "messages-bottom-spacer";
        messagesDiv.appendChild(spacer);
    }
    spacer.style.height = messagesDiv.clientHeight + "px";

    // Insert before the spacer so the spacer stays pinned at the bottom.
    messagesDiv.insertBefore(userDiv, spacer);

    // Now that the spacer guarantees scroll room, scrollIntoView works correctly.
    // block:"start" aligns the top of the user message with the top of the viewport.
    requestAnimationFrame(() => {
        userDiv.scrollIntoView({ block: "start", behavior: "smooth" });
    });

    // Grey horizontal bar below user message
    let userGreyBarDiv = document.createElement("div");
    userGreyBarDiv.className = "horizontal-bar grey";
    messagesDiv.insertBefore(userGreyBarDiv, spacer);

    // Add placeholder for streaming system message — no scroll, let it naturally appear below
    const sysDiv = document.createElement("div");
    sysDiv.className = "message system-message";
    const sysContent = document.createElement("div");
    sysContent.className = "message-content";
    sysDiv.appendChild(sysContent);
    messagesDiv.insertBefore(sysDiv, spacer);

    promptInput.value = "";

    // Stream response from backend
    const res = await fetch(`${API_BASE}/prompt`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt })
    });
    if (!res.body) {
        sysContent.textContent = "[No response]";
        isStreaming = false;
        return;
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let lineBuffer = "";
    let diffMode = false;

    while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        const raw = decoder.decode(value, { stream: true });

        if (!diffMode) {
            // Phase 1: plain text — watch for the diff_start sentinel
            const sentinelIdx = raw.indexOf('{"op": "diff_start"}');
            if (sentinelIdx === -1) {
                sysContent.textContent += raw;
            } else {
                // Append prose that arrived before the sentinel
                if (sentinelIdx > 0) sysContent.textContent += raw.slice(0, sentinelIdx);
                // Switch to diff mode — clear content, rebuild from diff spans
                diffMode = true;
                diffInsertIndex = 0;
                sysContent.textContent = "";
                lineBuffer += raw.slice(sentinelIdx + '{"op": "diff_start"}'.length);
                lineBuffer = applyDiffLines(lineBuffer, sysContent);
            }
        } else {
            lineBuffer += raw;
            lineBuffer = applyDiffLines(lineBuffer, sysContent);
        }
    }



    isStreaming = false;
    // Only poll after streaming is done
    pollAll();
});
// --- Modal helpers ---
function isInputLocked() {
    return promptSend && promptSend.disabled;
}

function openModal(modalId) {
    const el = document.getElementById(modalId);
    if (el) { el.setAttribute("aria-hidden", "false"); el.classList.add("open"); }
}

function closeModal(modalId) {
    const el = document.getElementById(modalId);
    if (el) { el.setAttribute("aria-hidden", "true"); el.classList.remove("open"); }
}

// --- Toast ---
let toastTimer = null;
function showToast(msg, durationMs = 3000) {
    const toast = document.getElementById("toast");
    toast.textContent = msg;
    toast.classList.remove("toast-hidden");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.add("toast-hidden"), durationMs);
}

// --- Restore from backup ---
promptRestore.addEventListener("click", async () => {
    if (promptRestore.disabled) return;

    promptRestore.disabled = true;
    promptSend.disabled = true;

    try {
        const res = await fetch(`${API_BASE}/restore_from_backup`, { method: "POST" });

        if (res.status === 404) {
            showToast("No backups found.");
            return;
        }
        if (!res.ok) {
            const data = await res.json().catch(() => ({}));
            showToast(`Restore failed: ${data.error ?? res.statusText}`);
            return;
        }

        // Success — re-render messages and scroll to bottom
        const data = await fetchMessages();
        renderMessages(data);
        requestAnimationFrame(() => {
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        });
        await pollAll();

    } catch (e) {
        showToast(`Restore error: ${e.message}`);
    } finally {
        // Re-enable based on current agent state
        updatePromptSendState(agentStatus);
    }
});

document.querySelectorAll(".modal-overlay").forEach(overlay => {
    overlay.addEventListener("click", (e) => { if (e.target === overlay) closeModal(overlay.id); });
});
document.querySelectorAll(".modal-close").forEach(btn => {
    btn.addEventListener("click", () => closeModal(btn.dataset.modal));
});

// --- Inventory modal ---
function setInventoryViewMode(content) {
    document.getElementById("inventory-display").textContent = content || "(empty)";
    document.getElementById("inventory-display").style.display = "";
    document.getElementById("inventory-edit").style.display = "none";
    document.getElementById("inventory-edit-btn").style.display = "";
    document.getElementById("inventory-save-btn").style.display = "none";
    document.getElementById("inventory-cancel-btn").style.display = "none";
}
function setInventoryEditMode(content) {
    document.getElementById("inventory-display").style.display = "none";
    const ta = document.getElementById("inventory-edit");
    ta.value = content || "";
    ta.style.display = "";
    document.getElementById("inventory-edit-btn").style.display = "none";
    document.getElementById("inventory-save-btn").style.display = "";
    document.getElementById("inventory-cancel-btn").style.display = "";
    ta.focus();
}

document.getElementById("btn-inventory").addEventListener("click", async () => {
    openModal("modal-inventory");
    updateInventoryEditBtnState();
    const data = await fetchMessages();
    setInventoryViewMode(data.inventory || "");
});
document.getElementById("inventory-edit-btn").addEventListener("click", () => {
    if (isInputLocked()) return;
    const current = document.getElementById("inventory-display").textContent;
    setInventoryEditMode(current === "(empty)" ? "" : current);
});

function updateInventoryEditBtnState() {
    const btn = document.getElementById("inventory-edit-btn");
    if (!btn) return;
    const locked = isInputLocked();
    btn.disabled = locked;
    btn.style.opacity = locked ? 0.5 : 1;
    btn.title = locked ? "Can't edit while mid turn" : "";
}
document.getElementById("inventory-cancel-btn").addEventListener("click", async () => {
    const data = await fetchMessages();
    setInventoryViewMode(data.inventory || "");
});
document.getElementById("inventory-save-btn").addEventListener("click", async () => {
    if (isInputLocked()) return;
    const newVal = document.getElementById("inventory-edit").value;
    const saveBtn = document.getElementById("inventory-save-btn");
    const footer = saveBtn.closest(".modal-footer");
    let indicator = footer.querySelector(".modal-saving");
    if (!indicator) {
        indicator = document.createElement("span");
        indicator.className = "modal-saving";
        indicator.textContent = "Saving\u2026";
        footer.insertBefore(indicator, footer.firstChild);
    }
    saveBtn.disabled = true;
    try {
        await fetch(`${API_BASE}/overwrite_inventory`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ inventory: newVal })
        });
        setInventoryViewMode(newVal);
    } catch (e) { console.error("Failed to save inventory", e); }
    finally { indicator.remove(); saveBtn.disabled = false; }
});

// --- Memory modal ---
(function () {
    // Section definitions — order controls tab order
    const SECTIONS = [
        { key: "current_state", label: "Current State", type: "text" },
        { key: "characters_raw", label: "Characters",   type: "text" },
        { key: "rules",         label: "Rules",         type: "text" },
        { key: "facts",         label: "Facts",         type: "list" },
        { key: "events",        label: "Events",        type: "list" },
    ];

    let memoryData = {};       // live copy of the memory object from the API
    let activeSection = SECTIONS[0].key;
    let editingSection = null; // key of section currently being edited, or null

    // ── Build tab bar ──────────────────────────────────────────────────────
    const tabBar = document.getElementById("memory-tab-bar");
    const contentArea = document.getElementById("memory-content-area");
    const editBtn   = document.getElementById("memory-edit-btn");
    const saveBtn   = document.getElementById("memory-save-btn");
    const cancelBtn = document.getElementById("memory-cancel-btn");

    SECTIONS.forEach(sec => {
        const btn = document.createElement("button");
        btn.className = "memory-tab" + (sec.key === activeSection ? " active" : "");
        btn.dataset.key = sec.key;
        btn.textContent = sec.label;
        btn.addEventListener("click", () => switchSection(sec.key));
        tabBar.appendChild(btn);
    });

    // ── Section switching ──────────────────────────────────────────────────
    function switchSection(key) {
        if (editingSection) cancelEdit();
        activeSection = key;
        tabBar.querySelectorAll(".memory-tab").forEach(b => {
            b.classList.toggle("active", b.dataset.key === key);
        });
        renderView();
    }

    // ── Render helpers ─────────────────────────────────────────────────────
    function getSectionValue(key) {
        const sec = SECTIONS.find(s => s.key === key);
        const val = memoryData[key];
        if (sec.type === "list") {
            return Array.isArray(val) && val.length ? val.join("\n") : "";
        }
        return val || "";
    }

    function renderView() {
        contentArea.innerHTML = "";
        const value = getSectionValue(activeSection);
        const pre = document.createElement("pre");
        pre.className = "modal-pre";
        pre.id = "memory-section-display";
        pre.textContent = value || "(empty)";
        contentArea.appendChild(pre);

        editBtn.style.display = "";
        saveBtn.style.display = "none";
        cancelBtn.style.display = "none";
        editingSection = null;
    }

    function renderEdit() {
        contentArea.innerHTML = "";
        const value = getSectionValue(activeSection);
        const ta = document.createElement("textarea");
        ta.className = "modal-textarea";
        ta.id = "memory-section-edit";
        ta.value = value;
        contentArea.appendChild(ta);
        ta.focus();

        editBtn.style.display = "none";
        saveBtn.style.display = "";
        cancelBtn.style.display = "";
        editingSection = activeSection;
    }

    function cancelEdit() {
        renderView();
    }

    function updateMemoryEditBtnState() {
        const locked = isInputLocked();
        editBtn.disabled = locked;
        editBtn.style.opacity = locked ? 0.5 : 1;
        editBtn.title = locked ? "Can't edit while mid turn" : "";
    }

    // ── Button handlers ────────────────────────────────────────────────────
    editBtn.addEventListener("click", () => {
        if (isInputLocked()) return;
        renderEdit();
    });

    cancelBtn.addEventListener("click", () => cancelEdit());

    saveBtn.addEventListener("click", async () => {
        if (isInputLocked()) return;
        const ta = document.getElementById("memory-section-edit");
        if (!ta) return;
        const newVal = ta.value;

        // Write back into memoryData
        const sec = SECTIONS.find(s => s.key === editingSection);
        if (sec.type === "list") {
            memoryData[editingSection] = newVal.split("\n").map(l => l.trim()).filter(Boolean);
        } else {
            memoryData[editingSection] = newVal;
        }

        // Show saving indicator
        const footer = saveBtn.closest(".modal-footer");
        let indicator = footer.querySelector(".modal-saving");
        if (!indicator) {
            indicator = document.createElement("span");
            indicator.className = "modal-saving";
            indicator.textContent = "Saving\u2026";
            footer.insertBefore(indicator, footer.firstChild);
        }
        saveBtn.disabled = true;

        try {
            const res = await fetch(`${API_BASE}/overwrite_memory`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ 
                    memory_sector: editingSection,
                    memory: memoryData[editingSection]
                })
            });
            if (res.status === 400) {
                console.error(`400 error returned from overwrite_memory, ${await res.text()}`);
            }
            renderView();
        } catch (e) {
            console.error("Failed to save memory", e);
        } finally {
            indicator.remove();
            saveBtn.disabled = false;
        }
    });

    // ── Open modal ─────────────────────────────────────────────────────────
    document.getElementById("btn-memory").addEventListener("click", async () => {
        openModal("modal-memory");
        updateMemoryEditBtnState();
        const data = await fetchMessages();
        memoryData = (data && data.memory) ? { ...data.memory } : {};
        switchSection(activeSection);
    });

})();
// --- end Memory modal ---

// --- end modal logic ---

// --- Manage Stories modal ---
(function () {
    const TABS = { load: "stories-tab-load", new: "stories-tab-new" };
    let activeTab = "load";

    // Tab switching
    document.querySelectorAll(".stories-tab").forEach(btn => {
        btn.addEventListener("click", () => {
            document.querySelectorAll(".stories-tab").forEach(t => t.classList.remove("active"));
            btn.classList.add("active");
            activeTab = btn.dataset.tab;
            Object.entries(TABS).forEach(([key, id]) => {
                document.getElementById(id).style.display = key === activeTab ? "" : "none";
            });
            if (activeTab === "load") loadSavedStories();
            else loadTemplates();
        });
    });

    function setStatus(msg, visible = true) {
        const el = document.getElementById("stories-status");
        el.textContent = msg;
        el.style.display = visible ? "inline-flex" : "none";
    }

    function showLoading(tab) {
        document.getElementById(`stories-${tab}-loading`).style.display = "";
        document.getElementById(`stories-${tab}-empty`).style.display = "none";
        document.getElementById(`stories-${tab}-list`).innerHTML = "";
    }

    function hideLoading(tab) {
        document.getElementById(`stories-${tab}-loading`).style.display = "none";
    }

    async function loadSavedStories() {
        showLoading("saved");
        try {
            const res = await fetch(`${API_BASE}/get_saved_stories`);
            const data = await res.json();
            hideLoading("saved");
            const list = document.getElementById("stories-saved-list");
            const empty = document.getElementById("stories-saved-empty");
            list.innerHTML = "";
            if (!data.stories || data.stories.length === 0) {
                empty.style.display = "";
                return;
            }
            empty.style.display = "none";
            data.stories.forEach(name => {
                const li = buildListItem("", name, "Load", async () => {
                    setStatus("Loading story…");
                    try {
                        const r = await fetch(`${API_BASE}/load_story`, {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({ filename: name })
                        });
                        if (!r.ok) {
                            const error = await r.json();
                            throw new Error(error?.error ?? 'Unknown Error');
                        }
                        setStatus("Story loaded!");
                        renderMessages(await fetchMessages()); // immediately update title/turn while waiting for first poll
                        startPolling();
                        await pollAll();
                        setTimeout(() => closeModal("modal-stories"), 800);
                    } catch (e) { setStatus(e.toString()); }
                });
                list.appendChild(li);
            });
        } catch (e) {
            hideLoading("saved");
            document.getElementById("stories-saved-empty").textContent = "Failed to fetch saved stories.";
            document.getElementById("stories-saved-empty").style.display = "";
        }
    }

    async function loadTemplates() {
        showLoading("template");
        try {
            const res = await fetch(`${API_BASE}/get_templates`);
            const data = await res.json();
            hideLoading("template");
            const list = document.getElementById("stories-template-list");
            const empty = document.getElementById("stories-template-empty");
            list.innerHTML = "";
            if (!data.templates || data.templates.length === 0) {
                empty.style.display = "";
                return;
            }
            empty.style.display = "none";
            data.templates.forEach(name => {
                const li = buildListItem("", name, "Create", async () => {
                    setStatus("Creating story…");
                    try {
                        const r = await fetch(`${API_BASE}/create_from_template`, {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({ template: name })
                        });
                        if (!r.ok) {
                            const error = await r.json();
                            throw new Error(error?.error ?? 'Unknown Error');
                        }
                        setStatus("Story created!");
                        startPolling();
                        await pollAll();
                        setTimeout(() => closeModal("modal-stories"), 800);
                    } catch (e) { setStatus(e.toString()); }
                });
                list.appendChild(li);
            });
        } catch (e) {
            hideLoading("template");
            document.getElementById("stories-template-empty").textContent = "Failed to fetch templates.";
            document.getElementById("stories-template-empty").style.display = "";
        }
    }

    function buildListItem(icon, name, btnLabel, onAction) {
        const li = document.createElement("li");
        li.className = "stories-list-item";

        const iconSpan = document.createElement("span");
        iconSpan.className = "stories-item-icon";
        iconSpan.textContent = icon;

        const nameSpan = document.createElement("span");
        nameSpan.className = "stories-item-name";
        nameSpan.textContent = name;
        nameSpan.title = name;

        const btn = document.createElement("button");
        btn.className = "stories-item-load-btn";
        btn.textContent = btnLabel;
        btn.addEventListener("click", (e) => { e.stopPropagation(); onAction(); });

        li.addEventListener("click", () => {
            document.querySelectorAll(".stories-list-item").forEach(i => i.classList.remove("selected"));
            li.classList.add("selected");
        });

        li.appendChild(iconSpan);
        li.appendChild(nameSpan);
        li.appendChild(btn);
        return li;
    }

    document.getElementById("btn-stories").addEventListener("click", () => {
        setStatus("", false);
        openModal("modal-stories");
        if (activeTab === "load") loadSavedStories();
        else loadTemplates();
    });

    // Auto-open on page load (fired by DOMContentLoaded above)
    document.getElementById("btn-stories").addEventListener("_autoopen", () => {
        setStatus("", false);
        loadSavedStories();
    });
})();
// --- end Manage Stories modal ---