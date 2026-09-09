'use strict';
const menuButton = document.querySelector('.menu-toggle');
const nav = document.querySelector('.nav-links');
menuButton.addEventListener('click', () => {
  const expanded = menuButton.getAttribute('aria-expanded') !== 'true';
  menuButton.setAttribute('aria-expanded', String(expanded));
  nav.classList.toggle('is-open', expanded);
});
nav.querySelectorAll('a').forEach(link => link.addEventListener('click', () => {
  nav.classList.remove('is-open');
  menuButton.setAttribute('aria-expanded', 'false');
}));
document.addEventListener('keydown', event => {
  if (event.key === 'Escape' && nav.classList.contains('is-open')) {
    nav.classList.remove('is-open'); menuButton.setAttribute('aria-expanded', 'false'); menuButton.focus();
  }
});
const languageLink = document.querySelector('.language-toggle');
languageLink.addEventListener('click', () => {
  languageLink.href = '?lang=' + (document.body.dataset.lang === 'en' ? 'zh' : 'en') + window.location.hash;
});
const sections = document.querySelectorAll('main > section[id]');
const observer = new IntersectionObserver(entries => {
  entries.forEach(entry => {
    if (!entry.isIntersecting) return;
    nav.querySelectorAll('a').forEach(link => {
      if (link.hash === '#' + entry.target.id) link.setAttribute('aria-current', 'location');
      else link.removeAttribute('aria-current');
    });
  });
}, {rootMargin: '-15% 0px -65% 0px'});
sections.forEach(section => observer.observe(section));

const dialog = document.querySelector('#chat-dialog');
const form = document.querySelector('#chat-form');
let csrf = '', pollTimer = null, busy = false, initialized = false, lastMessages = '';
let submission = null;
const status = document.querySelector('#chat-status');
const messages = document.querySelector('#chat-messages');
const sendButton = document.querySelector('#chat-send');
const labels = dialog.dataset;
function setStatus(message, isError = false) {
  if (!status) return;
  status.textContent = message;
  status.classList.toggle('error', isError);
}
function buttonText(value) { if (sendButton) sendButton.textContent = value; }
async function initializeSession() {
  const response = await fetch('/api/chat/session', {cache: 'no-store'});
  if (!response.ok) throw new Error('session');
  const data = await response.json();
  if (!data.enabled || !data.csrf) throw new Error('session');
  csrf = data.csrf;
  initialized = true;
}
async function pollMessages() {
  if (!dialog.open || !form) return;
  try {
    const response = await fetch('/api/chat/messages', {cache: 'no-store'});
    if (!response.ok) throw new Error('poll');
    const data = await response.json();
    const signature = JSON.stringify(data.messages);
    if (signature !== lastMessages) {
      const existingIds = new Set([...messages.children].map(node => node.dataset.id));
      for (const msg of data.messages) {
        let node = messages.querySelector('[data-id="' + Number(msg.id) + '"]');
        if (!node) {
          node = document.createElement('div');
          node.dataset.id = String(msg.id);
          node.className = 'chat-message ' + (msg.direction === 'professor' ? 'professor' : 'student');
          const heading = document.createElement('small');
          const date = new Intl.DateTimeFormat(document.documentElement.lang, {hour: '2-digit', minute: '2-digit'}).format(new Date(msg.created * 1000));
          heading.textContent = (msg.direction === 'professor' ? labels.chatTeacher + ' · ' : '') + date;
          const body = document.createElement('span'); body.textContent = msg.body;
          node.append(heading, body);
          messages.append(node);
        }
        existingIds.delete(String(msg.id));
        let delivery = node.querySelector('.delivery-status');
        if (msg.status !== 'accepted') {
          if (!delivery) { delivery = document.createElement('span'); delivery.className = 'delivery-status'; node.append(delivery); }
          delivery.textContent = msg.status === 'failed' ? labels.chatFailed : labels.chatPending;
          if (msg.request_id && !node.querySelector('.retry-message') && Date.now() / 1000 - msg.created < 23 * 3600) {
            const retry = document.createElement('button');
            retry.type = 'button'; retry.className = 'retry-message'; retry.textContent = labels.chatRetry;
            retry.addEventListener('click', () => {
              if (busy) return;
              form.elements.name.value = msg.name; form.elements.message.value = msg.body;
              submission = {name: msg.name, message: msg.body, request_id: msg.request_id, website: ''};
              form.requestSubmit();
            });
            node.append(retry);
          }
        } else { delivery?.remove(); node.querySelector('.retry-message')?.remove(); }
      }
      existingIds.forEach(id => messages.querySelector('[data-id="' + Number(id) + '"]')?.remove());
      lastMessages = signature;
      const scroller = document.querySelector('.chat-scroll'); scroller.scrollTop = scroller.scrollHeight;
    }
    if (status?.textContent === labels.chatFetchError) setStatus('');
  } catch (_) { setStatus(labels.chatFetchError, true); }
}
document.querySelectorAll('.open-chat').forEach(button => button.addEventListener('click', async () => {
  dialog.showModal();
  if (!form) return;
  try {
    await initializeSession();
    await pollMessages();
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = setInterval(() => { if (!document.hidden) pollMessages(); }, 3500);
  } catch (_) { setStatus(labels.chatSession, true); }
}));
document.querySelector('.chat-close').addEventListener('click', () => dialog.close());
dialog.addEventListener('close', () => { clearInterval(pollTimer); pollTimer = null; });
dialog.addEventListener('click', event => {
  if (event.target !== dialog) return;
  const rect = dialog.getBoundingClientRect();
  if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) dialog.close();
});
if (form) form.addEventListener('submit', async event => {
  event.preventDefault();
  if (busy || !form.reportValidity()) return;
  const name = form.elements.name.value.trim(), message = form.elements.message.value.trim();
  if (!name || !message) return;
  if (!submission || submission.name !== name || submission.message !== message) {
    submission = {name, message, request_id: crypto.randomUUID(), website: form.elements.website.value};
  }
  busy = true; sendButton.disabled = true;
  form.elements.name.readOnly = true; form.elements.message.readOnly = true;
  buttonText(labels.chatSending); setStatus('');
  try {
    if (!initialized) await initializeSession();
    const response = await fetch('/api/chat/messages', {
      method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf}, body: JSON.stringify(submission)
    });
    const data = await response.json();
    if (!response.ok) {
      if (response.status === 403) { initialized = false; setStatus(labels.chatSession, true); }
      else if (response.status === 429) setStatus(labels.chatRate, true);
      else setStatus(labels.chatFailure, true);
      buttonText(labels.chatRetry);
    } else if (data.status === 'accepted') {
      setStatus(labels.chatAccepted);
      form.elements.message.value = ''; submission = null;
      buttonText(labels.chatSend);
    }
    await pollMessages();
  } catch (_) { setStatus(labels.chatFailure, true); buttonText(labels.chatRetry); }
  finally { busy = false; sendButton.disabled = false; form.elements.name.readOnly = false; form.elements.message.readOnly = false; }
});
// Updated Markdown appears on refresh; idle open pages also refresh automatically.
setInterval(async () => {
  if (document.hidden || dialog.open || busy) return;
  try {
    const response = await fetch('/api/content/version', {cache: 'no-store'});
    if (response.ok && (await response.json()).version !== document.body.dataset.version) location.reload();
  } catch (_) { /* Keep the current page available during a temporary outage. */ }
}, 30000);
