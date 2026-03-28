# ADR-008: Python 3.12 고정 (3.14 호환성 문제)

- **상태**: accepted
- **날짜**: 2026-03-28

## 맥락

시스템의 기본 Python이 3.14였으나, 핵심 의존성이 3.14를 지원하지 않는 문제가 발생했다.

## 문제 상세

### 시도 1: Python 3.14 + chromadb
```
chromadb → onnxruntime → Python 3.14 미지원 ❌
```
chromadb의 모든 버전(0.6.3 ~ 1.5.5)이 onnxruntime에 의존하는데, onnxruntime이 Python 3.14용 바이너리 휠을 배포하지 않음.

### 시도 2: Python 3.14 + chromadb-client (HTTP 전용)
```
chromadb-client는 설치 가능 → 하지만 PersistentClient 사용 불가
                              → ChromaDB 서버 컨테이너 필요
```
HTTP-only 클라이언트라 서버가 필요. 로컬 임베딩(sentence-transformers)도 사용 불가.

### 시도 3: Python 3.14 + sentence-transformers
```
sentence-transformers → torch → Python 3.14 미지원 ❌
```

### 시도 4: Python 3.12 + 전부 설치
```
Python 3.12 → chromadb ✅, sentence-transformers ✅, torch 2.2.2 ✅
             → 단, numpy < 2 필요 (torch 2.2 호환)
             → sentence-transformers < 4.0 필요 (torch 2.2 호환)
```

## 결정

venv를 `/usr/local/bin/python3.12`로 고정 생성한다.

```bash
/usr/local/bin/python3.12 -m venv backend/.venv
```

requirements.txt에 호환 범위 명시:
```
sentence-transformers>=3.0,<4.0
numpy<2
```

## 근거

- Voyage API 등 외부 임베딩 API를 사용하면 3.14에서도 가능하지만, 로컬 임베딩이 비용 절감 + 레이턴시 우위
- Docker 컨테이너 내부는 Python 3.12 기반 이미지를 사용하면 되므로 프로덕션 배포에는 영향 없음
- macOS x86_64에서 torch 2.2.2가 최대 버전 (2.4+는 x86_64 미지원)

## 결과

- **동작 확인된 버전**: Python 3.12.13, torch 2.2.2, numpy 1.26.4, onnxruntime 1.19.2, sentence-transformers 3.4.1, chromadb 1.5.5
- **후속**: Dockerfile은 `python:3.12-slim` 기반으로 작성 (이미 반영됨)
