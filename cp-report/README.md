# 방식전위측정 보고서 앱

방식전위(Cathodic Protection Potential) 측정 결과를 현장에서 기록하고 **A4 보고서로 출력**하는 웹앱입니다.
설치 없이 브라우저에서 바로 사용하며, 스마트폰·태블릿·PC 모두 지원합니다.

## 주요 기능

- 📷 **측정지 사진 촬영/첨부** — 측정 지점마다 측정표(측정지) 사진을 카메라로 촬영하거나 갤러리에서 선택
- 📍 **측정 지점 선택** — NO.1 ~ NO.10, G/S1, G/S2 중 드롭다운으로 선택
- ✍️ **측정 평균값 입력** — 지점별 평균 전위값(mV) 입력
- ✅ **자동 판정** — 판정 기준값(−850 mV 고정) 대비 합격/부적합 자동 표시 및 종합 판정
- 🔢 **지점 순서 자동 정렬** — 보고서의 측정 결과·측정지 사진이 NO.1 → NO.10 → G/S1 → G/S2 순서로 자동 정렬
- 📄 **A4 보고서 출력** — 측정일자 + 측정 결과표 + 측정지 사진 첨부 페이지를 A4 규격으로 인쇄 / PDF 저장
- 📧 **이메일 바로 전송** — 앱에서 받는사람 주소를 입력하면 사진이 포함된 보고서가 그 주소로 바로 발송 (본인 Gmail 연동, 최초 1회 설정)
- 💾 **자동 저장** — 입력 내용이 브라우저에 저장되어 앱을 닫아도 유지됨

## 사용 방법

1. `index.html` 을 브라우저에서 엽니다. (더블클릭 또는 모바일에서 파일 열기)
2. **① 측정 정보 · 판정 기준**에서 측정일자를 입력합니다. (방식 방법 = 외부전원법, 판정 기준값 = −850 mV 고정)
3. **② 측정 지점**에서 지점을 추가하고, 측정 지점(NO.1~NO.10 / G/S1 / G/S2)을 선택한 뒤 측정 평균값(mV)을 입력하고 측정지 사진을 촬영/첨부합니다.
4. 하단 **`A4 보고서 출력 →`** 버튼을 눌러 미리보기 후 출력/전송합니다.
   - **`🖨 인쇄 / PDF`** — 인쇄하거나, 인쇄 대화상자에서 프린터를 **"PDF로 저장"** 으로 선택해 PDF 저장
   - **`📧 이메일 전송`** — 받는사람 주소를 입력하고 **보내기**를 누르면 사진이 포함된 보고서가 그 주소로 바로 발송됩니다. (최초 1회 발신 설정 필요 — 아래 참고)

## 이메일 전송 설정 (최초 1회, 무료)

서버가 없는 단일 HTML 앱이므로, 입력한 주소로 메일을 **직접 발송**하려면 본인 Gmail로 보내는 Google Apps Script 웹앱을 한 번만 배포하면 됩니다. (앱의 `📧 이메일 전송 → ⚙ 발신 설정`에도 동일한 코드/안내가 들어 있습니다.)

1. [script.google.com](https://script.google.com/home/projects/create) 접속 → **새 프로젝트**
2. 기본 코드를 지우고 아래 코드를 붙여넣기 → 저장
3. **배포 → 새 배포 → 유형: 웹 앱**
4. 실행 계정 **나**, 액세스 권한 **모든 사용자** → **배포**
5. 최초 1회 권한 승인(Gmail 전송) 후 생성된 **웹 앱 URL(.../exec)** 복사
6. 앱의 발신 설정 칸에 그 URL을 붙여넣기 (이 기기에 저장되어 이후에는 받는사람만 입력하면 됨)

```javascript
function doPost(e) {
  try {
    var d = JSON.parse(e.postData.contents);
    var opts = { name: '방식전위측정 보고서' };
    if (d.cc) opts.cc = d.cc;
    if (d.htmlBase64) {
      var bytes = Utilities.base64Decode(d.htmlBase64);
      opts.attachments = [
        Utilities.newBlob(bytes, 'text/html', d.filename || 'report.html')
      ];
    }
    GmailApp.sendEmail(d.to, d.subject || '방식전위 측정 보고서', d.body || '', opts);
    return ContentService.createTextOutput(JSON.stringify({ ok: true }))
      .setMimeType(ContentService.MimeType.JSON);
  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({ ok: false, error: String(err) }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}
```

> 보고서는 본인 Gmail 계정에서 발송되며, 받는사람에게 사진이 포함된 `.html` 보고서가 첨부됩니다.

## 판정 기준

- 측정값이 판정 기준값(**−850 mV 고정**)보다 **더 음(−)의 값**이면 **합격**(방식 상태 양호)으로 판정합니다.
  - 예) 기준 −850 mV, 측정 −1050 mV → 합격

## 기술

- 단일 HTML 파일 (외부 의존성·서버 없음), 오프라인 동작
- 사진은 업로드 시 자동으로 리사이즈/압축하여 저장 용량을 최소화
- 데이터는 브라우저 `localStorage` 에만 저장됩니다 (기기 외부로 전송되지 않음)

> 참고: 종합 판정은 입력값 기준의 참고용이며, 최종 판정은 관련 기준·규정에 따라 담당자가 확인하시기 바랍니다.
