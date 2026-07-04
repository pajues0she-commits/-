/**
 * 유해화학물질 자체점검 앱 — Gmail 자동 발송용 Google Apps Script
 *
 * 이 스크립트를 웹앱으로 배포하면, 앱에서 보낸 점검 PDF를
 * 내 Google(Gmail) 계정으로 수신자에게 자동 발송합니다.
 *
 * 배포 방법은 GMAIL_설정방법.md 를 참고하세요.
 */
function doPost(e) {
  try {
    var p = (e && e.parameter) || {};
    var to = (p.to || "").trim();
    if (!to) throw new Error("받는 사람(to)이 없습니다.");

    var subject = p.subject || "유해화학물질 자체점검 결과";
    var body = p.body || "";
    var options = {};

    // PDF 첨부(base64)가 있으면 첨부
    if (p.pdf) {
      var bytes = Utilities.base64Decode(p.pdf);
      var filename = p.filename || "자체점검대장.pdf";
      var blob = Utilities.newBlob(bytes, "application/pdf", filename);
      options.attachments = [blob];
    }

    GmailApp.sendEmail(to, subject, body, options);
    return json({ ok: true });
  } catch (err) {
    return json({ ok: false, error: String(err) });
  }
}

// 배포 상태 확인용(브라우저로 URL 열었을 때)
function doGet() {
  return json({ ok: true, service: "chem-selfcheck-mailer" });
}

function json(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(
    ContentService.MimeType.JSON
  );
}
