// 외부 라이브러리 없이 SVG로 그리는 라인 차트
// points: [{x: Date문자열, y: 숫자}], options: {band:[min,max], unit, color, ideal}

function renderLineChart(container, points, options = {}) {
  const {
    band = null, // [min,max] 표준 범위 밴드
    unit = "",
    color = "#6366f1",
    ideal = null, // 이상 기준선
    height = 220,
  } = options;

  container.innerHTML = "";

  const valid = points.filter((p) => p.y != null && !isNaN(p.y));
  if (valid.length === 0) {
    container.innerHTML =
      '<div class="chart-empty">기록이 없어요. 수치를 입력하면 추이가 표시됩니다.</div>';
    return;
  }

  const W = container.clientWidth || 600;
  const H = height;
  const pad = { top: 16, right: 16, bottom: 28, left: 40 };
  const innerW = W - pad.left - pad.right;
  const innerH = H - pad.top - pad.bottom;

  const ys = valid.map((p) => p.y);
  let minY = Math.min(...ys);
  let maxY = Math.max(...ys);
  if (band) {
    minY = Math.min(minY, band[0]);
    maxY = Math.max(maxY, band[1]);
  }
  if (ideal != null) {
    minY = Math.min(minY, ideal);
    maxY = Math.max(maxY, ideal);
  }
  // 여백
  const span = maxY - minY || 1;
  minY -= span * 0.1;
  maxY += span * 0.1;

  const n = valid.length;
  const xFor = (i) => pad.left + (n === 1 ? innerW / 2 : (innerW * i) / (n - 1));
  const yFor = (v) => pad.top + innerH - ((v - minY) / (maxY - minY)) * innerH;

  const svgNS = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(svgNS, "svg");
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.setAttribute("width", "100%");
  svg.setAttribute("height", H);
  svg.classList.add("chart-svg");

  const el = (tag, attrs) => {
    const e = document.createElementNS(svgNS, tag);
    for (const k in attrs) e.setAttribute(k, attrs[k]);
    return e;
  };

  // Y축 그리드 & 라벨
  const ticks = 4;
  for (let t = 0; t <= ticks; t++) {
    const v = minY + ((maxY - minY) * t) / ticks;
    const y = yFor(v);
    svg.appendChild(
      el("line", {
        x1: pad.left,
        y1: y,
        x2: W - pad.right,
        y2: y,
        class: "chart-grid",
      })
    );
    const label = el("text", {
      x: pad.left - 6,
      y: y + 4,
      class: "chart-axis-label",
      "text-anchor": "end",
    });
    label.textContent = v.toFixed(1);
    svg.appendChild(label);
  }

  // 표준 범위 밴드
  if (band) {
    const yTop = yFor(band[1]);
    const yBot = yFor(band[0]);
    svg.appendChild(
      el("rect", {
        x: pad.left,
        y: yTop,
        width: innerW,
        height: Math.max(0, yBot - yTop),
        class: "chart-band",
      })
    );
  }

  // 이상 기준선
  if (ideal != null) {
    const y = yFor(ideal);
    svg.appendChild(
      el("line", {
        x1: pad.left,
        y1: y,
        x2: W - pad.right,
        y2: y,
        class: "chart-ideal",
      })
    );
  }

  // 라인 경로
  let d = "";
  valid.forEach((p, i) => {
    d += (i === 0 ? "M" : "L") + xFor(i) + " " + yFor(p.y);
  });
  svg.appendChild(el("path", { d, class: "chart-line", stroke: color }));

  // 면적 채우기
  let area = d + `L${xFor(n - 1)} ${pad.top + innerH} L${xFor(0)} ${pad.top + innerH} Z`;
  const areaEl = el("path", { d: area, class: "chart-area", fill: color });
  areaEl.setAttribute("opacity", "0.08");
  svg.appendChild(areaEl);

  // 데이터 포인트 & X 라벨
  valid.forEach((p, i) => {
    const cx = xFor(i);
    const cy = yFor(p.y);
    const dot = el("circle", { cx, cy, r: 3.5, class: "chart-dot", fill: color });
    const title = el("title", {});
    title.textContent = `${p.x} · ${p.y}${unit}`;
    dot.appendChild(title);
    svg.appendChild(dot);

    // 처음/중간/끝만 X 라벨 표시(과밀 방지)
    if (i === 0 || i === n - 1 || (n > 2 && i === Math.floor((n - 1) / 2))) {
      const tx = el("text", {
        x: cx,
        y: H - 8,
        class: "chart-axis-label",
        "text-anchor": i === 0 ? "start" : i === n - 1 ? "end" : "middle",
      });
      tx.textContent = shortDate(p.x);
      svg.appendChild(tx);
    }
  });

  container.appendChild(svg);
}

function shortDate(iso) {
  // YYYY-MM-DD -> MM/DD
  const parts = iso.split("-");
  if (parts.length === 3) return `${parts[1]}/${parts[2]}`;
  return iso;
}
