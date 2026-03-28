export interface Preset {
  id: string;
  label: string;
  query: string;
  tools: string[]; // 기대 도구 힌트
  storyId: string; // ANSWER_SHEET 매핑
}

export interface PresetCategory {
  id: string;
  label: string;
  presets: Preset[];
}

export const INTELLIGENCE_PRESETS: PresetCategory[] = [
  {
    id: "trend",
    label: "트렌드",
    presets: [
      {
        id: "s01",
        label: "JP 비건 선크림 상승",
        query: "최근 6개월간 일본 선크림 시장에서 주목할 만한 트렌드가 있나요?",
        tools: ["order"],
        storyId: "S-01",
      },
      {
        id: "s02",
        label: "JP 톤업 선크림 하락",
        query: "일본에서 톤업 선크림의 인기가 어떻게 변하고 있나요?",
        tools: ["order"],
        storyId: "S-02",
      },
      {
        id: "s03",
        label: "SG 워터프루프 일관",
        query: "싱가포르에서 선크림을 판매하려면 어떤 속성이 가장 중요한가요?",
        tools: ["order", "kg"],
        storyId: "S-03",
      },
    ],
  },
  {
    id: "causal",
    label: "인과 추론",
    presets: [
      {
        id: "s05",
        label: "JP 비건+무기자차 왜?",
        query: "왜 일본에서 비건 무기자차 선크림에 대한 수요가 있는 건가요?",
        tools: ["kg", "order"],
        storyId: "S-05",
      },
      {
        id: "s10",
        label: "JP 선크림 왜 잘 팔려?",
        query: "일본에서 선크림이 잘 팔리는 이유가 뭔가요? 어떤 특성의 선크림이 앞으로 더 잘 팔릴까요?",
        tools: ["kg", "order"],
        storyId: "S-10",
      },
    ],
  },
  {
    id: "market",
    label: "시장 분석",
    presets: [
      {
        id: "s08",
        label: "국가별 성분 선호",
        query: "한국, 일본, 싱가포르에서 토너/세럼 구매 시 각각 어떤 성분을 선호하나요?",
        tools: ["order", "kg"],
        storyId: "S-08",
      },
      {
        id: "s09",
        label: "SG 진출 전략",
        query: "싱가포르 시장에 진출하려면 어떤 제품 라인업이 효과적일까요?",
        tools: ["order", "kg"],
        storyId: "S-09",
      },
    ],
  },
  {
    id: "emerging",
    label: "신규 속성",
    presets: [
      {
        id: "s06",
        label: "마이크로바이옴 감지",
        query: "최근에 새롭게 등장하거나 급성장하는 성분/속성이 있나요?",
        tools: ["order"],
        storyId: "S-06",
      },
    ],
  },
  {
    id: "edge",
    label: "함정 질의",
    presets: [
      {
        id: "s12",
        label: "SG 워터프루프 트렌드?",
        query: "싱가포르에서 워터프루프 선크림의 인기가 최근 들어 올라가고 있나요?",
        tools: ["order"],
        storyId: "S-12",
      },
      {
        id: "s13",
        label: "KR 비건 트렌드?",
        query: "한국에서도 비건 선크림이 인기가 올라가고 있나요?",
        tools: ["order"],
        storyId: "S-13",
      },
    ],
  },
];

export const EXTRACT_PRESETS = [
  "이니스프리 아쿠아 UV 프로텍션 크림 SPF50+ PA++++ 50ml 비건 무기자차",
  "토리든 다이브인 워터리 선크림 SPF50+ PA++++ 60ml 워터프루프",
  "라운드랩 독도 토너 300ml 약산성 히알루론산",
  "스킨푸드 로열허니 프로폴리스 인리치드 에센스 50ml 피부장벽",
];
