const API_BASE_URL = '/api';

const state = {
  isGenerating: false,
  activeConversation: 'New conversation',
  backendConversationId: null,
  backendReady: false,
  modelConfigured: false,
  lastUserPrompt: '',
  abortController: null,
  selectedDocuments: [],
  webSearchEnabled: false,
  recentSources: [],
};

const dom = {};

function cacheDom() {
  dom.sidebar = document.querySelector('#sidebar');
  dom.sidebarScrim = document.querySelector('#sidebarScrim');
  dom.menuButton = document.querySelector('#menuButton');
  dom.newChatButton = document.querySelector('#newChatButton');
  dom.conversationList = document.querySelector('#conversationList');
  dom.conversationTitle = document.querySelector('#conversationTitle');
  dom.chatScroll = document.querySelector('#chatScroll');
  dom.quickPrompts = document.querySelector('#quickPrompts');
  dom.dynamicMessages = document.querySelector('#dynamicMessages');
  dom.typingRow = document.querySelector('#typingRow');
  dom.composer = document.querySelector('#composer');
  dom.messageInput = document.querySelector('#messageInput');
  dom.sendButton = document.querySelector('#sendButton');
  dom.stopButton = document.querySelector('#stopButton');
  dom.regenerateButton = document.querySelector('#regenerateButton');
  dom.renameConversationButton = document.querySelector('#renameConversationButton');
  dom.deleteConversationButton = document.querySelector('#deleteConversationButton');
  dom.fileInput = document.querySelector('#fileInput');
  dom.attachmentRow = document.querySelector('#attachmentRow');
  dom.searchToggle = document.querySelector('#searchToggle');
  dom.modelSelect = document.querySelector('#modelSelect');
  dom.documentCount = document.querySelector('#documentCount');
  dom.sourceCount = document.querySelector('#sourceCount');
  dom.recentSources = document.querySelector('#recentSources');
  dom.serviceChip = document.querySelector('#serviceChip');
  dom.databaseStatus = document.querySelector('#databaseStatus');
  dom.databaseDetail = document.querySelector('#databaseDetail');
  dom.memoryStatus = document.querySelector('#memoryStatus');
  dom.memoryDetail = document.querySelector('#memoryDetail');
  dom.modelStatus = document.querySelector('#modelStatus');
  dom.modelDetail = document.querySelector('#modelDetail');
  dom.brainPulse = document.querySelector('#brainPulse');
  dom.brainStatus = document.querySelector('#brainStatus');
  dom.brainDetail = document.querySelector('#brainDetail');
  dom.lessonCount = document.querySelector('#lessonCount');
  dom.feedbackCount = document.querySelector('#feedbackCount');
  dom.knowledgeCount = document.querySelector('#knowledgeCount');
  dom.trainingGuideButton = document.querySelector('#trainingGuideButton');
  dom.toast = document.querySelector('#toast');
}

function escapeHtml(value) {
  return String(value).replace(/[&<>'"]/g, (character) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#039;', '"': '&quot;',
  }[character]));
}

class ApiError extends Error {
  constructor(message, status) { super(message); this.status = status; }
}

async function api(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: { Accept: 'application/json', ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }), ...(options.headers || {}) },
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new ApiError(payload.detail || `Request failed (${response.status})`, response.status);
  return payload;
}

function showToast(message) {
  if (!dom.toast) return;
  dom.toast.textContent = message;
  dom.toast.classList.add('is-visible');
  clearTimeout(showToast.timeoutId);
  showToast.timeoutId = setTimeout(() => dom.toast.classList.remove('is-visible'), 3600);
}

function setSidebar(open) {
  dom.sidebar.classList.toggle('is-open', open);
  dom.sidebarScrim.classList.toggle('is-visible', open);
}

function autoResize() {
  dom.messageInput.style.height = 'auto';
  dom.messageInput.style.height = `${Math.min(dom.messageInput.scrollHeight, 150)}px`;
}

function scrollToBottom() {
  requestAnimationFrame(() => { dom.chatScroll.scrollTop = dom.chatScroll.scrollHeight; });
}

function setGenerating(isGenerating) {
  state.isGenerating = isGenerating;
  dom.typingRow.classList.toggle('is-hidden', !isGenerating);
  dom.stopButton.classList.toggle('is-hidden', !isGenerating);
  dom.sendButton.disabled = isGenerating;
  dom.messageInput.disabled = isGenerating;
  if (isGenerating) scrollToBottom();
}

function addMessage(role, content, sources = []) {
  const group = document.createElement('div');
  group.className = `message-group ${role === 'user' ? 'user-group' : 'assistant-group'}`;
  if (role === 'user') {
    group.innerHTML = `<div class="message-meta user-meta"><span>You</span></div><article class="message-card user-message"><p>${escapeHtml(content)}</p></article>`;
  } else {
    const sourceLinks = sources.map((source, index) => {
      const label = `[S${index + 1}] ${escapeHtml(source.title || 'Source')}${source.page ? ` — p. ${source.page}` : ''}`;
      return source.url
        ? `<a class="citation" href="${escapeHtml(source.url)}" target="_blank" rel="noopener noreferrer">${label}</a>`
        : `<span class="citation">${label}</span>`;
    }).join('');
    group.innerHTML = `<div class="message-meta"><span class="message-avatar"><img src="/firebox-ai-icon.svg" alt="" /></span><span>FIREBOX AI</span><span class="source-label">LOCAL CHECKPOINT</span></div><article class="message-card assistant-message"><p>${escapeHtml(content).replace(/\n/g, '<br>')}</p>${sourceLinks ? `<div class="response-divider"></div><div class="citation-row">${sourceLinks}</div>` : ''}<div class="feedback-row"><span>Teach FIREBOX</span><button type="button" data-feedback="good" data-response="${escapeHtml(content)}">Useful</button><button type="button" data-feedback="incorrect" data-response="${escapeHtml(content)}">Correct it</button></div></article>`;
  }
  dom.dynamicMessages.appendChild(group);
  if (role === 'assistant') renderRecentSources(sources);
  scrollToBottom();
  return group;
}

function addErrorMessage(message) {
  const group = document.createElement('div');
  group.className = 'message-group assistant-group';
  group.innerHTML = `<div class="message-meta"><span>FIREBOX AI</span><span class="source-label">REQUEST ERROR</span></div><article class="message-card assistant-message"><p>${escapeHtml(message)}</p></article>`;
  dom.dynamicMessages.appendChild(group);
  scrollToBottom();
}

function renderAttachments() {
  dom.attachmentRow.innerHTML = state.selectedDocuments.map((doc, index) => `
    <span class="attachment-chip"><span aria-hidden="true">▧</span>${escapeHtml(doc.filename)}<button type="button" data-remove-document="${index}" aria-label="Remove ${escapeHtml(doc.filename)} from this prompt">×</button></span>
  `).join('');
  dom.attachmentRow.classList.toggle('is-hidden', state.selectedDocuments.length === 0);
}

function renderConversations(items) {
  if (!items.length) {
    dom.conversationList.innerHTML = '<p class="empty-conversations">No saved conversations yet.</p>';
    return;
  }
  dom.conversationList.innerHTML = items.map((conversation) => `
    <button class="conversation-item ${conversation.id === state.backendConversationId ? 'is-active' : ''}" type="button" data-conversation-id="${escapeHtml(conversation.id)}" data-conversation="${escapeHtml(conversation.title)}">
      <span class="conversation-dot"></span><span class="conversation-item-copy"><strong>${escapeHtml(conversation.title)}</strong><small>${new Date(conversation.updated_at).toLocaleString()}</small></span>
    </button>
  `).join('');
}

function renderRecentSources(sources) {
  const known = new Set(state.recentSources.map((item) => item.url || `${item.title}:${item.page || ''}`));
  for (const source of sources) {
    const key = source.url || `${source.title}:${source.page || ''}`;
    if (!known.has(key)) { state.recentSources.push(source); known.add(key); }
  }
  state.recentSources = state.recentSources.slice(-8);
  dom.sourceCount.textContent = String(state.recentSources.length);
  if (!state.recentSources.length) {
    dom.recentSources.className = 'empty-source';
    dom.recentSources.innerHTML = '<span class="empty-source-mark">⌁</span><strong>No sources yet</strong><small>Sources from completed answers appear here.</small>';
    return;
  }
  dom.recentSources.className = 'recent-source-list';
  dom.recentSources.innerHTML = state.recentSources.map((source) => {
    const title = `${escapeHtml(source.title || 'Source')}${source.page ? ` — p. ${source.page}` : ''}`;
    return source.url ? `<a class="recent-source-item" href="${escapeHtml(source.url)}" target="_blank" rel="noopener noreferrer">${title}</a>` : `<div class="recent-source-item">${title}</div>`;
  }).join('');
}

async function refreshConversations() {
  const result = await api('/conversations');
  renderConversations(result.items || []);
}

async function loadConversation(id) {
  const conversation = await api(`/conversations/${encodeURIComponent(id)}`);
  state.backendConversationId = conversation.id;
  state.activeConversation = conversation.title;
  state.recentSources = [];
  renderRecentSources([]);
  dom.conversationTitle.textContent = conversation.title;
  dom.dynamicMessages.innerHTML = '';
  dom.quickPrompts.classList.toggle('is-hidden', conversation.messages.length > 0);
  for (const message of conversation.messages) {
    if (message.role === 'user' || message.role === 'assistant') addMessage(message.role, message.content, message.metadata?.sources || []);
  }
  await refreshConversations();
}

async function ensureBackendConversation(title = state.activeConversation) {
  if (state.backendConversationId) return state.backendConversationId;
  const created = await api('/conversations', { method: 'POST', body: JSON.stringify({ title }) });
  state.backendConversationId = created.id;
  state.activeConversation = created.title;
  dom.conversationTitle.textContent = created.title;
  return created.id;
}

async function persistMessage(conversationId, role, content, metadata = {}) {
  return api(`/conversations/${encodeURIComponent(conversationId)}/messages`, {
    method: 'POST', body: JSON.stringify({ role, content, metadata }),
  });
}

async function generateResponse(prompt, { persistUser = true } = {}) {
  if (!state.backendReady) {
    addErrorMessage('The database is not available. Your message was not sent or saved.');
    return;
  }
  setGenerating(true);
  state.abortController = new AbortController();
  let userSaved = !persistUser;
  try {
    const conversationId = await ensureBackendConversation(prompt.slice(0, 80) || 'New conversation');
    if (persistUser) {
      await persistMessage(conversationId, 'user', prompt);
      userSaved = true;
      if (state.activeConversation === 'New conversation') {
        await api(`/conversations/${encodeURIComponent(conversationId)}`, { method: 'PATCH', body: JSON.stringify({ title: prompt.slice(0, 80) }) });
        state.activeConversation = prompt.slice(0, 80);
        dom.conversationTitle.textContent = state.activeConversation;
      }
    }
    const result = await api('/chat', {
      method: 'POST', signal: state.abortController.signal,
      body: JSON.stringify({ message: prompt, model: dom.modelSelect.value || null, webSearch: state.webSearchEnabled, conversation_id: conversationId, document_ids: state.selectedDocuments.map((doc) => doc.id) }),
    });
    addMessage('assistant', result.answer, result.sources || []);
    try { await persistMessage(conversationId, 'assistant', result.answer, { sources: result.sources || [] }); }
    catch (error) { showToast(`Answer generated, but it was not saved: ${error.message}`); }
    dom.regenerateButton.disabled = false;
    await refreshConversations();
  } catch (error) {
    const cancelled = error.name === 'AbortError';
    addErrorMessage(cancelled
      ? (userSaved ? 'Generation cancelled. The user message remains saved.' : 'Generation cancelled before the message was saved.')
      : `No answer was generated. ${error.message}${userSaved ? ' The user message was saved.' : ' The user message was not saved.'}`);
    if (error.status === 503) showToast(error.message);
  } finally {
    state.abortController = null;
    setGenerating(false);
  }
}

async function submitPrompt(prompt) {
  const trimmed = prompt.trim();
  if (!trimmed || state.isGenerating) return;
  state.lastUserPrompt = trimmed;
  dom.messageInput.value = '';
  autoResize();
  dom.quickPrompts.classList.add('is-hidden');
  addMessage('user', trimmed);
  await generateResponse(trimmed);
}

async function createNewChat() {
  if (!state.backendReady) return showToast('MongoDB is unavailable; no conversation was created.');
  try {
    const conversation = await api('/conversations', { method: 'POST', body: JSON.stringify({ title: 'New conversation' }) });
    state.backendConversationId = conversation.id;
    state.activeConversation = conversation.title;
    state.lastUserPrompt = '';
    state.selectedDocuments = [];
    state.recentSources = [];
    renderRecentSources([]);
    dom.conversationTitle.textContent = conversation.title;
    dom.dynamicMessages.innerHTML = '';
    dom.quickPrompts.classList.remove('is-hidden');
    dom.regenerateButton.disabled = true;
    renderAttachments();
    await refreshConversations();
    setSidebar(false);
  } catch (error) { showToast(`Conversation was not created: ${error.message}`); }
}

async function deleteCurrentConversation() {
  if (!state.backendConversationId || !window.confirm('Delete this conversation and its saved messages?')) return;
  try {
    await api(`/conversations/${encodeURIComponent(state.backendConversationId)}`, { method: 'DELETE' });
    state.backendConversationId = null;
    state.activeConversation = 'New conversation';
    state.recentSources = [];
    renderRecentSources([]);
    dom.conversationTitle.textContent = state.activeConversation;
    dom.dynamicMessages.innerHTML = '';
    dom.quickPrompts.classList.remove('is-hidden');
    dom.regenerateButton.disabled = true;
    await refreshConversations();
    showToast('Conversation deleted.');
  } catch (error) { showToast(`Conversation was not deleted: ${error.message}`); }
}

async function renameCurrentConversation() {
  if (!state.backendConversationId) return showToast('Create a conversation before renaming it.');
  const title = window.prompt('Conversation name', state.activeConversation);
  if (title === null || !title.trim()) return;
  try {
    const updated = await api(`/conversations/${encodeURIComponent(state.backendConversationId)}`, { method: 'PATCH', body: JSON.stringify({ title: title.trim() }) });
    state.activeConversation = updated.title;
    dom.conversationTitle.textContent = updated.title;
    await refreshConversations();
    showToast('Conversation renamed.');
  } catch (error) { showToast(`Conversation was not renamed: ${error.message}`); }
}

async function uploadDocuments(files) {
  for (const file of files) {
    const formData = new FormData();
    formData.append('file', file);
    try {
      const document = await api('/documents/upload', { method: 'POST', body: formData });
      state.selectedDocuments.push(document);
      dom.documentCount.textContent = String(Number(dom.documentCount.textContent || 0) + 1);
      renderAttachments();
      showToast(`${document.filename} processed (${document.chunk_count} text chunks).`);
    } catch (error) {
      showToast(`${file.name} was not processed: ${error.message}`);
    }
  }
}

async function syncBackendStatus() {
  const statusStrong = document.querySelector('.preview-status strong');
  const statusSmall = document.querySelector('.preview-status small');
  try {
    const health = await api('/health');
    state.backendReady = Boolean(health.mongodb?.connected);
    state.modelConfigured = Boolean(health.model?.configured);
    dom.serviceChip.lastChild.textContent = state.backendReady && state.modelConfigured ? ' READY' : ' DEGRADED';
    dom.databaseStatus.textContent = state.backendReady ? 'MongoDB connected' : 'MongoDB unavailable';
    dom.databaseDetail.textContent = state.backendReady ? `Database: ${health.mongodb.database}` : (health.mongodb?.error || 'Persistence unavailable');
    dom.memoryStatus.textContent = state.backendReady ? 'Conversation persistence' : 'Conversation memory';
    dom.memoryDetail.textContent = state.backendReady ? 'Saved messages are available' : 'Requires MongoDB connection';
    dom.modelStatus.textContent = state.modelConfigured ? 'Model configured' : 'Model unavailable';
    dom.modelDetail.textContent = state.modelConfigured ? `${health.model.provider} · checkpoint loaded` : (health.model?.error || 'Train a local checkpoint first');
    if (state.backendReady) {
      statusStrong.textContent = state.modelConfigured ? 'Services connected' : 'Database connected';
      statusSmall.textContent = state.modelConfigured ? 'Persistence and model available' : 'Model configuration required';
      await refreshConversations();
      await api('/documents').then(({ items = [] }) => { state.allDocuments = items; });
      dom.documentCount.textContent = String(state.allDocuments.length);
      await loadSettings();
      await refreshBrainLab();
    } else {
      statusStrong.textContent = 'Storage unavailable';
      statusSmall.textContent = health.mongodb?.error || 'Messages cannot be saved';
    }
  } catch (error) {
    state.backendReady = false;
    dom.serviceChip.lastChild.textContent = ' OFFLINE';
    dom.databaseStatus.textContent = 'Backend unavailable';
    dom.databaseDetail.textContent = error.message || 'Health check failed';
    dom.memoryStatus.textContent = 'Conversation memory unavailable';
    dom.memoryDetail.textContent = 'No data was saved';
    dom.modelStatus.textContent = 'Model status unknown';
    dom.modelDetail.textContent = 'Backend health check failed';
    statusStrong.textContent = error.status === 401 ? 'Authentication required' : 'Backend unavailable';
    statusSmall.textContent = error.message || 'No data was saved';
  }
}

async function refreshBrainLab() {
  try {
    const [learning, lessons, feedback, knowledge] = await Promise.all([
      api('/learning/status'), api('/learning/lessons'), api('/learning/feedback'), api('/learning/knowledge'),
    ]);
    const model = learning.model || {};
    const ready = Boolean(model.configured);
    dom.brainPulse.classList.toggle('is-ready', ready);
    dom.brainStatus.textContent = ready ? 'Checkpoint active' : 'Checkpoint not loaded';
    dom.brainDetail.textContent = ready ? `Epoch ${model.epoch || 0} · loss ${model.validation_loss ?? 'n/a'}` : (model.error || 'Train the local model to activate the brain.');
    dom.lessonCount.textContent = String((lessons.items || []).length);
    dom.feedbackCount.textContent = String((feedback.items || []).length);
    dom.knowledgeCount.textContent = String((knowledge.items || []).filter((item) => item.approved).length);
  } catch (error) {
    dom.brainStatus.textContent = 'Learning data unavailable';
    dom.brainDetail.textContent = error.message || 'Connect MongoDB to view learning state.';
  }
}

async function loadSettings() {
  const settings = await api('/settings');
  state.webSearchEnabled = Boolean(settings.web_search_enabled);
  dom.searchToggle.setAttribute('aria-pressed', String(state.webSearchEnabled));
}

async function saveSettings(patch) {
  try {
    await api('/settings', { method: 'PATCH', body: JSON.stringify(patch) });
    showToast('Settings saved.');
  } catch (error) { showToast(`Settings were not saved: ${error.message}`); }
}

function attachEvents() {
  dom.menuButton.addEventListener('click', () => setSidebar(true));
  dom.sidebarScrim.addEventListener('click', () => setSidebar(false));
  dom.newChatButton.addEventListener('click', createNewChat);
  dom.renameConversationButton?.addEventListener('click', renameCurrentConversation);
  dom.deleteConversationButton?.addEventListener('click', deleteCurrentConversation);
  dom.searchToggle.addEventListener('click', async () => {
    state.webSearchEnabled = !state.webSearchEnabled;
    dom.searchToggle.setAttribute('aria-pressed', String(state.webSearchEnabled));
    await saveSettings({ web_search_enabled: state.webSearchEnabled });
  });
  dom.messageInput.addEventListener('input', autoResize);
  dom.messageInput.addEventListener('keydown', (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') { event.preventDefault(); void submitPrompt(dom.messageInput.value); }
  });
  dom.composer.addEventListener('submit', (event) => { event.preventDefault(); void submitPrompt(dom.messageInput.value); });
  dom.stopButton.addEventListener('click', () => state.abortController?.abort());
  dom.trainingGuideButton.addEventListener('click', () => showToast('Train locally: python training/train_firebox.py --data training_data/starter.jsonl --checkpoint storage/checkpoints/latest.pt --epochs 8'));
  dom.regenerateButton.addEventListener('click', () => {
    if (state.lastUserPrompt && !state.isGenerating) void generateResponse(state.lastUserPrompt, { persistUser: false });
  });
  dom.fileInput.addEventListener('change', (event) => {
    const files = Array.from(event.target.files || []);
    event.target.value = '';
    if (!state.backendReady) return showToast('Storage is unavailable; the selected files were not uploaded.');
    void uploadDocuments(files);
  });
  dom.conversationList.addEventListener('click', (event) => {
    const button = event.target.closest('.conversation-item');
    if (button?.dataset.conversationId) void loadConversation(button.dataset.conversationId).catch((error) => showToast(`Conversation could not be loaded: ${error.message}`));
  });
  dom.dynamicMessages.addEventListener('click', async (event) => {
    const feedbackButton = event.target.closest('[data-feedback]');
    if (feedbackButton) {
      try {
        await api('/learning/feedback', { method: 'POST', body: JSON.stringify({ prompt: state.lastUserPrompt || 'Conversation response', response: feedbackButton.dataset.response || '', rating: feedbackButton.dataset.feedback }) });
        showToast('Feedback saved for the next FIREBOX training run.');
        await refreshBrainLab();
      } catch (error) { showToast(`Feedback was not saved: ${error.message}`); }
      return;
    }
    const copyButton = event.target.closest('[data-copy]');
    if (!copyButton) return;
    try { await navigator.clipboard.writeText(copyButton.dataset.copy); showToast('Copied.'); }
    catch { showToast('Copy is unavailable in this browser context.'); }
  });
  dom.attachmentRow.addEventListener('click', (event) => {
    const button = event.target.closest('[data-remove-document]');
    if (!button) return;
    state.selectedDocuments.splice(Number(button.dataset.removeDocument), 1);
    renderAttachments();
  });
  document.addEventListener('click', (event) => {
    const promptButton = event.target.closest('[data-prompt]');
    if (promptButton) { dom.messageInput.value = promptButton.dataset.prompt; autoResize(); dom.messageInput.focus(); }
    const toastTarget = event.target.closest('[data-toast]');
    if (toastTarget) showToast(toastTarget.dataset.toast);
  });
  document.addEventListener('keydown', (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
      event.preventDefault();
      void createNewChat();
    }
  });
}

function init() {
  cacheDom();
  attachEvents();
  autoResize();
  dom.conversationTitle.textContent = state.activeConversation;
  void syncBackendStatus();
}

document.addEventListener('DOMContentLoaded', init);
