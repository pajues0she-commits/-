//go:build !windows

// 개발·테스트용 진입점(리눅스/맥) — 브라우저를 열지 않고 서버만 띄운다.
// 사용:  go run . [데이터폴더]   (기본 ./devdata)
package main

import (
	"fmt"
	"os"
	"path/filepath"
)

func main() {
	dir := "devdata"
	if len(os.Args) > 1 {
		dir = os.Args[1]
	}
	_ = os.MkdirAll(dir, 0o755)
	storePath = filepath.Join(dir, storeName)
	url, serving := launchServer()
	if url == "" {
		fmt.Println("포트를 잡지 못했습니다 (8975~8984)")
		os.Exit(1)
	}
	fmt.Println("serving:", url, "store:", storePath)
	if serving {
		select {}
	}
}
