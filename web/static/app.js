// Wordle solver page: a 6x5 tile grid, an on-screen keyboard and the results table.
// No build step; talks to the API next to this page (api/words, api/solve).
'use strict';

const STORAGE_KEY = 'wordle-solver:v1';
const COLORS = ['black', 'yellow', 'green'];
const PATTERN = 'byg';
const PAGE_SIZE = 50;
const KEY_ROWS = ['qwertyuiop', 'asdfghjkl', '+zxcvbnm-'];  // + Enter, - Backspace

const $ = (id) => document.getElementById(id);
const grid = $('grid');
const statusEl = $('status');
const submitBtn = $('submit');
const resetBtn = $('reset');
const keyboard = $('keyboard');
const results = $('results');

// rows: submitted guesses; active: the row being typed (its colors cycle too)
let state = { rows: [], active: emptyActive() };
let wordSet = null;       // from api/words; until it loads, the server checks words
let lastSolved = null;    // key of the rows behind the results shown
let busy = false;
let requestId = 0;
let data = null;          // last api/solve response
let sort = { key: 'probability', dir: 'desc' };
let showAll = false;
let focusAfterRender = null;

function emptyActive() {
  return { letters: '', colors: [0, 0, 0, 0, 0] };
}

// --- storage (every access guarded: private mode, quota, disabled storage) ---

function load() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return;
    const saved = JSON.parse(raw);
    const okColors = (c) => Array.isArray(c) && c.length === 5 && c.every((x) => x === 0 || x === 1 || x === 2);
    const rows = Array.isArray(saved.rows) ? saved.rows : [];
    const valid = rows.every((r) => r && /^[a-z]{5}$/.test(r.word) && okColors(r.colors));
    const a = saved.active;
    const activeOk = a && /^[a-z]{0,5}$/.test(a.letters) && okColors(a.colors);
    if (valid && rows.length <= 6) {
      state.rows = rows.map((r) => ({ word: r.word, colors: r.colors.slice() }));
      if (activeOk && rows.length < 6) state.active = { letters: a.letters, colors: a.colors.slice() };
    }
  } catch (e) {
    // unreadable or blocked storage: start empty
  }
}

function save() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch (e) {
    // storage full or blocked: progress just isn't kept
  }
}

// --- helpers ---

function payload() {
  return state.rows.map((r) => ({ guess: r.word, pattern: r.colors.map((c) => PATTERN[c]).join('') }));
}

function rowsKey() {
  return JSON.stringify(payload());
}

function isDirty() {
  return rowsKey() !== lastSolved;
}

function setStatus(text) {
  statusEl.textContent = text;
}

function shake(rowIndex, text) {
  setStatus(text);
  const row = grid.children[rowIndex];
  if (!row) return;
  row.classList.remove('shake');
  void row.offsetWidth;  // restart the animation
  row.classList.add('shake');
}

function el(tag, attrs, text) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (k === 'class') node.className = v;
    else node.setAttribute(k, v);
  }
  if (text !== undefined) node.textContent = text;
  return node;
}

// --- rendering ---

function tile(letter, color, rowIndex, col) {
  if (!letter) return el('div', { class: 'tile' });
  const btn = el('button', {
    type: 'button',
    class: `tile c${color}`,
    'data-row': rowIndex,
    'data-col': col,
    'aria-label': `Letter ${letter.toUpperCase()}, position ${col + 1}, ${COLORS[color]}`,
  }, letter);
  btn.addEventListener('click', (e) => cycle(rowIndex, col, e.detail === 0));
  return btn;
}

function renderGrid() {
  grid.replaceChildren();
  for (let r = 0; r < 6; r++) {
    const row = el('div', { class: 'row' });
    let letters = '';
    let colors = [0, 0, 0, 0, 0];
    if (r < state.rows.length) {
      letters = state.rows[r].word;
      colors = state.rows[r].colors;
    } else if (r === state.rows.length) {
      row.classList.add('active');
      letters = state.active.letters;
      colors = state.active.colors;
    }
    for (let c = 0; c < 5; c++) row.append(tile(letters[c], colors[c], r, c));
    grid.append(row);
  }
  if (focusAfterRender) {
    const [r, c] = focusAfterRender;
    focusAfterRender = null;
    const target = grid.querySelector(`button[data-row="${r}"][data-col="${c}"]`);
    if (target) target.focus();
  }
}

function renderKeyboard() {
  // best color seen per letter in submitted rows: green > yellow > black
  const best = {};
  for (const r of state.rows) {
    for (let i = 0; i < 5; i++) {
      const ch = r.word[i];
      best[ch] = Math.max(best[ch] ?? -1, r.colors[i]);
    }
  }
  keyboard.replaceChildren();
  for (const keys of KEY_ROWS) {
    const row = el('div', { class: 'krow' });
    for (const k of keys) {
      let btn;
      if (k === '+') btn = el('button', { type: 'button', class: 'key wide', 'data-key': 'Enter' }, 'Enter');
      else if (k === '-') btn = el('button', { type: 'button', class: 'key wide', 'data-key': 'Backspace', 'aria-label': 'Backspace' }, '⌫');
      else {
        const seen = best[k] !== undefined ? ` c${best[k]}` : '';
        const label = best[k] !== undefined ? `${k.toUpperCase()}, ${COLORS[best[k]]}` : k.toUpperCase();
        btn = el('button', { type: 'button', class: `key${seen}`, 'data-key': k, 'aria-label': label }, k);
      }
      row.append(btn);
    }
    keyboard.append(row);
  }
}

function renderControls() {
  const dirty = isDirty();
  const update = state.active.letters.length === 0 && dirty && state.rows.length > 0;
  submitBtn.textContent = update ? 'Update' : 'Submit';
  submitBtn.disabled = busy || (state.active.letters.length === 0 && !dirty);
}

function render() {
  renderGrid();
  renderKeyboard();
  renderControls();
}

function formatPercent(p) {
  const pct = p * 100;
  return pct >= 0.01 ? `${pct.toFixed(2)}%` : '<0.01%';
}

function formatE(v) {
  return v === null || v === undefined ? '–' : v.toFixed(2);
}

const COLUMNS = [
  { key: 'word', label: 'Word', dir: 'asc' },
  { key: 'probability', label: 'Probability', dir: 'desc' },
  { key: 'ev', label: 'E(|v|)', dir: 'asc' },
  { key: 'wev', label: 'Weighted E(|v|)', dir: 'asc' },
];

function sortedWords() {
  const { key, dir } = sort;
  const sign = dir === 'asc' ? 1 : -1;
  return data.words.slice().sort((a, b) => {
    const x = a[key];
    const y = b[key];
    if (x === y) return b.probability - a.probability;
    if (x === null) return 1;  // unscored rows last either way
    if (y === null) return -1;
    if (key === 'word') return sign * x.localeCompare(y);
    return sign * (x - y);
  });
}

function renderResults() {
  results.replaceChildren();
  if (!data) return;
  const n = data.remaining;
  results.append(el('h2', {}, `${n.toLocaleString('en-US')} ${n === 1 ? 'word' : 'words'} left`));
  if (n === 0) {
    results.append(el('p', { class: 'note' }, 'No words match. Check your tile colors.'));
    return;
  }
  if (data.capped) {
    results.append(el('p', { class: 'note' },
      `Too many words left to score guesses (> ${data.cap.toLocaleString('en-US')}); make another guess`));
  }

  const table = el('table');
  const head = el('tr');
  for (const col of COLUMNS) {
    const th = el('th', { scope: 'col' });
    if (sort.key === col.key) th.setAttribute('aria-sort', sort.dir === 'asc' ? 'ascending' : 'descending');
    const btn = el('button', { type: 'button' }, col.label);
    btn.addEventListener('click', (e) => {
      sort = sort.key === col.key
        ? { key: col.key, dir: sort.dir === 'asc' ? 'desc' : 'asc' }
        : { key: col.key, dir: col.dir };
      renderResults();
      // keep keyboard focus on the header; after a mouse click let a physical Enter submit
      if (e.detail === 0) results.querySelector('th[aria-sort] button')?.focus();
    });
    th.append(btn);
    head.append(th);
  }
  table.append(el('thead'));
  table.tHead.append(head);

  const body = el('tbody');
  const words = sortedWords();
  const shown = showAll ? words : words.slice(0, PAGE_SIZE);
  for (const w of shown) {
    const tr = el('tr');
    tr.append(el('td', {}, w.word), el('td', {}, formatPercent(w.probability)), el('td', {}, formatE(w.ev)), el('td', {}, formatE(w.wev)));
    body.append(tr);
  }
  table.append(body);
  const box = el('div', { class: 'table-box' });
  box.append(table);
  results.append(box);

  if (!showAll && words.length > PAGE_SIZE) {
    const more = el('button', { type: 'button', class: 'btn', id: 'more' }, `Show all (${words.length.toLocaleString('en-US')})`);
    more.addEventListener('click', () => {
      showAll = true;
      renderResults();
    });
    results.append(more);
  }

  const legend = el('dl', { class: 'legend' });
  legend.append(
    el('dt', {}, 'Probability'),
    el('dd', {}, 'How likely the word is to be the answer, from how common it is in English.'),
    el('dt', {}, 'E(|v|)'),
    el('dd', {}, 'If you guess this word, how many words you can expect to be left on average. Lower is better.'),
    el('dt', {}, 'Weighted E(|v|)'),
    el('dd', {}, 'The same, but common words count for more than rare ones. Lower is better.'),
  );
  results.append(legend);
}

function renderError(message) {
  results.replaceChildren();
  const p = el('p', { class: 'note' }, `${message} `);
  const retry = el('button', { type: 'button', class: 'btn' }, 'Try again');
  retry.addEventListener('click', () => solve(false));
  p.append(retry);
  results.append(p);
}

// --- actions ---

function cycle(rowIndex, col, viaKeyboard) {
  const row = rowIndex < state.rows.length ? state.rows[rowIndex] : state.active;
  row.colors[col] = (row.colors[col] + 1) % 3;
  if (viaKeyboard) focusAfterRender = [rowIndex, col];
  setStatus('');
  save();
  render();
}

function typeLetter(ch) {
  if (state.rows.length >= 6 || state.active.letters.length >= 5) return;
  state.active.letters += ch;
  state.active.colors[state.active.letters.length - 1] = 0;
  setStatus('');
  save();
  render();
}

function backspace() {
  setStatus('');
  if (state.active.letters.length > 0) {
    state.active.letters = state.active.letters.slice(0, -1);
  } else if (state.rows.length > 0) {
    // reopen the last submitted row for editing
    const last = state.rows.pop();
    state.active = { letters: last.word, colors: last.colors.slice() };
  } else {
    return;
  }
  save();
  render();
}

function submit() {
  if (busy) return;
  const rowIndex = state.rows.length;
  const letters = state.active.letters;
  if (letters.length > 0) {
    if (letters.length < 5) return shake(rowIndex, 'Not enough letters');
    if (wordSet && !wordSet.has(letters)) return shake(rowIndex, 'Not in word list');
    state.rows.push({ word: letters, colors: state.active.colors.slice() });
    state.active = emptyActive();
    save();
    render();
    solve(true);
  } else if (isDirty()) {
    solve(false);
  }
}

async function solve(justSubmitted) {
  const id = ++requestId;
  const key = rowsKey();
  busy = true;
  setStatus('');
  renderControls();
  try {
    const res = await fetch('api/solve', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ rows: payload() }),
    });
    if (id !== requestId) return;
    if (res.status === 422) {
      const body = await res.json().catch(() => ({}));
      const detail = typeof body.detail === 'string' ? body.detail : 'Check your guesses.';
      // the word list hadn't loaded yet and the server rejected the row just submitted: give it back,
      // unless the rows changed while the request was in flight
      const lastRow = `Row ${state.rows.length}: `;
      if (justSubmitted && detail.startsWith(lastRow) && /not in the word list/.test(detail) && rowsKey() === key) {
        const last = state.rows.pop();
        state.active = { letters: last.word, colors: last.colors.slice() };
        save();
        render();
        shake(state.rows.length, 'Not in word list');
      } else {
        setStatus(detail);
      }
      return;
    }
    if (!res.ok) throw new Error(`the server answered ${res.status}`);
    data = await res.json();
    lastSolved = key;
    showAll = false;
    renderResults();
  } catch (e) {
    if (id !== requestId) return;
    renderError(`Couldn't load the results (${e.message || 'network error'}).`);
  } finally {
    if (id === requestId) {
      busy = false;
      renderControls();
    }
  }
}

function reset() {
  state = { rows: [], active: emptyActive() };
  lastSolved = null;
  data = null;
  sort = { key: 'probability', dir: 'desc' };
  setStatus('');
  save();
  render();
  solve(false);
}

async function loadWords() {
  try {
    const res = await fetch('api/words');
    if (res.ok) wordSet = new Set(await res.json());
  } catch (e) {
    // the server still checks each guess
  }
}

// --- events ---

// after a mouse click, drop focus so a later physical Enter submits instead of pressing the button again
submitBtn.addEventListener('click', (e) => {
  if (e.detail > 0) submitBtn.blur();
  submit();
});
resetBtn.addEventListener('click', (e) => {
  if (e.detail > 0) resetBtn.blur();
  reset();
});

keyboard.addEventListener('click', (e) => {
  const btn = e.target.closest('button[data-key]');
  if (!btn) return;
  if (e.detail > 0) btn.blur();
  const k = btn.dataset.key;
  if (k === 'Enter') submit();
  else if (k === 'Backspace') backspace();
  else typeLetter(k);
});

document.addEventListener('keydown', (e) => {
  if (e.ctrlKey || e.metaKey || e.altKey) return;
  const tag = e.target.tagName;
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
  if (e.key === 'Enter') {
    if (tag === 'BUTTON' || tag === 'A') return;  // let the focused control act
    e.preventDefault();
    submit();
  } else if (e.key === 'Backspace') {
    e.preventDefault();
    backspace();
  } else if (/^[a-zA-Z]$/.test(e.key)) {
    typeLetter(e.key.toLowerCase());
  }
});

grid.addEventListener('animationend', (e) => e.target.classList.remove('shake'));

load();
render();
loadWords();
solve(false);
