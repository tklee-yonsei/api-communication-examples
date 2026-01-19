# 지원하는 데모 작업 목록

## 동기 작업 (즉시 결과 반환)

- **echo**: `POST /echo` - params 그대로 반환
- **calc**: `POST /calc` - op(add|sub|mul|div), a, b 사칙연산
- **stats**: `POST /stats` - values(list[float])에 대해 count/min/max/sum/mean/median 통계

## 비동기 작업 (job_id 반환 후 조회)

- **hash**: `POST /hash_jobs` - params를 정렬된 JSON 문자열로 SHA-256 해시
- **fib**: `POST /fib_jobs` - n(0~40)번째 피보나치 수 계산

비동기 작업은 `GET /jobs/{job_id}`로 결과를 조회할 수 있습니다.
