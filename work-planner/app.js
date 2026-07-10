/* ================= 데이터 저장 ================= */
const STORAGE_KEY = 'workPlanner.v1';

let state = {
  tasks: [],          // {id,title,important,urgent,dueDate,createdAt,done,completedAt,completionNote,routineId?}
  plans: {},          // { 'YYYY-MM-DD': { '9': '보고서 작성', ... } }
  routines: []        // {id,title,repeat,days,dayOfMonth,time,important,urgent,enabled,lastDate,lastNotified}
};

function load() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      state.tasks = Array.isArray(parsed.tasks) ? parsed.tasks : [];
      state.plans = parsed.plans && typeof parsed.plans === 'object' ? parsed.plans : {};
      state.routines = Array.isArray(parsed.routines) ? parsed.routines : [];
    }
  } catch (e) {
    console.error('데이터 로드 실패', e);
  }
}

function save() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}

/* ================= 날짜 유틸 ================= */
const DAY_NAMES = ['일', '월', '화', '수', '목', '금', '토'];

function fmtDate(d) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}
function todayStr() { return fmtDate(new Date()); }
function parseDate(s) {
  const [y, m, d] = s.split('-').map(Number);
  return new Date(y, m - 1, d);
}
function addDays(d, n) {
  const r = new Date(d);
  r.setDate(r.getDate() + n);
  return r;
}
function weekStart(d) {           // 월요일 시작
  const r = new Date(d);
  const dow = (r.getDay() + 6) % 7;
  return addDays(r, -dow);
}
function fmtKorean(s) {
  const d = parseDate(s);
  return `${d.getMonth() + 1}/${d.getDate()}(${DAY_NAMES[d.getDay()]})`;
}
function fmtDateTime(iso) {
  const d = new Date(iso);
  const hh = String(d.getHours()).padStart(2, '0');
  const mm = String(d.getMinutes()).padStart(2, '0');
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${hh}:${mm}`;
}

/* ================= 분류(아이젠하워) ================= */
const QUADS = {
  q1: { label: '🔴 중요하고 급한 일 (먼저 하기)', badge: '중요·급함' },
  q2: { label: '🟠 중요하지만 천천히 해도 되는 일 (계획 세우기)', badge: '중요·여유' },
  q3: { label: '🟡 덜 중요하지만 급한 일 (빨리 처리)', badge: '덜중요·급함' },
  q4: { label: '🟢 덜 중요하고 천천히 해도 되는 일 (여유 있을 때)', badge: '덜중요·여유' }
};
function quadOf(t) {
  if (t.important && t.urgent) return 'q1';
  if (t.important && !t.urgent) return 'q2';
  if (!t.important && t.urgent) return 'q3';
  return 'q4';
}
const QUAD_COLORS = { q1: '#e5484d', q2: '#f0883e', q3: '#d5b60a', q4: '#30a46c' };

/* ================= 공통 헬퍼 ================= */
function esc(s) {
  return String(s).replace(/[&<>"']/g, c =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}
function uid() {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
}
function activeTasks() { return state.tasks.filter(t => !t.done); }
function doneTasks() { return state.tasks.filter(t => t.done); }
function tasksOn(dateStr) {
  return state.tasks.filter(t => t.dueDate === dateStr);
}

/* ================= 화면 전환 ================= */
let currentView = 'list';
document.querySelectorAll('.nav-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    currentView = btn.dataset.view;
    document.querySelectorAll('.nav-btn').forEach(b => b.classList.toggle('active', b === btn));
    document.querySelectorAll('.view').forEach(v => v.classList.add('hidden'));
    document.getElementById('view-' + currentView).classList.remove('hidden');
    render();
  });
});

function render() {
  renderSidebarInfo();
  if (currentView === 'list') renderList();
  else if (currentView === 'yearly') renderYearly();
  else if (currentView === 'monthly') renderMonthly();
  else if (currentView === 'weekly') renderWeekly();
  else if (currentView === 'daily') renderDaily();
  else if (currentView === 'today') renderToday();
  else if (currentView === 'routine') renderRoutines();
  else if (currentView === 'history') renderHistory();
}

function renderSidebarInfo() {
  const d = new Date();
  const remain = activeTasks().length;
  const doneToday = doneTasks().filter(t => t.completedAt && t.completedAt.slice(0, 10) === todayStr()).length;
  document.getElementById('todayInfo').innerHTML =
    `${d.getFullYear()}년 ${d.getMonth() + 1}월 ${d.getDate()}일 (${DAY_NAMES[d.getDay()]})<br>` +
    `남은 할 일 <b>${remain}</b>건 · 오늘 완료 <b>${doneToday}</b>건`;
}

/* ================= 1·2. 할 일 목록 + 분류 ================= */
let listFilter = 'all';

document.getElementById('addForm').addEventListener('submit', e => {
  e.preventDefault();
  const title = document.getElementById('inputTitle').value.trim();
  if (!title) return;
  state.tasks.push({
    id: uid(),
    title,
    important: document.getElementById('inputImportant').value === '1',
    urgent: document.getElementById('inputUrgent').value === '1',
    dueDate: document.getElementById('inputDue').value || todayStr(),
    createdAt: new Date().toISOString(),
    done: false,
    completedAt: null,
    completionNote: '',
    memo: '',
    subtasks: []
  });
  save();
  document.getElementById('inputTitle').value = '';
  document.getElementById('inputTitle').focus();
  render();
});

document.getElementById('filterBar').addEventListener('click', e => {
  const chip = e.target.closest('.chip');
  if (!chip) return;
  listFilter = chip.dataset.filter;
  document.querySelectorAll('#filterBar .chip').forEach(c => c.classList.toggle('active', c === chip));
  renderList();
});

function taskCardHTML(t, opts = {}) {
  const q = quadOf(t);
  const today = todayStr();
  const overdue = !t.done && t.dueDate < today;
  const dueLabel = t.dueDate === today ? '오늘' : fmtKorean(t.dueDate);
  const subs = t.subtasks || [];
  const subDone = subs.filter(s => s.done).length;
  return `
    <div class="task-card ${q}" data-id="${t.id}">
      <div class="task-main">
        <div class="task-title">${esc(t.title)}</div>
        <div class="task-meta">
          <span class="badge ${q}">${QUADS[q].badge}</span>
          <span class="${overdue ? 'overdue' : ''}">📅 ${dueLabel}${overdue ? ' (지남!)' : ''}</span>
          ${t.routineId ? '<span title="루틴 업무에서 자동 등록됨">🔁 루틴</span>' : ''}
          ${t.yearly ? '<span title="연간 업무계획에 등록됨">📌 연간</span>' : ''}
          ${subs.length ? `<span class="task-progress">📋 세부 ${subDone}/${subs.length}</span>` : ''}
        </div>
      </div>
      <div class="task-actions">
        ${opts.readonly ? '' : `
          <button class="btn primary" data-act="done" title="완료 처리">✓ 완료</button>
          <button class="btn" data-act="detail" title="세부 계획">📋</button>
          <button class="btn" data-act="edit" title="수정">✎</button>
          <button class="btn danger" data-act="del" title="삭제">🗑</button>`}
      </div>
    </div>`;
}

function renderList() {
  const wrap = document.getElementById('taskList');
  const tasks = activeTasks()
    .filter(t => listFilter === 'all' || quadOf(t) === listFilter)
    .sort((a, b) => a.dueDate.localeCompare(b.dueDate));

  if (tasks.length === 0) {
    wrap.innerHTML = `<div class="empty">등록된 할 일이 없습니다.<br>위에서 새 할 일을 추가해 보세요!</div>`;
    return;
  }

  let html = '';
  for (const q of ['q1', 'q2', 'q3', 'q4']) {
    const group = tasks.filter(t => quadOf(t) === q);
    if (group.length === 0) continue;
    html += `<div class="quad-group"><h3>${QUADS[q].label} — ${group.length}건</h3>`;
    html += group.map(t => taskCardHTML(t)).join('');
    html += `</div>`;
  }
  wrap.innerHTML = html;
}

/* 목록/일간 카드 버튼 공용 처리 */
function handleCardAction(e) {
  const btn = e.target.closest('button[data-act]');
  if (!btn) return;
  const card = btn.closest('.task-card');
  const task = state.tasks.find(t => t.id === card.dataset.id);
  if (!task) return;

  if (btn.dataset.act === 'done') {
    openCompleteModal(task);
  } else if (btn.dataset.act === 'detail') {
    openDetailModal(task);
  } else if (btn.dataset.act === 'edit') {
    editTask(task);
  } else if (btn.dataset.act === 'del') {
    if (confirm(`"${task.title}" 을(를) 삭제할까요?`)) {
      state.tasks = state.tasks.filter(t => t.id !== task.id);
      save();
      render();
    }
  }
}
document.getElementById('taskList').addEventListener('click', handleCardAction);
document.getElementById('dailyList').addEventListener('click', handleCardAction);

function editTask(task) {
  const title = prompt('할 일 제목 수정', task.title);
  if (title === null) return;
  if (title.trim()) task.title = title.trim();

  const imp = confirm('중요한 일인가요?\n(확인 = 중요한 일 / 취소 = 덜 중요한 일)');
  const urg = confirm('급한 일인가요?\n(확인 = 급한 일 / 취소 = 천천히 해도 되는 일)');
  task.important = imp;
  task.urgent = urg;

  const due = prompt('마감일 수정 (YYYY-MM-DD)', task.dueDate);
  if (due && /^\d{4}-\d{2}-\d{2}$/.test(due.trim())) task.dueDate = due.trim();

  save();
  render();
}

/* ================= 완료 처리 모달 ================= */
let completingTask = null;
const completeModal = document.getElementById('completeModal');

function openCompleteModal(task) {
  completingTask = task;
  document.getElementById('completeTaskTitle').textContent = task.title;
  document.getElementById('completeNote').value = '';
  completeModal.classList.remove('hidden');
  document.getElementById('completeNote').focus();
}
document.getElementById('completeCancel').addEventListener('click', () => {
  completingTask = null;
  completeModal.classList.add('hidden');
});
document.getElementById('completeSave').addEventListener('click', () => {
  if (!completingTask) return;
  completingTask.done = true;
  completingTask.completedAt = new Date().toISOString();
  completingTask.completionNote = document.getElementById('completeNote').value.trim();
  completingTask = null;
  completeModal.classList.add('hidden');
  save();
  render();
});
completeModal.addEventListener('click', e => {
  if (e.target === completeModal) {
    completingTask = null;
    completeModal.classList.add('hidden');
  }
});

/* ================= 세부 계획 모달 ================= */
let detailTask = null;
const detailModal = document.getElementById('detailModal');

function openDetailModal(task) {
  detailTask = task;
  if (!Array.isArray(task.subtasks)) task.subtasks = [];
  document.getElementById('detailTaskTitle').textContent = task.title;
  document.getElementById('detailMemo').value = task.memo || '';
  renderSubtasks();
  detailModal.classList.remove('hidden');
  document.getElementById('subtaskInput').focus();
}
function closeDetailModal() {
  detailTask = null;
  detailModal.classList.add('hidden');
  save();
  render();   // 카드의 세부 진행률(📋 n/n) 갱신
}
function renderSubtasks() {
  const wrap = document.getElementById('subtaskList');
  if (!detailTask.subtasks.length) {
    wrap.innerHTML = '<div class="hint">아직 세부 항목이 없습니다. 아래에서 추가하세요.</div>';
    return;
  }
  wrap.innerHTML = detailTask.subtasks.map(s => `
    <div class="subtask-item ${s.done ? 'done' : ''}">
      <input type="checkbox" data-sid="${s.id}" ${s.done ? 'checked' : ''}>
      <span class="subtask-text">${esc(s.text)}</span>
      <input type="date" class="subtask-due" data-sid="${s.id}" value="${s.due || ''}" title="기한">
      <button type="button" class="subtask-del" data-sid="${s.id}" title="항목 삭제">✕</button>
    </div>`).join('');
}
document.getElementById('subtaskList').addEventListener('change', e => {
  if (!detailTask) return;
  const cb = e.target.closest('input[type="checkbox"]');
  if (cb) {
    const s = detailTask.subtasks.find(x => x.id === cb.dataset.sid);
    if (s) { s.done = cb.checked; save(); renderSubtasks(); }
    return;
  }
  const due = e.target.closest('.subtask-due');
  if (due) {
    const s = detailTask.subtasks.find(x => x.id === due.dataset.sid);
    if (s) { s.due = due.value || null; save(); }
  }
});
document.getElementById('subtaskList').addEventListener('click', e => {
  const del = e.target.closest('.subtask-del');
  if (!del || !detailTask) return;
  detailTask.subtasks = detailTask.subtasks.filter(x => x.id !== del.dataset.sid);
  save();
  renderSubtasks();
});
document.getElementById('subtaskForm').addEventListener('submit', e => {
  e.preventDefault();
  if (!detailTask) return;
  const text = document.getElementById('subtaskInput').value.trim();
  if (!text) return;
  detailTask.subtasks.push({ id: uid(), text, done: false, due: document.getElementById('subtaskDue').value || null });
  document.getElementById('subtaskInput').value = '';
  save();
  renderSubtasks();
});
document.getElementById('detailMemo').addEventListener('input', e => {
  if (detailTask) { detailTask.memo = e.target.value; save(); }
});
document.getElementById('detailClose').addEventListener('click', closeDetailModal);
detailModal.addEventListener('click', e => { if (e.target === detailModal) closeDetailModal(); });

/* ================= 연간 업무계획 ================= */
let yearCursor = new Date().getFullYear();

document.getElementById('yearPrev').addEventListener('click', () => { yearCursor--; renderYearly(); });
document.getElementById('yearNext').addEventListener('click', () => { yearCursor++; renderYearly(); });
document.getElementById('yearNow').addEventListener('click', () => { yearCursor = new Date().getFullYear(); renderYearly(); });

document.getElementById('yearlyForm').addEventListener('submit', e => {
  e.preventDefault();
  const title = document.getElementById('yTitle').value.trim();
  const due = document.getElementById('yDue').value;
  if (!title || !due) return;
  state.tasks.push({
    id: uid(),
    title,
    important: document.getElementById('yImportant').value === '1',
    urgent: document.getElementById('yUrgent').value === '1',
    dueDate: due,
    createdAt: new Date().toISOString(),
    done: false,
    completedAt: null,
    completionNote: '',
    memo: '',
    subtasks: [],
    yearly: true
  });
  save();
  document.getElementById('yTitle').value = '';
  yearCursor = Number(due.slice(0, 4));   // 등록한 연도로 이동해서 바로 확인
  renderYearly();
  renderSidebarInfo();
});
document.getElementById('yearlyList').addEventListener('click', handleCardAction);

function renderYearly() {
  document.getElementById('yearlyTitle').textContent = `${yearCursor}년 업무계획`;
  const wrap = document.getElementById('yearlyList');
  const prefix = String(yearCursor) + '-';
  const yearTasks = state.tasks.filter(t => !t.routineId && t.dueDate.startsWith(prefix));
  if (yearTasks.length === 0) {
    wrap.innerHTML = `<div class="empty">${yearCursor}년에 등록된 업무가 없습니다.<br>위에서 마감기한과 함께 업무를 등록해 보세요.</div>`;
    return;
  }
  let html = '';
  for (let m = 1; m <= 12; m++) {
    const mm = String(m).padStart(2, '0');
    const monthTasks = yearTasks
      .filter(t => t.dueDate.slice(5, 7) === mm)
      .sort((a, b) => a.dueDate.localeCompare(b.dueDate));
    if (monthTasks.length === 0) continue;
    const doneCnt = monthTasks.filter(t => t.done).length;
    html += `<div class="quad-group"><h3>${m}월 — ${monthTasks.length}건 (완료 ${doneCnt}건)</h3>`;
    html += monthTasks.map(t => t.done
      ? `<div class="task-card ${quadOf(t)}" style="opacity:.6" data-id="${t.id}">
          <div class="task-main">
            <div class="task-title" style="text-decoration:line-through">${esc(t.title)}</div>
            <div class="task-meta"><span>완료: ${t.completedAt ? fmtDateTime(t.completedAt) : '-'}</span></div>
          </div>
        </div>`
      : taskCardHTML(t)).join('');
    html += `</div>`;
  }
  wrap.innerHTML = html;
}

/* ================= 3. 월간 ================= */
let monthCursor = new Date();

document.getElementById('monthPrev').addEventListener('click', () => { monthCursor.setMonth(monthCursor.getMonth() - 1); renderMonthly(); });
document.getElementById('monthNext').addEventListener('click', () => { monthCursor.setMonth(monthCursor.getMonth() + 1); renderMonthly(); });
document.getElementById('monthToday').addEventListener('click', () => { monthCursor = new Date(); renderMonthly(); });

function renderMonthly() {
  const y = monthCursor.getFullYear();
  const m = monthCursor.getMonth();
  document.getElementById('monthlyTitle').textContent = `${y}년 ${m + 1}월 업무`;

  const first = new Date(y, m, 1);
  const gridStart = addDays(first, -first.getDay()); // 일요일 시작
  const today = todayStr();

  let html = DAY_NAMES.map(n => `<div class="cal-head">${n}</div>`).join('');
  for (let i = 0; i < 42; i++) {
    const d = addDays(gridStart, i);
    const ds = fmtDate(d);
    const other = d.getMonth() !== m ? 'other' : '';
    const isToday = ds === today ? 'today' : '';
    const dow = d.getDay() === 0 ? 'sun' : d.getDay() === 6 ? 'sat' : '';
    const dayTasks = tasksOn(ds).sort((a, b) => quadOf(a).localeCompare(quadOf(b)));
    const dayRoutines = routinesOn(ds, d);
    const items = [
      ...dayTasks.map(t => ({ kind: 'task', v: t })),
      ...dayRoutines.map(r => ({ kind: 'routine', v: r }))
    ];
    const shown = items.slice(0, 3);
    const moreCnt = items.length - shown.length;
    html += `<div class="cal-cell ${other} ${isToday} ${dow}">
      <div class="cal-date">${d.getDate()}</div>
      ${shown.map(it => it.kind === 'task'
        ? `<div class="cal-task ${it.v.done ? 'done' : ''}" style="background:${QUAD_COLORS[quadOf(it.v)]}" title="${esc(it.v.title)}">${esc(it.v.title)}</div>`
        : `<div class="cal-task routine" style="border-color:${QUAD_COLORS[quadOf(it.v)]}" title="${esc(repeatDesc(it.v))}">🔁 ${esc(it.v.title)}</div>`).join('')}
      ${moreCnt > 0 ? `<div class="cal-more">+${moreCnt}건 더</div>` : ''}
    </div>`;
  }
  document.getElementById('monthlyCalendar').innerHTML = html;
}

/* ================= 3. 주간 ================= */
let weekCursor = new Date();

document.getElementById('weekPrev').addEventListener('click', () => { weekCursor = addDays(weekCursor, -7); renderWeekly(); });
document.getElementById('weekNext').addEventListener('click', () => { weekCursor = addDays(weekCursor, 7); renderWeekly(); });
document.getElementById('weekToday').addEventListener('click', () => { weekCursor = new Date(); renderWeekly(); });

function renderWeekly() {
  const start = weekStart(weekCursor);
  const end = addDays(start, 6);
  document.getElementById('weeklyTitle').textContent =
    `주간 업무 (${start.getMonth() + 1}/${start.getDate()} ~ ${end.getMonth() + 1}/${end.getDate()})`;

  const today = todayStr();
  let html = '';
  for (let i = 0; i < 7; i++) {
    const d = addDays(start, i);
    const ds = fmtDate(d);
    const dow = d.getDay() === 0 ? 'sun' : d.getDay() === 6 ? 'sat' : '';
    const dayTasks = tasksOn(ds).sort((a, b) => quadOf(a).localeCompare(quadOf(b)));
    const dayRoutines = routinesOn(ds, d);
    html += `<div class="week-col ${ds === today ? 'today' : ''} ${dow}">
      <div class="week-col-head">${d.getMonth() + 1}/${d.getDate()} (${DAY_NAMES[d.getDay()]})</div>
      ${dayTasks.length === 0 && dayRoutines.length === 0
        ? `<div class="hint" style="text-align:center;padding:12px 0">-</div>`
        : dayTasks.map(t => `
          <div class="cal-task ${t.done ? 'done' : ''}" style="background:${QUAD_COLORS[quadOf(t)]};margin-bottom:4px;white-space:normal" title="${esc(t.title)}">${esc(t.title)}</div>`).join('') +
          dayRoutines.map(r => `
          <div class="cal-task routine" style="border-color:${QUAD_COLORS[quadOf(r)]};margin-bottom:4px;white-space:normal" title="${esc(repeatDesc(r))}">🔁 ${esc(r.title)}</div>`).join('')}
    </div>`;
  }
  document.getElementById('weeklyGrid').innerHTML = html;
}

/* ================= 3. 일간 ================= */
let dayCursor = new Date();

document.getElementById('dayPrev').addEventListener('click', () => { dayCursor = addDays(dayCursor, -1); renderDaily(); });
document.getElementById('dayNext').addEventListener('click', () => { dayCursor = addDays(dayCursor, 1); renderDaily(); });
document.getElementById('dayToday').addEventListener('click', () => { dayCursor = new Date(); renderDaily(); });

function renderDaily() {
  const ds = fmtDate(dayCursor);
  document.getElementById('dailyTitle').textContent =
    `일간 업무 — ${dayCursor.getFullYear()}년 ${dayCursor.getMonth() + 1}월 ${dayCursor.getDate()}일 (${DAY_NAMES[dayCursor.getDay()]})`;

  const wrap = document.getElementById('dailyList');
  const dayTasks = tasksOn(ds).sort((a, b) => quadOf(a).localeCompare(quadOf(b)));
  const dayRoutines = routinesOn(ds, dayCursor);
  if (dayTasks.length === 0 && dayRoutines.length === 0) {
    wrap.innerHTML = `<div class="empty">이 날짜에 등록된 업무가 없습니다.</div>`;
    return;
  }
  const active = dayTasks.filter(t => !t.done);
  const finished = dayTasks.filter(t => t.done);
  let html = active.map(t => taskCardHTML(t)).join('');
  if (finished.length > 0) {
    html += `<div class="quad-group" style="margin-top:16px"><h3>✅ 완료됨 — ${finished.length}건</h3>`;
    html += finished.map(t => `
      <div class="task-card ${quadOf(t)}" style="opacity:.6">
        <div class="task-main">
          <div class="task-title" style="text-decoration:line-through">${esc(t.title)}</div>
          <div class="task-meta"><span>완료: ${t.completedAt ? fmtDateTime(t.completedAt) : ''}</span></div>
        </div>
      </div>`).join('');
    html += `</div>`;
  }
  if (dayRoutines.length > 0) {
    html += `<div class="quad-group" style="margin-top:16px"><h3>🔁 이 날의 루틴 업무 — ${dayRoutines.length}건</h3>`;
    html += dayRoutines.map(r => `
      <div class="task-card ${quadOf(r)}">
        <div class="task-main">
          <div class="task-title">🔁 ${esc(r.title)}</div>
          <div class="task-meta">
            <span class="badge ${quadOf(r)}">${QUADS[quadOf(r)].badge}</span>
            <span>⏰ ${esc(repeatDesc(r))}</span>
          </div>
        </div>
      </div>`).join('');
    html += `</div>`;
  }
  wrap.innerHTML = html;
}

/* ================= 4. 오늘 시간대별 계획 ================= */
const HOUR_START = 6, HOUR_END = 23;
let selectedHour = null;

function renderToday() {
  const ds = todayStr();
  const d = new Date();
  document.getElementById('todayPlanTitle').textContent =
    `오늘 시간대별 계획 — ${d.getMonth() + 1}월 ${d.getDate()}일 (${DAY_NAMES[d.getDay()]})`;

  const plan = state.plans[ds] || {};
  const nowHour = d.getHours();

  let html = '';
  for (let h = HOUR_START; h <= HOUR_END; h++) {
    const isNow = h === nowHour ? 'now' : '';
    html += `<div class="time-row ${isNow}">
      <div class="time-label">${String(h).padStart(2, '0')}:00</div>
      <input class="time-input ${selectedHour === h ? 'selected' : ''}" data-hour="${h}"
             value="${esc(plan[h] || '')}" placeholder="">
    </div>`;
  }
  document.getElementById('timeTable').innerHTML = html;

  document.querySelectorAll('.time-input').forEach(inp => {
    inp.addEventListener('input', () => {
      const h = inp.dataset.hour;
      if (!state.plans[ds]) state.plans[ds] = {};
      if (inp.value.trim()) state.plans[ds][h] = inp.value;
      else delete state.plans[ds][h];
      save();
    });
    inp.addEventListener('focus', () => {
      selectedHour = Number(inp.dataset.hour);
      document.querySelectorAll('.time-input').forEach(i => i.classList.toggle('selected', i === inp));
    });
  });

  // 오늘 마감 할 일 풀 + 기한 있는 세부 항목 + 다가오는 마감(7일 이내)
  const pool = activeTasks().filter(t => t.dueDate <= ds).sort((a, b) => quadOf(a).localeCompare(quadOf(b)));
  const weekAhead = fmtDate(addDays(new Date(), 7));
  const upcoming = activeTasks().filter(t => t.dueDate > ds && t.dueDate <= weekAhead)
    .sort((a, b) => a.dueDate.localeCompare(b.dueDate));
  const subDue = [];
  for (const t of activeTasks()) {
    for (const s of (t.subtasks || [])) {
      if (!s.done && s.due) subDue.push({ t, s });
    }
  }
  const subToday = subDue.filter(x => x.s.due <= ds);
  const subUpcoming = subDue.filter(x => x.s.due > ds && x.s.due <= weekAhead)
    .sort((a, b) => a.s.due.localeCompare(b.s.due));
  const poolWrap = document.getElementById('todayTaskPool');
  if (pool.length === 0 && upcoming.length === 0 && subToday.length === 0 && subUpcoming.length === 0) {
    poolWrap.innerHTML = `<div class="hint">오늘까지 할 일이 없습니다 🎉</div>`;
  } else {
    const subItemHTML = x =>
      `<div class="pool-item ${quadOf(x.t)}" data-id="${x.t.id}" data-sid="${x.s.id}">📋 ${esc(x.s.text)} <span class="pool-due">${esc(x.t.title)}${x.s.due > ds ? ' · ' + fmtKorean(x.s.due) : ''}</span></div>`;
    const upcomingItems = [
      ...upcoming.map(t => ({ kind: 'task', date: t.dueDate, t })),
      ...subUpcoming.map(x => ({ kind: 'sub', date: x.s.due, t: x.t, s: x.s }))
    ].sort((a, b) => a.date.localeCompare(b.date));
    poolWrap.innerHTML =
      pool.map(t =>
        `<div class="pool-item ${quadOf(t)}" data-id="${t.id}">${esc(t.title)}</div>`).join('') +
      subToday.map(subItemHTML).join('') +
      (upcomingItems.length ? `<div class="pool-sub">다가오는 마감 (7일 이내)</div>` +
        upcomingItems.map(it => it.kind === 'task'
          ? `<div class="pool-item ${quadOf(it.t)}" data-id="${it.t.id}">${esc(it.t.title)} <span class="pool-due">${fmtKorean(it.t.dueDate)}</span></div>`
          : subItemHTML(it)).join('') : '');
    poolWrap.querySelectorAll('.pool-item').forEach(item => {
      item.addEventListener('click', () => {
        const task = state.tasks.find(t => t.id === item.dataset.id);
        if (!task) return;
        let label = task.title;
        if (item.dataset.sid) {
          const s = (task.subtasks || []).find(x => x.id === item.dataset.sid);
          if (s) label = `${s.text} (${task.title})`;
        }
        if (selectedHour === null) {
          alert('먼저 왼쪽에서 넣을 시간대 칸을 클릭해 주세요.');
          return;
        }
        if (!state.plans[ds]) state.plans[ds] = {};
        const cur = state.plans[ds][selectedHour] || '';
        state.plans[ds][selectedHour] = cur ? cur + ', ' + label : label;
        save();
        renderToday();
      });
    });
  }
}

/* ================= 루틴 업무 (반복 + 자동 알림) ================= */

function occursToday(r, d) {
  d = d || new Date();
  if (r.repeat === 'daily') return true;
  if (r.repeat === 'weekly') return Array.isArray(r.days) && r.days.includes(d.getDay());
  if (r.repeat === 'monthly') {
    const lastDay = new Date(d.getFullYear(), d.getMonth() + 1, 0).getDate();
    return d.getDate() === Math.min(r.dayOfMonth, lastDay); // 31일 설정 + 30일까지인 달 → 말일에 실행
  }
  return false;
}

/* 해당 날짜에 예정된 루틴 (이미 할 일로 생성된 날은 제외 → 중복 표시 방지) */
function routinesOn(ds, d) {
  return state.routines.filter(r =>
    r.enabled && occursToday(r, d) &&
    !state.tasks.some(t => t.routineId === r.id && t.dueDate === ds));
}

function repeatDesc(r) {
  let base = '';
  if (r.repeat === 'daily') base = '매일';
  else if (r.repeat === 'weekly') base = '매주 ' + (r.days || []).slice().sort().map(i => DAY_NAMES[i]).join('·');
  else base = `매월 ${r.dayOfMonth}일`;
  return `${base} ${r.time}`;
}

/* 주기가 된 루틴을 오늘의 할 일로 자동 등록 */
function generateRoutineTasks() {
  const today = todayStr();
  let changed = false;
  for (const r of state.routines) {
    if (!r.enabled || !occursToday(r) || r.lastDate === today) continue;
    if (!state.tasks.some(t => t.routineId === r.id && t.dueDate === today)) {
      state.tasks.push({
        id: uid(),
        title: r.title,
        important: r.important,
        urgent: r.urgent,
        dueDate: today,
        createdAt: new Date().toISOString(),
        done: false,
        completedAt: null,
        completionNote: '',
        memo: '',
        subtasks: [],
        routineId: r.id
      });
    }
    r.lastDate = today;
    changed = true;
  }
  if (changed) save();
  return changed;
}

/* 지정 시간이 지나면 하루 한 번 알림 */
function checkAlarms() {
  const now = new Date();
  const today = todayStr();
  const hhmm = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
  let changed = false;
  for (const r of state.routines) {
    if (!r.enabled || !occursToday(r, now)) continue;
    if (r.lastNotified === today || !r.time || r.time > hhmm) continue;
    fireAlarm('🔁 루틴 업무 알림', `${r.title} — ${r.time}`);
    r.lastNotified = today;
    changed = true;
  }
  if (changed) save();
}

function fireAlarm(title, body) {
  showToast(title, body);
  beep();
  try {
    if ('Notification' in window) {
      if (Notification.permission === 'granted') {
        new Notification(title, { body });
      } else if (Notification.permission !== 'denied') {
        Notification.requestPermission().then(p => {
          if (p === 'granted') new Notification(title, { body });
        });
      }
    }
  } catch (e) { /* 알림 미지원 환경은 토스트만 표시 */ }
}

function showToast(title, body) {
  const box = document.getElementById('toastBox');
  const el = document.createElement('div');
  el.className = 'toast';
  el.innerHTML = `<b>${esc(title)}</b><span>${esc(body)}</span>`;
  el.addEventListener('click', () => el.remove());
  box.appendChild(el);
  setTimeout(() => el.remove(), 10000);
}

function beep() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.frequency.value = 880;
    gain.gain.setValueAtTime(0.08, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.4);
    osc.start();
    osc.stop(ctx.currentTime + 0.4);
  } catch (e) { /* 소리 재생 불가 시 무시 */ }
}

/* --- 루틴 등록 폼 --- */
const rDaysWrap = document.getElementById('rDays');
rDaysWrap.innerHTML = DAY_NAMES.map((n, i) =>
  `<button type="button" class="dow-btn" data-day="${i}">${n}</button>`).join('');
rDaysWrap.addEventListener('click', e => {
  const b = e.target.closest('.dow-btn');
  if (b) b.classList.toggle('on');
});

document.getElementById('rRepeat').addEventListener('change', e => {
  rDaysWrap.classList.toggle('hidden', e.target.value !== 'weekly');
  document.getElementById('rDomWrap').classList.toggle('hidden', e.target.value !== 'monthly');
});

document.getElementById('routineForm').addEventListener('submit', e => {
  e.preventDefault();
  const errEl = document.getElementById('routineError');
  errEl.textContent = '';
  const title = document.getElementById('rTitle').value.trim();
  if (!title) return;
  const repeat = document.getElementById('rRepeat').value;
  const days = [...rDaysWrap.querySelectorAll('.dow-btn.on')].map(b => Number(b.dataset.day));
  if (repeat === 'weekly' && days.length === 0) {
    errEl.textContent = '매주 반복은 요일을 하나 이상 선택해 주세요.';
    return;
  }
  const dayOfMonth = Math.min(31, Math.max(1, Number(document.getElementById('rDom').value) || 1));

  state.routines.push({
    id: uid(),
    title,
    repeat,
    days,
    dayOfMonth,
    time: document.getElementById('rTime').value || '09:00',
    important: document.getElementById('rImportant').value === '1',
    urgent: document.getElementById('rUrgent').value === '1',
    enabled: true,
    lastDate: null,
    lastNotified: null
  });
  save();

  try {
    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission();
    }
  } catch (e2) { /* 무시 */ }

  document.getElementById('rTitle').value = '';
  generateRoutineTasks();   // 오늘이 주기면 즉시 할 일에 등록
  checkAlarms();            // 시간이 이미 지났으면 즉시 알림
  render();
});

document.getElementById('routineList').addEventListener('click', e => {
  const btn = e.target.closest('button[data-act]');
  if (!btn) return;
  const card = btn.closest('.task-card');
  const routine = state.routines.find(r => r.id === card.dataset.id);
  if (!routine) return;

  if (btn.dataset.act === 'toggle') {
    routine.enabled = !routine.enabled;
    save();
    renderRoutines();
  } else if (btn.dataset.act === 'del') {
    if (confirm(`루틴 "${routine.title}" 을(를) 삭제할까요?\n(이미 등록된 할 일은 남습니다)`)) {
      state.routines = state.routines.filter(r => r.id !== routine.id);
      save();
      renderRoutines();
    }
  }
});

function renderRoutines() {
  const wrap = document.getElementById('routineList');
  if (state.routines.length === 0) {
    wrap.innerHTML = `<div class="empty">등록된 루틴 업무가 없습니다.<br>매일 반복하는 업무를 등록하면 자동으로 할 일에 추가되고 알림을 받습니다.</div>`;
    return;
  }
  wrap.innerHTML = state.routines.map(r => {
    const q = quadOf(r);
    return `
      <div class="task-card ${q} ${r.enabled ? '' : 'routine-off'}" data-id="${r.id}">
        <div class="task-main">
          <div class="task-title">🔁 ${esc(r.title)}</div>
          <div class="task-meta">
            <span class="badge ${q}">${QUADS[q].badge}</span>
            <span>⏰ ${esc(repeatDesc(r))}</span>
            <span>${r.enabled ? '🔔 알림 켜짐' : '🔕 알림 꺼짐'}</span>
          </div>
        </div>
        <div class="task-actions">
          <button class="btn" data-act="toggle">${r.enabled ? '🔕 끄기' : '🔔 켜기'}</button>
          <button class="btn danger" data-act="del" title="삭제">🗑</button>
        </div>
      </div>`;
  }).join('');
}

/* ================= 5. 완료 이력 ================= */
document.getElementById('historySearch').addEventListener('input', renderHistory);
document.getElementById('historyList').addEventListener('click', e => {
  const btn = e.target.closest('button[data-act]');
  if (!btn) return;
  const card = btn.closest('.history-card');
  const task = state.tasks.find(t => t.id === card.dataset.id);
  if (!task) return;

  if (btn.dataset.act === 'restore') {
    task.done = false;
    task.completedAt = null;
    task.completionNote = '';
    save();
    render();
  } else if (btn.dataset.act === 'del') {
    if (confirm(`이력에서 "${task.title}" 을(를) 완전히 삭제할까요?`)) {
      state.tasks = state.tasks.filter(t => t.id !== task.id);
      save();
      render();
    }
  }
});

function renderHistory() {
  const kw = document.getElementById('historySearch').value.trim().toLowerCase();
  const wrap = document.getElementById('historyList');
  let items = doneTasks()
    .filter(t => !kw ||
      t.title.toLowerCase().includes(kw) ||
      (t.completionNote || '').toLowerCase().includes(kw))
    .sort((a, b) => (b.completedAt || '').localeCompare(a.completedAt || ''));

  if (items.length === 0) {
    wrap.innerHTML = `<div class="empty">${kw ? '검색 결과가 없습니다.' : '아직 완료된 업무가 없습니다.'}</div>`;
    return;
  }

  let html = '';
  let curMonth = '';
  for (const t of items) {
    const month = t.completedAt ? t.completedAt.slice(0, 7) : '날짜 없음';
    if (month !== curMonth) {
      curMonth = month;
      const [y, m] = month.split('-');
      html += `<div class="history-month">${y}년 ${Number(m)}월</div>`;
    }
    const q = quadOf(t);
    html += `
      <div class="history-card" data-id="${t.id}">
        <div class="history-main">
          <div class="history-title">✅ ${esc(t.title)} <span class="badge ${q}">${QUADS[q].badge}</span></div>
          ${t.completionNote ? `<div class="history-note">💬 ${esc(t.completionNote)}</div>` : ''}
          <div class="history-meta">완료: ${t.completedAt ? fmtDateTime(t.completedAt) : '-'} · 마감일: ${t.dueDate}</div>
        </div>
        <div class="task-actions">
          <button class="btn" data-act="restore" title="다시 할 일로 되돌리기">↩ 되돌리기</button>
          <button class="btn danger" data-act="del" title="이력 삭제">🗑</button>
        </div>
      </div>`;
  }
  wrap.innerHTML = html;
}

/* ================= 시작 ================= */
load();
document.getElementById('inputDue').value = todayStr();
generateRoutineTasks();
checkAlarms();
setInterval(() => {          // 30초마다: 자정 넘김·알림 시간 확인
  if (generateRoutineTasks()) render();
  checkAlarms();
  renderSidebarInfo();
}, 30000);
render();
