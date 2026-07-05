/* ============================================================
 * charts.js — 의존성 없는 SVG 라인 차트 렌더러
 * 외부 라이브러리/CDN 없이 오프라인 동작.
 * ============================================================ */
(function (global) {
  'use strict';

  var NS = 'http://www.w3.org/2000/svg';

  function el(name, attrs) {
    var e = document.createElementNS(NS, name);
    if (attrs) for (var k in attrs) e.setAttribute(k, attrs[k]);
    return e;
  }

  /**
   * 라인 차트 SVG 생성
   * @param points [{date, value}]  (과거→최신 정렬 가정)
   * @param opts { color, unit, height }
   * @returns SVGElement
   */
  function line(points, opts) {
    opts = opts || {};
    var color = opts.color || '#4f7cff';
    var unit = opts.unit || '';
    var W = 320, H = opts.height || 150;
    var padL = 34, padR = 14, padT = 14, padB = 24;
    var iw = W - padL - padR, ih = H - padT - padB;

    var svg = el('svg', { viewBox: '0 0 ' + W + ' ' + H, preserveAspectRatio: 'none', role: 'img' });

    if (!points || points.length === 0) return svg;

    var vals = points.map(function (p) { return p.value; });
    var min = Math.min.apply(null, vals);
    var max = Math.max.apply(null, vals);
    if (min === max) { min = min - 1; max = max + 1; }
    // 여백
    var range = max - min;
    min = min - range * 0.12;
    max = max + range * 0.12;

    function x(i) {
      if (points.length === 1) return padL + iw / 2;
      return padL + (i / (points.length - 1)) * iw;
    }
    function y(v) {
      return padT + (1 - (v - min) / (max - min)) * ih;
    }

    // 가로 그리드 + y라벨 (3줄)
    for (var g = 0; g <= 2; g++) {
      var gv = min + (max - min) * (g / 2);
      var gy = y(gv);
      svg.appendChild(el('line', { x1: padL, y1: gy, x2: W - padR, y2: gy, class: 'grid-line' }));
      var t = el('text', { x: 4, y: gy + 3, class: 'axis-label' });
      t.textContent = fmt(gv);
      svg.appendChild(t);
    }

    // 라인 path
    var dLine = '', dArea = '';
    points.forEach(function (p, i) {
      var px = x(i), py = y(p.value);
      dLine += (i === 0 ? 'M' : 'L') + px.toFixed(1) + ' ' + py.toFixed(1) + ' ';
    });
    dArea = dLine + 'L' + x(points.length - 1).toFixed(1) + ' ' + (padT + ih) + ' L' + x(0).toFixed(1) + ' ' + (padT + ih) + ' Z';

    svg.appendChild(el('path', { d: dArea, class: 'area', fill: color }));
    svg.appendChild(el('path', { d: dLine, class: 'line-path', stroke: color }));

    // 점 + 최신값 강조
    points.forEach(function (p, i) {
      var last = i === points.length - 1;
      svg.appendChild(el('circle', {
        cx: x(i), cy: y(p.value), r: last ? 4.5 : 3, class: 'dot', fill: color
      }));
    });

    // x 라벨: 처음/중간/끝
    var idxs = points.length <= 1 ? [0] :
      points.length === 2 ? [0, points.length - 1] :
      [0, Math.floor((points.length - 1) / 2), points.length - 1];
    idxs.forEach(function (i) {
      var t = el('text', { x: x(i), y: H - 6, class: 'axis-label', 'text-anchor': i === 0 ? 'start' : (i === points.length - 1 ? 'end' : 'middle') });
      t.textContent = shortDate(points[i].date);
      svg.appendChild(t);
    });

    return svg;
  }

  function fmt(v) {
    if (Math.abs(v) >= 100) return Math.round(v).toString();
    return (Math.round(v * 10) / 10).toString();
  }
  function shortDate(d) {
    // 'YYYY-MM-DD' -> 'M/D'
    var p = (d || '').split('-');
    if (p.length < 3) return d || '';
    return parseInt(p[1], 10) + '/' + parseInt(p[2], 10);
  }

  /** 차트 카드(제목 + 최신값 + 그래프) DOM 생성 */
  function card(title, points, opts) {
    opts = opts || {};
    var wrap = document.createElement('div');
    wrap.className = 'chart-card';
    var head = document.createElement('div');
    head.className = 'cc-head';
    var t = document.createElement('span'); t.className = 'cc-title'; t.textContent = title;
    var latest = document.createElement('span'); latest.className = 'cc-latest';
    if (points && points.length) {
      latest.textContent = fmt(points[points.length - 1].value) + (opts.unit ? ' ' + opts.unit : '');
      latest.style.color = opts.color || '#eef1f6';
    }
    head.appendChild(t); head.appendChild(latest);
    wrap.appendChild(head);
    wrap.appendChild(line(points, opts));
    return wrap;
  }

  global.Charts = { line: line, card: card };
})(window);
