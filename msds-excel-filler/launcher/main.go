//go:build windows

// 켐세이프 (ChemSafe) Windows 실행 파일 런처.
//
// 오프라인 단일 HTML(켐세이프_화학물질통합안전관리.html)을 exe 안에 내장하고,
// 실행하면 %LOCALAPPDATA%\ChemSafe 에 풀어 기본 브라우저로 연다.
// 항상 같은 경로에 저장하므로 브라우저 localStorage(등록 이력)가 유지된다.
//
// 빌드:  python3 build_exe.py   (standalone/build_html.py 실행 후 크로스 컴파일)
package main

import (
	_ "embed"
	"os"
	"path/filepath"
	"syscall"
	"unsafe"
)

//go:embed app.html
var appHTML []byte

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

func openInBrowser(path string) bool {
	shell32 := syscall.NewLazyDLL("shell32.dll")
	proc := shell32.NewProc("ShellExecuteW")
	// SW_SHOWNORMAL = 1, 반환값 32 이하 = 실패
	r, _, _ := proc.Call(0, uintptr(unsafe.Pointer(utf16Ptr("open"))),
		uintptr(unsafe.Pointer(utf16Ptr(path))), 0, 0, 1)
	return r > 32
}

func main() {
	base := os.Getenv("LOCALAPPDATA")
	if base == "" {
		base = os.TempDir()
	}
	dir := filepath.Join(base, "ChemSafe")
	_ = os.MkdirAll(dir, 0o755)
	path := filepath.Join(dir, htmlName)
	if err := os.WriteFile(path, appHTML, 0o644); err != nil {
		// 쓰기 실패 — 이전 실행이 남긴 파일이라도 있으면 그대로 연다
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
}
