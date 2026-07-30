# -*- coding: utf-8 -*-
"""켐세이프 Windows 실행 파일(exe) 빌드 스크립트.

standalone/build_html.py 로 단일 HTML을 만든 뒤 launcher/app.html 로 복사하고,
Go 크로스 컴파일(GOOS=windows)로 HTML을 내장한 exe 를 만든다.

실행:  python3 build_exe.py
결과:  dist/켐세이프_ChemSafe.exe
"""
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HTML = os.path.join(HERE, "standalone", "켐세이프_화학물질통합안전관리.html")
LAUNCHER = os.path.join(HERE, "launcher")
DIST = os.path.join(HERE, "dist")
EXE = os.path.join(DIST, "켐세이프_ChemSafe.exe")


def main():
    subprocess.run([sys.executable, "build_html.py"],
                   cwd=os.path.join(HERE, "standalone"), check=True)
    shutil.copyfile(HTML, os.path.join(LAUNCHER, "app.html"))
    os.makedirs(DIST, exist_ok=True)
    env = dict(os.environ, GOOS="windows", GOARCH="amd64", CGO_ENABLED="0")
    subprocess.run(["go", "build", "-trimpath",
                    "-ldflags", "-s -w -H=windowsgui", "-o", EXE],
                   cwd=LAUNCHER, env=env, check=True)
    print(f"완료: {EXE} ({os.path.getsize(EXE) / 1024 / 1024:.1f} MB)")


if __name__ == "__main__":
    main()
