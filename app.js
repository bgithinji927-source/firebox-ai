const API_BASE_URL = '/api';
const STORAGE_KEY = 'firebox-ai-dashboard-state';

const state = {
  isGenerating: false,
  activeConversation: 'API authentication patterns',
  lastUserPrompt: '',
  timeoutId: null,
  attachedFiles: [],
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
  dom.fileInput = document.querySelector('#fileInput');
  dom.attachmentRow = document.querySelector('#attachmentRow');
  dom.searchToggle = document.querySelector('#searchToggle');
  dom.modelSelect = document.querySelector('#modelSelect');
  dom.toast = document.querySelector('#toast');
}

function escapeHtml(value) {
  return value.replace(/[&<>'"]/g, (character) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    "'": '&#039;',
    '"': '&quot;',
  }[character]));
}

function showToast(message) {
  dom.toast.textContent = message;
  dom.toast.classList.add('is-visible');
  clearTimeout(showToast.timeoutId);
  showToast.timeoutId = setTimeout(() => dom.toast.classList.remove('is-visible'), 2800);
}

function setSidebar(open) {
  dom.sidebar.classList.toggle('is-open', open);
  dom.sidebarScrim.classList.toggle('is-visible', open);
}

function autoResize() {
  dom.messageInput.style.height = 'auto';
  dom.messageInput.style.height = `${Math.min(dom.messageInput.scrollHeight, 150)}px`;
}

function persistState() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify({ activeConversation: state.activeConversation }));
}

function restoreState() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY));
    if (saved?.activeConversation) state.activeConversation = saved.activeConversation;
  } catch {
    localStorage.removeItem(STORAGE_KEY);
  }
}

function addUserMessage(prompt) {
  const message = document.createElement('div');
  message.className = 'message-group user-group';
  message.innerHTML = `
    <div class="message-meta user-meta"><span>You</span><span class="message-time">now</span></div>
    <article class="message-card user-message"><p>${escapeHtml(prompt)}</p></article>
  `;
  dom.dynamicMessages.appendChild(message);
  scrollToBottom();
}

function responseMarkup(prompt) {
  const normalized = prompt.toLowerCase();
  if (normalized.includes('python') || normalized.includes('code') || normalized.includes('example')) {
    return `
      <p>Here is a focused starting point. The important part is to keep the network boundary explicit, validate the response, and surface failures instead of silently continuing.</p>
      <div class="code-block">
        <div class="code-header"><span>python · safe_request.py</span><button class="copy-code" type="button" data-copy="import requests\n\ndef fetch_json(url):\n    response = requests.get(url, timeout=10)\n    response.raise_for_status()\n    return response.json()">Copy</button></div>
        <pre><span class="code-keyword">import</span> requests\n\n<span class="code-keyword">def</span> fetch_json(url):\n    response = requests.get(url, timeout=<span class="code-muted">10</span>)\n    response.raise_for_status()\n    <span class="code-keyword">return</span> response.json()</pre>
      </div>
      <p>In production, add authentication, retry policy, structured logging, and a schema check for the JSON payload. This preview has not executed the code.</p>
      <div class="citation-row"><a class="citation" href="https://docs.python.org/3/library/urllib.request.html" target="_blank" rel="noreferrer"><span>↗</span> Python networking docs</a><a class="citation" href="https://requests.readthedocs.io/" target="_blank" rel="noreferrer"><span>↗</span> Requests documentation</a></div>
    `;
  }
  if (normalized.includes('security') || normalized.includes('risk') || normalized.includes('threat')) {
    return `
      <p>Start with the trust boundaries rather than the endpoint list. For a small API, the highest-value review usually covers identity, authorization, input handling, and observability.</p>
      <div class="response-divider"></div>
      <p><strong>1 / Identity:</strong> verify tokens at the edge and reject expired or incorrectly scoped credentials.<br /><strong>2 / Authorization:</strong> check object ownership on every read and write; authentication alone is not authorization.<br /><strong>3 / Input:</strong> validate shape, size, and content before it reaches business logic or a shell/database boundary.<br /><strong>4 / Operations:</strong> log security-relevant decisions without writing secrets or raw tokens to logs.</p>
      <div class="citation-row"><a class="citation" href="https://owasp.org/API-Security/" target="_blank" rel="noreferrer"><span>↗</span> OWASP API Security</a><a class="citation" href="https://csrc.nist.gov/publications/detail/sp/800-63/3/final" target="_blank" rel="noreferrer"><span>↗</span> NIST digital identity</a></div>
    `;
  }
  return `
    <p>A useful way to approach this is to separate the decision into three layers: the goal, the constraints, and the next smallest experiment.</p>
    <div class="response-divider"></div>
    <p><strong>Goal:</strong> define the outcome in one sentence.<br /><strong>Constraints:</strong> list the runtime, data, security, and performance limits that cannot move.<br /><strong>Next experiment:</strong> build the smallest slice that can produce evidence in under an hour.</p>
    <p>This is a local preview response. Connect a model endpoint at <code>/api/chat</code> when you want live reasoning, conversation memory, and grounded retrieval.</p>
    <div class="citation-row"><a class="citation" href="#chat"><span>⌁</span> FIREBOX workspace note</a></div>
  `;
}

function addAssistantMessage(prompt) {
  const message = document.createElement('div');
  message.className = 'message-group assistant-group';
  message.innerHTML = `
    <div class="message-meta"><span class="message-avatar"><img src="/firebox-ai-icon.svg" alt="" /></span><span>FIREBOX AI</span><span class="message-time">now</span><span class="source-label">PREVIEW RESPONSE</span></div>
    <article class="message-card assistant-message">${responseMarkup(prompt)}<div class="response-divider"></div><div class="message-note"><span class="note-mark">i</span> Preview mode · No live model request was made.</div></article>
  `;
  dom.dynamicMessages.appendChild(message);
  dom.regenerateButton.disabled = false;
  scrollToBottom();
}

function scrollToBottom() {
  requestAnimationFrame(() => { dom.chatScroll.scrollTop = dom.chatScroll.scrollHeight; });
}

async function tryLiveRequest(prompt) {
  // The dashboard stays honest when no backend exists. A future API can opt in here.
  if (!API_BASE_URL) return null;
  try {
    const response = await fetch(`${API_BASE_URL}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: prompt, model: dom.modelSelect.value, webSearch: dom.searchToggle.getAttribute('aria-pressed') === 'true' }),
    });
    if (!response.ok) return null;
    return await response.json();
  } catch {
    return null;
  }
}

function setGenerating(isGenerating) {
  state.isGenerating = isGenerating;
  dom.typingRow.classList.toggle('is-hidden', !isGenerating);
  dom.stopButton.classList.toggle('is-hidden', !isGenerating);
  dom.sendButton.disabled = isGenerating;
  dom.messageInput.disabled = isGenerating;
  if (isGenerating) scrollToBottom();
}

async function generateResponse(prompt) {
  setGenerating(true);
  const liveResult = await tryLiveRequest(prompt);
  if (!state.isGenerating) return;
  if (liveResult?.answer) {
    const message = document.createElement('div');
    message.className = 'message-group assistant-group';
    message.innerHTML = `<div class="message-meta"><span class="message-avatar"><img src="/firebox-ai-icon.svg" alt="" /></span><span>FIREBOX AI</span><span class="message-time">now</span><span class="source-label">LIVE MODEL</span></div><article class="message-card assistant-message"><p>${escapeHtml(liveResult.answer)}</p></article>`;
    dom.dynamicMessages.appendChild(message);
    dom.regenerateButton.disabled = false;
    setGenerating(false);
    return;
  }
  state.timeoutId = setTimeout(() => {
    if (!state.isGenerating) return;
    setGenerating(false);
    addAssistantMessage(prompt);
  }, 900);
}

function submitPrompt(prompt) {
  const trimmed = prompt.trim();
  if (!trimmed || state.isGenerating) return;
  state.lastUserPrompt = trimmed;
  dom.messageInput.value = '';
  autoResize();
  dom.quickPrompts.classList.add('is-hidden');
  addUserMessage(trimmed);
  generateResponse(trimmed);
}

function stopGeneration() {
  if (!state.isGenerating) return;
  clearTimeout(state.timeoutId);
  setGenerating(false);
  const message = document.createElement('div');
  message.className = 'message-group assistant-group';
  message.innerHTML = '<article class="message-card assistant-message"><div class="message-note"><span class="note-mark">×</span> Generation stopped by user.</div></article>';
  dom.dynamicMessages.appendChild(message);
  showToast('Generation stopped.');
}

function renderAttachments() {
  dom.attachmentRow.innerHTML = state.attachedFiles.map((file, index) => `
    <span class="attachment-chip"><span aria-hidden="true">▧</span>${escapeHtml(file.name)}<button type="button" data-remove-file="${index}" aria-label="Remove ${escapeHtml(file.name)}">×</button></span>
  `).join('');
  dom.attachmentRow.classList.toggle('is-hidden', state.attachedFiles.length === 0);
}

function setConversation(button) {
  document.querySelectorAll('.conversation-item').forEach((item) => item.classList.remove('is-active'));
  button.classList.add('is-active');
  state.activeConversation = button.dataset.conversation;
  dom.conversationTitle.textContent = state.activeConversation;
  persistState();
  setSidebar(false);
  showToast(`Opened “${state.activeConversation}”.`);
}

function createNewChat() {
  document.querySelectorAll('.conversation-item').forEach((item) => item.classList.remove('is-active'));
  state.activeConversation = 'New technical session';
  dom.conversationTitle.textContent = state.activeConversation;
  dom.dynamicMessages.innerHTML = '';
  dom.quickPrompts.classList.remove('is-hidden');
  dom.regenerateButton.disabled = true;
  state.lastUserPrompt = '';
  dom.messageInput.value = '';
  autoResize();
  setSidebar(false);
  persistState();
  showToast('New conversation started.');
}

function toggleSearch() {
  const enabled = dom.searchToggle.getAttribute('aria-pressed') !== 'true';
  dom.searchToggle.setAttribute('aria-pressed', String(enabled));
  showToast(enabled ? 'Web search enabled for the next request.' : 'Web search disabled.');
}

function attachEvents() {
  dom.menuButton.addEventListener('click', () => setSidebar(true));
  dom.sidebarScrim.addEventListener('click', () => setSidebar(false));
  dom.newChatButton.addEventListener('click', createNewChat);
  dom.searchToggle.addEventListener('click', toggleSearch);
  dom.messageInput.addEventListener('input', autoResize);
  dom.messageInput.addEventListener('keydown', (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
      event.preventDefault();
      submitPrompt(dom.messageInput.value);
    }
  });
  dom.composer.addEventListener('submit', (event) => {
    event.preventDefault();
    submitPrompt(dom.messageInput.value);
  });
  dom.stopButton.addEventListener('click', stopGeneration);
  dom.regenerateButton.addEventListener('click', () => {
    if (state.lastUserPrompt && !state.isGenerating) generateResponse(state.lastUserPrompt);
  });
  dom.fileInput.addEventListener('change', (event) => {
    state.attachedFiles.push(...Array.from(event.target.files));
    renderAttachments();
    event.target.value = '';
    if (state.attachedFiles.length) showToast(`${state.attachedFiles.length} file${state.attachedFiles.length === 1 ? '' : 's'} attached for the next request.`);
  });
  dom.conversationList.addEventListener('click', (event) => {
    const button = event.target.closest('.conversation-item');
    if (button) setConversation(button);
  });
  document.addEventListener('click', async (event) => {
    const promptButton = event.target.closest('[data-prompt]');
    if (promptButton) {
      dom.messageInput.value = promptButton.dataset.prompt;
      autoResize();
      dom.messageInput.focus();
      return;
    }
    const removeButton = event.target.closest('[data-remove-file]');
    if (removeButton) {
      state.attachedFiles.splice(Number(removeButton.dataset.removeFile), 1);
      renderAttachments();
      return;
    }
    const copyButton = event.target.closest('[data-copy]');
    if (copyButton) {
      try {
        await navigator.clipboard.writeText(copyButton.dataset.copy);
        copyButton.textContent = 'Copied';
        setTimeout(() => { copyButton.textContent = 'Copy'; }, 1500);
      } catch {
        showToast('Copy is unavailable in this browser context.');
      }
      return;
    }
    const toastTarget = event.target.closest('[data-toast]');
    if (toastTarget) showToast(toastTarget.dataset.toast);
  });
}

function init() {
  cacheDom();
  restoreState();
  attachEvents();
  autoResize();
}

document.addEventListener('DOMContentLoaded', init);
