// 모바일 앱 메인 로직 — 화면 전환 & 렌더링

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

const UI = {
  screen: "home",
  trendMetric: "weight",
};

function fmt(n, digits = 1) {
  return n == null || isNaN(n) ? "-" : Number(n).toFixed(digits);
}
function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function dogEmoji(breed) {
  if (!breed) return "🐶";
  if (breed.size === "대형") return "🐕";
  if (breed.size === "중형") return "🐕‍🦺";
  return "🐩";
}
function toast(msg) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.add("show");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => t.classList.remove("show"), 1800);
}

// ---------- 견종 select 옵션 ----------
function populateBreedOptions(select, selectedId) {
  select.innerHTML = "";
  const groups = { 소형: [], 중형: [], 대형: [] };
  BREEDS.forEach((b) => groups[b.size]?.push(b));
  Object.entries(groups).forEach(([size, list]) => {
    const og = document.createElement("optgroup");
    og.label = size + "견";
    list.forEach((b) => {
      const opt = document.createElement("option");
      opt.value = b.id;
      opt.textContent = b.name;
      if (b.id === selectedId) opt.selected = true;
      og.appendChild(opt);
    });
    select.appendChild(og);
  });
}

// ================= 화면 라우팅 =================
function navigate(screen) {
  UI.screen = screen;
  $$(".tabbar-item").forEach((t) => t.classList.toggle("active", t.dataset.screen === screen));
  renderScreen();
}

function renderScreen() {
  const dog = Store.getActiveDog();
  const screen = $("#screen");
  const fab = $("#fab");
  const title = $("#appbarTitle");

  // 강아지가 없으면 무조건 온보딩
  if (!dog && UI.screen !== "more") {
    title.textContent = "멍멍 건강수첩";
    fab.hidden = true;
    screen.innerHTML = onboardingHTML();
    $("#onboardAdd")?.addEventListener("click", () => openDogSheet());
    return;
  }

  if (UI.screen === "home") {
    title.textContent = "멍멍 건강수첩";
    fab.hidden = false;
    renderHome(dog);
  } else if (UI.screen === "trends") {
    title.textContent = "트렌드";
    fab.hidden = false;
    renderTrends(dog);
  } else if (UI.screen === "records") {
    title.textContent = "기록";
    fab.hidden = false;
    renderRecords(dog);
  } else if (UI.screen === "more") {
    title.textContent = "더보기";
    fab.hidden = true;
    renderMore();
  }
  screen.scrollTop = 0;
}

function onboardingHTML() {
  return `
    <div class="empty-state">
      <div class="empty-emoji">🐾</div>
      <h2>반려견을 등록해 주세요</h2>
      <p>체중·체고·몸통 둘레를 기록하면<br>견종별 비만도와 건강 추이를 볼 수 있어요.</p>
      <button class="btn btn-primary" id="onboardAdd">＋ 강아지 추가하기</button>
    </div>`;
}

// ---------- 강아지 셀렉터 스트립 ----------
function dogStripHTML() {
  const dogs = Store.getDogs();
  const active = Store.getActiveDog();
  const chips = dogs.map((d) => {
    const breed = getBreed(d.breedId);
    return `<button class="dog-chip ${active && d.id === active.id ? "active" : ""}" data-dog="${d.id}">
      <span class="chip-emoji">${dogEmoji(breed)}</span>${escapeHtml(d.name)}</button>`;
  }).join("");
  return `<div class="dog-strip">${chips}
    <button class="dog-chip add" data-add-dog>＋ 추가</button></div>`;
}
function bindDogStrip(root) {
  $$("[data-dog]", root).forEach((b) => b.addEventListener("click", () => {
    Store.setActiveDog(b.dataset.dog);
    renderScreen();
  }));
  $("[data-add-dog]", root)?.addEventListener("click", () => openDogSheet());
}

// ================= 홈 화면 =================
function renderHome(dog) {
  const breed = getBreed(dog.breedId);
  const records = Store.getRecords(dog.id);
  const last = records[records.length - 1];
  const prev = records[records.length - 2];
  const pct = last && breed ? obesityPercent(last, breed) : null;
  const grade = obesityGrade(pct);
  const bcs = estimateBCS(pct);
  const wDelta = last && prev ? delta(last.weight, prev.weight) : null;

  const screen = $("#screen");
  screen.innerHTML = `
    ${dogStripHTML()}
    <div class="profile-hero">
      <div class="profile-avatar">${dogEmoji(breed)}</div>
      <div class="profile-info">
        <h2>${escapeHtml(dog.name)}</h2>
        <p>${breed ? breed.name + " · " + breed.size + "견" : "견종 미지정"}${dog.sex ? " · " + (dog.sex === "M" ? "♂" : "♀") : ""}${dog.birth ? " · " + (ageFromBirth(dog.birth) || "") : ""}</p>
      </div>
    </div>

    <div class="stat-grid">
      ${statCard("비만도", pct != null ? fmt(pct, 0) + "%" : "-", grade.label, grade.color)}
      ${statCard("체중", last ? fmt(last.weight) + " kg" : "-",
        wDelta != null ? (wDelta >= 0 ? "▲ " : "▼ ") + fmt(Math.abs(wDelta), 2) + "kg" : "기록을 추가하세요",
        wDelta != null ? (wDelta > 0 ? "#f59e0b" : wDelta < 0 ? "#38bdf8" : "#94a3b8") : "#94a3b8")}
      ${statCard("체고", last && last.height ? fmt(last.height) + " cm" : "-", breed ? `표준 ${breed.height[0]}~${breed.height[1]}` : "", "#8b5cf6")}
      ${statCard("몸통 둘레", last && last.chest ? fmt(last.chest) + " cm" : "-", breed ? `표준 ${breed.chest[0]}~${breed.chest[1]}` : "", "#0ea5b7")}
    </div>

    ${breed ? obesityPanel(pct, grade, bcs, breed, last) : ""}
    ${breed ? bodyShapePanel(last, breed, grade) : ""}
    ${breed ? tipsPanel(breed) : ""}
  `;
  bindDogStrip(screen);
}

function statCard(label, value, sub, color) {
  return `<div class="stat-card">
    <div class="stat-label">${label}</div>
    <div class="stat-value">${value}</div>
    <div class="stat-sub" style="color:${color || "#94a3b8"}">${sub || ""}</div>
  </div>`;
}

function obesityPanel(pct, grade, bcs, breed, record) {
  const frame = record ? frameLabel(record, breed) : null;
  const iw = record ? idealWeight(record, breed) : breedIdealWeight(breed);
  const advice = weightAdvice(pct, breed, iw);
  const gaugePos = pct == null ? 50 : Math.max(0, Math.min(100, ((pct - 70) / 80) * 100));
  // 체격 배지: 체고가 있으면 프레임 분류, 없으면 입력 유도
  const frameChip = frame
    ? `<span class="badge" style="background:#8b5cf61a;color:#8b5cf6">🦴 ${frame}</span>`
    : `<span class="badge" style="background:${grade.color === "#94a3b8" ? "#94a3b820" : "#94a3b820"};color:#94a3b8">체고 입력 시 체격 반영</span>`;
  return `<section class="card">
    <div class="card-head"><h3>⚖️ 비만도 평가</h3>
      <span class="badge-lg" style="background:${grade.color}1a;color:${grade.color}">${grade.label}${pct != null ? " · " + fmt(pct, 0) + "%" : ""}</span>
    </div>
    <div class="gauge">
      <div class="gauge-track">
        <span class="gauge-seg"></span><span class="gauge-seg"></span><span class="gauge-seg"></span><span class="gauge-seg"></span>
        ${pct != null ? `<span class="gauge-marker" style="left:${gaugePos}%"></span>` : ""}
      </div>
      <div class="gauge-scale"><span>저체중</span><span>정상</span><span>과체중</span><span>비만</span></div>
    </div>
    <div style="margin:-4px 0 12px">${frameChip}</div>
    <div class="obesity-meta">
      <div><span class="muted small">체격 기준 이상 체중</span><b>${fmt(iw)} kg</b></div>
      <div><span class="muted small">견종 표준 범위</span><b>${breed.weight[0]}~${breed.weight[1]} kg</b></div>
      <div><span class="muted small">추정 BCS</span><b>${bcs != null ? bcs + " / 9" : "-"}</b></div>
    </div>
    <p class="advice">${advice}</p>
  </section>`;
}

function bodyShapePanel(record, breed, weightGrade) {
  if (!record) return "";
  const bsi = bodyShapeIndex(record, breed);
  if (bsi == null) {
    // 몸통 둘레 또는 체고가 없어 체형 분석 불가 — 안내만 표시
    const missing = record.chest == null ? "몸통 둘레" : "체고";
    return `<section class="card">
      <div class="card-head"><h3>📐 체형 분석 <span class="muted small">몸통 둘레 기준</span></h3></div>
      <p class="muted small">${missing}를 함께 기록하면, 골격 대비 몸통 두께로 지방 축적을 교차 검증해 드려요.</p>
    </section>`;
  }
  const grade = bodyShapeGrade(bsi);
  const ec = expectedChest(record, breed);
  const combined = combinedAssessment(weightGrade, grade);
  const pos = Math.max(0, Math.min(100, ((bsi - 80) / 50) * 100)); // 80~130% 구간 매핑
  return `<section class="card">
    <div class="card-head"><h3>📐 체형 분석 <span class="muted small">몸통 둘레 기준</span></h3>
      <span class="badge-lg" style="background:${grade.color}1a;color:${grade.color}">${grade.label} · ${fmt(bsi, 0)}%</span>
    </div>
    <div class="shape-bar">
      <div class="shape-bar-track"><span class="shape-marker" style="left:${pos}%"></span></div>
      <div class="shape-scale"><span>마름</span><span>이상</span><span>통통</span><span>비만</span></div>
    </div>
    <div class="obesity-meta">
      <div><span class="muted small">프레임 기대 둘레</span><b>${fmt(ec)} cm</b></div>
      <div><span class="muted small">실제 둘레</span><b>${fmt(record.chest)} cm</b></div>
      <div><span class="muted small">체형 지수</span><b>${fmt(bsi, 0)}%</b></div>
    </div>
    ${combined ? `<p class="advice">${combined}</p>` : ""}
  </section>`;
}

function tipsPanel(breed) {
  return `<section class="card">
    <div class="card-head"><h3>💡 ${escapeHtml(breed.name)} 관리 포인트</h3></div>
    <ul class="tips-list">${breed.tips.map((t) => `<li>${escapeHtml(t)}</li>`).join("")}</ul>
  </section>`;
}

// ================= 트렌드 화면 =================
function renderTrends(dog) {
  const breed = getBreed(dog.breedId);
  const records = Store.getRecords(dog.id);
  const screen = $("#screen");
  screen.innerHTML = `
    ${dogStripHTML()}
    <div class="tabs" id="trendTabs">
      <button class="tab ${UI.trendMetric === "weight" ? "active" : ""}" data-metric="weight">체중</button>
      <button class="tab ${UI.trendMetric === "obesity" ? "active" : ""}" data-metric="obesity">비만도</button>
      <button class="tab ${UI.trendMetric === "height" ? "active" : ""}" data-metric="height">체고</button>
      <button class="tab ${UI.trendMetric === "chest" ? "active" : ""}" data-metric="chest">몸통</button>
      <button class="tab ${UI.trendMetric === "shape" ? "active" : ""}" data-metric="shape">체형</button>
    </div>
    <section class="card">
      <div id="chartArea" class="chart-area-wrap"></div>
      <p class="chart-note muted small" id="chartNote"></p>
    </section>
  `;
  bindDogStrip(screen);
  const draw = () => drawTrend(UI.trendMetric, breed, records);
  $$("#trendTabs .tab").forEach((tab) => tab.addEventListener("click", () => {
    UI.trendMetric = tab.dataset.metric;
    $$("#trendTabs .tab").forEach((t) => t.classList.toggle("active", t === tab));
    draw();
  }));
  draw();
}

function drawTrend(metric, breed, records) {
  const area = $("#chartArea");
  const note = $("#chartNote");
  let points, opts;
  if (metric === "weight") {
    // 체격 보정 이상 체중 기준선 — 가장 최근에 체고가 기록된 값 기준
    const framed = [...records].reverse().find((r) => r.height != null);
    const idealRef = breed ? idealWeight(framed || {}, breed) : null;
    points = records.map((r) => ({ x: r.date, y: r.weight }));
    opts = { unit: "kg", color: "#6366f1", band: breed ? breed.weight : null, ideal: idealRef };
    note.textContent = breed
      ? `연두색 밴드 = 견종 표준 체중(${breed.weight[0]}~${breed.weight[1]}kg), 점선 = 체격 보정 이상 체중${framed ? "" : " (체고 미입력 → 표준 중앙값)"}.`
      : "";
  } else if (metric === "obesity") {
    points = records.map((r) => ({ x: r.date, y: breed ? obesityPercent(r, breed) : null }));
    opts = { unit: "%", color: "#ef4444", ideal: 100, band: [85, 115] };
    note.textContent = "체격 보정 비만도. 100% = 체격에 맞는 이상 체중, 밴드(85~115%) 안이면 정상이에요.";
  } else if (metric === "height") {
    points = records.map((r) => ({ x: r.date, y: r.height }));
    opts = { unit: "cm", color: "#8b5cf6", band: breed ? breed.height : null };
    note.textContent = breed ? `밴드 = 표준 체고(${breed.height[0]}~${breed.height[1]}cm).` : "";
  } else if (metric === "chest") {
    points = records.map((r) => ({ x: r.date, y: r.chest }));
    opts = { unit: "cm", color: "#0ea5b7", band: breed ? breed.chest : null };
    note.textContent = breed ? `밴드 = 표준 몸통 둘레(${breed.chest[0]}~${breed.chest[1]}cm).` : "";
  } else {
    // 체형 지수 (몸통 둘레 ÷ 프레임 기대 둘레)
    points = records.map((r) => ({ x: r.date, y: breed ? bodyShapeIndex(r, breed) : null }));
    opts = { unit: "%", color: "#f59e0b", ideal: 100, band: [93, 108] };
    note.textContent = "몸통 둘레 ÷ 프레임 기대 둘레. 100% = 이상 체형, 밴드(93~108%) 안이면 이상적이에요. (체고·몸통 둘레 필요)";
  }
  renderLineChart(area, points, opts);
}

// ================= 기록 화면 =================
function renderRecords(dog) {
  const breed = getBreed(dog.breedId);
  const records = Store.getRecords(dog.id);
  const screen = $("#screen");
  let listHTML;
  if (records.length === 0) {
    listHTML = `<div class="empty-state"><div class="empty-emoji">📋</div>
      <h2>기록이 없어요</h2><p>아래 ＋ 버튼으로 첫 수치를 기록해 보세요.</p></div>`;
  } else {
    const items = [...records].reverse().map((r, idx, arr) => {
      const prevRec = arr[idx + 1];
      const wD = prevRec ? delta(r.weight, prevRec.weight) : null;
      const pct = breed ? obesityPercent(r, breed) : null;
      const grade = obesityGrade(pct);
      const metrics = [
        r.height ? `체고 ${fmt(r.height)}` : null,
        r.chest ? `몸통 ${fmt(r.chest)}` : null,
        r.neck ? `목 ${fmt(r.neck)}` : null,
      ].filter(Boolean).join(" · ");
      return `<button class="record-card" data-rec="${r.id}">
        <div class="record-main">
          <div class="record-date">${r.date}</div>
          <div class="record-weight">${fmt(r.weight)}kg${wD != null ? `<span class="mini ${wD > 0 ? "up" : wD < 0 ? "down" : ""}">${wD > 0 ? "▲" : wD < 0 ? "▼" : ""}${fmt(Math.abs(wD), 2)}</span>` : ""}</div>
          ${metrics ? `<div class="record-metrics">${metrics} cm</div>` : ""}
          ${r.note ? `<div class="record-note">📝 ${escapeHtml(r.note)}</div>` : ""}
        </div>
        ${pct != null ? `<span class="badge" style="background:${grade.color}20;color:${grade.color}">${fmt(pct, 0)}%</span>` : ""}
      </button>`;
    }).join("");
    listHTML = `<div class="record-list">${items}</div>`;
  }
  screen.innerHTML = `${dogStripHTML()}
    <div class="section-title">${escapeHtml(dog.name)}의 기록 (${records.length}건)</div>
    ${listHTML}`;
  bindDogStrip(screen);
  $$("[data-rec]", screen).forEach((b) => b.addEventListener("click", () => {
    const rec = Store.db.records.find((x) => x.id === b.dataset.rec);
    openRecordSheet(rec);
  }));
}

// ================= 더보기 화면 =================
function renderMore() {
  const dogs = Store.getDogs();
  const screen = $("#screen");
  const dogItems = dogs.length
    ? dogs.map((d) => {
        const breed = getBreed(d.breedId);
        return `<button class="manage-item" data-manage="${d.id}">
          <span class="m-emoji">${dogEmoji(breed)}</span>
          <span class="m-info"><span class="m-name">${escapeHtml(d.name)}</span><br>
          <span class="m-breed">${breed ? breed.name : "미지정"}${d.birth ? " · " + (ageFromBirth(d.birth) || "") : ""}</span></span>
          <span class="m-arrow">✏️</span>
        </button>`;
      }).join("")
    : '<p class="muted small" style="padding:4px 2px">등록된 강아지가 없어요.</p>';

  screen.innerHTML = `
    <div class="section-title">우리 아이들</div>
    <div class="dog-manage-list">${dogItems}
      <button class="btn btn-ghost" id="addDogMore" style="margin-top:4px">＋ 강아지 추가</button>
    </div>

    <div class="section-title" style="margin-top:22px">데이터</div>
    <button class="settings-row" id="exportBtn"><span><span class="s-icon">⬇️</span>데이터 백업 (JSON)</span><span class="s-arrow">›</span></button>
    <button class="settings-row" id="importBtn"><span><span class="s-icon">⬆️</span>데이터 복원</span><span class="s-arrow">›</span></button>
    <input type="file" id="importFile" accept="application/json" hidden>

    <div class="section-title" style="margin-top:22px">앱 정보</div>
    <div class="card" style="font-size:0.85rem">
      <b>멍멍 건강수첩</b> <span class="muted">v1.0</span>
      <p class="muted" style="margin-top:8px">견종 표준값에 더해 <b>체고(체격)</b>로 이상 체중을 보정하고, <b>몸통 둘레 ÷ 체고</b> 체형 지수로 지방 축적을 교차 검증하는 앱입니다. 같은 견종이라도 골격 차이를 반영해 더 공정하게 판단합니다. 표준값은 참고용이며, 정확한 진단은 수의사와 상담하세요.</p>
      <p class="muted small" style="margin-top:8px">모든 데이터는 이 기기에만 저장됩니다.</p>
    </div>
  `;
  $$("[data-manage]", screen).forEach((b) => b.addEventListener("click", () => {
    openDogSheet(Store.getDog(b.dataset.manage));
  }));
  $("#addDogMore").addEventListener("click", () => openDogSheet());
  setupDataButtons();
}

// ================= 바텀시트: 강아지 추가/수정 =================
function openSheet(html) {
  const box = $("#sheetBox");
  box.innerHTML = `<div class="sheet-handle"></div>${html}`;
  $("#sheet").classList.add("open");
  document.body.style.overflow = "hidden";
}
function closeSheet() {
  $("#sheet").classList.remove("open");
  document.body.style.overflow = "";
}

function openDogSheet(dog = null) {
  const editing = !!dog;
  openSheet(`
    <div class="sheet-head"><h3>${editing ? "프로필 수정" : "강아지 추가"}</h3>
      <button class="sheet-close" data-close>✕</button></div>
    <form id="dogForm" class="form">
      <label>이름<input name="name" required maxlength="20" value="${editing ? escapeHtml(dog.name) : ""}" placeholder="예: 초코"></label>
      <label>견종<select name="breedId" id="breedSelect"></select></label>
      <div class="form-row">
        <label>성별<select name="sex">
          <option value="">선택 안함</option>
          <option value="M" ${editing && dog.sex === "M" ? "selected" : ""}>수컷</option>
          <option value="F" ${editing && dog.sex === "F" ? "selected" : ""}>암컷</option>
        </select></label>
        <label>생년월일<input type="date" name="birth" value="${editing && dog.birth ? dog.birth : ""}"></label>
      </div>
      <label class="check-inline"><input type="checkbox" name="neutered" ${editing && dog.neutered ? "checked" : ""}>중성화 완료</label>
      <button type="submit" class="btn btn-primary">${editing ? "저장" : "추가하기"}</button>
      ${editing ? '<button type="button" class="btn btn-danger" id="deleteDogBtn">이 강아지 삭제</button>' : ""}
    </form>`);
  populateBreedOptions($("#breedSelect"), editing ? dog.breedId : BREEDS[0].id);
  bindSheetClose();

  if (editing) {
    $("#deleteDogBtn").addEventListener("click", () => {
      if (confirm(`${dog.name}의 프로필과 모든 기록을 삭제할까요?`)) {
        Store.deleteDog(dog.id);
        closeSheet();
        toast("삭제했어요");
        renderScreen();
      }
    });
  }
  $("#dogForm").addEventListener("submit", (e) => {
    e.preventDefault();
    const f = e.target;
    const data = {
      name: f.name.value.trim(),
      breedId: f.breedId.value,
      sex: f.sex.value,
      neutered: f.neutered.checked,
      birth: f.birth.value,
    };
    if (!data.name) return;
    if (editing) { Store.updateDog(dog.id, data); toast("저장했어요"); }
    else { Store.addDog(data); toast("등록했어요 🐶"); if (UI.screen === "more") navigate("home"); }
    closeSheet();
    renderScreen();
  });
}

// ================= 바텀시트: 수치 기록 =================
function openRecordSheet(rec = null) {
  const dog = Store.getActiveDog();
  if (!dog) { toast("먼저 강아지를 등록하세요"); return; }
  const editing = !!rec;
  const today = todayStr();
  openSheet(`
    <div class="sheet-head"><h3>${editing ? "기록 수정" : "수치 기록"}</h3>
      <button class="sheet-close" data-close>✕</button></div>
    <form id="recForm" class="form">
      <label>측정 날짜<input type="date" name="date" required value="${editing ? rec.date : today}"></label>
      <div class="form-row">
        <label>체중 (kg) *<input type="number" inputmode="decimal" name="weight" step="0.01" min="0" required value="${editing ? rec.weight : ""}" placeholder="4.2"></label>
        <label>체고 (cm)<input type="number" inputmode="decimal" name="height" step="0.1" min="0" value="${editing && rec.height ? rec.height : ""}" placeholder="어깨높이"></label>
      </div>
      <div class="form-row">
        <label>몸통 둘레 (cm)<input type="number" inputmode="decimal" name="chest" step="0.1" min="0" value="${editing && rec.chest ? rec.chest : ""}" placeholder="가슴둘레"></label>
        <label>목 둘레 (cm)<input type="number" inputmode="decimal" name="neck" step="0.1" min="0" value="${editing && rec.neck ? rec.neck : ""}" placeholder="선택"></label>
      </div>
      <label>메모<input name="note" maxlength="60" value="${editing && rec.note ? escapeHtml(rec.note) : ""}" placeholder="예: 병원 검진, 사료 변경"></label>
      <button type="submit" class="btn btn-primary">${editing ? "저장" : "기록하기"}</button>
      ${editing ? '<button type="button" class="btn btn-danger" id="deleteRecBtn">이 기록 삭제</button>' : ""}
    </form>`);
  bindSheetClose();

  if (editing) {
    $("#deleteRecBtn").addEventListener("click", () => {
      if (confirm("이 기록을 삭제할까요?")) {
        Store.deleteRecord(rec.id);
        closeSheet();
        toast("삭제했어요");
        renderScreen();
      }
    });
  }
  $("#recForm").addEventListener("submit", (e) => {
    e.preventDefault();
    const f = e.target;
    const num = (v) => (v === "" ? null : parseFloat(v));
    const data = {
      dogId: dog.id, date: f.date.value,
      weight: num(f.weight.value), height: num(f.height.value),
      chest: num(f.chest.value), neck: num(f.neck.value), note: f.note.value.trim(),
    };
    if (data.weight == null) return;
    if (editing) { Store.updateRecord(rec.id, data); toast("저장했어요"); }
    else { Store.addRecord(data); toast("기록 완료 ✅"); }
    closeSheet();
    renderScreen();
  });
}

function bindSheetClose() {
  $("[data-close]")?.addEventListener("click", closeSheet);
}

function todayStr() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

// ================= 데이터 백업/복원 =================
function setupDataButtons() {
  $("#exportBtn").addEventListener("click", () => {
    const blob = new Blob([Store.exportJSON()], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "dog-health-backup.json";
    a.click();
    URL.revokeObjectURL(a.href);
    toast("백업 파일을 내보냈어요");
  });
  $("#importBtn").addEventListener("click", () => $("#importFile").click());
  $("#importFile").addEventListener("change", (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      try {
        Store.importJSON(reader.result);
        toast("복원했어요");
        navigate("home");
      } catch (err) {
        alert("불러오기 실패: " + err.message);
      }
    };
    reader.readAsText(file);
    e.target.value = "";
  });
}

// ================= 초기화 =================
document.addEventListener("DOMContentLoaded", () => {
  $$(".tabbar-item").forEach((t) => t.addEventListener("click", () => navigate(t.dataset.screen)));
  $("#fab").addEventListener("click", () => openRecordSheet());
  $("#sheet").addEventListener("click", (e) => { if (e.target.id === "sheet") closeSheet(); });

  navigate("home");

  // 리사이즈 시 트렌드 차트 다시 그리기
  let rt;
  window.addEventListener("resize", () => {
    clearTimeout(rt);
    rt = setTimeout(() => { if (UI.screen === "trends" && Store.getActiveDog()) renderScreen(); }, 200);
  });

  // 서비스워커 등록 (오프라인 지원)
  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("sw.js").catch(() => {});
    });
  }
});
