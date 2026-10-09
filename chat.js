const api = async (path, options = {}) => {
  const response = await fetch(`/api${path}`, {
    ...options,
    headers: { Accept: 'application/json', 'Content-Type': 'application/json', ...(options.headers || {}) },
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || `Request failed (${response.status})`);
  return payload;
};

const state = { conversationId: null, busy: false };
const messages = document.querySelector('#messages');
const welcome = document.querySelector('#welcome');
const composer = document.querySelector('#composer');
const input = document.querySelector('#message');
const send = document.querySelector('#send');
const typing = document.querySelector('#typing');

function escapeHtml(value) {
  return String(value).replace(/[&<>'"]/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#039;', '"': '&quot;' }[character]));
}

function scrollToBottom() { messages.scrollTop = messages.scrollHeight; }

function addMessage(role, content, sources = []) {
  welcome.classList.add('is-hidden');
  const item = document.createElement('article');
  item.className = `message ${role}`;
  if (role === 'assistant') {
    const sourceMarkup = sources.length
      ? `<div class="sources">${sources.map((source, index) => `<span class="source">[S${index + 1}] ${escapeHtml(source.title || 'Source')}${source.page ? ` — p. ${source.page}` : ''}</span>`).join('')}</div>`
      : '';
    item.innerHTML = `<div class="assistant-label">FIREBOX AI</div><div class="bubble">${escapeHtml(content)}</div>${sourceMarkup}`;
  } else {
    item.innerHTML = `<div class="bubble">${escapeHtml(content)}</div>`;
  }
  messages.appendChild(item);
  scrollToBottom();
}

function setBusy(value) {
  state.busy = value;
  send.disabled = value;
  input.disabled = value;
  typing.classList.toggle('is-hidden', !value);
  if (value) scrollToBottom();
}

async function startConversation() {
  const result = await api('/conversations', { method: 'POST', body: JSON.stringify({ title: 'User chat' }) });
  state.conversationId = result.id;
}

async function submit(text) {
  const prompt = text.trim();
  if (!prompt || state.busy) return;
  addMessage('user', prompt);
  input.value = '';
  input.style.height = 'auto';
  setBusy(true);
  try {
    if (!state.conversationId) await startConversation();
    await api(`/conversations/${encodeURIComponent(state.conversationId)}/messages`, {
      method: 'POST', body: JSON.stringify({ role: 'user', content: prompt }),
    });
    const result = await api('/chat', {
      method: 'POST',
      body: JSON.stringify({ message: prompt, conversation_id: state.conversationId, webSearch: false }),
    });
    addMessage('assistant', result.answer, result.sources || []);
    await api(`/conversations/${encodeURIComponent(state.conversationId)}/messages`, {
      method: 'POST',
      body: JSON.stringify({ role: 'assistant', content: result.answer, metadata: { sources: result.sources || [], teacher_review_id: result.teacher_review_id || null } }),
    });
  } catch (error) {
    addMessage('assistant', `I could not answer that request. ${error.message}`);
  } finally {
    setBusy(false);
    input.focus();
  }
}

composer.addEventListener('submit', (event) => { event.preventDefault(); void submit(input.value); });
input.addEventListener('input', () => { input.style.height = 'auto'; input.style.height = `${Math.min(input.scrollHeight, 140)}px`; });
input.addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); void submit(input.value); }
});
document.querySelectorAll('[data-prompt]').forEach((button) => button.addEventListener('click', () => void submit(button.dataset.prompt)));
document.querySelector('#newChat').addEventListener('click', () => {
  state.conversationId = null;
  messages.querySelectorAll('.message').forEach((item) => item.remove());
  welcome.classList.remove('is-hidden');
  input.focus();
});
