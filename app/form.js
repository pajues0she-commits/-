/*
 * 양식 렌더러 — 저장된 점검 결과를 별지 제42호서식과 동일한 레이아웃으로 생성.
 * 미리보기 · 인쇄 · PDF(이메일 첨부) 모두 이 DOM을 사용한다.
 */

function escapeHtml(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function fmtDate(iso) {
  if (!iso) return "";
  const [y, m, d] = iso.split("-");
  if (!y) return iso;
  return `${y}. ${m}. ${d}.`;
}

function fmtTimeRange(start, end) {
  if (!start && !end) return "(&nbsp;&nbsp;:&nbsp;&nbsp; ~ &nbsp;&nbsp;:&nbsp;&nbsp;)";
  return `(${escapeHtml(start || "  :  ")} ~ ${escapeHtml(end || "  :  ")})`;
}

// 이상 유무 3개 선택지 셀
function statusCellHtml(selectedKey) {
  return STATUS_OPTIONS.map((opt) => {
    const mark = opt.key === selectedKey ? "✔" : "&nbsp;&nbsp;";
    return `<div class="gf-opt"><span class="gf-box">[${mark}]</span> ${escapeHtml(
      opt.label
    )}</div>`;
  }).join("");
}

/**
 * record → 양식 DOM element
 * record = { date, timeStart, timeEnd, org, inspector, signature, remark, items:{ [no]: statusKey } , itemRemarks:{[no]:text} }
 */
function buildFormElement(record) {
  const r = record || {};
  const items = r.items || {};
  const itemRemarks = r.itemRemarks || {};

  const rows = CHECK_ITEMS.map((it) => {
    return `
      <tr>
        <td class="gf-item">
          <span class="gf-no">${it.no}</span>
          <span class="gf-item-text">${escapeHtml(it.text)}</span>
        </td>
        <td class="gf-status">${statusCellHtml(items[it.no])}</td>
        <td class="gf-remark-cell">${escapeHtml(itemRemarks[it.no] || "")}</td>
      </tr>`;
  }).join("");

  const signCell = r.signature
    ? `<img class="gf-sign-img" src="${r.signature}" alt="서명" />`
    : "";

  const notesHtml = REMARK_NOTES.map(
    (n, i) => `<div class="gf-note">${i + 1}. ${escapeHtml(n)}</div>`
  ).join("");

  const userRemark = r.remark
    ? `<div class="gf-user-remark">${escapeHtml(r.remark).replace(/\n/g, "<br>")}</div>`
    : "";

  const el = document.createElement("div");
  el.className = "gov-form";
  el.innerHTML = `
    <div class="gf-law">${escapeHtml(FORM_META.lawText)}</div>
    <h1 class="gf-title">유해화학물질취급시설 자체점검대장${
      r.facility ? `<span class="gf-title-sub">${escapeHtml(r.facility)}</span>` : ""
    }</h1>

    <table class="gf-head">
      <colgroup>
        <col style="width:18%" />
        <col style="width:22%" />
        <col style="width:20%" />
        <col style="width:20%" />
        <col style="width:20%" />
      </colgroup>
      <tr>
        <th>점검연월일</th>
        <th>점검시간<br>(00:00 ~ 00:00)</th>
        <th>소속</th>
        <th>점검자성명</th>
        <th>서명</th>
      </tr>
      <tr>
        <td>${fmtDate(r.date)}</td>
        <td>${fmtTimeRange(r.timeStart, r.timeEnd)}</td>
        <td>${escapeHtml(r.org || "")}</td>
        <td>${escapeHtml(r.inspector || "")}</td>
        <td class="gf-sign-cell">${signCell}</td>
      </tr>
    </table>

    <table class="gf-main">
      <colgroup>
        <col style="width:56%" />
        <col style="width:26%" />
        <col style="width:18%" />
      </colgroup>
      <thead>
        <tr>
          <th>점검 항목</th>
          <th>이상 유무</th>
          <th>비고</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>

    <div class="gf-notes-wrap">
      <div class="gf-notes-title">비고</div>
      ${userRemark}
      ${notesHtml}
    </div>

    <div class="gf-paper">${escapeHtml(FORM_META.paper)}</div>
  `;
  return el;
}
