/* ============================================================
 * store.js — 로컬 저장소 (localStorage) 데이터 계층
 * 모든 데이터는 사용자 기기에만 저장됩니다. 서버 전송 없음.
 * ============================================================ */
(function (global) {
  'use strict';

  var KEY = 'fitlog.v1';

  // 기본 데이터 구조
  function blank() {
    return {
      workouts: [], // { id, date:'YYYY-MM-DD', name, sets:[{w,r}], note }
      inbody: [],   // { id, date, weight, muscle, fatmass, fatpct, bmi, score, note }
      exercises: [] // 사용자가 입력한 운동 이름 사전(자동완성/빠른선택용)
    };
  }

  var state = load();

  function load() {
    try {
      var raw = localStorage.getItem(KEY);
      if (!raw) return blank();
      var d = JSON.parse(raw);
      var b = blank();
      d.workouts = Array.isArray(d.workouts) ? d.workouts : b.workouts;
      d.inbody = Array.isArray(d.inbody) ? d.inbody : b.inbody;
      d.exercises = Array.isArray(d.exercises) ? d.exercises : b.exercises;
      return d;
    } catch (e) {
      return blank();
    }
  }

  function persist() {
    try {
      localStorage.setItem(KEY, JSON.stringify(state));
    } catch (e) {
      // 저장공간 초과 등
      console.error('저장 실패', e);
    }
  }

  // 간단한 고유 id (충돌 방지: 시간 + 카운터)
  var _seq = 0;
  function uid() {
    _seq = (_seq + 1) % 100000;
    return Date.now().toString(36) + '-' + _seq.toString(36);
  }

  // ---------- 운동 사전 ----------
  function rememberExercise(name) {
    name = (name || '').trim();
    if (!name) return;
    var lower = name.toLowerCase();
    var exists = state.exercises.some(function (e) { return e.toLowerCase() === lower; });
    if (!exists) {
      state.exercises.unshift(name);
      state.exercises = state.exercises.slice(0, 60);
    }
  }

  // ---------- 운동 CRUD ----------
  function workoutsByDate(date) {
    return state.workouts
      .filter(function (w) { return w.date === date; })
      .slice()
      .sort(function (a, b) { return (a.order || 0) - (b.order || 0); });
  }

  function saveWorkout(rec) {
    // sets 정제: 숫자만
    rec.sets = (rec.sets || [])
      .map(function (s) { return { w: num(s.w), r: intg(s.r) }; })
      .filter(function (s) { return s.w !== null || s.r !== null; });
    rec.name = (rec.name || '').trim();
    rec.note = (rec.note || '').trim();

    if (rec.id) {
      var idx = state.workouts.findIndex(function (w) { return w.id === rec.id; });
      if (idx >= 0) state.workouts[idx] = Object.assign(state.workouts[idx], rec);
    } else {
      rec.id = uid();
      rec.order = state.workouts.filter(function (w) { return w.date === rec.date; }).length;
      state.workouts.push(rec);
    }
    rememberExercise(rec.name);
    persist();
    return rec;
  }

  function deleteWorkout(id) {
    state.workouts = state.workouts.filter(function (w) { return w.id !== id; });
    persist();
  }

  // ---------- 인바디 CRUD ----------
  function inbodyAll() {
    return state.inbody.slice().sort(function (a, b) {
      return a.date < b.date ? 1 : a.date > b.date ? -1 : 0; // 최신순
    });
  }
  function inbodyChrono() {
    return state.inbody.slice().sort(function (a, b) {
      return a.date < b.date ? -1 : a.date > b.date ? 1 : 0; // 과거→최신
    });
  }

  function saveInbody(rec) {
    ['weight', 'muscle', 'fatmass', 'fatpct', 'bmi', 'score'].forEach(function (k) {
      rec[k] = num(rec[k]);
    });
    rec.note = (rec.note || '').trim();
    if (rec.id) {
      var idx = state.inbody.findIndex(function (r) { return r.id === rec.id; });
      if (idx >= 0) state.inbody[idx] = Object.assign(state.inbody[idx], rec);
    } else {
      rec.id = uid();
      state.inbody.push(rec);
    }
    persist();
    return rec;
  }

  function deleteInbody(id) {
    state.inbody = state.inbody.filter(function (r) { return r.id !== id; });
    persist();
  }

  // ---------- 통계 ----------
  // 운동별 최고 중량 추이(과거→최신, 날짜별 그 운동의 최대 중량)
  function exerciseTrend(name) {
    var byDate = {};
    state.workouts.forEach(function (w) {
      if (w.name !== name) return;
      var maxW = 0;
      (w.sets || []).forEach(function (s) { if (s.w != null && s.w > maxW) maxW = s.w; });
      if (maxW > 0) byDate[w.date] = Math.max(byDate[w.date] || 0, maxW);
    });
    return Object.keys(byDate).sort().map(function (d) {
      return { date: d, value: byDate[d] };
    });
  }

  function exerciseNames() {
    var set = {};
    state.workouts.forEach(function (w) { if (w.name) set[w.name] = (set[w.name] || 0) + 1; });
    return Object.keys(set).sort(function (a, b) { return set[b] - set[a]; });
  }

  function volumeOf(w) {
    return (w.sets || []).reduce(function (t, s) {
      return t + ((s.w || 0) * (s.r || 0));
    }, 0);
  }

  function totals() {
    var days = {};
    state.workouts.forEach(function (w) { days[w.date] = true; });
    var totalVol = state.workouts.reduce(function (t, w) { return t + volumeOf(w); }, 0);
    var totalSets = state.workouts.reduce(function (t, w) { return t + (w.sets ? w.sets.length : 0); }, 0);
    return {
      days: Object.keys(days).length,
      workouts: state.workouts.length,
      sets: totalSets,
      volume: totalVol,
      inbodyCount: state.inbody.length
    };
  }

  // ---------- 백업/복원 ----------
  function exportData() {
    return JSON.stringify(state, null, 2);
  }
  function importData(json) {
    var d = JSON.parse(json);
    if (!d || typeof d !== 'object') throw new Error('형식 오류');
    var b = blank();
    state = {
      workouts: Array.isArray(d.workouts) ? d.workouts : b.workouts,
      inbody: Array.isArray(d.inbody) ? d.inbody : b.inbody,
      exercises: Array.isArray(d.exercises) ? d.exercises : b.exercises
    };
    persist();
  }
  function reset() { state = blank(); persist(); }

  function loadSample() {
    var today = new Date();
    function dstr(offset) {
      var d = new Date(today.getFullYear(), today.getMonth(), today.getDate() - offset);
      return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate());
    }
    state = blank();
    // 운동 4주치 샘플
    var plan = [
      { off: 0, ex: [['벤치프레스', [[60, 10], [70, 8], [70, 8], [75, 6]]], ['인클라인 덤벨프레스', [[22, 12], [24, 10], [24, 9]]], ['케이블 플라이', [[15, 15], [15, 14], [15, 12]]]] },
      { off: 2, ex: [['스쿼트', [[80, 10], [90, 8], [100, 6], [100, 6]]], ['레그프레스', [[140, 12], [160, 10], [180, 8]]], ['레그 익스텐션', [[40, 15], [45, 12], [45, 12]]]] },
      { off: 4, ex: [['데드리프트', [[100, 8], [120, 5], [130, 3]]], ['랫풀다운', [[55, 12], [60, 10], [60, 10]]], ['바벨로우', [[50, 10], [55, 10], [60, 8]]]] },
      { off: 7, ex: [['벤치프레스', [[60, 10], [72, 8], [75, 7], [77, 5]]], ['숄더프레스', [[30, 10], [34, 8], [34, 8]]], ['사이드 레터럴', [[8, 15], [10, 12], [10, 12]]]] },
      { off: 9, ex: [['스쿼트', [[80, 10], [95, 8], [105, 6], [105, 5]]], ['루마니안 데드', [[70, 10], [80, 8], [80, 8]]]] },
      { off: 14, ex: [['벤치프레스', [[62, 10], [74, 8], [78, 6], [80, 5]]], ['딥스', [[0, 12], [0, 10], [0, 9]]]] },
    ];
    plan.forEach(function (day) {
      day.ex.forEach(function (e, i) {
        saveWorkout({
          date: dstr(day.off), name: e[0],
          sets: e[1].map(function (s) { return { w: s[0], r: s[1] }; }),
          note: ''
        });
      });
    });
    // 인바디 샘플
    [
      { off: 21, weight: 74.5, muscle: 33.2, fatmass: 15.1, fatpct: 20.3, bmi: 23.8, score: 76 },
      { off: 14, weight: 74.0, muscle: 33.8, fatmass: 14.2, fatpct: 19.2, bmi: 23.6, score: 79 },
      { off: 7, weight: 73.6, muscle: 34.3, fatmass: 13.3, fatpct: 18.1, bmi: 23.5, score: 82 },
      { off: 0, weight: 73.2, muscle: 34.9, fatmass: 12.4, fatpct: 16.9, bmi: 23.4, score: 85 },
    ].forEach(function (r) {
      saveInbody({
        date: dstr(r.off), weight: r.weight, muscle: r.muscle, fatmass: r.fatmass,
        fatpct: r.fatpct, bmi: r.bmi, score: r.score, note: ''
      });
    });
    persist();
  }

  // ---------- 유틸 ----------
  function num(v) {
    if (v === '' || v === null || v === undefined) return null;
    var n = parseFloat(v);
    return isNaN(n) ? null : n;
  }
  function intg(v) {
    if (v === '' || v === null || v === undefined) return null;
    var n = parseInt(v, 10);
    return isNaN(n) ? null : n;
  }
  function pad(n) { return n < 10 ? '0' + n : '' + n; }

  global.Store = {
    state: function () { return state; },
    uid: uid,
    workoutsByDate: workoutsByDate,
    saveWorkout: saveWorkout,
    deleteWorkout: deleteWorkout,
    inbodyAll: inbodyAll,
    inbodyChrono: inbodyChrono,
    saveInbody: saveInbody,
    deleteInbody: deleteInbody,
    exerciseTrend: exerciseTrend,
    exerciseNames: exerciseNames,
    volumeOf: volumeOf,
    totals: totals,
    exportData: exportData,
    importData: importData,
    loadSample: loadSample,
    reset: reset,
    pad: pad
  };
})(window);
