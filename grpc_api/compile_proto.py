#!/usr/bin/env python3
"""Proto 파일을 Python 코드로 컴파일하는 스크립트.

사용법:
    python -m grpc_api.compile_proto

또는:
    python grpc_api/compile_proto.py
"""

import subprocess
import sys
from pathlib import Path


def fix_imports(proto_dir: Path) -> None:
    """생성된 파일의 import 경로를 패키지 경로로 수정합니다.

    grpc_tools.protoc가 생성하는 파일은 상대 import를 사용하지 않아서
    패키지로 사용할 때 문제가 됩니다. 이 함수는 import 문을 수정합니다.
    """
    grpc_file = proto_dir / "jobs_pb2_grpc.py"

    if grpc_file.exists():
        content = grpc_file.read_text()
        # 'import jobs_pb2' -> 'from grpc_api.protos import jobs_pb2'
        # 또는 'from . import jobs_pb2'로 변경
        fixed_content = content.replace(
            "import jobs_pb2 as jobs__pb2",
            "from grpc_api.protos import jobs_pb2 as jobs__pb2",
        )
        grpc_file.write_text(fixed_content)
        print("  - Fixed imports in jobs_pb2_grpc.py")


def compile_protos() -> None:
    """Proto 파일을 컴파일합니다."""
    # 프로젝트 루트 디렉토리 찾기
    script_dir = Path(__file__).parent
    proto_dir = script_dir / "protos"
    proto_file = proto_dir / "jobs.proto"

    if not proto_file.exists():
        print(f"Error: Proto file not found: {proto_file}")
        sys.exit(1)

    # grpc_tools.protoc를 사용하여 컴파일
    cmd = [
        sys.executable,
        "-m",
        "grpc_tools.protoc",
        f"--proto_path={proto_dir}",
        f"--python_out={proto_dir}",
        f"--grpc_python_out={proto_dir}",
        f"--pyi_out={proto_dir}",  # 타입 스텁 생성
        str(proto_file),
    ]

    print(f"Compiling: {proto_file}")
    print(f"Command: {' '.join(cmd)}")

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"Error compiling proto file:")
        print(result.stderr)
        sys.exit(1)

    print("Proto compilation successful!")
    print(f"Generated files in: {proto_dir}")

    # 생성된 파일 확인
    for generated in proto_dir.glob("*_pb2*.py*"):
        print(f"  - {generated.name}")

    # import 경로 수정
    print("\nFixing import paths...")
    fix_imports(proto_dir)
    print("Done!")


if __name__ == "__main__":
    compile_protos()
