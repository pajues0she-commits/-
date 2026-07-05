/* ============================================================
 * app.js — 화면 제어 및 이벤트 처리
 * ============================================================ */
(function () {
  'use strict';

  var $ = function (id) { return document.getElementById(id); };
  var pad = Store.pad;

  // ---------- 상태 ----------
  var currentTab = 'workout';
  var wkDate = todayStr();
  var editingWorkoutId = null;
  var editingInbodyId = null;

  var TITLES = { workout: '운동 기록', inbody: '인바디', stats: '통계' };

  // 자주 쓰는 운동 빠른 선택 기본값
  var DEFAULT_EXERCISES = [
    '벤치프레스', '스쿼트', '데드리프트', '숄더프레스', '바벨로우',
    '랫풀다운', '레그프레스', '인클라인 덤벨프레스', '풀업', '딥스'
  ];

  // ============================================================
  // 유틸
  // ============================================================
  function todayStr() {
    var d = new Date();
    return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate());
  }
  function shiftDate(str, delta) {
    var p = str.split('-');
    var d = new Date(parseInt(p[0]), parseInt(p[1]) - 1, parseInt(p[2]) + delta);
    return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate());
  }
  function prettyDate(str) {
    var p = str.split('-');
    var d = new Date(parseInt(p[0]), parseInt(p[1]) - 1, parseInt(p[2]));
    var days = ['일', '월', '화', '수', '목', '금', '토'];
    var t = todayStr();
    var label = (str === t) ? ' · 오늘' : '';
    return (d.getMonth() + 1) + '월 ' + d.getDate() + '일 (' + days[d.getDay()] + ')' + label;
  }
  function toast(msg) {
    var t = $('toast');
    t.textContent = msg;
    t.classList.remove('hidden');
    clearTimeout(toast._t);
    toast._t = setTimeout(function () { t.classList.add('hidden'); }, 1900);
  }
  function fmtNum(n) {
    if (n == null) return '–';
    return (Math.round(n * 10) / 10).toLocaleString();
  }

  // ============================================================
  // 탭 전환
  // ============================================================
  function switchTab(tab) {
    currentTab = tab;
    document.querySelectorAll('.tab').forEach(function (b) {
      b.classList.toggle('active', b.dataset.tab === tab);
    });
    document.querySelectorAll('.view').forEach(function (v) {
      v.classList.toggle('hidden', v.dataset.view !== tab);
    });
    $('appbar-title').textContent = TITLES[tab];
    if (tab === 'workout') renderWorkout();
    else if (tab === 'inbody') renderInbody();
    else if (tab === 'stats') renderStats();
    window.scrollTo(0, 0);
  }

  // ============================================================
  // 운동 화면 렌더
  // ============================================================
  function renderWorkout() {
    $('wk-date').value = wkDate;
    var list = Store.workoutsByDate(wkDate);
    var box = $('wk-list');
    box.innerHTML = '';

    if (list.length === 0) {
      $('wk-empty').classList.remove('hidden');
      $('wk-summary').classList.add('hidden');
    } else {
      $('wk-empty').classList.add('hidden');
      $('wk-summary').classList.remove('hidden');
      renderWkSummary(list);
      list.forEach(function (w) { box.appendChild(workoutCard(w)); });
    }
  }

  function renderWkSummary(list) {
    var totalSets = 0, totalVol = 0;
    list.forEach(function (w) {
      totalSets += (w.sets ? w.sets.length : 0);
      totalVol += Store.volumeOf(w);
    });
    $('wk-summary').innerHTML =
      pill(list.length, '운동') + pill(totalSets, '세트') + pill(Math.round(totalVol).toLocaleString(), '총 볼륨(kg)');
  }
  function pill(num, lab) {
    return '<div class="summary-pill"><div class="num">' + num + '</div><div class="lab">' + lab + '</div></div>';
  }

  function workoutCard(w) {
    var card = document.createElement('div');
    card.className = 'ex-card';
    var vol = Store.volumeOf(w);

    var setsHtml = (w.sets || []).map(function (s, i) {
      var wv = s.w == null ? '–' : s.w;
      var rv = s.r == null ? '–' : s.r;
      return '<div class="set-tag"><span class="si">' + (i + 1) + '</span>' +
        '<span class="sv">' + wv + '<small style="color:var(--txt-faint)">kg</small></span>' +
        '<span class="sx">×</span><span class="sv">' + rv + '<small style="color:var(--txt-faint)">회</small></span></div>';
    }).join('');

    card.innerHTML =
      '<div class="ex-card-top"><span class="ex-card-name">' + esc(w.name || '운동') + '</span>' +
      (vol > 0 ? '<span class="ex-card-vol">' + Math.round(vol).toLocaleString() + ' kg</span>' : '') + '</div>' +
      '<div class="set-grid">' + setsHtml + '</div>' +
      (w.note ? '<div class="ex-note">💬 ' + esc(w.note) + '</div>' : '');

    card.addEventListener('click', function () { openWorkoutSheet(w); });
    return card;
  }

  // ============================================================
  // 운동 입력 시트
  // ============================================================
  function openWorkoutSheet(rec) {
    editingWorkoutId = rec ? rec.id : null;
    $('wk-sheet-title').textContent = rec ? '운동 편집' : '운동 추가';
    $('wk-name').value = rec ? (rec.name || '') : '';
    $('wk-note').value = rec ? (rec.note || '') : '';
    $('wk-delete').classList.toggle('hidden', !rec);

    // 세트 초기화
    var sets = (rec && rec.sets && rec.sets.length) ? rec.sets.slice() : [{ w: '', r: '' }, { w: '', r: '' }, { w: '', r: '' }];
    renderSetRows(sets);

    // 빠른선택 칩 & 자동완성
    buildExerciseSuggestions();

    showSheet('wk-sheet');
    if (!rec) setTimeout(function () { $('wk-name').focus(); }, 250);
  }

  function renderSetRows(sets) {
    var box = $('wk-sets');
    box.innerHTML = '';
    sets.forEach(function (s) { box.appendChild(setRow(s.w, s.r)); });
    renumberSets();
  }

  function setRow(w, r) {
    var row = document.createElement('div');
    row.className = 'set-row';
    row.innerHTML =
      '<div class="set-no"></div>' +
      '<input type="number" inputmode="decimal" step="0.5" class="in-w" placeholder="중량" value="' + (w === '' || w == null ? '' : w) + '" />' +
      '<span class="set-unit">kg</span>' +
      '<input type="number" inputmode="numeric" step="1" class="in-r" placeholder="회수" value="' + (r === '' || r == null ? '' : r) + '" />' +
      '<span class="set-unit">회</span>' +
      '<button class="set-del" aria-label="세트 삭제">×</button>';
    row.querySelector('.set-del').addEventListener('click', function () {
      row.remove();
      renumberSets();
    });
    return row;
  }

  function renumberSets() {
    var rows = $('wk-sets').querySelectorAll('.set-row');
    rows.forEach(function (r, i) { r.querySelector('.set-no').textContent = (i + 1); });
  }

  function collectSets() {
    var rows = $('wk-sets').querySelectorAll('.set-row');
    var out = [];
    rows.forEach(function (r) {
      out.push({ w: r.querySelector('.in-w').value, r: r.querySelector('.in-r').value });
    });
    return out;
  }

  function buildExerciseSuggestions() {
    // 사용자 사전 + 기본값 병합(중복 제거)
    var used = Store.state().exercises || [];
    var merged = [];
    var seen = {};
    used.concat(DEFAULT_EXERCISES).forEach(function (n) {
      var k = n.toLowerCase();
      if (!seen[k]) { seen[k] = 1; merged.push(n); }
    });

    // datalist
    var dl = $('exercise-suggestions');
    dl.innerHTML = merged.map(function (n) { return '<option value="' + esc(n) + '">'; }).join('');

    // 칩(상위 8개)
    var chipBox = $('wk-quick');
    chipBox.innerHTML = '';
    merged.slice(0, 8).forEach(function (n) {
      var c = document.createElement('button');
      c.className = 'chip';
      c.type = 'button';
      c.textContent = n;
      c.addEventListener('click', function () { $('wk-name').value = n; });
      chipBox.appendChild(c);
    });
  }

  function saveWorkoutFromSheet() {
    var name = $('wk-name').value.trim();
    if (!name) { toast('운동 이름을 입력하세요'); $('wk-name').focus(); return; }
    var sets = collectSets().filter(function (s) {
      return String(s.w).trim() !== '' || String(s.r).trim() !== '';
    });
    if (sets.length === 0) { toast('세트를 1개 이상 입력하세요'); return; }

    Store.saveWorkout({
      id: editingWorkoutId,
      date: wkDate,
      name: name,
      sets: sets,
      note: $('wk-note').value
    });
    hideSheet('wk-sheet');
    toast(editingWorkoutId ? '수정되었습니다' : '저장되었습니다');
    renderWorkout();
  }

  // ============================================================
  // 인바디 화면 렌더
  // ============================================================
  function renderInbody() {
    var all = Store.inbodyAll();      // 최신순
    var chrono = Store.inbodyChrono(); // 과거→최신

    if (all.length === 0) {
      $('ib-empty').classList.remove('hidden');
      $('ib-latest').classList.add('hidden');
      $('ib-charts').innerHTML = '';
      $('ib-list').innerHTML = '';
      document.querySelectorAll('#view-inbody .section-title').forEach(function (s) { s.classList.add('hidden'); });
      return;
    }
    document.querySelectorAll('#view-inbody .section-title').forEach(function (s) { s.classList.remove('hidden'); });
    $('ib-empty').classList.add('hidden');
    $('ib-latest').classList.remove('hidden');

    renderInbodyHero(all[0], all[1]);
    renderInbodyCharts(chrono);
    renderInbodyList(all);
  }

  function renderInbodyHero(latest, prev) {
    function metric(label, val, unit, prevVal, cls, invert) {
      var v = (val == null) ? '–' : fmtNum(val);
      var delta = '';
      if (val != null && prev && prevVal != null) {
        var diff = val - prevVal;
        var dr = Math.round(diff * 10) / 10;
        if (dr === 0) delta = '<div class="d flat">±0</div>';
        else {
          var good = invert ? dr < 0 : dr > 0;
          var arrow = dr > 0 ? '▲' : '▼';
          delta = '<div class="d ' + (good ? 'up' : 'down') + '">' + arrow + ' ' + Math.abs(dr) + '</div>';
        }
      }
      return '<div class="ih-metric ' + (cls || '') + '"><div class="v">' + v +
        (val != null && unit ? '<small>' + unit + '</small>' : '') + '</div>' +
        '<div class="l">' + label + '</div>' + delta + '</div>';
    }
    $('ib-latest').innerHTML =
      '<div class="ih-date">📅 ' + prettyDate(latest.date) + ' 측정</div>' +
      '<div class="ih-grid">' +
      metric('체중', latest.weight, 'kg', prev && prev.weight, '', true) +
      metric('골격근량', latest.muscle, 'kg', prev && prev.muscle, 'ih-muscle', false) +
      metric('체지방률', latest.fatpct, '%', prev && prev.fatpct, 'ih-fat', true) +
      metric('체지방량', latest.fatmass, 'kg', prev && prev.fatmass, '', true) +
      metric('BMI', latest.bmi, '', prev && prev.bmi, '', true) +
      metric('점수', latest.score, '', prev && prev.score, '', false) +
      '</div>';
  }

  function renderInbodyCharts(chrono) {
    var box = $('ib-charts');
    box.innerHTML = '';
    var series = [
      { key: 'weight', title: '체중', unit: 'kg', color: '#4f7cff' },
      { key: 'muscle', title: '골격근량', unit: 'kg', color: '#35c98a' },
      { key: 'fatpct', title: '체지방률', unit: '%', color: '#ff9f45' }
    ];
    series.forEach(function (s) {
      var pts = chrono
        .filter(function (r) { return r[s.key] != null; })
        .map(function (r) { return { date: r.date, value: r[s.key] }; });
      if (pts.length === 0) return;
      box.appendChild(Charts.card(s.title, pts, { color: s.color, unit: s.unit, height: 150 }));
    });
  }

  function renderInbodyList(all) {
    var box = $('ib-list');
    box.innerHTML = '';
    all.forEach(function (r) {
      var card = document.createElement('div');
      card.className = 'ib-card';
      card.innerHTML =
        '<div><div class="ibc-date">' + prettyDate(r.date) + '</div>' +
        '<div class="ibc-meta">' +
        '<span>체중 <b>' + fmtNum(r.weight) + '</b></span>' +
        '<span>근육 <b>' + fmtNum(r.muscle) + '</b></span>' +
        '<span>체지방 <b>' + fmtNum(r.fatpct) + '%</b></span>' +
        '</div></div><div class="ibc-chev">›</div>';
      card.addEventListener('click', function () { openInbodySheet(r); });
      box.appendChild(card);
    });
  }

  // ============================================================
  // 인바디 입력 시트
  // ============================================================
  function openInbodySheet(rec) {
    editingInbodyId = rec ? rec.id : null;
    $('ib-sheet-title').textContent = rec ? '인바디 편집' : '인바디 추가';
    $('ib-date').value = rec ? rec.date : todayStr();
    $('ib-weight').value = rec && rec.weight != null ? rec.weight : '';
    $('ib-muscle').value = rec && rec.muscle != null ? rec.muscle : '';
    $('ib-fatmass').value = rec && rec.fatmass != null ? rec.fatmass : '';
    $('ib-fatpct').value = rec && rec.fatpct != null ? rec.fatpct : '';
    $('ib-bmi').value = rec && rec.bmi != null ? rec.bmi : '';
    $('ib-score').value = rec && rec.score != null ? rec.score : '';
    $('ib-note').value = rec ? (rec.note || '') : '';
    $('ib-delete').classList.toggle('hidden', !rec);
    showSheet('ib-sheet');
  }

  function saveInbodyFromSheet() {
    var date = $('ib-date').value;
    if (!date) { toast('측정일을 입력하세요'); return; }
    var vals = ['weight', 'muscle', 'fatmass', 'fatpct', 'bmi', 'score'].map(function (k) {
      return $('ib-' + k).value;
    });
    var anyFilled = vals.some(function (v) { return String(v).trim() !== ''; });
    if (!anyFilled) { toast('항목을 1개 이상 입력하세요'); return; }

    Store.saveInbody({
      id: editingInbodyId,
      date: date,
      weight: $('ib-weight').value,
      muscle: $('ib-muscle').value,
      fatmass: $('ib-fatmass').value,
      fatpct: $('ib-fatpct').value,
      bmi: $('ib-bmi').value,
      score: $('ib-score').value,
      note: $('ib-note').value
    });
    hideSheet('ib-sheet');
    toast(editingInbodyId ? '수정되었습니다' : '저장되었습니다');
    renderInbody();
  }

  // ============================================================
  // 통계 화면
  // ============================================================
  function renderStats() {
    var t = Store.totals();
    $('st-cards').innerHTML =
      statCard('📆', t.days, '운동한 날') +
      statCard('🏋️', t.workouts, '총 운동 수') +
      statCard('🔢', t.sets, '누적 세트') +
      statCard('🧮', Math.round(t.volume).toLocaleString(), '총 볼륨(kg)');

    var names = Store.exerciseNames();
    var sel = $('st-exercise');
    if (names.length === 0) {
      $('st-empty').classList.remove('hidden');
      $('st-chart').innerHTML = '';
      document.querySelector('#view-stats .section-title').classList.add('hidden');
      $('st-exercise').classList.add('hidden');
      return;
    }
    document.querySelector('#view-stats .section-title').classList.remove('hidden');
    $('st-exercise').classList.remove('hidden');
    $('st-empty').classList.add('hidden');

    var prev = sel.value;
    sel.innerHTML = names.map(function (n) { return '<option value="' + esc(n) + '">' + esc(n) + '</option>'; }).join('');
    if (prev && names.indexOf(prev) >= 0) sel.value = prev;
    drawExerciseChart(sel.value);
  }

  function statCard(ico, num, lab) {
    return '<div class="stat-card"><div class="sc-ico">' + ico + '</div>' +
      '<div class="sc-num">' + num + '</div><div class="sc-lab">' + lab + '</div></div>';
  }

  function drawExerciseChart(name) {
    var box = $('st-chart');
    box.innerHTML = '';
    var trend = Store.exerciseTrend(name);
    if (trend.length === 0) {
      box.innerHTML = '<div class="empty-state"><p class="muted">중량 기록이 없습니다.</p></div>';
      return;
    }
    box.appendChild(Charts.card(name + ' · 최고 중량', trend, { color: '#a78bfa', unit: 'kg', height: 170 }));

    // 개인 최고 기록 표시
    var pr = Math.max.apply(null, trend.map(function (p) { return p.value; }));
    var info = document.createElement('div');
    info.className = 'chart-card';
    info.style.textAlign = 'center';
    info.innerHTML = '<div class="cc-title" style="margin-bottom:4px">🏆 개인 최고 (PR)</div>' +
      '<div style="font-size:28px;font-weight:800;color:#a78bfa;letter-spacing:-1px">' + pr + ' kg</div>';
    box.appendChild(info);
  }

  // ============================================================
  // 시트 열기/닫기
  // ============================================================
  function showSheet(id) { $(id).classList.remove('hidden'); document.body.style.overflow = 'hidden'; }
  function hideSheet(id) { $(id).classList.add('hidden'); document.body.style.overflow = ''; }

  // ============================================================
  // 메뉴 / 백업
  // ============================================================
  function doExport() {
    var data = Store.exportData();
    var blob = new Blob([data], { type: 'application/json' });
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = 'fitlog-backup-' + todayStr() + '.json';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
    hideSheet('menu-sheet');
    toast('백업 파일을 저장했습니다');
  }

  function doImport(file) {
    var reader = new FileReader();
    reader.onload = function () {
      try {
        Store.importData(reader.result);
        hideSheet('menu-sheet');
        toast('데이터를 복원했습니다');
        switchTab(currentTab);
      } catch (e) {
        toast('가져오기 실패: 올바른 백업 파일이 아닙니다');
      }
    };
    reader.readAsText(file);
  }

  // ============================================================
  // 이벤트 바인딩
  // ============================================================
  function bind() {
    // 탭
    document.querySelectorAll('.tab').forEach(function (b) {
      b.addEventListener('click', function () { switchTab(b.dataset.tab); });
    });

    // 날짜
    $('wk-prev').addEventListener('click', function () { wkDate = shiftDate(wkDate, -1); renderWorkout(); });
    $('wk-next').addEventListener('click', function () { wkDate = shiftDate(wkDate, 1); renderWorkout(); });
    $('wk-date').addEventListener('change', function () { wkDate = $('wk-date').value || todayStr(); renderWorkout(); });

    // 운동 시트
    $('wk-add').addEventListener('click', function () { openWorkoutSheet(null); });
    $('wk-cancel').addEventListener('click', function () { hideSheet('wk-sheet'); });
    $('wk-save').addEventListener('click', saveWorkoutFromSheet);
    $('wk-add-set').addEventListener('click', function () {
      $('wk-sets').appendChild(setRow('', ''));
      renumberSets();
    });
    $('wk-delete').addEventListener('click', function () {
      if (editingWorkoutId && confirm('이 운동 기록을 삭제할까요?')) {
        Store.deleteWorkout(editingWorkoutId);
        hideSheet('wk-sheet');
        toast('삭제되었습니다');
        renderWorkout();
      }
    });

    // 인바디 시트
    $('ib-add').addEventListener('click', function () { openInbodySheet(null); });
    $('ib-cancel').addEventListener('click', function () { hideSheet('ib-sheet'); });
    $('ib-save').addEventListener('click', saveInbodyFromSheet);
    $('ib-delete').addEventListener('click', function () {
      if (editingInbodyId && confirm('이 측정 기록을 삭제할까요?')) {
        Store.deleteInbody(editingInbodyId);
        hideSheet('ib-sheet');
        toast('삭제되었습니다');
        renderInbody();
      }
    });

    // 통계 운동 선택
    $('st-exercise').addEventListener('change', function () { drawExerciseChart($('st-exercise').value); });

    // 메뉴
    $('btn-menu').addEventListener('click', function () { showSheet('menu-sheet'); });
    $('menu-cancel').addEventListener('click', function () { hideSheet('menu-sheet'); });
    $('menu-export').addEventListener('click', doExport);
    $('menu-import').addEventListener('click', function () { $('menu-file').click(); });
    $('menu-file').addEventListener('change', function (e) {
      if (e.target.files && e.target.files[0]) doImport(e.target.files[0]);
      e.target.value = '';
    });
    $('menu-sample').addEventListener('click', function () {
      if (confirm('예시 데이터로 채웁니다. 현재 데이터는 덮어써집니다. 계속할까요?')) {
        Store.loadSample();
        hideSheet('menu-sheet');
        toast('예시 데이터를 불러왔습니다');
        wkDate = todayStr();
        switchTab('workout');
      }
    });
    $('menu-reset').addEventListener('click', function () {
      if (confirm('모든 운동·인바디 기록을 삭제합니다. 되돌릴 수 없습니다. 계속할까요?')) {
        Store.reset();
        hideSheet('menu-sheet');
        toast('모든 데이터를 삭제했습니다');
        switchTab('workout');
      }
    });

    // 배경 탭하면 시트 닫기
    document.querySelectorAll('.sheet-backdrop').forEach(function (bd) {
      bd.addEventListener('click', function (e) {
        if (e.target === bd) hideSheet(bd.id);
      });
    });
  }

  // ============================================================
  // 이스케이프
  // ============================================================
  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  // ============================================================
  // 시작
  // ============================================================
  bind();
  switchTab('workout');
})();
