<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from "vue";

const apiBase = import.meta.env.VITE_API_BASE || "";
const skills = ref([]);
const selectedSkill = ref("");
const conversations = ref([]);
const activeConversationId = ref("");
const messages = ref([]);
const chatInput = ref("");
const loadingSkills = ref(false);
const loadingConversations = ref(false);
const sending = ref(false);
const errorMessage = ref("");

const authMode = ref("login");
const authUsername = ref("");
const authPassword = ref("");
const authLoading = ref(false);
const token = ref(localStorage.getItem("auth_token") || "");
const currentUser = ref(null);
const nightMode = ref(localStorage.getItem("night_mode") === "1");
const readAloudMode = ref(localStorage.getItem("read_aloud_mode") === "1");
const alertVisible = ref(false);
const alertTitle = ref("");
const alertContent = ref("");
const chatStreamRef = ref(null);
const isSpeaking = ref(false);

let audioPlayer = null;

const isAuthed = computed(() => !!token.value && !!currentUser.value);
const activeConversation = computed(() =>
  conversations.value.find((item) => item.conversation_id === activeConversationId.value)
);
const messageCount = computed(() => messages.value.length);

function showAlert(content, title = "提示") {
  alertTitle.value = title;
  alertContent.value = content;
  alertVisible.value = true;
}

function closeAlert() {
  alertVisible.value = false;
}

function scrollChatToBottom(smooth = true) {
  const el = chatStreamRef.value;
  if (!el) return;
  const behavior = smooth ? "smooth" : "auto";
  requestAnimationFrame(() => {
    el.scrollTo({ top: el.scrollHeight, behavior });
  });
}

function stopSpeech() {
  if ("speechSynthesis" in window) {
    window.speechSynthesis.cancel();
  }
  if (audioPlayer) {
    audioPlayer.pause();
    audioPlayer = null;
  }
  isSpeaking.value = false;
}

function toggleReadAloudMode() {
  readAloudMode.value = !readAloudMode.value;
  localStorage.setItem("read_aloud_mode", readAloudMode.value ? "1" : "0");
  if (!readAloudMode.value) {
    stopSpeech();
  }
}

async function speakAssistantText(text) {
  const plain = sanitizeTextForSpeech(text || "");
  if (!readAloudMode.value || !plain) return;

  stopSpeech();
  const source = (import.meta.env.VITE_TTS_SOURCE || "browser").toLowerCase();
  if (source === "api") {
    try {
      const ttsResult = await request("/api/tts/synthesize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: plain })
      });
      await playTtsResult(ttsResult);
      return;
    } catch (err) {
      showAlert(`TTS接口暂不可用，已切换为浏览器朗读。\n${err.message}`, "朗读提醒");
    }
  }
  speakByBrowser(plain);
}

function sanitizeTextForSpeech(inputText) {
  const raw = (inputText || "").trim();
  if (!raw) return "";

  // Remove content wrapped by () or （） with nested support.
  let depth = 0;
  let out = "";
  for (const ch of raw) {
    if (ch === "(" || ch === "（") {
      depth += 1;
      continue;
    }
    if (ch === ")" || ch === "）") {
      if (depth > 0) {
        depth -= 1;
        continue;
      }
      // unmatched right bracket: skip it
      continue;
    }
    if (depth === 0) {
      out += ch;
    }
  }

  // Collapse duplicated spaces after removal.
  return out.replace(/\s{2,}/g, " ").trim();
}

function speakByBrowser(text) {
  if (!("speechSynthesis" in window)) {
    showAlert("当前浏览器不支持朗读功能，请后续接入 TTS 音频播放。", "朗读不可用");
    return;
  }

  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = "zh-CN";
  utterance.rate = 1;
  utterance.pitch = 1;
  utterance.onstart = () => {
    isSpeaking.value = true;
  };
  utterance.onend = () => {
    isSpeaking.value = false;
  };
  utterance.onerror = () => {
    isSpeaking.value = false;
  };

  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(utterance);
}

async function playTtsResult(ttsResult) {
  let audioSrc = "";
  if (ttsResult.audio_url) {
    audioSrc = ttsResult.audio_url;
  } else if (ttsResult.audio_base64) {
    const mime = ttsResult.mime_type || "audio/mpeg";
    audioSrc = `data:${mime};base64,${ttsResult.audio_base64}`;
  } else {
    throw new Error("TTS 响应缺少音频数据。");
  }

  const audio = new Audio(audioSrc);
  audioPlayer = audio;
  isSpeaking.value = true;
  audio.onended = () => {
    isSpeaking.value = false;
    audioPlayer = null;
  };
  audio.onerror = () => {
    isSpeaking.value = false;
    audioPlayer = null;
  };
  await audio.play();
}

function saveAuth(authToken, user) {
  token.value = authToken;
  currentUser.value = user;
  localStorage.setItem("auth_token", authToken);
  localStorage.setItem("auth_user", JSON.stringify(user));
}

function clearAuth() {
  stopSpeech();
  token.value = "";
  currentUser.value = null;
  localStorage.removeItem("auth_token");
  localStorage.removeItem("auth_user");
  conversations.value = [];
  messages.value = [];
  activeConversationId.value = "";
}

async function request(path, options = {}, requiresAuth = true) {
  const headers = { ...(options.headers || {}) };
  if (requiresAuth && token.value) {
    headers.Authorization = `Bearer ${token.value}`;
  }

  const response = await fetch(`${apiBase}${path}`, {
    ...options,
    headers
  });
  const rawText = await response.text();
  let data;
  try {
    data = rawText ? JSON.parse(rawText) : {};
  } catch {
    data = rawText || {};
  }

  if (!response.ok) {
    if (response.status === 401 && requiresAuth) {
      clearAuth();
    }

    const code = typeof data === "object" && data ? data.error_code || "" : "";
    let message = typeof data === "object" && data ? data.error_message || "" : "";

    if (!message && typeof data === "object" && data && data.detail) {
      if (typeof data.detail === "string") {
        message = data.detail;
      } else if (Array.isArray(data.detail)) {
        message = data.detail.map((item) => item?.msg || "参数错误").join("；");
      } else {
        message = "请求参数错误";
      }
    }

    if (!message && typeof data === "string") {
      message = data;
    }
    if (!message) {
      message = `Request failed: ${response.status}`;
    }

    const err = new Error(message);
    err.code = code;
    throw err;
  }
  return data;
}

async function bootstrapUserSpace() {
  await loadSkills();
  await loadConversations();
}

async function loginOrRegister() {
  const username = authUsername.value.trim();
  const password = authPassword.value.trim();

  if (!username || !password) {
    showAlert("用户名和密码不能为空。", "输入错误");
    return;
  }
  if (username.length < 3 || username.length > 32) {
    showAlert("用户名长度需在 3~32 位之间。", "输入错误");
    return;
  }
  if (/\s/.test(username)) {
    showAlert("用户名不能包含空格。", "输入错误");
    return;
  }
  if (password.length < 6) {
    showAlert("密码至少需要 6 位。", "输入错误");
    return;
  }

  authLoading.value = true;
  errorMessage.value = "";
  try {
    const path = authMode.value === "login" ? "/api/auth/login" : "/api/auth/register";
    const data = await request(
      path,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username,
          password
        })
      },
      false
    );
    saveAuth(data.token, data.user);
    authPassword.value = "";
    await bootstrapUserSpace();
  } catch (err) {
    if (authMode.value === "login" && err.code === "INVALID_CREDENTIALS") {
      showAlert("密码错误，请重新输入。", "登录失败");
    } else {
      showAlert(
        err.message,
        authMode.value === "login" ? "登录失败" : "注册失败"
      );
    }
  } finally {
    authLoading.value = false;
  }
}

function toggleAuthMode(target) {
  authMode.value = target;
  errorMessage.value = "";
}

async function loadMe() {
  try {
    const data = await request("/api/auth/me");
    currentUser.value = data;
    return true;
  } catch {
    clearAuth();
    return false;
  }
}

async function loadSkills() {
  loadingSkills.value = true;
  errorMessage.value = "";
  try {
    const data = await request("/api/skills");
    skills.value = data;
    if (!selectedSkill.value && data.length) {
      selectedSkill.value = data[0].skill_id;
    }
  } catch (err) {
    errorMessage.value = err.message;
  } finally {
    loadingSkills.value = false;
  }
}

async function loadConversations() {
  loadingConversations.value = true;
  errorMessage.value = "";
  try {
    const data = await request("/api/conversations");
    conversations.value = data;
  } catch (err) {
    errorMessage.value = err.message;
  } finally {
    loadingConversations.value = false;
  }
}

async function openConversation(conversationId) {
  activeConversationId.value = conversationId;
  errorMessage.value = "";
  try {
    const data = await request(`/api/conversations/${conversationId}/messages`);
    messages.value = data;
    await nextTick();
    scrollChatToBottom(false);
  } catch (err) {
    errorMessage.value = err.message;
  }
}

async function createConversation() {
  if (!selectedSkill.value || !isAuthed.value) return;
  errorMessage.value = "";
  try {
    const data = await request("/api/conversations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        skill_id: selectedSkill.value,
        channel: "web"
      })
    });
    await loadConversations();
    await openConversation(data.conversation_id);
  } catch (err) {
    errorMessage.value = err.message;
  }
}

async function sendMessage() {
  const text = chatInput.value.trim();
  if (!text || !selectedSkill.value || !isAuthed.value || sending.value) return;

  sending.value = true;
  errorMessage.value = "";

  const localUserMessage = {
    message_id: `local_user_${Date.now()}`,
    role: "user",
    content: text,
    created_at: new Date().toISOString()
  };
  messages.value.push(localUserMessage);
  await nextTick();
  scrollChatToBottom(true);
  chatInput.value = "";

  try {
    const data = await request("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        conversation_id: activeConversationId.value || null,
        skill_id: selectedSkill.value,
        channel: "web",
        message: text
      })
    });

    activeConversationId.value = data.conversation_id;
    messages.value.push({
      message_id: data.message_id,
      role: "assistant",
      content: data.reply,
      created_at: data.created_at
    });
    await nextTick();
    scrollChatToBottom(true);
    void speakAssistantText(data.reply);
    await loadConversations();
  } catch (err) {
    errorMessage.value = err.message;
    messages.value = messages.value.filter((item) => item.message_id !== localUserMessage.message_id);
    chatInput.value = text;
  } finally {
    sending.value = false;
  }
}

function toggleNightMode() {
  nightMode.value = !nightMode.value;
  localStorage.setItem("night_mode", nightMode.value ? "1" : "0");
}

function logout() {
  clearAuth();
  errorMessage.value = "";
}

function formatTime(value) {
  if (!value) return "";
  const date = new Date(value);
  return `${date.toLocaleDateString()} ${date.toLocaleTimeString()}`;
}

onMounted(async () => {
  const cachedUser = localStorage.getItem("auth_user");
  if (cachedUser) {
    try {
      currentUser.value = JSON.parse(cachedUser);
    } catch {
      clearAuth();
    }
  }

  if (token.value) {
    const ok = await loadMe();
    if (ok) {
      await bootstrapUserSpace();
    }
  } else {
    await loadSkills();
  }
});

onBeforeUnmount(() => {
  stopSpeech();
});
</script>

<template>
  <div :class="['page-shell', { 'authed-theme': isAuthed, 'night-mode': isAuthed && nightMode }]">
    <header class="top-bar">
      <h1>Skill Chat Console</h1>
      <p v-if="isAuthed">当前用户：{{ currentUser.username }}</p>
      <p v-else>请先登录或注册后开始对话</p>
    </header>

    <main v-if="!isAuthed" class="auth-layout">
      <section class="auth-shell">
        <article class="auth-hero">
          <h2>Welcome Back</h2>
          <p>登录你的账号，继续你专属的对话上下文。</p>
          <ul>
            <li>账号密码持久保存</li>
            <li>会话与账号强绑定</li>
            <li>切换账号互不干扰</li>
          </ul>
        </article>

        <transition name="auth-swap" mode="out-in">
          <section class="panel auth-panel" :key="authMode">
            <div class="auth-tabs">
              <button
                :class="['tab-btn', { active: authMode === 'login' }]"
                @click="toggleAuthMode('login')"
              >
                登录
              </button>
              <button
                :class="['tab-btn', { active: authMode === 'register' }]"
                @click="toggleAuthMode('register')"
              >
                注册
              </button>
            </div>

            <h3>{{ authMode === "login" ? "账号登录" : "创建账号" }}</h3>
            <label class="field">
              <span>用户名</span>
              <input v-model="authUsername" placeholder="3-32位，不含空格" />
            </label>
            <label class="field">
              <span>密码</span>
              <input
                v-model="authPassword"
                type="password"
                placeholder="至少6位"
                @keydown.enter="loginOrRegister"
              />
            </label>
            <button class="primary-btn" @click="loginOrRegister" :disabled="authLoading">
              {{ authLoading ? "处理中..." : authMode === "login" ? "登录并进入" : "注册并进入" }}
            </button>
          </section>
        </transition>
      </section>
    </main>

    <main v-else class="layout">
      <div class="blue-orb orb-1" aria-hidden="true"></div>
      <div class="blue-orb orb-2" aria-hidden="true"></div>
      <aside class="panel left-panel">
        <section class="section">
          <h2>连接配置</h2>
          <label class="field">
            <span>Skill</span>
            <select v-model="selectedSkill" :disabled="loadingSkills">
              <option value="" disabled>选择 skill</option>
              <option v-for="skill in skills" :key="skill.skill_id" :value="skill.skill_id">
                {{ skill.name }} ({{ skill.skill_id }})
              </option>
            </select>
          </label>
          <div class="actions">
            <button @click="loadSkills" :disabled="loadingSkills">
              {{ loadingSkills ? "加载中..." : "刷新 Skill" }}
            </button>
            <button @click="loadConversations" :disabled="loadingConversations">
              {{ loadingConversations ? "加载中..." : "刷新会话" }}
            </button>
          </div>
          <div class="actions">
            <button class="ghost-btn" @click="logout">退出登录</button>
          </div>
          <div class="actions">
            <button class="ghost-btn" @click="toggleNightMode">
              {{ nightMode ? "切换淡蓝模式" : "切换夜间蓝黑" }}
            </button>
          </div>
          <div class="actions">
            <button class="ghost-btn" @click="toggleReadAloudMode">
              {{ readAloudMode ? "朗读模式：开" : "朗读模式：关" }}
            </button>
            <button class="ghost-btn" @click="stopSpeech" :disabled="!isSpeaking">
              {{ isSpeaking ? "停止朗读" : "未在朗读" }}
            </button>
          </div>
        </section>

        <section class="section">
          <div class="section-title-row">
            <h2>会话列表</h2>
            <button class="small-btn" @click="createConversation">新建</button>
          </div>
          <div class="conversation-list">
            <button
              v-for="item in conversations"
              :key="item.conversation_id"
              :class="['conversation-item', { active: item.conversation_id === activeConversationId }]"
              @click="openConversation(item.conversation_id)"
            >
              <strong>{{ item.title || "未命名会话" }}</strong>
              <span>{{ item.skill_id }}</span>
              <small>{{ formatTime(item.updated_at) }}</small>
            </button>
            <p v-if="!conversations.length" class="empty-tip">暂无会话，点击“新建”或直接发送消息。</p>
          </div>
        </section>
      </aside>

      <section class="panel right-panel">
        <div class="chat-header">
          <div class="chat-header-main">
            <h2>当前会话</h2>
            <p>{{ activeConversation?.conversation_id || "未创建" }}</p>
          </div>
          <div class="chat-header-meta">
            <span class="meta-pill">Skill: {{ selectedSkill || "未选择" }}</span>
            <span class="meta-pill">消息数: {{ messageCount }}</span>
          </div>
        </div>

        <div ref="chatStreamRef" class="chat-stream">
          <transition-group name="msg-pop" tag="div" class="message-list">
            <article
              v-for="msg in messages"
              :key="msg.message_id"
              :class="['msg', msg.role === 'assistant' ? 'assistant' : 'user']"
            >
              <header>
                <strong>{{ msg.role === "assistant" ? "Assistant" : "You" }}</strong>
                <small>{{ formatTime(msg.created_at) }}</small>
              </header>
              <p>{{ msg.content }}</p>
            </article>
          </transition-group>
          <div v-if="sending" class="typing-row">
            <span class="typing-dot"></span>
            <span class="typing-dot"></span>
            <span class="typing-dot"></span>
            <small>正在生成回复...</small>
          </div>
          <p v-if="!messages.length" class="empty-tip">还没有消息，输入内容开始对话。</p>
        </div>

        <div class="composer">
          <textarea
            v-model="chatInput"
            placeholder="输入消息，回车发送（Shift+Enter 换行）"
            @keydown.enter.exact.prevent="sendMessage"
          />
          <button @click="sendMessage" :disabled="sending">
            {{ sending ? "发送中..." : "发送" }}
          </button>
        </div>

        <p v-if="errorMessage" class="error">{{ errorMessage }}</p>
      </section>
    </main>

    <transition name="modal-fade">
      <div v-if="alertVisible" class="alert-backdrop" @click.self="closeAlert">
        <div class="alert-modal">
          <h3>{{ alertTitle }}</h3>
          <p>{{ alertContent }}</p>
          <button class="primary-btn" @click="closeAlert">我知道了</button>
        </div>
      </div>
    </transition>
  </div>
</template>
