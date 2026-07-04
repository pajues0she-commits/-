// 앱 메인 로직 — 화면 렌더링 & 이벤트 처리

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

function fmt(n, digits = 1) {
  return n == null || isNaN(n) ? "-" : Number(n).toFixed(digits);
}

// ---------- 견종 select 채우기 ----------
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

// ---------- 강아지 목록(사이드바) ----------
function renderDogList() {
  const wrap = $("#dogList");
  wrap.innerHTML = "";
  const dogs = Store.getDogs();
  const active = Store.getActiveDog();
  if (dogs.length === 0) {
    wrap.innerHTML = '<p class="muted small">등록된 강아지가 없어요.</p>';
    return;
  }
  dogs.forEach((dog) => {
    const breed = getBreed(dog.breedId);
    const records = Store.getRecords(dog.id);
    const last = records[records.length - 1];
    const pct = last && breed ? obesityPercent(last.weight, breed) : null;
    const grade = obesityGrade(pct);

    const item = document.createElement("button");
    item.className = "dog-item" + (active && dog.id === active.id ? " active" : "");
    item.innerHTML = `
      <span class="dog-emoji">${dogEmoji(breed)}</span>
      <span class="dog-item-info">
        <span class="dog-item-name">${escapeHtml(dog.name)}</span>
        <span class="dog-item-breed">${breed ? breed.name : "미지정"}</span>
      </span>
      <span class="badge" style="background:${grade.color}20;color:${grade.color}">${grade.label}</span>
    `;
    item.addEventListener("click", () => {
      Store.setActiveDog(dog.id);
      render();
    });
    wrap.appendChild(item);
  });
}

function dogEmoji(breed) {
  if (!breed) return "🐶";
  if (breed.size === "대형") return "🐕";
  if (breed.size === "중형") return "🐕‍🦺";
  return "🐩";
}

// ---------- 메인 대시보드 ----------
function renderDashboard() {
  const main = $("#dashboard");
  const dog = Store.getActiveDog();

  if (!dog) {
    main.innerHTML = `
      <div class="empty-state">
        <div class="empty-emoji">🐾</div>
        <h2>반려견을 등록해 주세요</h2>
        <p class="muted">왼쪽의 <b>+ 강아지 추가</b> 버튼으로 시작하세요.<br>
        체중·체고·몸통 둘레를 기록하면 견종별 비만도와 건강 추이를 볼 수 있어요.</p>
        <button class="btn btn-primary" id="emptyAddBtn">+ 강아지 추가</button>
      </div>`;
    $("#emptyAddBtn")?.addEventListener("click", openDogModal);
    return;
  }

  const breed = getBreed(dog.breedId);
  const records = Store.getRecords(dog.id);
  const last = records[records.length - 1];
  const prev = records[records.length - 2];

  const pct = last && breed ? obesityPercent(last.weight, breed) : null;
  const grade = obesityGrade(pct);
  const bcs = estimateBCS(pct);
  const wDelta = last && prev ? delta(last.weight, prev.weight) : null;

  main.innerHTML = `
    <header class="dash-header">
      <div>
        <h1>${escapeHtml(dog.name)} <span class="dash-emoji">${dogEmoji(breed)}</span></h1>
        <p class="muted">${breed ? breed.name : "견종 미지정"} · ${breed ? breed.size + "견" : ""}
          ${dog.sex ? " · " + (dog.sex === "M" ? "수컷" : "암컷") : ""}
          ${dog.neutered ? " · 중성화" : ""}
          ${dog.birth ? " · " + (ageFromBirth(dog.birth) || "") : ""}</p>
      </div>
      <div class="dash-actions">
        <button class="btn" id="editDogBtn">프로필 수정</button>
        <button class="btn btn-primary" id="addRecordBtn">＋ 수치 기록</button>
      </div>
    </header>

    <section class="stat-grid">
      ${statCard("비만도", pct != null ? fmt(pct, 0) + "%" : "-", grade.label, grade.color)}
      ${statCard("체중", last ? fmt(last.weight) + " kg" : "-",
        wDelta != null ? (wDelta >= 0 ? "▲ " : "▼ ") + fmt(Math.abs(wDelta), 2) + "kg" : "기록 필요",
        wDelta != null ? (wDelta > 0 ? "#f59e0b" : wDelta < 0 ? "#38bdf8" : "#94a3b8") : "#94a3b8")}
      ${statCard("체고", last && last.height ? fmt(last.height) + " cm" : "-",
        breed ? `표준 ${breed.height[0]}~${breed.height[1]}cm` : "", "#8b5cf6")}
      ${statCard("몸통 둘레", last && last.chest ? fmt(last.chest) + " cm" : "-",
        breed ? `표준 ${breed.chest[0]}~${breed.chest[1]}cm` : "", "#0ea5b7")}
    </section>

    ${breed ? obesityPanel(pct, grade, bcs, breed) : ""}

    <section class="card">
      <div class="card-head">
        <h3>📈 트렌드</h3>
        <div class="tabs" id="trendTabs">
          <button class="tab active" data-metric="weight">체중</button>
          <button class="tab" data-metric="obesity">비만도</button>
          <button class="tab" data-metric="height">체고</button>
          <button class="tab" data-metric="chest">몸통 둘레</button>
        </div>
      </div>
      <div id="chartArea" class="chart-area-wrap"></div>
      <p class="chart-note muted small" id="chartNote"></p>
    </section>

    ${breed ? tipsPanel(breed) : ""}

    <section class="card">
      <div class="card-head">
        <h3>📋 기록 내역</h3>
        <span class="muted small">${records.length}건</span>
      </div>
      <div id="recordTable"></div>
    </section>
  `;

  $("#editDogBtn").addEventListener("click", () => openDogModal(dog));
  $("#addRecordBtn").addEventListener("click", () => openRecordModal());

  // 트렌드 탭
  let currentMetric = "weight";
  const drawChart = () => renderTrend(currentMetric, dog, breed, records);
  $$("#trendTabs .tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      $$("#trendTabs .tab").forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");
      currentMetric = tab.dataset.metric;
      drawChart();
    });
  });
  drawChart();

  renderRecordTable(records, breed);
}

function statCard(label, value, sub, color) {
  return `
    <div class="stat-card">
      <div class="stat-label">${label}</div>
      <div class="stat-value">${value}</div>
      <div class="stat-sub" style="color:${color || "#94a3b8"}">${sub || ""}</div>
    </div>`;
}

function obesityPanel(pct, grade, bcs, breed) {
  const advice = weightAdvice(pct, breed);
  // 게이지 위치: 70%~150% 구간을 0~100 막대에 매핑
  const gaugePos = pct == null ? 50 : Math.max(0, Math.min(100, ((pct - 70) / 80) * 100));
  return `
    <section class="card obesity-panel">
      <div class="card-head"><h3>⚖️ 비만도 평가</h3>
        <span class="badge-lg" style="background:${grade.color}1a;color:${grade.color}">${grade.label}${pct != null ? " · " + fmt(pct, 0) + "%" : ""}</span>
      </div>
      <div class="gauge">
        <div class="gauge-track">
          <span class="gauge-seg" style="background:#38bdf8"></span>
          <span class="gauge-seg" style="background:#22c55e"></span>
          <span class="gauge-seg" style="background:#f59e0b"></span>
          <span class="gauge-seg" style="background:#ef4444"></span>
          ${pct != null ? `<span class="gauge-marker" style="left:${gaugePos}%"></span>` : ""}
        </div>
        <div class="gauge-scale">
          <span>저체중</span><span>정상</span><span>과체중</span><span>비만</span>
        </div>
      </div>
      <div class="obesity-meta">
        <div><span class="muted small">이상 체중</span><b>${fmt(breedIdealWeight(breed))} kg</b></div>
        <div><span class="muted small">표준 범위</span><b>${breed.weight[0]}~${breed.weight[1]} kg</b></div>
        <div><span class="muted small">추정 BCS</span><b>${bcs != null ? bcs + " / 9" : "-"}</b></div>
      </div>
      <p class="advice">${advice}</p>
    </section>`;
}

function tipsPanel(breed) {
  return `
    <section class="card">
      <div class="card-head"><h3>💡 ${escapeHtml(breed.name)} 주요 관리 포인트</h3></div>
      <ul class="tips-list">
        ${breed.tips.map((t) => `<li>${escapeHtml(t)}</li>`).join("")}
      </ul>
    </section>`;
}

// ---------- 트렌드 차트 ----------
function renderTrend(metric, dog, breed, records) {
  const area = $("#chartArea");
  const note = $("#chartNote");
  let points, opts;

  if (metric === "weight") {
    points = records.map((r) => ({ x: r.date, y: r.weight }));
    opts = {
      unit: "kg",
      color: "#6366f1",
      band: breed ? breed.weight : null,
      ideal: breed ? breedIdealWeight(breed) : null,
    };
    note.textContent = breed
      ? `연두색 밴드 = 견종 표준 체중 범위(${breed.weight[0]}~${breed.weight[1]}kg), 점선 = 이상 체중.`
      : "";
  } else if (metric === "obesity") {
    points = records.map((r) => ({
      x: r.date,
      y: breed ? obesityPercent(r.weight, breed) : null,
    }));
    opts = { unit: "%", color: "#ef4444", ideal: 100, band: [85, 115] };
    note.textContent = "100% = 이상 체중. 밴드(85~115%) 안이면 정상 범위예요.";
  } else if (metric === "height") {
    points = records.map((r) => ({ x: r.date, y: r.height }));
    opts = { unit: "cm", color: "#8b5cf6", band: breed ? breed.height : null };
    note.textContent = breed ? `밴드 = 견종 표준 체고(${breed.height[0]}~${breed.height[1]}cm).` : "";
  } else {
    points = records.map((r) => ({ x: r.date, y: r.chest }));
    opts = { unit: "cm", color: "#0ea5b7", band: breed ? breed.chest : null };
    note.textContent = breed ? `밴드 = 견종 표준 몸통 둘레(${breed.chest[0]}~${breed.chest[1]}cm).` : "";
  }

  renderLineChart(area, points, opts);
}

// ---------- 기록 테이블 ----------
function renderRecordTable(records, breed) {
  const wrap = $("#recordTable");
  if (records.length === 0) {
    wrap.innerHTML = '<p class="muted small">아직 기록이 없어요. 수치를 기록해 보세요.</p>';
    return;
  }
  const rows = [...records].reverse().map((r, idx, arr) => {
    // reverse된 배열에서 다음 인덱스가 이전 기록
    const prevRec = arr[idx + 1];
    const wD = prevRec ? delta(r.weight, prevRec.weight) : null;
    const pct = breed ? obesityPercent(r.weight, breed) : null;
    const grade = obesityGrade(pct);
    return `
      <tr>
        <td>${r.date}</td>
        <td>${fmt(r.weight)}${wD != null ? ` <span class="mini ${wD > 0 ? "up" : wD < 0 ? "down" : ""}">${wD > 0 ? "▲" : wD < 0 ? "▼" : ""}${fmt(Math.abs(wD), 2)}</span>` : ""}</td>
        <td>${r.height ? fmt(r.height) : "-"}</td>
        <td>${r.chest ? fmt(r.chest) : "-"}</td>
        <td>${r.neck ? fmt(r.neck) : "-"}</td>
        <td>${pct != null ? `<span class="badge" style="background:${grade.color}20;color:${grade.color}">${fmt(pct, 0)}%</span>` : "-"}</td>
        <td class="note-cell">${r.note ? escapeHtml(r.note) : ""}</td>
        <td class="row-actions">
          <button class="icon-btn" data-edit="${r.id}" title="수정">✏️</button>
          <button class="icon-btn" data-del="${r.id}" title="삭제">🗑️</button>
        </td>
      </tr>`;
  }).join("");

  wrap.innerHTML = `
    <div class="table-scroll">
      <table class="rec-table">
        <thead><tr>
          <th>날짜</th><th>체중(kg)</th><th>체고(cm)</th><th>몸통(cm)</th><th>목(cm)</th><th>비만도</th><th>메모</th><th></th>
        </tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;

  $$("[data-edit]", wrap).forEach((b) =>
    b.addEventListener("click", () => {
      const rec = Store.db.records.find((x) => x.id === b.dataset.edit);
      openRecordModal(rec);
    })
  );
  $$("[data-del]", wrap).forEach((b) =>
    b.addEventListener("click", () => {
      if (confirm("이 기록을 삭제할까요?")) {
        Store.deleteRecord(b.dataset.del);
        render();
      }
    })
  );
}

// ---------- 강아지 추가/수정 모달 ----------
function openDogModal(dog = null) {
  const editing = !!dog;
  const modal = $("#modal");
  modal.innerHTML = `
    <div class="modal-box">
      <div class="modal-head">
        <h3>${editing ? "프로필 수정" : "강아지 추가"}</h3>
        <button class="icon-btn" id="closeModal">✕</button>
      </div>
      <form id="dogForm" class="form">
        <label>이름<input name="name" required maxlength="20" value="${editing ? escapeAttr(dog.name) : ""}" placeholder="예: 초코"></label>
        <label>견종<select name="breedId" id="breedSelect"></select></label>
        <div class="form-row">
          <label>성별
            <select name="sex">
              <option value="">선택 안함</option>
              <option value="M" ${editing && dog.sex === "M" ? "selected" : ""}>수컷</option>
              <option value="F" ${editing && dog.sex === "F" ? "selected" : ""}>암컷</option>
            </select>
          </label>
          <label class="check-inline">중성화
            <input type="checkbox" name="neutered" ${editing && dog.neutered ? "checked" : ""}>
          </label>
        </div>
        <label>생년월일<input type="date" name="birth" value="${editing && dog.birth ? dog.birth : ""}"></label>
        <div class="modal-actions">
          ${editing ? '<button type="button" class="btn btn-danger" id="deleteDogBtn">삭제</button>' : "<span></span>"}
          <div>
            <button type="button" class="btn" id="cancelModal">취소</button>
            <button type="submit" class="btn btn-primary">${editing ? "저장" : "추가"}</button>
          </div>
        </div>
      </form>
    </div>`;
  modal.classList.add("open");
  populateBreedOptions($("#breedSelect"), editing ? dog.breedId : BREEDS[0].id);

  const close = () => modal.classList.remove("open");
  $("#closeModal").onclick = close;
  $("#cancelModal").onclick = close;
  modal.onclick = (e) => { if (e.target === modal) close(); };

  if (editing) {
    $("#deleteDogBtn").onclick = () => {
      if (confirm(`${dog.name}의 프로필과 모든 기록을 삭제할까요?`)) {
        Store.deleteDog(dog.id);
        close();
        render();
      }
    };
  }

  $("#dogForm").onsubmit = (e) => {
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
    if (editing) Store.updateDog(dog.id, data);
    else Store.addDog(data);
    close();
    render();
  };
}

// ---------- 수치 기록 모달 ----------
function openRecordModal(rec = null) {
  const dog = Store.getActiveDog();
  if (!dog) return;
  const editing = !!rec;
  const today = new Date().toISOString().slice(0, 10);
  const modal = $("#modal");
  modal.innerHTML = `
    <div class="modal-box">
      <div class="modal-head">
        <h3>${editing ? "기록 수정" : "수치 기록"} · ${escapeHtml(dog.name)}</h3>
        <button class="icon-btn" id="closeModal">✕</button>
      </div>
      <form id="recForm" class="form">
        <label>측정 날짜<input type="date" name="date" required value="${editing ? rec.date : today}"></label>
        <div class="form-row">
          <label>체중 (kg) *<input type="number" name="weight" step="0.01" min="0" required value="${editing ? rec.weight : ""}" placeholder="예: 4.2"></label>
          <label>체고 (cm)<input type="number" name="height" step="0.1" min="0" value="${editing && rec.height ? rec.height : ""}" placeholder="어깨 높이"></label>
        </div>
        <div class="form-row">
          <label>몸통 둘레 (cm)<input type="number" name="chest" step="0.1" min="0" value="${editing && rec.chest ? rec.chest : ""}" placeholder="가슴 둘레"></label>
          <label>목 둘레 (cm)<input type="number" name="neck" step="0.1" min="0" value="${editing && rec.neck ? rec.neck : ""}" placeholder="선택"></label>
        </div>
        <label>메모<input name="note" maxlength="60" value="${editing && rec.note ? escapeAttr(rec.note) : ""}" placeholder="예: 병원 검진, 사료 변경 등"></label>
        <div class="modal-actions">
          ${editing ? '<button type="button" class="btn btn-danger" id="deleteRecBtn">삭제</button>' : "<span></span>"}
          <div>
            <button type="button" class="btn" id="cancelModal">취소</button>
            <button type="submit" class="btn btn-primary">${editing ? "저장" : "기록"}</button>
          </div>
        </div>
      </form>
    </div>`;
  modal.classList.add("open");
  const close = () => modal.classList.remove("open");
  $("#closeModal").onclick = close;
  $("#cancelModal").onclick = close;
  modal.onclick = (e) => { if (e.target === modal) close(); };

  if (editing) {
    $("#deleteRecBtn").onclick = () => {
      if (confirm("이 기록을 삭제할까요?")) { Store.deleteRecord(rec.id); close(); render(); }
    };
  }

  $("#recForm").onsubmit = (e) => {
    e.preventDefault();
    const f = e.target;
    const num = (v) => (v === "" ? null : parseFloat(v));
    const data = {
      dogId: dog.id,
      date: f.date.value,
      weight: num(f.weight.value),
      height: num(f.height.value),
      chest: num(f.chest.value),
      neck: num(f.neck.value),
      note: f.note.value.trim(),
    };
    if (data.weight == null) return;
    if (editing) Store.updateRecord(rec.id, data);
    else Store.addRecord(data);
    close();
    render();
  };
}

// ---------- 데이터 내보내기/가져오기 ----------
function setupDataButtons() {
  $("#exportBtn").addEventListener("click", () => {
    const blob = new Blob([Store.exportJSON()], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "dog-health-backup.json";
    a.click();
    URL.revokeObjectURL(a.href);
  });
  $("#importBtn").addEventListener("click", () => $("#importFile").click());
  $("#importFile").addEventListener("change", (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      try {
        Store.importJSON(reader.result);
        render();
        alert("데이터를 불러왔어요.");
      } catch (err) {
        alert("불러오기 실패: " + err.message);
      }
    };
    reader.readAsText(file);
    e.target.value = "";
  });
}

// ---------- 유틸 ----------
function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function escapeAttr(s) { return escapeHtml(s); }

// ---------- 전체 렌더 ----------
function render() {
  renderDogList();
  renderDashboard();
}

document.addEventListener("DOMContentLoaded", () => {
  $("#addDogBtn").addEventListener("click", () => openDogModal());
  setupDataButtons();
  render();
  // 리사이즈 시 차트 다시 그리기
  let rt;
  window.addEventListener("resize", () => {
    clearTimeout(rt);
    rt = setTimeout(() => { if (Store.getActiveDog()) renderDashboard(); }, 200);
  });
});
