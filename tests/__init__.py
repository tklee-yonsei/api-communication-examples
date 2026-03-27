"""테스트 패키지 초기화.

테스트 디렉토리 구조:
- contract/: 클라이언트 인터페이스 준수 테스트 (계약 테스트)
- integration/: REST API 통합 테스트
- rest_api/: REST API 모듈 테스트 (소스 구조 미러링)
    - core/: rest_api/core 모듈 테스트
        - jobs/: Job Handler 단위 테스트
        - test_job_queue.py: JobQueue 테스트
        - test_validation.py: Validation 테스트
    - test_rest_client_contract.py: REST 클라이언트 계약 테스트
"""
