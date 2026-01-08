# 자주 사용하는 명령어 모음

이 문서는 실습 중 자주 사용하는 명령어들을 복사-붙여넣기로 쉽게 사용할 수 있도록 정리한 것입니다.

## Git Flow 명령어

수업 중 기능 단위 개발을 위해 Git Flow를 사용합니다. 터미널(Terminal)에서 아래 명령어를 사용하세요.

### 초기화 (최초 1회)

```bash
git flow init -d
```

### 작업 시작

```bash
git flow feature start 실습이름
```

### 작업 완료

```bash
git flow feature finish 실습이름
```

## Python 실행 명령어

### 단일 파일 실행

```bash
python3 파일명.py
```

예시:

```bash
python3 sample/sample.py
```

### 패키지 모듈로 실행

```bash
python -m 패키지명.모듈명
```

예시:

```bash
python -m sample_project_with_unittest.main
```

## pytest 테스트 명령어

### 모든 테스트 실행

```bash
pytest
```

### 특정 폴더의 테스트 실행

```bash
pytest tests/sample_project_with_unittest/
```

### 상세 출력으로 테스트 실행

```bash
pytest -v
```

### 특정 테스트 파일 실행

```bash
pytest tests/sample_project_with_unittest/test_calculator.py
```

### 특정 테스트 함수 실행

```bash
pytest tests/sample_project_with_unittest/test_calculator.py::test_add
```

### 실패한 테스트만 재실행

```bash
pytest --lf
```

## Git 기본 명령어

### 저장소 클론

```bash
git clone <저장소_URL>
cd py_programming_base
```

### Git 버전 확인

```bash
git --version
```

### 변경 사항 확인

```bash
git status
```

### 모든 변경 사항 스테이징

```bash
git add .
```

### 커밋

```bash
git commit -m "커밋 메시지"
```

### 원격 저장소에 푸시

```bash
git push
```

## 코드 품질 도구

### Black 포맷터 실행

```bash
black 파일명.py
```

또는 전체 프로젝트:

```bash
black .
```

### Pylint 린터 실행

```bash
pylint 파일명.py
```

### mypy 타입 체크

```bash
mypy 파일명.py
```
