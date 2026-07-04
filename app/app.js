/* 유해화학물질 취급시설 자체점검 — 앱 로직 */
(function () {
  "use strict";

  const APP_VERSION = "1.0.0";
  const LS_RECORDS = "chk.records.v1";
  const LS_SETTINGS = "chk.settings.v1";
  const LS_DRAFT = "chk.draft.v1";

  const $ = (sel, root) => (root || document).querySelector(sel);
  const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));

  // ---------- 저장소 ----------
  const store = {
    records() {
      try {
        return JSON.parse(localStorage.getItem(LS_RECORDS) || "[]");
      } catch (e) {
        return [];
      }
    },
    saveRecords(list) {
      localStorage.setItem(LS_RECORDS, JSON.stringify(list));
    },
    upsert(rec) {
      const list = store.records();
      const i = list.findIndex((r) => r.id === rec.id);
      if (i >= 0) list[i] = rec;
      else list.unshift(rec);
      store.saveRecords(list);
    },
    remove(id) {
      store.saveRecords(store.records().filter((r) => r.id !== id));
    },
    settings() {
      try {
        return JSON.parse(localStorage.getItem(LS_SETTINGS) || "{}");
      } catch (e) {
        return {};
      }
    },
    saveSettings(s) {
      localStorage.setItem(LS_SETTINGS, JSON.stringify(s));
    },
    draft() {
      try {
        return JSON.parse(localStorage.getItem(LS_DRAFT) || "null");
      } catch (e) {
        return null;
      }
    },
    saveDraft(d) {
      localStorage.setItem(LS_DRAFT, JSON.stringify(d));
    },
    clearDraft() {
      localStorage.removeItem(LS_DRAFT);
    },
  };

  // ---------- 현재 편집중인 점검 ----------
  let current = null;

  function newRecord() {
    const s = store.settings();
    const now = new Date();
    return {
      id: "chk_" + now.getTime(),
      date: now.toISOString().slice(0, 10),
      timeStart: "",
      timeEnd: "",
      org: s.org || "",
      inspector: s.inspector || "",
      signature: null,
      remark: "",
      items: {},
      itemRemarks: {},
      savedAt: null,
    };
  }

  // ---------- 항목 렌더링 ----------
  function renderItems() {
    const wrap = $("#items");
    wrap.innerHTML = "";
    CHECK_ITEMS.forEach((it) => {
      const sel = current.items[it.no];
      const div = document.createElement("div");
      div.className = "item" + (sel ? " item--done" : "");
      div.dataset.no = it.no;

      const opts = STATUS_OPTIONS.map((opt) => {
        const active = sel === opt.key ? " seg__btn--active seg__btn--" + opt.key : "";
        return `<button type="button" class="seg__btn${active}" data-key="${opt.key}">${opt.label}</button>`;
      }).join("");

      div.innerHTML = `
        <div class="item__head">
          <span class="item__no">${it.no}</span>
          <p class="item__text">${it.text}</p>
        </div>
        <div class="seg" role="group">${opts}</div>
        <input type="text" class="item__remark" placeholder="비고 (선택)" value="${(
          current.itemRemarks[it.no] || ""
        ).replace(/"/g, "&quot;")}" />
      `;
      wrap.appendChild(div);
    });
    updateProgress();
  }

  function updateProgress() {
    const done = CHECK_ITEMS.filter((it) => current.items[it.no]).length;
    const total = CHECK_ITEMS.length;
    const recheck = CHECK_ITEMS.filter(
      (it) => current.items[it.no] === "recheck"
    ).length;
    const txt = $("#progress-text");
    let msg = `${done} / ${total} 항목 점검 완료`;
    if (recheck > 0) msg += ` · ⚠ 정밀 재점검 필요 ${recheck}건`;
    txt.textContent = msg;
    txt.classList.toggle("progress--warn", recheck > 0);
    txt.classList.toggle("progress--done", done === total && recheck === 0);
  }

  // ---------- 폼 ↔ 상태 동기화 ----------
  function fillFormFromCurrent() {
    $("#f-date").value = current.date || "";
    $("#f-time-start").value = current.timeStart || "";
    $("#f-time-end").value = current.timeEnd || "";
    $("#f-org").value = current.org || "";
    $("#f-inspector").value = current.inspector || "";
    $("#f-remark").value = current.remark || "";
    renderItems();
    restoreSignature();
  }

  function readHeaderIntoCurrent() {
    current.date = $("#f-date").value;
    current.timeStart = $("#f-time-start").value;
    current.timeEnd = $("#f-time-end").value;
    current.org = $("#f-org").value.trim();
    current.inspector = $("#f-inspector").value.trim();
    current.remark = $("#f-remark").value;
  }

  // ---------- 서명 캔버스 ----------
  let sign = { drawing: false, dirty: false, ctx: null, canvas: null };

  function initSignature() {
    const canvas = $("#sign-canvas");
    sign.canvas = canvas;
    const ratio = window.devicePixelRatio || 1;
    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      if (rect.width === 0) return;
      canvas.width = rect.width * ratio;
      canvas.height = rect.height * ratio;
      const ctx = canvas.getContext("2d");
      ctx.scale(ratio, ratio);
      ctx.lineWidth = 2.2;
      ctx.lineCap = "round";
      ctx.lineJoin = "round";
      ctx.strokeStyle = "#0b132b";
      sign.ctx = ctx;
      if (current && current.signature) restoreSignature();
    };
    // 다음 프레임에 사이즈 확정
    requestAnimationFrame(resize);
    window.addEventListener("resize", () => requestAnimationFrame(resize));

    const pos = (e) => {
      const rect = canvas.getBoundingClientRect();
      const p = e.touches ? e.touches[0] : e;
      return { x: p.clientX - rect.left, y: p.clientY - rect.top };
    };
    const start = (e) => {
      e.preventDefault();
      sign.drawing = true;
      const { x, y } = pos(e);
      sign.ctx.beginPath();
      sign.ctx.moveTo(x, y);
      $("#sign-hint").style.display = "none";
    };
    const move = (e) => {
      if (!sign.drawing) return;
      e.preventDefault();
      const { x, y } = pos(e);
      sign.ctx.lineTo(x, y);
      sign.ctx.stroke();
      sign.dirty = true;
    };
    const end = () => {
      if (!sign.drawing) return;
      sign.drawing = false;
      if (sign.dirty) {
        current.signature = canvas.toDataURL("image/png");
        saveDraftSoon();
      }
    };
    canvas.addEventListener("mousedown", start);
    canvas.addEventListener("mousemove", move);
    window.addEventListener("mouseup", end);
    canvas.addEventListener("touchstart", start, { passive: false });
    canvas.addEventListener("touchmove", move, { passive: false });
    canvas.addEventListener("touchend", end);

    $("#btn-sign-clear").addEventListener("click", () => {
      sign.ctx.clearRect(0, 0, canvas.width, canvas.height);
      sign.dirty = false;
      current.signature = null;
      $("#sign-hint").style.display = "";
      saveDraftSoon();
    });
  }

  function restoreSignature() {
    if (!sign.ctx || !sign.canvas) return;
    const c = sign.canvas;
    sign.ctx.clearRect(0, 0, c.width, c.height);
    if (current.signature) {
      const img = new Image();
      img.onload = () => {
        const rect = c.getBoundingClientRect();
        sign.ctx.drawImage(img, 0, 0, rect.width, rect.height);
      };
      img.src = current.signature;
      $("#sign-hint").style.display = "none";
    } else {
      $("#sign-hint").style.display = "";
    }
  }

  // ---------- 임시저장(드래프트) ----------
  let draftTimer = null;
  function saveDraftSoon() {
    clearTimeout(draftTimer);
    draftTimer = setTimeout(() => {
      readHeaderIntoCurrent();
      store.saveDraft(current);
    }, 500);
  }

  // ---------- 확인 다이얼로그 (샌드박스에서도 동작하는 커스텀 모달) ----------
  function confirmDialog(msg, opts) {
    opts = opts || {};
    return new Promise((resolve) => {
      const d = $("#cdialog");
      $("#cdialog-msg").textContent = msg;
      const ok = $("#cdialog-ok");
      const cancel = $("#cdialog-cancel");
      ok.textContent = opts.okText || "확인";
      cancel.textContent = opts.cancelText || "취소";
      ok.classList.toggle("btn--danger-solid", !!opts.danger);
      ok.classList.toggle("btn--primary", !opts.danger);
      d.hidden = false;
      const close = (val) => {
        d.hidden = true;
        ok.onclick = null;
        cancel.onclick = null;
        d.onclick = null;
        resolve(val);
      };
      ok.onclick = () => close(true);
      cancel.onclick = () => close(false);
      d.onclick = (e) => {
        if (e.target === d) close(false);
      };
    });
  }

  // ---------- 토스트 ----------
  let toastTimer = null;
  function toast(msg, kind) {
    const t = $("#toast");
    t.textContent = msg;
    t.className = "toast" + (kind ? " toast--" + kind : "");
    t.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => (t.hidden = true), 2600);
  }

  // ---------- 저장 ----------
  function validate() {
    readHeaderIntoCurrent();
    const missing = CHECK_ITEMS.filter((it) => !current.items[it.no]);
    if (!current.date) return "점검연월일을 입력하세요.";
    if (!current.inspector) return "점검자 성명을 입력하세요.";
    if (missing.length)
      return `점검하지 않은 항목이 ${missing.length}건 있습니다 (${missing
        .map((m) => m.no)
        .join(" ")}).`;
    return null;
  }

  function saveCurrent(silent) {
    readHeaderIntoCurrent();
    current.savedAt = new Date().toISOString();
    store.upsert(current);
    store.clearDraft();
    if (!silent) toast("저장되었습니다.", "ok");
    renderHistory();
  }

  // ---------- 양식(PDF/인쇄) ----------
  async function renderFormCanvas(record) {
    const stage = $("#form-stage");
    stage.innerHTML = "";
    const el = buildFormElement(record);
    stage.appendChild(el);
    // 폰트/이미지 레이아웃 안정화
    await new Promise((r) => setTimeout(r, 60));
    const canvas = await html2canvas(el, {
      scale: 2,
      backgroundColor: "#ffffff",
      useCORS: true,
      logging: false,
      windowWidth: el.scrollWidth,
      windowHeight: el.scrollHeight,
    });
    stage.innerHTML = "";
    return canvas;
  }

  // 원본 별지 제42호서식과 동일한 A4 세로(210㎜×297㎜) 규격으로 생성
  function pdfFromCanvas(canvas) {
    const { jsPDF } = window.jspdf;
    const pdf = new jsPDF({ orientation: "portrait", unit: "mm", format: "a4" });
    const pw = pdf.internal.pageSize.getWidth(); // 210
    const ph = pdf.internal.pageSize.getHeight(); // 297
    const margin = 8;
    const availW = pw - margin * 2;
    const availH = ph - margin * 2;
    // 폭을 A4 인쇄영역에 맞추고, 넘치면 높이에 맞춰 축소
    let w = availW;
    let h = (canvas.height / canvas.width) * w;
    if (h > availH) {
      h = availH;
      w = (canvas.width / canvas.height) * h;
    }
    const x = (pw - w) / 2; // 가로 중앙
    const y = margin; // 상단 여백부터
    const img = canvas.toDataURL("image/jpeg", 0.92);
    pdf.addImage(img, "JPEG", x, y, w, h);
    return pdf.output("blob");
  }

  function pdfFilename(record) {
    const d = (record.date || "").replace(/-/g, "");
    const who = (record.inspector || "점검자").replace(/\s+/g, "");
    return `자체점검대장_${d || "날짜"}_${who}.pdf`;
  }

  // ---------- PDF 저장: 미리보기 모달을 먼저 연다 ----------
  // (미리보기 환경에서 다운로드가 막혀도 결과 PDF를 눈으로 확인 가능)
  let pdfCtx = null; // { blob, filename }

  async function savePdf() {
    const err = validate();
    if (err) {
      toast(err, "warn");
      return;
    }
    saveCurrent(true);
    await openPdfModal(current);
  }

  async function openPdfModal(record) {
    const btn = $("#btn-pdf");
    const prev = btn ? btn.textContent : "";
    if (btn) {
      btn.disabled = true;
      btn.textContent = "PDF 생성 중…";
    }
    try {
      const canvas = await renderFormCanvas(record);
      const blob = pdfFromCanvas(canvas);
      pdfCtx = { blob, filename: pdfFilename(record) };
      $("#pdf-img").src = canvas.toDataURL("image/png");
      $("#pdf-modal").hidden = false;
      document.body.classList.add("modal-open");
    } catch (e) {
      console.error(e);
      toast("PDF 생성 중 오류가 발생했습니다.", "warn");
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.textContent = prev;
      }
    }
  }

  function closePdfModal() {
    $("#pdf-modal").hidden = true;
    document.body.classList.remove("modal-open");
  }

  function downloadPdf() {
    if (!pdfCtx) return;
    const ok = downloadBlob(pdfCtx.blob, pdfCtx.filename);
    toast(
      ok
        ? "A4 규격 PDF를 내려받았습니다."
        : "이 미리보기 환경에서는 다운로드가 제한됩니다. 배포 후 이용하세요.",
      ok ? "ok" : "warn"
    );
  }

  // 다운로드 시도. 예외가 없으면 true(브라우저가 처리) — 샌드박스에서 막히면 false.
  function downloadBlob(blob, filename) {
    try {
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.rel = "noopener";
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 4000);
      return true;
    } catch (e) {
      console.error("download blocked", e);
      return false;
    }
  }

  // ---------- 미리보기 · 인쇄 ----------
  function openPreview(record) {
    readHeaderIntoCurrent();
    const rec = record || current;
    const holder = $("#preview-holder");
    holder.innerHTML = "";
    holder.appendChild(buildFormElement(rec));
    holder.dataset.recid = rec.id;
    $("#preview-modal").hidden = false;
    document.body.classList.add("modal-open");
  }
  function closePreview() {
    $("#preview-modal").hidden = true;
    document.body.classList.remove("modal-open");
  }
  function printForm() {
    // 인쇄용 루트에 양식을 복제 후 window.print()
    const holder = $("#preview-holder");
    const root = document.getElementById("print-root") || document.createElement("div");
    root.id = "print-root";
    root.innerHTML = "";
    root.appendChild(holder.firstElementChild.cloneNode(true));
    if (!root.parentNode) document.body.appendChild(root);
    window.print();
  }

  // ---------- 저장내역 ----------
  function statusBadge(record) {
    const done = CHECK_ITEMS.filter((it) => record.items[it.no]).length;
    const recheck = CHECK_ITEMS.filter((it) => record.items[it.no] === "recheck").length;
    if (recheck > 0)
      return `<span class="rec__badge rec__badge--warn">재점검 ${recheck}</span>`;
    if (done === CHECK_ITEMS.length)
      return `<span class="rec__badge rec__badge--ok">정상</span>`;
    return `<span class="rec__badge">${done}/${CHECK_ITEMS.length}</span>`;
  }

  function renderHistory() {
    const list = store.records();
    $("#history-count").textContent = list.length + "건";
    $("#record-list").innerHTML = "";
    $("#history-empty").style.display = list.length ? "none" : "block";
    list.forEach((r) => {
      const li = document.createElement("li");
      li.className = "rec";
      li.innerHTML = `
        <div class="rec__main" data-act="open" data-id="${r.id}">
          <div class="rec__row">
            <strong>${r.date || "날짜 미상"}</strong>
            ${statusBadge(r)}
          </div>
          <div class="rec__sub">${(r.org || "-")} · ${(r.inspector || "-")} · ${
        r.timeStart || "--:--"
      }~${r.timeEnd || "--:--"}</div>
        </div>
        <div class="rec__acts">
          <button class="mini" data-act="pdf" data-id="${r.id}">PDF</button>
          <button class="mini mini--danger" data-act="del" data-id="${r.id}">삭제</button>
        </div>`;
      $("#record-list").appendChild(li);
    });
  }

  // ---------- 뷰 전환 ----------
  function showView(name) {
    $$(".view").forEach((v) => v.classList.remove("view--active"));
    $("#view-" + name).classList.add("view--active");
    $$(".tab").forEach((t) =>
      t.classList.toggle("tab--active", t.dataset.view === name)
    );
    if (name === "history") renderHistory();
    window.scrollTo(0, 0);
  }

  // ---------- 이벤트 바인딩 ----------
  function bind() {
    // 항목 선택 & 항목별 비고
    $("#items").addEventListener("click", (e) => {
      const btn = e.target.closest(".seg__btn");
      if (!btn) return;
      const item = btn.closest(".item");
      const no = item.dataset.no;
      const key = btn.dataset.key;
      current.items[no] = current.items[no] === key ? undefined : key;
      if (current.items[no] === undefined) delete current.items[no];
      renderItems();
      saveDraftSoon();
    });
    $("#items").addEventListener("input", (e) => {
      const inp = e.target.closest(".item__remark");
      if (!inp) return;
      const no = inp.closest(".item").dataset.no;
      current.itemRemarks[no] = inp.value;
      saveDraftSoon();
    });

    // 일괄 "모두 문제없음"
    $(".bulk").addEventListener("click", (e) => {
      const b = e.target.closest("[data-bulk]");
      if (!b) return;
      CHECK_ITEMS.forEach((it) => (current.items[it.no] = "ok"));
      renderItems();
      saveDraftSoon();
      toast("모든 항목을 '문제없음'으로 설정했습니다.");
    });

    // 헤더 입력 → 드래프트 저장
    ["#f-date", "#f-time-start", "#f-time-end", "#f-org", "#f-inspector", "#f-remark"].forEach(
      (id) => $(id).addEventListener("input", saveDraftSoon)
    );

    $("#btn-save").addEventListener("click", async () => {
      const err = validate();
      if (err && !(await confirmDialog(err + "\n그래도 저장하시겠습니까?"))) return;
      saveCurrent();
    });
    $("#btn-pdf").addEventListener("click", savePdf);
    $("#btn-preview").addEventListener("click", () => openPreview());
    $("#btn-reset").addEventListener("click", async () => {
      if (
        !(await confirmDialog("현재 입력한 내용을 지우고 새 점검을 시작할까요?", {
          okText: "새 점검",
        }))
      )
        return;
      current = newRecord();
      store.clearDraft();
      fillFormFromCurrent();
      toast("새 점검을 시작합니다.");
    });

    // 미리보기 모달
    $("#btn-preview-close").addEventListener("click", closePreview);
    $("#btn-print").addEventListener("click", printForm);

    // PDF 저장 미리보기 모달
    $("#btn-pdf-close").addEventListener("click", closePdfModal);
    $("#btn-pdf-download").addEventListener("click", downloadPdf);

    // 탭
    $$(".tab").forEach((t) =>
      t.addEventListener("click", () => showView(t.dataset.view))
    );

    // 내역 액션
    $("#record-list").addEventListener("click", (e) => {
      const el = e.target.closest("[data-act]");
      if (!el) return;
      const id = el.dataset.id;
      const rec = store.records().find((r) => r.id === id);
      if (!rec) return;
      const act = el.dataset.act;
      if (act === "open") openPreview(rec);
      else if (act === "pdf") openPdfModal(rec);
      else if (act === "del") {
        confirmDialog("이 점검 내역을 삭제할까요?", {
          okText: "삭제",
          danger: true,
        }).then((yes) => {
          if (!yes) return;
          store.remove(id);
          renderHistory();
          toast("삭제되었습니다.");
        });
      }
    });

    // 설정
    $("#btn-save-settings").addEventListener("click", () => {
      store.saveSettings({
        org: $("#s-org").value.trim(),
        inspector: $("#s-inspector").value.trim(),
      });
      toast("설정이 저장되었습니다.", "ok");
    });
    $("#btn-export-json").addEventListener("click", () => {
      const blob = new Blob([JSON.stringify(store.records(), null, 2)], {
        type: "application/json",
      });
      downloadBlob(blob, "자체점검_백업.json");
    });
    $("#btn-clear-all").addEventListener("click", async () => {
      if (
        !(await confirmDialog("저장된 모든 점검 내역을 삭제합니다. 계속할까요?", {
          okText: "전체 삭제",
          danger: true,
        }))
      )
        return;
      store.saveRecords([]);
      renderHistory();
      toast("전체 삭제되었습니다.");
    });
  }

  function loadSettingsIntoForm() {
    const s = store.settings();
    $("#s-org").value = s.org || "";
    $("#s-inspector").value = s.inspector || "";
    $("#app-version").textContent = "버전 " + APP_VERSION;
  }

  // ---------- 초기화 ----------
  function init() {
    const draft = store.draft();
    current = draft || newRecord();
    bind();
    initSignature();
    fillFormFromCurrent();
    loadSettingsIntoForm();
    renderHistory();

    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.register("sw.js").catch(() => {});
    }
  }

  document.addEventListener("DOMContentLoaded", init);
})();
