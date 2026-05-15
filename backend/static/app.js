const chatWindow = document.getElementById("chat-window");
const input = document.getElementById("user-input");
const typingIndicator = document.getElementById("typing-indicator");
const themeToggle = document.getElementById("theme-toggle");
const sendBtn = document.getElementById("send-btn");
const micBtn = document.getElementById("mic-btn");
const newChatBtn = document.getElementById("new-chat-btn");
const historyList = document.getElementById("history-list");
const downloadBtn = document.getElementById("download-chat");
const deleteBtn = document.getElementById("delete-chat");


// --- Conversation state (localStorage) ---
let conversations = [];
let currentConversationId = null;
const STORAGE_KEY = "unigpt_conversations_v1";

// Load from localStorage
function loadConversations() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      conversations = [];
      return;
    }
    conversations = JSON.parse(raw);
  } catch (e) {
    console.error("Failed to load conversations:", e);
    conversations = [];
  }
}

// Save to localStorage
function saveConversations() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations));
  } catch (e) {
    console.error("Failed to save conversations:", e);
  }
}

function createNewConversation() {
  const id = Date.now().toString();
  const conv = {
    id,
    title: "New chat",
    createdAt: new Date().toISOString(),
    messages: [],
  };
  conversations.unshift(conv); // newest first
  currentConversationId = id;
  saveConversations();
  renderHistoryList();
  renderCurrentConversation();
}

// Get current conversation object
function getCurrentConversation() {
  return conversations.find((c) => c.id === currentConversationId) || null;
}

// Set title as first user message
function updateConversationTitleIfNeeded(conv) {
  if (!conv) return;
  const firstUserMsg = conv.messages.find((m) => m.sender === "user");
  if (firstUserMsg && (!conv.title || conv.title === "New chat")) {
    conv.title =
      firstUserMsg.text.length > 28
        ? firstUserMsg.text.slice(0, 28) + "..."
        : firstUserMsg.text;
  }
}

// Render history list in sidebar
function renderHistoryList() {
  if (!historyList) return;
  historyList.innerHTML = "";

  if (conversations.length === 0) {
    const empty = document.createElement("div");
    empty.className = "history-item-time";
    empty.textContent = "No chats yet.";
    historyList.appendChild(empty);
    return;
  }

  conversations.forEach((conv) => {
    const item = document.createElement("div");
    item.className = "history-item";
    if (conv.id === currentConversationId) item.classList.add("active");

    const titleDiv = document.createElement("div");
    titleDiv.className = "history-item-title";
    titleDiv.textContent = conv.title || "New chat";

    const timeDiv = document.createElement("div");
    timeDiv.className = "history-item-time";
    const dt = new Date(conv.createdAt || Date.now());
    timeDiv.textContent = dt.toLocaleString([], {
      month: "short",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });

    item.appendChild(titleDiv);
    item.appendChild(timeDiv);

    item.addEventListener("click", () => {
      currentConversationId = conv.id;
      renderHistoryList();
      renderCurrentConversation();
    });

    historyList.appendChild(item);
  });
}

// Render all messages of current conversation
function renderCurrentConversation() {
  if (!chatWindow) return;
  chatWindow.innerHTML = "";

  const conv = getCurrentConversation();
  if (!conv) return;

  if (conv.messages.length === 0) {
    // Empty state with starter chips
    const emptyState = document.createElement("div");
    emptyState.className = "empty-state";
    
    emptyState.innerHTML = `
      <h3>Welcome to uniGPT!</h3>
      <p>I can answer questions about the university.</p>
      <div class="starter-chips">
        <button class="chip" onclick="handleStarterClick('What are the attendance rules?')">📋 What are the attendance rules?</button>
        <button class="chip" onclick="handleStarterClick('How do I pay my fees?')">💳 How do I pay my fees?</button>
        <button class="chip" onclick="handleStarterClick('Where is the library?')">📚 Where is the library?</button>
      </div>
    `;
    chatWindow.appendChild(emptyState);
    return;
  }

  conv.messages.forEach((m) => {
    displayMessage(m.sender, m.text, m.time, false, m.sources); // no auto-store
  });

  scrollToBottom(false);
}

window.handleStarterClick = function(text) {
  if (input) {
    input.value = text;
    sendMessage();
  }
};

// --- Smooth scroll helper ---
function scrollToBottom(smooth = true) {
  if (!chatWindow) return;
  chatWindow.scrollTo({
    top: chatWindow.scrollHeight,
    behavior: smooth ? "smooth" : "auto",
  });
}

// --- Typing indicator control ---
function setTyping(isTyping) {
  if (!typingIndicator) return;
  typingIndicator.classList.toggle("hidden", !isTyping);
  if (isTyping) scrollToBottom(false);
}

// --- Message display with timestamp ---
function displayMessage(sender, text, timeString = null, storeInConv = true, sources = null) {
  if (!chatWindow) return;

  // Row wrapper for avatar + bubble
  const row = document.createElement("div");
  row.className = `msg-row ${sender}`;

  // Avatar
  const avatar = document.createElement("div");
  avatar.className = `avatar ${
    sender === "user" ? "avatar-user" : "avatar-bot"
  }`;
  // Avatar label
  avatar.textContent = sender === "user" ? "U" : "AI";

  // Bubble
  const msg = document.createElement("div");
  msg.className = `msg ${sender}`;

  const textDiv = document.createElement("div");
  textDiv.className = "msg-text";
  textDiv.textContent = text;
  msg.appendChild(textDiv);

  // Sources block
  if (sources && sender === "bot") {
    const sourcesDiv = document.createElement("div");
    sourcesDiv.className = "msg-sources";
    
    if (sources.pdf_sources && sources.pdf_sources.length > 0) {
      // Remove duplicates
      const uniqueDocs = [...new Set(sources.pdf_sources)];
      uniqueDocs.forEach(src => {
        const span = document.createElement("span");
        span.className = "source-badge";
        span.textContent = `📄 ${src}`;
        sourcesDiv.appendChild(span);
      });
    }
    
    if (sources.from_web) {
      const span = document.createElement("span");
      span.className = "source-badge web";
      span.textContent = "🌐 Web Search";
      sourcesDiv.appendChild(span);
    }
    
    if (sourcesDiv.children.length > 0) {
      msg.appendChild(sourcesDiv);
    }
  }

  // Footer (Meta + Copy)
  const footerDiv = document.createElement("div");
  footerDiv.className = "bot-msg-footer";

  const metaDiv = document.createElement("div");
  metaDiv.className = "msg-meta";
  const now = timeString ? new Date(timeString) : new Date();
  metaDiv.textContent = now.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
  footerDiv.appendChild(metaDiv);

  if (sender === "bot") {
    const copyBtn = document.createElement("button");
    copyBtn.className = "copy-btn";
    copyBtn.innerHTML = "📋";
    copyBtn.title = "Copy to clipboard";
    copyBtn.onclick = () => {
      navigator.clipboard.writeText(textDiv.textContent);
      copyBtn.innerHTML = "✅";
      setTimeout(() => copyBtn.innerHTML = "📋", 2000);
    };
    footerDiv.appendChild(copyBtn);
  } else {
    footerDiv.style.justifyContent = "flex-end";
  }

  msg.appendChild(footerDiv);

  row.appendChild(avatar);
  row.appendChild(msg);

  // Remove empty state if it's the first message
  const emptyState = chatWindow.querySelector(".empty-state");
  if (emptyState) emptyState.remove();

  chatWindow.appendChild(row);

  // Store in conversation
  if (storeInConv) {
    const conv = getCurrentConversation();
    if (conv) {
      conv.messages.push({
        sender,
        text,
        time: now.toISOString(),
        sources: sources
      });
      updateConversationTitleIfNeeded(conv);
      saveConversations();
      renderHistoryList();
    }
  }

  scrollToBottom();
}

// --- Send message (streaming word-by-word) ---
async function sendMessage() {
  const question = input.value.trim();
  if (!question) return;

  // Ensure we have a current conversation
  if (!currentConversationId) {
    createNewConversation();
  }

  const activeConvIdAtSend = currentConversationId;

  // User message
  displayMessage("user", question);
  input.value = "";
  input.focus();

  // Show typing indicator
  setTyping(true);

  try {
    const response = await fetch("/api/chat/stream/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });

    if (!response.ok) {
      const errData = await response.json();
      setTyping(false);
      displayMessage("bot", "⚠ " + (errData.error || "Server error"));
      return;
    }

    // Hide typing indicator and create the bot bubble immediately
    setTyping(false);

    // Remove empty state if present
    const emptyState = chatWindow.querySelector(".empty-state");
    if (emptyState) emptyState.remove();

    // Create bot message row (empty, will fill token by token)
    const row = document.createElement("div");
    row.className = "msg-row bot";

    const avatar = document.createElement("div");
    avatar.className = "avatar avatar-bot";
    avatar.textContent = "AI";

    const msg = document.createElement("div");
    msg.className = "msg bot";

    const textDiv = document.createElement("div");
    textDiv.className = "msg-text";
    textDiv.textContent = "";

    msg.appendChild(textDiv);
    row.appendChild(avatar);
    row.appendChild(msg);
    chatWindow.appendChild(row);
    scrollToBottom();

    // Read SSE stream
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let fullAnswer = "";
    let buffer = "";

    let finalSources = null;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // Process complete SSE lines
      const lines = buffer.split("\n");
      buffer = lines.pop(); // Keep incomplete line in buffer

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;

        const jsonStr = line.slice(6); // Remove "data: "
        try {
          const payload = JSON.parse(jsonStr);

          if (payload.error) {
            textDiv.textContent += "⚠ " + payload.error;
            break;
          }

          if (payload.done) {
            if (payload.sources) {
              finalSources = payload.sources;
            }
            break;
          }

          if (payload.token) {
            fullAnswer += payload.token;
            textDiv.textContent = fullAnswer;
            scrollToBottom();
          }
        } catch (e) {
          // Skip malformed JSON
        }
      }
    }
    
    // Add meta, sources, and copy button after streaming is done
    const now = new Date();
    
    if (finalSources) {
      const sourcesDiv = document.createElement("div");
      sourcesDiv.className = "msg-sources";
      
      if (finalSources.pdf_sources && finalSources.pdf_sources.length > 0) {
        const uniqueDocs = [...new Set(finalSources.pdf_sources)];
        uniqueDocs.forEach(src => {
          const span = document.createElement("span");
          span.className = "source-badge";
          span.textContent = `📄 ${src}`;
          sourcesDiv.appendChild(span);
        });
      }
      
      if (finalSources.from_web) {
        const span = document.createElement("span");
        span.className = "source-badge web";
        span.textContent = "🌐 Web Search";
        sourcesDiv.appendChild(span);
      }
      
      if (sourcesDiv.children.length > 0) {
        msg.appendChild(sourcesDiv);
      }
    }

    const footerDiv = document.createElement("div");
    footerDiv.className = "bot-msg-footer";

    const metaDiv = document.createElement("div");
    metaDiv.className = "msg-meta";
    metaDiv.textContent = now.toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });
    footerDiv.appendChild(metaDiv);

    const copyBtn = document.createElement("button");
    copyBtn.className = "copy-btn";
    copyBtn.innerHTML = "📋";
    copyBtn.title = "Copy to clipboard";
    copyBtn.onclick = () => {
      navigator.clipboard.writeText(textDiv.textContent);
      copyBtn.innerHTML = "✅";
      setTimeout(() => copyBtn.innerHTML = "📋", 2000);
    };
    footerDiv.appendChild(copyBtn);

    msg.appendChild(footerDiv);
    scrollToBottom();

    // Check if user switched conversations
    if (currentConversationId !== activeConvIdAtSend) {
      const targetConv = conversations.find(c => c.id === activeConvIdAtSend);
      if (targetConv) {
        targetConv.messages.push({
          sender: "bot",
          text: fullAnswer || "⚠ Chat switched.",
          time: new Date().toISOString(),
          sources: finalSources
        });
        saveConversations();
      }
      return;
    }

    // Save to conversation in localStorage
    const conv = getCurrentConversation();
    if (conv && fullAnswer) {
      conv.messages.push({
        sender: "bot",
        text: fullAnswer,
        time: now.toISOString(),
        sources: finalSources
      });
      updateConversationTitleIfNeeded(conv);
      saveConversations();
      renderHistoryList();
    }
  } catch (err) {
    console.error(err);
    setTyping(false);
    if (currentConversationId === activeConvIdAtSend) {
      displayMessage("bot", "⚠ Server error. Please try again.");
    }
  }
}

// --- Enter key to send ---
if (input) {
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      sendMessage();
    }
  });
}

// --- Theme toggle (light / dark) ---
function applyThemeFromStorage() {
  const saved = localStorage.getItem("unigpt_theme");
  if (saved === "dark") {
    document.body.classList.add("dark");
    if (themeToggle) themeToggle.textContent = "☾";
  } else {
    document.body.classList.remove("dark");
    if (themeToggle) themeToggle.textContent = "☀";
  }
}

if (themeToggle) {
  themeToggle.addEventListener("click", () => {
    const isDark = document.body.classList.toggle("dark");
    localStorage.setItem("unigpt_theme", isDark ? "dark" : "light");
    themeToggle.textContent = isDark ? "☾" : "☀";
  });
}

// Apply saved theme on load
applyThemeFromStorage();

// --- Voice input (Speech Recognition) ---
let recognition = null;
let isRecording = false;

if ("webkitSpeechRecognition" in window || "SpeechRecognition" in window) {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  recognition = new SR();
  recognition.lang = "en-IN";
  recognition.continuous = false;
  recognition.interimResults = false;

  recognition.onstart = () => {
    isRecording = true;
    if (micBtn) micBtn.classList.add("active");
  };

  recognition.onend = () => {
    isRecording = false;
    if (micBtn) micBtn.classList.remove("active");
  };

  recognition.onresult = (event) => {
    const transcript = event.results[0][0].transcript;
    if (input) {
      input.value = transcript;
      input.focus();
    }
  };

  recognition.onerror = (event) => {
    console.error("Speech recognition error:", event.error);
    if (micBtn) micBtn.classList.remove("active");
  };
}

if (micBtn) {
  if (recognition) {
    micBtn.addEventListener("click", () => {
      if (isRecording) {
        recognition.stop();
      } else {
        recognition.start();
      }
    });
  } else {
    micBtn.disabled = true;
    micBtn.title = "Speech recognition not supported in this browser";
  }
}

// --- New chat button (reset conversation but keep history) ---
if (newChatBtn) {
  newChatBtn.addEventListener("click", () => {
    createNewConversation();
  });
}

// --- Initial load: conversations + pick current session ---
(function init() {
  loadConversations();

  if (conversations.length === 0) {
    createNewConversation();
  } else {
    currentConversationId = conversations[0].id;
    renderHistoryList();
    renderCurrentConversation();
  }
})();



// --- Download current chat as .txt ---
if (downloadBtn) {
  downloadBtn.addEventListener("click", () => {
    const conv = getCurrentConversation();
    if (!conv || !conv.messages || conv.messages.length === 0) {
      alert("No messages in this chat to download.");
      return;
    }

    let text = "";
    text += `uniGPT Conversation\n`;
    text += `Title: ${conv.title || "Untitled"}\n`;
    text += `Started: ${
      conv.createdAt
        ? new Date(conv.createdAt).toLocaleString()
        : new Date().toLocaleString()
    }\n\n`;

    conv.messages.forEach((m) => {
      const t = m.time
        ? new Date(m.time).toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          })
        : "";
      const who = m.sender === "user" ? "You" : "uniGPT";
      text += `[${t}] ${who}: ${m.text}\n`;
    });

    const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = (conv.title || "unigpt-chat") + ".txt";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  });
}

// --- Delete current chat ---
if (deleteBtn) {
  deleteBtn.addEventListener("click", () => {
    if (!currentConversationId) return;
    
    // Remove from array
    conversations = conversations.filter(c => c.id !== currentConversationId);
    saveConversations();
    
    // Pick the next available conversation, or create a new one
    if (conversations.length > 0) {
      currentConversationId = conversations[0].id;
      renderHistoryList();
      renderCurrentConversation();
    } else {
      currentConversationId = null;
      renderHistoryList();
      if (chatWindow) chatWindow.innerHTML = "";
      createNewConversation();
    }
  });
}

