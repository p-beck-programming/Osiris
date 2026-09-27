const state = {
  currentPage: 'osiris',
  currentIdeaId: null,
  ideasView: localStorage.getItem('osiris-ideas-view') || 'grid',
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

function escapeHtml(value = '') {
  return value.replace(/[&<>'"]/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[ch]));
}

function formatDate(iso, withTime = false) {
  const d = new Date(iso);
  return new Intl.DateTimeFormat(undefined, withTime
    ? { month:'short', day:'numeric', year:'numeric', hour:'numeric', minute:'2-digit' }
    : { month:'short', day:'numeric' }
  ).format(d);
}

function showToast(message) {
  const toast = $('#toast');
  toast.textContent = message;
  toast.classList.add('show');
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => toast.classList.remove('show'), 2400);
}

async function api(path, options = {}) {
  const headers = {...(options.headers || {})};
  if (options.body && !(options.body instanceof FormData)) headers['Content-Type'] = 'application/json';
  const response = await fetch(path, {...options, headers});
  let data = null;
  try { data = await response.json(); } catch { /* no body */ }
  if (!response.ok) throw new Error(data?.detail || `Request failed (${response.status})`);
  return data;
}

function ideaCard(idea) {
  const preview = idea.latest_note || idea.notes?.at(-1)?.content || '';
  const noteCount = idea.note_count ?? idea.notes?.length ?? 1;
  return `
    <article class="idea-card ${idea.status === 'archived' ? 'archived' : ''}" data-idea-id="${idea.id}" tabindex="0" role="button">
      <h3>${escapeHtml(idea.title)}</h3>
      <p class="preview">${escapeHtml(preview)}</p>
      <div class="idea-card-footer">
        <span>${formatDate(idea.updated_at)}</span>
        <span>${noteCount} ${noteCount === 1 ? 'note' : 'notes'}</span>
      </div>
    </article>`;
}

function bindIdeaCards(root = document) {
  root.querySelectorAll('[data-idea-id]').forEach(card => {
    const open = () => openIdea(card.dataset.ideaId);
    card.addEventListener('click', open);
    card.addEventListener('keydown', e => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(); }
    });
  });
}

async function loadDashboard() {
  try {
    const data = await api('/api/dashboard');
    $('#dashboard-stats').innerHTML = `
      <span class="stat-pill"><strong>${data.active_idea_count}</strong> active ideas</span>
      <span class="stat-pill"><strong>${data.note_count}</strong> timeline notes</span>`;
    const root = $('#recent-ideas');
    root.innerHTML = data.recent_ideas.map(ideaCard).join('');
    $('#recent-empty').classList.toggle('hidden', data.recent_ideas.length > 0);
    root.classList.toggle('hidden', data.recent_ideas.length === 0);
    bindIdeaCards(root);
  } catch (error) {
    showToast(error.message);
  }
}

async function loadIdeas() {
  const search = encodeURIComponent($('#idea-search').value.trim());
  const status = encodeURIComponent($('#status-filter').value);
  try {
    const ideas = await api(`/api/ideas?search=${search}&status=${status}`);
    const root = $('#ideas-container');
    root.innerHTML = ideas.map(ideaCard).join('');
    root.classList.toggle('list-view', state.ideasView === 'list');
    root.classList.toggle('hidden', ideas.length === 0);
    $('#ideas-empty').classList.toggle('hidden', ideas.length > 0);
    bindIdeaCards(root);
  } catch (error) {
    showToast(error.message);
  }
}

async function captureIdea(text, source = 'text') {
  const cleaned = text.trim();
  if (!cleaned) return;
  const button = $('#capture-form button[type="submit"]');
  button.disabled = true;
  try {
    const idea = await api('/api/ideas', {
      method: 'POST',
      body: JSON.stringify({initial_note: cleaned, source}),
    });
    $('#capture-input').value = '';
    showToast('Idea captured');
    await Promise.all([loadDashboard(), loadIdeas()]);
    return idea;
  } catch (error) {
    showToast(error.message);
  } finally {
    button.disabled = false;
  }
}

async function openIdea(id) {
  try {
    const idea = await api(`/api/ideas/${id}`);
    state.currentIdeaId = id;
    $('#idea-title').value = idea.title;
    $('#idea-meta').textContent = `Created ${formatDate(idea.created_at, true)} · ${idea.status}`;
    $('#archive-button').textContent = idea.status === 'archived' ? 'Restore' : 'Archive';
    $('#idea-timeline').innerHTML = idea.notes.map(note => `
      <article class="timeline-item">
        <span class="timeline-dot" aria-hidden="true"></span>
        <div class="timeline-body">
          <div class="note-time">${formatDate(note.created_at, true)} · ${escapeHtml(note.source)}</div>
          <div class="note-text">${escapeHtml(note.content)}</div>
        </div>
      </article>`).join('');
    if (!$('#idea-dialog').open) $('#idea-dialog').showModal();
    setTimeout(() => $('#idea-title').focus({preventScroll:true}), 0);
  } catch (error) {
    showToast(error.message);
  }
}

async function updateCurrentIdea(patch) {
  if (!state.currentIdeaId) return;
  try {
    const idea = await api(`/api/ideas/${state.currentIdeaId}`, {
      method:'PATCH', body:JSON.stringify(patch),
    });
    await Promise.all([loadDashboard(), loadIdeas()]);
    return idea;
  } catch (error) {
    showToast(error.message);
  }
}

function navigate(page) {
  state.currentPage = page;
  $$('.page').forEach(el => el.classList.toggle('active', el.id === `page-${page}`));
  $$('.nav-item').forEach(el => el.classList.toggle('active', el.dataset.page === page));
  if (page === 'ideas') loadIdeas();
  window.scrollTo({top:0, behavior:'instant'});
}

function setView(view) {
  state.ideasView = view;
  localStorage.setItem('osiris-ideas-view', view);
  $('#grid-view').classList.toggle('active', view === 'grid');
  $('#list-view').classList.toggle('active', view === 'list');
  $('#ideas-container').classList.toggle('list-view', view === 'list');
}

function setupEvents() {
  $$('.nav-item').forEach(button => button.addEventListener('click', () => navigate(button.dataset.page)));
  $$('[data-nav]').forEach(button => button.addEventListener('click', () => navigate(button.dataset.nav)));

  $('#capture-form').addEventListener('submit', async e => {
    e.preventDefault();
    await captureIdea($('#capture-input').value);
  });

  $('#new-idea-button').addEventListener('click', () => {
    navigate('osiris');
    $('#capture-input').focus();
  });

  let searchTimer;
  $('#idea-search').addEventListener('input', () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(loadIdeas, 180);
  });
  $('#status-filter').addEventListener('change', loadIdeas);
  $('#grid-view').addEventListener('click', () => setView('grid'));
  $('#list-view').addEventListener('click', () => setView('list'));

  $('#dialog-close').addEventListener('click', () => $('#idea-dialog').close());
  $('#idea-dialog').addEventListener('click', e => {
    if (e.target === $('#idea-dialog')) $('#idea-dialog').close();
  });
  $('#idea-title').addEventListener('change', async e => {
    const title = e.target.value.trim();
    if (title) await updateCurrentIdea({title});
  });
  $('#archive-button').addEventListener('click', async () => {
    if (!state.currentIdeaId) return;
    const current = await api(`/api/ideas/${state.currentIdeaId}`);
    const nextStatus = current.status === 'archived' ? 'active' : 'archived';
    await updateCurrentIdea({status:nextStatus});
    $('#idea-dialog').close();
    showToast(nextStatus === 'archived' ? 'Idea archived' : 'Idea restored');
  });
  $('#note-form').addEventListener('submit', async e => {
    e.preventDefault();
    const input = $('#note-input');
    const content = input.value.trim();
    if (!content || !state.currentIdeaId) return;
    try {
      await api(`/api/ideas/${state.currentIdeaId}/notes`, {
        method:'POST', body:JSON.stringify({content, source:'text'}),
      });
      input.value = '';
      await openIdea(state.currentIdeaId);
      await Promise.all([loadDashboard(), loadIdeas()]);
    } catch (error) {
      showToast(error.message);
    }
  });
}

async function boot() {
  $('#dashboard-date').textContent = new Intl.DateTimeFormat(undefined, {
    weekday:'long', month:'long', day:'numeric'
  }).format(new Date());
  setView(state.ideasView);
  setupEvents();
  await Promise.all([loadDashboard(), loadIdeas()]);

  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/service-worker.js').catch(() => {});
  }
}

boot();
