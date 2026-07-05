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
      facility: "",
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
    ensureFacilityOption(current.facility);
    $("#f-facility").value = current.facility || "";
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
    current.facility = $("#f-facility").value.trim();
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

  // ---------- 확인/입력 다이얼로그 (샌드박스에서도 동작하는 커스텀 모달) ----------
  function confirmDialog(msg, opts) {
    opts = opts || {};
    return new Promise((resolve) => {
      const d = $("#cdialog");
      $("#cdialog-msg").textContent = msg;
      $("#cdialog-input").hidden = true;
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

  // 텍스트 입력 다이얼로그 → 입력값(문자열) 또는 취소 시 null
  function promptDialog(msg, opts) {
    opts = opts || {};
    return new Promise((resolve) => {
      const d = $("#cdialog");
      $("#cdialog-msg").textContent = msg;
      const input = $("#cdialog-input");
      input.hidden = false;
      input.type = opts.type || "text";
      input.placeholder = opts.placeholder || "";
      input.value = opts.value || "";
      const ok = $("#cdialog-ok");
      const cancel = $("#cdialog-cancel");
      ok.textContent = opts.okText || "확인";
      cancel.textContent = opts.cancelText || "취소";
      ok.classList.remove("btn--danger-solid");
      ok.classList.add("btn--primary");
      d.hidden = false;
      setTimeout(() => input.focus(), 40);
      const close = (val) => {
        d.hidden = true;
        input.hidden = true;
        ok.onclick = null;
        cancel.onclick = null;
        d.onclick = null;
        input.onkeydown = null;
        resolve(val);
      };
      ok.onclick = () => close(input.value.trim() || null);
      cancel.onclick = () => close(null);
      d.onclick = (e) => {
        if (e.target === d) close(null);
      };
      input.onkeydown = (e) => {
        if (e.key === "Enter") close(input.value.trim() || null);
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
    if (!current.facility) return "시설명을 선택하세요.";
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

  // 현재 페이지에 캔버스를 A4 세로 인쇄영역에 맞춰 배치
  function addCanvasToPdf(pdf, canvas) {
    const pw = pdf.internal.pageSize.getWidth(); // 210
    const ph = pdf.internal.pageSize.getHeight(); // 297
    const margin = 8;
    const availW = pw - margin * 2;
    const availH = ph - margin * 2;
    let w = availW;
    let h = (canvas.height / canvas.width) * w;
    if (h > availH) {
      h = availH;
      w = (canvas.width / canvas.height) * h;
    }
    const x = (pw - w) / 2;
    const y = margin;
    pdf.addImage(canvas.toDataURL("image/jpeg", 0.92), "JPEG", x, y, w, h);
  }

  // 원본 별지 제42호서식과 동일한 A4 세로(210㎜×297㎜) 규격 1페이지 PDF
  function pdfFromCanvas(canvas) {
    const { jsPDF } = window.jspdf;
    const pdf = new jsPDF({ orientation: "portrait", unit: "mm", format: "a4" });
    addCanvasToPdf(pdf, canvas);
    return pdf.output("blob");
  }

  // 여러 점검을 한 페이지씩 담은 합본 A4 PDF (첫 페이지 캔버스도 함께 반환)
  async function buildRecordsPdf(records) {
    const { jsPDF } = window.jspdf;
    const pdf = new jsPDF({ orientation: "portrait", unit: "mm", format: "a4" });
    let firstCanvas = null;
    for (let i = 0; i < records.length; i++) {
      if (i > 0) pdf.addPage();
      const canvas = await renderFormCanvas(records[i]);
      if (i === 0) firstCanvas = canvas;
      addCanvasToPdf(pdf, canvas);
    }
    return { blob: pdf.output("blob"), firstCanvas };
  }

  function pdfFilename(record) {
    const d = (record.date || "").replace(/-/g, "");
    const fac = (record.facility || "시설").replace(/[\\/:*?"<>|\s]+/g, "");
    const who = (record.inspector || "점검자").replace(/\s+/g, "");
    return `자체점검대장_${fac}_${d || "날짜"}_${who}.pdf`;
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

  // PDF 미리보기 모달 표시(미리보기 이미지 + 안내 + 다운로드용 blob)
  function presentPdf(blob, filename, previewUrl, note) {
    pdfCtx = { blob, filename };
    $("#pdf-img").src = previewUrl;
    if ($("#pdf-note"))
      $("#pdf-note").innerHTML =
        note || "저장될 <b>별지 제42호서식 · A4 규격 PDF</b> 미리보기입니다.";
    $("#pdf-modal").hidden = false;
    document.body.classList.add("modal-open");
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
      presentPdf(
        blob,
        pdfFilename(record),
        canvas.toDataURL("image/png"),
        "저장될 <b>별지 제42호서식 · A4 규격 PDF</b> 미리보기입니다."
      );
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

  // 같은 날짜의 모든 점검을 합본 PDF로 미리보기(저장)
  async function openBatchPdf(date) {
    const recs = recordsByDate(date);
    if (!recs.length) {
      toast("해당 날짜의 점검 결과가 없습니다.", "warn");
      return;
    }
    const btn = $("#btn-batch-pdf");
    const prev = btn ? btn.textContent : "";
    if (btn) {
      btn.disabled = true;
      btn.textContent = "합본 PDF 생성 중…";
    }
    try {
      const { blob, firstCanvas } = await buildRecordsPdf(recs);
      presentPdf(
        blob,
        batchFilename(date, recs.length),
        firstCanvas.toDataURL("image/png"),
        `<b>${date}</b> 합본 PDF · 총 <b>${recs.length}건</b>(${recs.length}페이지) · 첫 페이지 미리보기`
      );
    } catch (e) {
      console.error(e);
      toast("합본 PDF 생성 중 오류가 발생했습니다.", "warn");
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

  // 기본 메일 앱을 지정 주소로 여는 mailto 실행(페이지 이동 없이 앵커 클릭)
  function openMailto(href) {
    try {
      const a = document.createElement("a");
      a.href = href;
      a.style.display = "none";
      document.body.appendChild(a);
      a.click();
      a.remove();
      return true;
    } catch (e) {
      try {
        window.location.href = href;
        return true;
      } catch (e2) {
        console.error("mailto blocked", e2);
        return false;
      }
    }
  }

  // Blob → base64 문자열(데이터URL 접두어 제거)
  function blobToBase64(blob) {
    return new Promise((resolve, reject) => {
      const r = new FileReader();
      r.onload = () => resolve(String(r.result).split(",")[1] || "");
      r.onerror = reject;
      r.readAsDataURL(blob);
    });
  }

  // Google Apps Script 웹앱으로 PDF 첨부 메일 발송(내 Gmail 계정 발송)
  // Apps Script 응답은 CORS 로 읽을 수 없으므로 no-cors 로 요청만 전달한다.
  async function sendViaGas(gasUrl, payload) {
    const form = new URLSearchParams();
    Object.keys(payload).forEach((k) => form.set(k, payload[k] == null ? "" : payload[k]));
    await fetch(gasUrl, { method: "POST", mode: "no-cors", body: form });
  }

  async function testGmail() {
    const s = store.settings();
    const gasUrl = (s.gasUrl || "").trim();
    if (!gasUrl) {
      toast("먼저 Gmail 발송 웹앱 URL을 저장하세요.", "warn");
      return;
    }
    let to = (s.email || "").trim();
    if (!isEmail(to)) {
      to = await promptDialog("테스트 메일을 받을 이메일을 입력하세요.", {
        type: "email",
        placeholder: "me@example.com",
        okText: "전송",
      });
      if (!isEmail(to || "")) {
        if (to) toast("이메일 형식이 올바르지 않습니다.", "warn");
        return;
      }
    }
    const btn = $("#btn-test-gas");
    const prev = btn.textContent;
    btn.disabled = true;
    btn.textContent = "전송 중…";
    try {
      await sendViaGas(gasUrl, {
        to: to,
        subject: "[자체점검] Gmail 발송 테스트",
        body: "이 메일이 수신되면 Gmail 자동 발송 설정이 정상입니다.",
        filename: "",
        pdf: "",
      });
      toast(`${to} 주소로 테스트 메일을 보냈습니다. 수신함을 확인하세요.`, "ok");
    } catch (e) {
      console.error(e);
      toast("전송 실패: 웹앱 URL/네트워크를 확인하세요.", "warn");
    } finally {
      btn.disabled = false;
      btn.textContent = prev;
    }
  }

  // ---------- 이메일 본문 요약 ----------
  function emailSummary(record) {
    const map = {};
    STATUS_OPTIONS.forEach((o) => (map[o.key] = o.label));
    const lines = [];
    lines.push("유해화학물질 취급시설 자체점검 결과");
    lines.push("(화학물질관리법 시행규칙 별지 제42호서식)");
    lines.push("");
    lines.push(`■ 시설명: ${record.facility || "-"}`);
    lines.push(`■ 점검연월일: ${record.date || "-"}`);
    lines.push(
      `■ 점검시간: ${record.timeStart || "--:--"} ~ ${record.timeEnd || "--:--"}`
    );
    lines.push(`■ 소속: ${record.org || "-"}`);
    lines.push(`■ 점검자: ${record.inspector || "-"}`);
    lines.push("");
    lines.push("[점검 항목 결과]");
    CHECK_ITEMS.forEach((it) => {
      const st = map[record.items[it.no]] || "미점검";
      const rm = record.itemRemarks[it.no] ? ` / 비고: ${record.itemRemarks[it.no]}` : "";
      lines.push(`${it.no} ${st}${rm}`);
    });
    const recheck = CHECK_ITEMS.filter((it) => record.items[it.no] === "recheck");
    lines.push("");
    lines.push(
      recheck.length
        ? `⚠ 정밀 재점검 필요: ${recheck.length}건 (${recheck.map((r) => r.no).join(" ")})`
        : "✔ 정밀 재점검 필요 항목 없음"
    );
    if (record.remark) {
      lines.push("");
      lines.push("[비고]");
      lines.push(record.remark);
    }
    lines.push("");
    lines.push("※ 상세 양식(별지 제42호서식)은 첨부된 A4 PDF를 확인하세요.");
    return lines.join("\n");
  }

  function emailSubject(record) {
    const fac = record.facility ? `[${record.facility}] ` : "";
    return `[자체점검] ${fac}유해화학물질 취급시설 자체점검대장 (${record.date || ""})`;
  }

  // ---------- 날짜별 일괄 ----------
  function recordsByDate(date) {
    return store.records().filter((r) => r.date === date);
  }
  function distinctDates() {
    const seen = [];
    store.records().forEach((r) => {
      const d = r.date || "";
      if (d && seen.indexOf(d) === -1) seen.push(d);
    });
    return seen.sort((a, b) => b.localeCompare(a)); // 최신 날짜 먼저
  }
  function batchFilename(date, count) {
    return `자체점검대장_합본_${(date || "").replace(/-/g, "")}_${count}건.pdf`;
  }
  function batchSubject(date, count) {
    return `[자체점검] 유해화학물질 취급시설 자체점검대장 합본 (${date}, ${count}건)`;
  }
  function batchSummary(date, recs) {
    const lines = [];
    lines.push("유해화학물질 취급시설 자체점검 결과 (합본)");
    lines.push("(화학물질관리법 시행규칙 별지 제42호서식)");
    lines.push("");
    lines.push(`■ 점검연월일: ${date}`);
    lines.push(`■ 점검 건수: ${recs.length}건`);
    lines.push("");
    lines.push("[시설별 결과]");
    recs.forEach((r) => {
      const rc = CHECK_ITEMS.filter((it) => r.items[it.no] === "recheck").length;
      const status = rc ? `⚠ 재점검 ${rc}건` : "✔ 이상없음";
      lines.push(
        `- ${r.facility || "(시설명 미지정)"} / 점검자 ${r.inspector || "-"} / ${status}`
      );
    });
    lines.push("");
    lines.push(`※ 상세 양식은 첨부된 합본 PDF(${recs.length}페이지)를 확인하세요.`);
    return lines.join("\n");
  }

  // 이메일 형식 간단 검증
  function isEmail(s) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(s || "");
  }

  // ---------- 이메일 전송: 저장된(설정) 이메일로 바로 전송 ----------
  async function emailResult() {
    const err = validate();
    if (err) {
      toast(err, "warn");
      return;
    }
    saveCurrent(true);
    await sendEmail(current);
  }

  // 공통 전송기: 준비된 PDF blob 을 Gmail(Apps Script)/공유/mailto 로 발송
  async function deliverEmail(opts) {
    const { blob, filename, subject, body, btn } = opts;
    const settings = store.settings();
    const savedTo = (settings.email || "").trim();
    const gasUrl = (settings.gasUrl || "").trim();

    async function ensureRecipient() {
      let to = savedTo;
      if (isEmail(to)) return to;
      to = await promptDialog("받는 사람 이메일을 입력하세요.", {
        type: "email",
        placeholder: "report@example.com",
        okText: "전송",
      });
      if (!to) return null;
      if (!isEmail(to)) {
        toast("이메일 형식이 올바르지 않습니다.", "warn");
        return null;
      }
      const s = store.settings();
      s.email = to;
      store.saveSettings(s);
      if ($("#s-email")) $("#s-email").value = to;
      return to;
    }

    // 0순위: Gmail 자동 발송(Apps Script) → 내 Google 계정으로 즉시 발송
    if (gasUrl) {
      const to = await ensureRecipient();
      if (!to) return;
      if (btn) btn.textContent = "Gmail 전송 중…";
      const pdfB64 = await blobToBase64(blob);
      await sendViaGas(gasUrl, { to, subject, body, filename, pdf: pdfB64 });
      toast(`${to} 주소로 Gmail 발송했습니다.`, "ok");
      return;
    }

    // 1순위(모바일): PDF 파일을 첨부해 그대로 공유 → 메일 앱에서 바로 전송
    const file = new File([blob], filename, { type: "application/pdf" });
    if (
      navigator.canShare &&
      navigator.canShare({ files: [file] }) &&
      navigator.share
    ) {
      try {
        await navigator.share({
          files: [file],
          title: subject,
          text: (savedTo ? `받는 사람: ${savedTo}\n\n` : "") + body,
        });
        toast("메일 앱을 선택하면 PDF가 첨부된 채로 전송됩니다.", "ok");
        return;
      } catch (e) {
        if (e && e.name === "AbortError") {
          toast("전송이 취소되었습니다.");
          return;
        }
        // 공유 실패 시 아래 폴백으로 진행
      }
    }

    // 2순위(공유 미지원·데스크톱): 저장된 주소로 메일 작성창(mailto) + PDF 내려받기
    const to = await ensureRecipient();
    if (!to) return;
    const dl = downloadBlob(blob, filename);
    const mailto =
      "mailto:" +
      to +
      "?subject=" +
      encodeURIComponent(subject) +
      "&body=" +
      encodeURIComponent(
        body + "\n\n※ 방금 내려받은 PDF 파일(" + filename + ")을 첨부해 주세요."
      );
    const opened = openMailto(mailto);
    toast(
      opened
        ? `${to} 주소로 메일 작성창을 열었습니다. 내려받은 PDF를 첨부 후 보내세요.`
        : dl
        ? "PDF를 내려받았습니다. 메일에 첨부해 주세요."
        : "이 미리보기 환경에서는 전송이 제한됩니다. 배포(HTTPS) 후 이용하세요.",
      opened || dl ? "ok" : "warn"
    );
  }

  // 단일 점검 이메일 전송 (모바일: PDF 첨부 발송)
  async function sendEmail(record) {
    const btn = $("#btn-email");
    const prev = btn ? btn.textContent : "";
    if (btn) {
      btn.disabled = true;
      btn.textContent = "PDF 생성 중…";
    }
    try {
      const canvas = await renderFormCanvas(record);
      const blob = pdfFromCanvas(canvas);
      await deliverEmail({
        blob,
        filename: pdfFilename(record),
        subject: emailSubject(record),
        body: emailSummary(record),
        btn,
      });
    } catch (e) {
      console.error(e);
      toast("전송 준비 중 오류가 발생했습니다.", "warn");
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.textContent = prev;
      }
    }
  }

  // 같은 날짜의 모든 점검을 합본 PDF로 이메일 전송
  async function sendDateEmail(date) {
    const recs = recordsByDate(date);
    if (!recs.length) {
      toast("해당 날짜의 점검 결과가 없습니다.", "warn");
      return;
    }
    const btn = $("#btn-batch-email");
    const prev = btn ? btn.textContent : "";
    if (btn) {
      btn.disabled = true;
      btn.textContent = "합본 PDF 생성 중…";
    }
    try {
      const { blob } = await buildRecordsPdf(recs);
      await deliverEmail({
        blob,
        filename: batchFilename(date, recs.length),
        subject: batchSubject(date, recs.length),
        body: batchSummary(date, recs),
        btn,
      });
    } catch (e) {
      console.error(e);
      toast("전송 준비 중 오류가 발생했습니다.", "warn");
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.textContent = prev;
      }
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

  const NO_FACILITY = "(시설명 미지정)";

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  // 시설명 선택(select) 옵션 구성 — FACILITIES + (레코드에 남은 그 외 시설)
  function buildFacilitySelect() {
    const sel = $("#f-facility");
    if (!sel) return;
    const current = sel.value;
    const extras = [];
    store.records().forEach((r) => {
      const f = (r.facility || "").trim();
      if (f && FACILITIES.indexOf(f) === -1 && extras.indexOf(f) === -1) extras.push(f);
    });
    const opts = ['<option value="" disabled>시설을 선택하세요</option>'];
    FACILITIES.forEach((f) => opts.push(`<option value="${esc(f)}">${esc(f)}</option>`));
    extras.forEach((f) => opts.push(`<option value="${esc(f)}">${esc(f)}</option>`));
    sel.innerHTML = opts.join("");
    sel.value = current || "";
  }

  // 선택지에 없는 시설명(과거 데이터 등)도 표시되도록 옵션 보강
  function ensureFacilityOption(name) {
    const sel = $("#f-facility");
    if (!sel || !name) return;
    const exists = Array.prototype.some.call(sel.options, (o) => o.value === name);
    if (!exists) {
      const o = document.createElement("option");
      o.value = name;
      o.textContent = name;
      sel.appendChild(o);
    }
  }

  const recheckCount = (r) =>
    CHECK_ITEMS.filter((it) => r.items[it.no] === "recheck").length;
  const hasRecheck = (r) => CHECK_ITEMS.some((it) => r.items[it.no] === "recheck");

  function recordItemHtml(r) {
    return `<li class="rec">
        <div class="rec__main" data-act="open" data-id="${r.id}">
          <div class="rec__row">
            <strong>${r.date || "날짜 미상"}</strong>
            ${statusBadge(r)}
          </div>
          <div class="rec__sub">${esc(r.org || "-")} · ${esc(r.inspector || "-")} · ${
    r.timeStart || "--:--"
  }~${r.timeEnd || "--:--"}</div>
        </div>
        <div class="rec__acts">
          <button class="mini" data-act="email" data-id="${r.id}">메일</button>
          <button class="mini" data-act="pdf" data-id="${r.id}">PDF</button>
          <button class="mini mini--danger" data-act="del" data-id="${r.id}">삭제</button>
        </div>
      </li>`;
  }

  const facilityOf = (r) => (r.facility || "").trim() || NO_FACILITY;
  let currentFolder = null; // 상세보기 중인 시설명

  // 날짜별 일괄 카드(날짜 선택 옵션) 갱신 — 데이터가 없어도 카드는 보이고 비활성 처리
  function renderBatchDates() {
    const sel = $("#batch-date");
    if (!sel) return;
    const dates = distinctDates();
    const emailBtn = $("#btn-batch-email");
    const pdfBtn = $("#btn-batch-pdf");
    const empty = dates.length === 0;
    sel.disabled = empty;
    if (emailBtn) emailBtn.disabled = empty;
    if (pdfBtn) pdfBtn.disabled = empty;
    if (empty) {
      sel.innerHTML = '<option value="">저장된 점검이 없습니다</option>';
      return;
    }
    const keep = sel.value;
    sel.innerHTML = dates
      .map((d) => `<option value="${d}">${d} (${recordsByDate(d).length}건)</option>`)
      .join("");
    if (dates.indexOf(keep) !== -1) sel.value = keep;
  }

  // 내역 = 시설별 폴더 그리드
  function renderHistory() {
    currentFolder = null;
    $("#detail-card").hidden = true;
    $("#folders-card").hidden = false;
    $("#batch-card").hidden = false;
    renderBatchDates();

    const list = store.records();
    $("#history-count").textContent = list.length + "건";

    // 시설별 개수 집계
    const counts = {};
    list.forEach((r) => {
      const f = facilityOf(r);
      counts[f] = (counts[f] || 0) + 1;
    });
    // 폴더 순서: 정의된 시설 → 그 외(미지정 포함)
    const extras = Object.keys(counts)
      .filter((f) => FACILITIES.indexOf(f) === -1)
      .sort((a, b) => (a === NO_FACILITY ? 1 : b === NO_FACILITY ? -1 : a.localeCompare(b, "ko")));
    const folders = FACILITIES.concat(extras);

    $("#folder-grid").innerHTML = folders
      .map((f) => {
        const recs = list.filter((r) => facilityOf(r) === f);
        const rc = recs.reduce((n, r) => n + (hasRecheck(r) ? 1 : 0), 0);
        const cls = recs.length ? "folder folder--has" : "folder folder--empty";
        const warn = rc ? `<span class="folder__warn">재점검 ${rc}</span>` : "";
        return `<button type="button" class="${cls}" data-facility="${esc(f)}">
            <div class="folder__top">
              <span class="folder__ico">${recs.length ? "📁" : "📂"}</span>
              <span class="folder__count">${recs.length}건</span>
            </div>
            <span class="folder__name">${esc(f)}</span>
            ${warn}
          </button>`;
      })
      .join("");
  }

  // 특정 시설 폴더 열기 → 해당 시설 점검 결과 목록
  function openFacility(name) {
    currentFolder = name;
    const recs = store.records().filter((r) => facilityOf(r) === name);
    $("#detail-title").textContent = "🏭 " + name;
    $("#record-list").innerHTML = recs.map(recordItemHtml).join("");
    $("#detail-empty").hidden = recs.length > 0;
    $("#folders-card").hidden = true;
    $("#batch-card").hidden = true;
    $("#detail-card").hidden = false;
    window.scrollTo(0, 0);
  }

  function backToFolders() {
    renderHistory();
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
    [
      "#f-facility",
      "#f-date",
      "#f-time-start",
      "#f-time-end",
      "#f-org",
      "#f-inspector",
      "#f-remark",
    ].forEach((id) => $(id).addEventListener("input", saveDraftSoon));

    $("#btn-save").addEventListener("click", async () => {
      const err = validate();
      if (err && !(await confirmDialog(err + "\n그래도 저장하시겠습니까?"))) return;
      saveCurrent();
    });
    $("#btn-email").addEventListener("click", emailResult);
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

    // 시설 폴더 열기 / 뒤로가기
    $("#folder-grid").addEventListener("click", (e) => {
      const f = e.target.closest("[data-facility]");
      if (f) openFacility(f.dataset.facility);
    });
    $("#btn-folder-back").addEventListener("click", backToFolders);

    // 날짜별 일괄 추출·전송
    $("#btn-batch-pdf").addEventListener("click", () => {
      const d = $("#batch-date").value;
      if (d) openBatchPdf(d);
    });
    $("#btn-batch-email").addEventListener("click", () => {
      const d = $("#batch-date").value;
      if (d) sendDateEmail(d);
    });

    // 내역(시설 상세) 액션
    $("#record-list").addEventListener("click", (e) => {
      const el = e.target.closest("[data-act]");
      if (!el) return;
      const id = el.dataset.id;
      const rec = store.records().find((r) => r.id === id);
      if (!rec) return;
      const act = el.dataset.act;
      if (act === "open") openPreview(rec);
      else if (act === "email") sendEmail(rec);
      else if (act === "pdf") openPdfModal(rec);
      else if (act === "del") {
        confirmDialog("이 점검 내역을 삭제할까요?", {
          okText: "삭제",
          danger: true,
        }).then((yes) => {
          if (!yes) return;
          store.remove(id);
          // 상세보기 중이면 해당 폴더 갱신, 아니면 폴더 목록 갱신
          if (currentFolder) openFacility(currentFolder);
          else renderHistory();
          toast("삭제되었습니다.");
        });
      }
    });

    // 설정 (기존 값 보존하며 병합 저장)
    $("#btn-save-settings").addEventListener("click", () => {
      const s = store.settings();
      s.email = $("#s-email").value.trim();
      s.org = $("#s-org").value.trim();
      s.inspector = $("#s-inspector").value.trim();
      store.saveSettings(s);
      toast("설정이 저장되었습니다.", "ok");
    });
    // Gmail(Apps Script) 발송 URL 저장
    $("#btn-save-gas").addEventListener("click", () => {
      const url = $("#s-gas").value.trim();
      if (url && !/^https:\/\/script\.google\.com\/.*\/exec$/.test(url)) {
        toast("Apps Script 웹앱 URL(.../exec)을 확인하세요.", "warn");
        return;
      }
      const s = store.settings();
      s.gasUrl = url;
      store.saveSettings(s);
      toast(url ? "Gmail 자동 발송이 설정되었습니다." : "Gmail 자동 발송을 해제했습니다.", "ok");
    });
    // Gmail 테스트 메일
    $("#btn-test-gas").addEventListener("click", testGmail);
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
    $("#s-email").value = s.email || "";
    $("#s-org").value = s.org || "";
    $("#s-inspector").value = s.inspector || "";
    $("#s-gas").value = s.gasUrl || "";
    $("#app-version").textContent = "버전 " + APP_VERSION;
  }

  // ---------- 초기화 ----------
  function init() {
    const draft = store.draft();
    current = draft || newRecord();
    bind();
    initSignature();
    buildFacilitySelect();
    fillFormFromCurrent();
    loadSettingsIntoForm();
    renderHistory();

    if ("serviceWorker" in navigator) {
      // 새 버전이 활성화되면 한 번만 새로고침해 최신 코드를 반영
      let refreshing = false;
      navigator.serviceWorker.addEventListener("controllerchange", () => {
        if (refreshing) return;
        refreshing = true;
        location.reload();
      });
      navigator.serviceWorker
        .register("sw.js")
        .then((reg) => {
          reg.update();
          // 대기 중인 새 워커가 있으면 즉시 적용 요청
          if (reg.waiting) reg.waiting.postMessage("skipWaiting");
          reg.addEventListener("updatefound", () => {
            const nw = reg.installing;
            if (!nw) return;
            nw.addEventListener("statechange", () => {
              if (nw.state === "installed" && navigator.serviceWorker.controller) {
                nw.postMessage("skipWaiting");
              }
            });
          });
        })
        .catch(() => {});
    }
  }

  document.addEventListener("DOMContentLoaded", init);
})();
