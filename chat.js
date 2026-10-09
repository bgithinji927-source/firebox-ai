const state = { conversationId: null, busy: false, webSearch: false, documents: [], media: [], lastPrompt: '' };
const $ = (selector) => document.querySelector(selector);
const messages = $('#messages');
const welcome = $('#welcome');
const composer = $('#composer');
const input = $('#message');
const send = $('#send');
const typing = $('#typing');
const attachmentPreview = $('#attachmentPreview');
const toast = $('#toast');

const api = async (path, options = {}) => {
  const response = await fetch(`/api${path}`, {
    ...options,
    headers: { Accept: 'application/json', ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }), ...(options.headers || {}) },
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || `Request failed (${response.status})`);
  return payload;
};

function escapeHtml(value) {
  return String(value).replace(/[&<>'"]/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#039;', '"': '&quot;' }[character]));
}
function showToast(message) {
  toast.textContent = message;
  toast.classList.add('is-visible');
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => toast.classList.remove('is-visible'), 4200);
}
function scrollToBottom() { requestAnimationFrame(() => { messages.scrollTop = messages.scrollHeight; }); }
function setBusy(value) {
  state.busy = value;
  send.disabled = value;
  input.disabled = value;
  typing.classList.toggle('is-hidden', !value);
  $('#statusText').textContent = value ? 'Composing' : 'Ready';
  if (value) scrollToBottom();
}
function resizeInput() {
  input.style.height = 'auto';
  input.style.height = `${Math.min(input.scrollHeight, 150)}px`;
}

function inlineMarkdown(text) {
  let html = escapeHtml(text).replace(/\[(?:s|S)\d+\]\s*/g, '');
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
  html = html.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');
  return html;
}

function highlightCode(code, language = '') {
  let html = escapeHtml(code);
  html = html.replace(/\b(const|let|var|function|return|if|else|for|while|class|new|import|from|export|async|await|def|in|True|False|None|try|except|with|as|SELECT|FROM|WHERE|JOIN|INSERT|INTO|UPDATE|DELETE)\b/g, '<span class="syntax-keyword">$1</span>');
  html = html.replace(/(&quot;[^&\n]*?&quot;|&#039;[^'\n]*?&#039;|`[^`\n]*?`)/g, '<span class="syntax-string">$1</span>');
  html = html.replace(/(\/\/[^\n]*|#[^\n]*|--[^\n]*)/g, '<span class="syntax-comment">$1</span>');
  html = html.replace(/\b(\d+(?:\.\d+)?)\b/g, '<span class="syntax-number">$1</span>');
  return html;
}

function renderCardRail(rows, mode = 'info') {
  const cards = rows.map((row) => {
    const separator = row.indexOf('|');
    const title = separator >= 0 ? row.slice(0, separator).trim() : row.trim();
    const description = separator >= 0 ? row.slice(separator + 1).trim() : '';
    if (!title) return '';
    const control = mode === 'checklist'
      ? '<label class="generated-card-check"><input type="checkbox" aria-label="Mark complete" /><span>Done</span></label>'
      : mode === 'suggestions'
        ? `<button class="generated-card-send" type="button" data-send-suggestion="${escapeHtml(description ? `${title}: ${description}` : title)}" aria-label="Send suggestion">↑ Send</button>`
        : '';
    return `<article class="generated-card ${mode === 'checklist' ? 'is-checklist' : ''}"><span class="generated-card-icon">${mode === 'checklist' ? '☑' : mode === 'suggestions' ? '✦' : '✦'}</span><h3>${inlineMarkdown(title)}</h3>${description ? `<p>${inlineMarkdown(description)}</p>` : ''}${control}</article>`;
  }).filter(Boolean);
  if (!cards.length) return '';
  return `<section class="generated-card-rail" aria-label="Generated interface cards"><div class="generated-card-rail-label">Generated interface</div><div class="generated-card-scroller">${cards.join('')}</div></section>`;
}

function renderApprovalBlock(rows) {
  const row = rows.find(Boolean) || 'Continue | Approve this next step';
  const separator = row.indexOf('|');
  const title = separator >= 0 ? row.slice(0, separator).trim() : row.trim();
  const description = separator >= 0 ? row.slice(separator + 1).trim() : '';
  const action = `Approved: ${title}. Continue with the next step.`;
  return `<section class="approval-block" aria-label="Approval required"><div class="approval-kicker">Approval required</div><h3>${inlineMarkdown(title)}</h3>${description ? `<p>${inlineMarkdown(description)}</p>` : ''}<div class="approval-actions"><button type="button" class="approval-button" data-approve-action="${escapeHtml(action)}">✓ Approve and continue</button><button type="button" class="approval-dismiss" data-approval-dismiss>Not now</button></div></section>`;
}

function renderActionButtons(rows) {
  const buttons = rows.map((row) => {
    const separator = row.indexOf('|');
    const label = separator >= 0 ? row.slice(0, separator).trim() : row.trim();
    const prompt = separator >= 0 ? row.slice(separator + 1).trim() : label;
    return label ? `<button type="button" class="generated-action-button" data-send-suggestion="${escapeHtml(prompt)}">${inlineMarkdown(label)} <span aria-hidden="true">→</span></button>` : '';
  }).filter(Boolean);
  return buttons.length ? `<div class="generated-actions" aria-label="Generated actions">${buttons.join('')}</div>` : '';
}

function renderFlowChart(rows, direction = 'horizontal') {
  const nodes = [];
  rows.forEach((row) => row.split(/\s*[-=]+>\s*/).map((item) => item.trim()).filter(Boolean).forEach((item) => { if (!nodes.includes(item)) nodes.push(item); }));
  if (!nodes.length) return '';
  return `<section class="generated-flow" aria-label="Generated flow chart"><div class="generated-card-rail-label">Generated flow chart</div><div class="flow-track ${direction === 'vertical' ? 'is-vertical' : ''}">${nodes.map((node, index) => `${index ? '<span class="flow-arrow" aria-hidden="true">→</span>' : ''}<div class="flow-node">${inlineMarkdown(node)}</div>`).join('')}</div></section>`;
}

function renderMarkdown(source) {
  const lines = String(source || '').replace(/\r/g, '').split('\n');
  const output = [];
  let paragraph = [];
  let list = [];
  let ordered = false;
  let code = null;
  let quote = [];
  let cards = null;
  let cardMode = 'info';
  let special = null;
  let specialMode = '';
  const flushParagraph = () => { if (paragraph.length) { output.push(`<p>${inlineMarkdown(paragraph.join(' '))}</p>`); paragraph = []; } };
  const flushList = () => { if (!list.length) return; const tag = ordered ? 'ol' : 'ul'; output.push(`<${tag}>${list.map((item) => `<li>${inlineMarkdown(item)}</li>`).join('')}</${tag}>`); list = []; ordered = false; };
  const flushQuote = () => { if (quote.length) { output.push(`<blockquote>${quote.map((item) => inlineMarkdown(item)).join('<br>')}</blockquote>`); quote = []; } };
  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index];
    const specialStart = line.trim().match(/^:::(approve|buttons|flow)(?:\s+(vertical))?$/i);
    if (specialStart) { flushParagraph(); flushList(); flushQuote(); special = []; specialMode = `${specialStart[1].toLowerCase()}${specialStart[2] ? `-${specialStart[2].toLowerCase()}` : ''}`; continue; }
    if (special) {
      if (line.trim() === ':::') {
        if (specialMode === 'approve') output.push(renderApprovalBlock(special));
        if (specialMode === 'buttons') output.push(renderActionButtons(special));
        if (specialMode === 'flow' || specialMode === 'flow-vertical') output.push(renderFlowChart(special, specialMode === 'flow-vertical' ? 'vertical' : 'horizontal'));
        special = null; specialMode = '';
      } else if (line.trim()) special.push(line.trim());
      continue;
    }
    if (line.trim().toLowerCase().startsWith(':::cards')) { flushParagraph(); flushList(); flushQuote(); cards = []; cardMode = line.trim().split(/\s+/)[1]?.toLowerCase() || 'info'; continue; }
    if (cards) {
      if (line.trim() === ':::') { output.push(renderCardRail(cards, cardMode)); cards = null; cardMode = 'info'; }
      else if (line.trim()) cards.push(line.trim().replace(/^[-*]\s+/, ''));
      continue;
    }
    if (line.trim().startsWith('```')) {
      if (code) {
        const id = `code-${Math.random().toString(36).slice(2)}`;
        window.__fireboxCode = window.__fireboxCode || {};
        window.__fireboxCode[id] = code.text;
        output.push(`<div class="code-card"><div class="code-card-head"><span>${escapeHtml(code.language || 'code')}</span><span><button type="button" data-copy-code="${id}">Copy</button> <button type="button" data-verify-code="${id}">Verify</button></span></div><pre><code>${highlightCode(code.text, code.language)}</code></pre></div>`);
        code = null;
      } else {
        flushParagraph(); flushList(); code = { language: line.trim().slice(3).trim(), text: '' };
      }
      continue;
    }
    if (code) { code.text += `${line}${index < lines.length - 1 ? '\n' : ''}`; continue; }
    const quoteLine = line.match(/^\s*>\s?(.*)$/);
    if (quoteLine) { flushParagraph(); flushList(); quote.push(quoteLine[1]); continue; }
    if (quote.length) flushQuote();
    const tableNext = lines[index + 1] || '';
    if (/^\s*\|/.test(line) && /^\s*\|?\s*:?-{3,}/.test(tableNext)) {
      flushParagraph(); flushList();
      const parseRow = (row) => row.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map((cell) => cell.trim());
      const head = parseRow(line); const rows = []; index += 2;
      while (index < lines.length && /^\s*\|/.test(lines[index])) { rows.push(parseRow(lines[index])); index += 1; }
      index -= 1;
      output.push(`<div class="rich-table-wrap"><table class="rich-table"><thead><tr>${head.map((cell) => `<th>${inlineMarkdown(cell)}</th>`).join('')}</tr></thead><tbody>${rows.map((row) => `<tr>${head.map((_, cellIndex) => `<td>${inlineMarkdown(row[cellIndex] || '')}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`);
      continue;
    }
    const heading = line.match(/^#{1,6}\s+(.+)/);
    const bullet = line.match(/^\s*[-*]\s+(?:\[[ xX]\]\s*)?(.+)/);
    const number = line.match(/^\s*\d+[.)]\s+(.+)/);
    if (heading) { flushParagraph(); flushList(); const level = Math.min(6, line.match(/^#+/)[0].length); output.push(`<h${level}>${inlineMarkdown(heading[1])}</h${level}>`); continue; }
    if (bullet || number) { if (number && !ordered) { flushList(); ordered = true; } if (bullet && ordered) flushList(); list.push((bullet || number)[1]); continue; }
    if (!line.trim()) {
      flushParagraph();
      const nextLine = lines[index + 1] || '';
      if (!/^\s*(?:[-*]|\d+[.)])\s+/.test(nextLine)) flushList();
      continue;
    }
    paragraph.push(line.trim());
  }
  if (cards) output.push(renderCardRail(cards, cardMode));
  if (special) {
    if (specialMode === 'approve') output.push(renderApprovalBlock(special));
    if (specialMode === 'buttons') output.push(renderActionButtons(special));
    if (specialMode === 'flow' || specialMode === 'flow-vertical') output.push(renderFlowChart(special, specialMode === 'flow-vertical' ? 'vertical' : 'horizontal'));
  }
  if (code) output.push(`<div class="code-card"><div class="code-card-head"><span>${escapeHtml(code.language || 'code')}</span></div><pre><code>${highlightCode(code.text, code.language)}</code></pre></div>`);
  flushParagraph(); flushList(); flushQuote();
  return output.join('') || '<p>No content returned.</p>';
}

function generatedPanel(prompt, answer) {
  const checklist = /checklist|steps|plan|to-do|todo/i.test(prompt) || /- \[[ xX]\]/.test(answer);
  if (!checklist) return '';
  const items = answer.split('\n').map((line) => line.match(/^\s*(?:[-*]|\d+[.)])\s+(?:\[[ xX]\]\s*)?(.+)/)?.[1]).filter(Boolean).slice(0, 12);
  if (!items.length) return '';
  return `<section class="generated-panel"><div class="generated-label">Interactive checklist · generated from this answer</div>${items.map((item) => `<label class="generated-check"><input type="checkbox" /> <span>${inlineMarkdown(item)}</span></label>`).join('')}</section>`;
}
function sourceCards(sources = []) {
  return '';
}

function addMessage(role, content, sources = [], prompt = '') {
  welcome.classList.add('is-hidden');
  const item = document.createElement('article');
  item.className = `message ${role}`;
  if (role === 'user') {
    item.innerHTML = `<div class="bubble">${escapeHtml(content).replace(/\n/g, '<br>')}</div>`;
  } else {
    item.innerHTML = `<div class="assistant-label">FIREBOX AI · RICH RESPONSE</div><div class="bubble"><div class="rich-content">${renderMarkdown(content)}</div>${generatedPanel(prompt, content)}${sourceCards(sources)}<div class="response-actions"><button class="response-action icon-action" type="button" data-copy-answer aria-label="Copy answer" title="Copy answer"><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="8" y="8" width="11" height="11" rx="2"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/></svg></button><button class="response-action icon-action" type="button" data-share-answer aria-label="Share answer" title="Share answer"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="18" cy="5" r="2.5"/><circle cx="6" cy="12" r="2.5"/><circle cx="18" cy="19" r="2.5"/><path d="m8.2 10.8 7.5-4.4m-7.5 6.8 7.5 4.4"/></svg></button><button class="response-action icon-action" type="button" data-regenerate aria-label="Regenerate answer" title="Regenerate answer"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 11a8 8 0 0 0-14.9-4L3 10m0-4v4h4M4 13a8 8 0 0 0 14.9 4L21 14m0 4v-4h-4"/></svg></button></div></div>`;
    item.dataset.prompt = prompt;
  }
  messages.appendChild(item);
  scrollToBottom();
  return item;
}

async function startConversation(title) {
  const result = await api('/conversations', { method: 'POST', body: JSON.stringify({ title }) });
  state.conversationId = result.id;
}
async function persistMessage(role, content, metadata = {}) {
  if (!state.conversationId) return;
  await api(`/conversations/${encodeURIComponent(state.conversationId)}/messages`, { method: 'POST', body: JSON.stringify({ role, content, metadata }) });
}

async function submit(rawText) {
  const prompt = rawText.trim();
  if (!prompt || state.busy) return;
  state.lastPrompt = prompt;
  addMessage('user', prompt);
  input.value = ''; resizeInput(); setBusy(true);
  try {
    if (!state.conversationId) await startConversation(prompt.slice(0, 72));
    await persistMessage('user', prompt);
    const result = await api('/chat', { method: 'POST', body: JSON.stringify({ message: prompt, conversation_id: state.conversationId, webSearch: state.webSearch, document_ids: state.documents.map((doc) => doc.id) }) });
    addMessage('assistant', result.answer, result.sources || [], prompt);
    await persistMessage('assistant', result.answer, { sources: result.sources || [], teacher_review_id: result.teacher_review_id || null });
  } catch (error) {
    addMessage('assistant', `I could not complete that request. ${error.message}`);
  } finally { setBusy(false); input.focus(); }
}

async function uploadFile(file) {
  const supported = ['.pdf', '.txt', '.md', '.csv', '.json', '.py', '.js', '.ts'].some((extension) => file.name.toLowerCase().endsWith(extension));
  if (!supported) {
    state.media.push({ name: file.name, type: file.type, url: file.type.startsWith('image/') ? URL.createObjectURL(file) : null });
    renderAttachments();
    showToast(`${file.name} is previewed locally. This deployment grounds answers from PDF and text files.`);
    return;
  }
  const form = new FormData(); form.append('file', file);
  try {
    const document = await api('/documents/upload', { method: 'POST', body: form });
    state.documents.push(document); renderAttachments();
    showToast(`${file.name} is ready as knowledge for the next answer.`);
  } catch (error) { showToast(`Could not upload ${file.name}: ${error.message}`); }
}
function renderAttachments() {
  const documentChips = state.documents.map((doc, index) => `<span class="attachment-chip"><span aria-hidden="true">▧</span><span>${escapeHtml(doc.filename)}</span><button type="button" data-remove-document="${index}" aria-label="Remove ${escapeHtml(doc.filename)}">×</button></span>`).join('');
  const mediaChips = state.media.map((file, index) => `<span class="attachment-chip">${file.url ? `<img src="${file.url}" alt="" />` : '<span aria-hidden="true">◉</span>'}<span>${escapeHtml(file.name)}</span><button type="button" data-remove-media="${index}" aria-label="Remove ${escapeHtml(file.name)}">×</button></span>`).join('');
  attachmentPreview.innerHTML = `${documentChips}${mediaChips}${state.media.length ? '<span class="attachment-note">Media preview attached; add a prompt to continue.</span>' : ''}`;
  attachmentPreview.classList.toggle('is-hidden', !documentChips && !mediaChips);
}
async function verifyCode(id, button) {
  const code = window.__fireboxCode?.[id] || '';
  const language = button.closest('.code-card')?.querySelector('.code-card-head span')?.textContent || 'code';
  const tool = language.toLowerCase().includes('python') ? 'python_syntax' : language.toLowerCase().includes('json') ? 'json_validate' : null;
  if (!tool) return showToast('Verification is available for Python and JSON code blocks.');
  button.disabled = true;
  try { const result = await api('/tools/verify', { method: 'POST', body: JSON.stringify({ tool, input: code }) }); showToast(result.message); }
  catch (error) { showToast(`Verification failed: ${error.message}`); }
  finally { button.disabled = false; }
}

composer.addEventListener('submit', (event) => { event.preventDefault(); void submit(input.value); });
input.addEventListener('input', resizeInput);
input.addEventListener('keydown', (event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); void submit(input.value); } });
document.querySelectorAll('[data-prompt]').forEach((button) => button.addEventListener('click', () => { if (button.dataset.scroll) $('#composer').scrollIntoView({ behavior: 'smooth', block: 'center' }); void submit(button.dataset.prompt); }));
$('#newChat').addEventListener('click', () => { state.conversationId = null; state.documents = []; state.media = []; messages.querySelectorAll('.message').forEach((item) => item.remove()); welcome.classList.remove('is-hidden'); renderAttachments(); input.focus(); });
$('#shareChat').addEventListener('click', async () => {
  const shareData = { title: 'FIREBOX AI chat', text: 'Chat with FIREBOX AI', url: window.location.href };
  try {
    if (navigator.share) await navigator.share(shareData);
    else { await navigator.clipboard.writeText(window.location.href); showToast('Chat link copied.'); }
  } catch (error) { if (error.name !== 'AbortError') showToast('Chat sharing is unavailable.'); }
});
$('#searchButton').addEventListener('click', () => { state.webSearch = !state.webSearch; $('#searchButton').setAttribute('aria-pressed', String(state.webSearch)); showToast(state.webSearch ? 'Web search is on for the next answer.' : 'Web search is off.'); });
$('#attachButton').addEventListener('click', () => $('#fileInput').click());
$('#fileInput').addEventListener('change', async (event) => { for (const file of event.target.files) await uploadFile(file); event.target.value = ''; });
attachmentPreview.addEventListener('click', (event) => { const documentIndex = event.target.closest('[data-remove-document]')?.dataset.removeDocument; const mediaIndex = event.target.closest('[data-remove-media]')?.dataset.removeMedia; if (documentIndex !== undefined) state.documents.splice(Number(documentIndex), 1); if (mediaIndex !== undefined) { const removed = state.media.splice(Number(mediaIndex), 1)[0]; if (removed?.url) URL.revokeObjectURL(removed.url); } renderAttachments(); });
messages.addEventListener('click', async (event) => {
  const suggestion = event.target.closest('[data-send-suggestion]');
  const approve = event.target.closest('[data-approve-action]');
  const dismissApproval = event.target.closest('[data-approval-dismiss]');
  const copyCode = event.target.closest('[data-copy-code]');
  const verify = event.target.closest('[data-verify-code]');
  const copyAnswer = event.target.closest('[data-copy-answer]');
  const regenerate = event.target.closest('[data-regenerate]');
  if (copyCode) { await navigator.clipboard.writeText(window.__fireboxCode?.[copyCode.dataset.copyCode] || ''); showToast('Code copied.'); }
  if (suggestion) void submit(suggestion.dataset.sendSuggestion || '');
  if (approve) { approve.disabled = true; approve.closest('.approval-block')?.classList.add('is-approved'); void submit(approve.dataset.approveAction || 'Approved. Continue.'); }
  if (dismissApproval) dismissApproval.closest('.approval-block')?.classList.add('is-dismissed');
  if (verify) await verifyCode(verify.dataset.verifyCode, verify);
  if (copyAnswer) { const content = copyAnswer.closest('.bubble')?.querySelector('.rich-content')?.innerText || ''; await navigator.clipboard.writeText(content); showToast('Answer copied.'); }
  const shareAnswer = event.target.closest('[data-share-answer]');
  if (shareAnswer) {
    const content = shareAnswer.closest('.bubble')?.querySelector('.rich-content')?.innerText || '';
    try { if (navigator.share) await navigator.share({ title: 'FIREBOX AI answer', text: content, url: window.location.href }); else { await navigator.clipboard.writeText(content); showToast('Answer copied for sharing.'); } }
    catch (error) { if (error.name !== 'AbortError') showToast('Answer sharing is unavailable.'); }
  }
  if (regenerate) void submit(regenerate.closest('.message')?.dataset.prompt || state.lastPrompt);
});
