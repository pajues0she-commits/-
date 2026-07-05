/* 서비스 워커 — 네트워크 우선(최신 코드 자동 반영) + 오프라인 캐시 폴백 */
const CACHE = "chk-selfcheck-v3";
const ASSETS = [
  "./",
  "./index.html",
  "./styles.css",
  "./data.js",
  "./form.js",
  "./app.js",
  "./manifest.webmanifest",
  "./vendor/jspdf.umd.min.js",
  "./vendor/html2canvas.min.js",
  "./icons/icon-192.png",
  "./icons/icon-512.png",
];

self.addEventListener("install", (e) => {
  // 새 버전을 즉시 대기 없이 활성화
  e.waitUntil(
    caches
      .open(CACHE)
      .then((c) => c.addAll(ASSETS))
      .catch(() => {})
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (e) => {
  // 이전 버전 캐시 삭제 후 즉시 모든 탭 제어
  e.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
      )
      .then(() => self.clients.claim())
  );
});

self.addEventListener("message", (e) => {
  if (e.data === "skipWaiting") self.skipWaiting();
});

// 동일 출처 GET 요청은 "네트워크 우선": 온라인이면 항상 최신본을 받고,
// 실패(오프라인) 시에만 캐시로 폴백한다. 배포 후 새 코드가 즉시 반영된다.
self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return; // 외부 요청(예: Apps Script)은 그대로

  e.respondWith(
    fetch(req)
      .then((res) => {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(req, copy)).catch(() => {});
        return res;
      })
      .catch(() =>
        caches.match(req).then((hit) => hit || caches.match("./index.html"))
      )
  );
});
