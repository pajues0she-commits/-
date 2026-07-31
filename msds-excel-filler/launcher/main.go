//go:build windows

// 켐세이프 (ChemSafe) Windows 실행 파일 런처.
//
// 오프라인 단일 HTML을 exe 안에 내장하고, 실행하면 127.0.0.1 로컬 서버로
// 서비스해 기본 브라우저로 연다. 저장 데이터(등록·이력)는
// %LOCALAPPDATA%\ChemSafe\storage.json 파일로 보관·복원되므로 브라우저
// 설정(종료 시 데이터 삭제 등)과 무관하게 유지된다. exe는 브라우저 사용
// 중 백그라운드에 상주하며, 이미 실행 중이면 창만 다시 연다.
//
// 빌드:  python3 build_exe.py   (standalone/build_html.py 실행 후 크로스 컴파일)
package main

import (
	"os"
	"path/filepath"
	"syscall"
	"unsafe"
)

const htmlName = "켐세이프_화학물질통합안전관리.html"

func utf16Ptr(s string) *uint16 {
	p, _ := syscall.UTF16PtrFromString(s)
	return p
}

func msgBox(text, title string) {
	user32 := syscall.NewLazyDLL("user32.dll")
	proc := user32.NewProc("MessageBoxW")
	// 0x10 = MB_ICONERROR
	proc.Call(0, uintptr(unsafe.Pointer(utf16Ptr(text))),
		uintptr(unsafe.Pointer(utf16Ptr(title))), 0x10)
}

func openInBrowser(target string) bool {
	shell32 := syscall.NewLazyDLL("shell32.dll")
	proc := shell32.NewProc("ShellExecuteW")
	// SW_SHOWNORMAL = 1, 반환값 32 이하 = 실패
	r, _, _ := proc.Call(0, uintptr(unsafe.Pointer(utf16Ptr("open"))),
		uintptr(unsafe.Pointer(utf16Ptr(target))), 0, 0, 1)
	return r > 32
}

func main() {
	base := os.Getenv("LOCALAPPDATA")
	if base == "" {
		base = os.TempDir()
	}
	dir := filepath.Join(base, "ChemSafe")
	_ = os.MkdirAll(dir, 0o755)
	storePath = filepath.Join(dir, storeName)

	url, serving := launchServer()
	if url == "" {
		// 포트를 하나도 못 잡음 — 예전 방식(파일로 풀어 열기)으로 동작.
		// 이 경우 저장은 브라우저 localStorage에만 남는다.
		path := filepath.Join(dir, htmlName)
		if err := os.WriteFile(path, appHTML, 0o644); err != nil {
			if _, statErr := os.Stat(path); statErr != nil {
				msgBox("프로그램 파일을 저장하지 못했습니다.\n"+err.Error(),
					"켐세이프 (ChemSafe)")
				return
			}
		}
		if !openInBrowser(path) {
			msgBox("기본 브라우저로 열지 못했습니다.\n"+
				"직접 열어 주세요: "+path, "켐세이프 (ChemSafe)")
		}
		return
	}
	if !openInBrowser(url) {
		msgBox("기본 브라우저로 열지 못했습니다.\n"+
			"직접 열어 주세요: "+url, "켐세이프 (ChemSafe)")
	}
	if serving {
		select {} // 서버 상주 — 브라우저에서 계속 사용
	}
}
