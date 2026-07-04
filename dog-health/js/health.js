// 건강 지표 계산 로직

// 체격(프레임) 비율 — 이 아이가 견종 표준 체고 범위에서 어디에 위치하는지
// 0 = 하한(작은 체격), 1 = 상한(큰 체격).
// 체고(어깨높이)는 골격 지표라 살이 쪄도 변하지 않으므로 체격 판단에 적합합니다.
// (몸통 둘레는 살이 찌면 함께 늘어 프레임 판단에는 쓰지 않습니다.)
function frameRatio(record, breed) {
  if (!record || record.height == null || isNaN(record.height)) return null;
  const [hMin, hMax] = breed.height;
  if (hMax <= hMin) return null;
  const r = (record.height - hMin) / (hMax - hMin);
  // 표준 범위를 약간 벗어난 체격도 반영하되 과도한 외삽은 제한
  return Math.max(-0.3, Math.min(1.3, r));
}

// 체격 보정 이상 체중(kg)
// 체고가 기록돼 있으면 프레임 위치에 맞춰 표준 체중 범위 안에서 이상 체중을 보정하고,
// 체고가 없으면 견종 표준 체중의 중앙값을 사용합니다.
function idealWeight(record, breed) {
  const r = frameRatio(record, breed);
  if (r == null) return breedIdealWeight(breed);
  return breed.weight[0] + r * (breed.weight[1] - breed.weight[0]);
}

// 체격 분류 라벨 (같은 견종 내 상대적 골격)
function frameLabel(record, breed) {
  const r = frameRatio(record, breed);
  if (r == null) return null;
  if (r < 0.34) return "작은 체격";
  if (r <= 0.66) return "보통 체격";
  return "큰 체격";
}

// 비만도(%) = 현재 체중 / 체격 보정 이상 체중 * 100
// 100% = 이 아이의 체격에 맞는 이상 체중, 그 이상이면 과체중/비만 경향
// record: {weight, height?} 형태의 측정 기록 객체
function obesityPercent(record, breed) {
  if (!record || record.weight == null || isNaN(record.weight)) return null;
  const ideal = idealWeight(record, breed);
  if (!ideal) return null;
  return (record.weight / ideal) * 100;
}

// 비만도 등급 판정
// 임상적으로 이상 체중 대비 +15% 과체중, +30% 비만으로 봅니다.
function obesityGrade(pct) {
  if (pct == null) return { label: "-", level: "none", color: "#94a3b8" };
  if (pct < 85) return { label: "저체중", level: "under", color: "#38bdf8" };
  if (pct <= 115) return { label: "정상", level: "normal", color: "#22c55e" };
  if (pct <= 130) return { label: "과체중", level: "over", color: "#f59e0b" };
  return { label: "비만", level: "obese", color: "#ef4444" };
}

// 체중이 견종 표준 범위 내인지
function weightRangeStatus(weight, breed) {
  const [min, max] = breed.weight;
  if (weight < min) return "below";
  if (weight > max) return "above";
  return "in";
}

// Body Condition Score(BCS 9단계) 근사 추정 — 비만도 기반 참고값
function estimateBCS(pct) {
  if (pct == null) return null;
  if (pct < 85) return 3;
  if (pct <= 100) return 4;
  if (pct <= 115) return 5;
  if (pct <= 125) return 6;
  if (pct <= 135) return 7;
  if (pct <= 145) return 8;
  return 9;
}

// 두 기록 사이의 변화량과 방향
function delta(current, previous) {
  if (current == null || previous == null) return null;
  return current - previous;
}

// 목표 체중 기반 조언 문구 — ideal은 체격 보정 이상 체중(kg)
function weightAdvice(pct, breed, ideal) {
  const grade = obesityGrade(pct);
  const target = ideal != null ? ideal : breedIdealWeight(breed);
  switch (grade.level) {
    case "under":
      return `체격에 견주면 가벼운 편이에요. 사료량과 영양 상태를 점검하고 필요 시 수의사와 상담하세요. (체격 기준 목표 ${target.toFixed(1)}kg)`;
    case "normal":
      return `체격에 딱 맞는 이상적인 체중이에요. 지금의 식사·운동 습관을 유지하세요. (체격 기준 목표 ${target.toFixed(1)}kg)`;
    case "over":
      return `약간 과체중이에요. 간식을 줄이고 산책량을 늘려 ${target.toFixed(1)}kg 근처를 목표로 하세요.`;
    case "obese":
      return `비만 단계예요. 관절·심장 부담이 커질 수 있으니 식단 관리와 수의사 상담을 권장합니다. 체격 기준 목표 체중 ${target.toFixed(1)}kg.`;
    default:
      return "체중을 기록하면 맞춤 조언을 볼 수 있어요.";
  }
}

// 나이 계산 (개월/년)
function ageFromBirth(birthStr, refDate) {
  if (!birthStr) return null;
  const birth = new Date(birthStr);
  const ref = refDate ? new Date(refDate) : new Date();
  if (isNaN(birth)) return null;
  let months =
    (ref.getFullYear() - birth.getFullYear()) * 12 +
    (ref.getMonth() - birth.getMonth());
  if (ref.getDate() < birth.getDate()) months -= 1;
  if (months < 0) months = 0;
  const years = Math.floor(months / 12);
  const rem = months % 12;
  if (years === 0) return `${rem}개월`;
  if (rem === 0) return `${years}살`;
  return `${years}살 ${rem}개월`;
}
