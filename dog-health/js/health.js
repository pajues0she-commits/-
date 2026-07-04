// 건강 지표 계산 로직

// 비만도(%) = 현재 체중 / 견종 표준 체중 중앙값 * 100
// 100% = 이상 체중, 그 이상이면 과체중/비만 경향
function obesityPercent(weight, breed) {
  const ideal = breedIdealWeight(breed);
  if (!ideal) return null;
  return (weight / ideal) * 100;
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

// 목표 체중 범위 기반 조언 문구
function weightAdvice(pct, breed) {
  const grade = obesityGrade(pct);
  const ideal = breedIdealWeight(breed);
  switch (grade.level) {
    case "under":
      return `표준보다 가벼운 편이에요. 사료량과 영양 상태를 점검하고 필요 시 수의사와 상담하세요. (권장 ${breed.weight[0]}~${breed.weight[1]}kg)`;
    case "normal":
      return `이상적인 체중 범위예요. 지금의 식사·운동 습관을 유지하세요. (권장 ${breed.weight[0]}~${breed.weight[1]}kg)`;
    case "over":
      return `약간 과체중이에요. 간식을 줄이고 산책량을 늘려 ${ideal.toFixed(1)}kg 근처를 목표로 하세요.`;
    case "obese":
      return `비만 단계예요. 관절·심장 부담이 커질 수 있으니 식단 관리와 수의사 상담을 권장합니다. 목표 체중 ${ideal.toFixed(1)}kg.`;
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
