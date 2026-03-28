# ADR-006: Confidence 모듈 제거

- **상태**: accepted
- **날짜**: 2026-03-28

## 맥락

초기 설계에서는 confidence 점수(similarity×0.5 + validation×0.3 + richness×0.2)로 high/medium/low tier를 분류하고, tier별 자동 승인/검수를 나누려 했다.

## 결정

별도 confidence 점수/tier 모듈을 만들지 않는다. validator의 errors 유무만으로 판단한다.

## 근거

1. **MVP에서 1,000건 전부 배치로 처리** — "이건 자동 승인, 저건 검수"를 분류할 운영 시나리오가 없음. 어차피 전부 돌리고 전부 DB에 넣음.

2. **가중치의 근거 부재** — similarity가 50%이고 validation이 30%인 이유를 설명할 수 없음. 가중 합산은 "점수는 나오지만 의미를 모르겠는" 상태.

3. **validator 판단만으로 충분**:
   - errors 없음 → 적재 + graph_sync
   - errors 있음 → 적재하되 graph_sync 안 함 + 검수 플래그

4. **confidence가 필요해지는 시점** = Phase 2 이후, 일일 처리량이 많아져서 자동/수동 분류가 운영적으로 의미 있을 때.

## 초기 설계에서 변경된 점

- `extraction/schemas.py`에서 `ConfidenceScore` 제거
- `extraction/confidence.py` 파일 자체를 만들지 않음
- `ExtractionResult`에서 confidence 필드 제거

## 결과

- **장점**: 코드 단순화, 설명 불가능한 점수 제거
- **장점**: extractor.py가 더 명확 — "errors 있으면 sync 안 한다"
- **단점**: 프로덕션에서 대량 처리 시 자동 승인 비율 최적화 불가
- **후속**: Phase 2에서 조건 기반(가중 합산이 아닌) confidence 도입 검토
