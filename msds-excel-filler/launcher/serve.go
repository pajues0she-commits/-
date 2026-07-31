// 켐세이프 (ChemSafe) 로컬 서버 — OS 공통 부분.
//
// 내장 단일 HTML을 http://127.0.0.1:포트 로 서비스하고, 앱의 저장 데이터
// (localStorage 스냅숏)를 데이터 폴더의 storage.json 파일로 보관한다.
// 브라우저가 종료 시 사이트 데이터를 지우도록 설정돼 있어도(사내 보안 정책
// 등) 다음 실행 때 서버 파일에서 그대로 복원되므로 등록·이력이 사라지지
// 않는다.
package main

import (
	_ "embed"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"os"
	"sync"
	"time"
)

//go:embed app.html
var appHTML []byte

const storeName = "storage.json"

var (
	storeMu   sync.Mutex
	storePath string
)

func handleStore(w http.ResponseWriter, r *http.Request) {
	switch r.Method {
	case http.MethodGet:
		storeMu.Lock()
		b, err := os.ReadFile(storePath)
		storeMu.Unlock()
		if err != nil {
			b = []byte("{}")
		}
		w.Header().Set("Content-Type", "application/json; charset=utf-8")
		w.Header().Set("Cache-Control", "no-store")
		_, _ = w.Write(b)
	case http.MethodPost:
		var data map[string]string
		body, err := io.ReadAll(io.LimitReader(r.Body, 64<<20))
		if err == nil {
			err = json.Unmarshal(body, &data)
		}
		if err != nil {
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}
		storeMu.Lock()
		defer storeMu.Unlock()
		tmp := storePath + ".tmp"
		if err := os.WriteFile(tmp, body, 0o644); err == nil {
			_ = os.Rename(tmp, storePath) // 원자적 교체 — 손상 방지
		}
		w.WriteHeader(http.StatusNoContent)
	default:
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
	}
}

func serveHTTP(ln net.Listener) {
	mux := http.NewServeMux()
	mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/" {
			http.NotFound(w, r)
			return
		}
		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		w.Header().Set("Cache-Control", "no-store")
		_, _ = w.Write(appHTML)
	})
	mux.HandleFunc("/chemsafe/ping", func(w http.ResponseWriter, r *http.Request) {
		_, _ = w.Write([]byte("chemsafe"))
	})
	mux.HandleFunc("/chemsafe/store", handleStore)
	_ = http.Serve(ln, mux)
}

func pingChemSafe(addr string) bool {
	c := http.Client{Timeout: 500 * time.Millisecond}
	resp, err := c.Get("http://" + addr + "/chemsafe/ping")
	if err != nil {
		return false
	}
	defer resp.Body.Close()
	b, _ := io.ReadAll(io.LimitReader(resp.Body, 16))
	return string(b) == "chemsafe"
}

// launchServer 는 127.0.0.1의 고정 포트 대역에서 서버를 시작한다.
// 이미 켐세이프가 떠 있으면 그 주소를 돌려준다(두 번째 실행은 창만 연다).
func launchServer() (url string, serving bool) {
	for port := 8975; port <= 8984; port++ {
		addr := fmt.Sprintf("127.0.0.1:%d", port)
		ln, err := net.Listen("tcp", addr)
		if err != nil {
			if pingChemSafe(addr) {
				return "http://" + addr + "/", false
			}
			continue // 다른 프로그램이 쓰는 포트 — 다음 포트 시도
		}
		go serveHTTP(ln)
		return "http://" + addr + "/", true
	}
	return "", false
}
