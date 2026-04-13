<script setup>
import { computed, onMounted, ref } from "vue";

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

const isAuthed = computed(() => !!token.value && !!currentUser.value);
const activeConversation = computed(() =>
  conversations.value.find((item) => item.conversation_id === activeConversationId.value)
);

function saveAuth(authToken, user) {
  token.value = authToken;
  currentUser.value = user;
  localStorage.setItem("auth_token", authToken);
  localStorage.setItem("auth_user", JSON.stringify(user));
}

function clearAuth() {
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
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    if (response.status === 401 && requiresAuth) {
      clearAuth();
    }
    throw new Error(data.error_message || `Request failed: ${response.status}`);
  }
  return data;
}

async function bootstrapUserSpace() {
  await loadSkills();
  await loadConversations();
}

async function loginOrRegister() {
  if (!authUsername.value.trim() || !authPassword.value.trim()) return;
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
          username: authUsername.value.trim(),
          password: authPassword.value
        })
      },
      false
    );
    saveAuth(data.token, data.user);
    authPassword.value = "";
    await bootstrapUserSpace();
  } catch (err) {
    errorMessage.value = err.message;
  } finally {
    authLoading.value = false;
  }
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
    await loadConversations();
  } catch (err) {
    errorMessage.value = err.message;
    messages.value = messages.value.filter((item) => item.message_id !== localUserMessage.message_id);
    chatInput.value = text;
  } finally {
    sending.value = false;
  }
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
</script>

<template>
  <div class="page-shell">
    <header class="top-bar">
      <h1>Skill Chat Console</h1>
      <p v-if="isAuthed">当前用户：{{ currentUser.username }}</p>
      <p v-else>请先登录或注册后开始对话</p>
    </header>

    <main v-if="!isAuthed" class="auth-layout">
      <section class="panel auth-panel">
        <h2>{{ authMode === "login" ? "登录" : "注册" }}</h2>
        <label class="field">
          <span>用户名</span>
          <input v-model="authUsername" placeholder="3-32位，不含空格" />
        </label>
        <label class="field">
          <span>密码</span>
          <input v-model="authPassword" type="password" placeholder="至少6位" @keydown.enter="loginOrRegister" />
        </label>
        <div class="actions">
          <button @click="loginOrRegister" :disabled="authLoading">
            {{ authLoading ? "处理中..." : authMode === "login" ? "登录" : "注册" }}
          </button>
          <button class="ghost-btn" @click="authMode = authMode === 'login' ? 'register' : 'login'">
            切换到{{ authMode === "login" ? "注册" : "登录" }}
          </button>
        </div>
      </section>
    </main>

    <main v-else class="layout">
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
          <h2>当前会话</h2>
          <p>{{ activeConversation?.conversation_id || "未创建" }}</p>
        </div>

        <div class="chat-stream">
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
  </div>
</template>

