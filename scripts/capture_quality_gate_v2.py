"""Generated UI Quality Gate v2 — **実描画して撮る**
(`docs/spec/GENERATED-UI-QUALITY-GATE-V2.md` §3、2026-08-26)。

---

## 撮っただけでは Gate を通っていない

`AGENTS.md`:

> 「PNGを生成しただけ」を Visual Review と呼ばない。

この script が作るのは**人が見るための材料**である。撮ったあと
**全部開いて**、spec §4 の13軸で評価し、`manifest.md` へ書く。

## 使い方

```
python scripts/export_quality_gate_fixtures.py
cd frontend && flutter build web --debug \
    -t lib/forge_quality_gate_visual.dart --output=<build_dir>
python scripts/capture_quality_gate_v2.py <build_dir> <out_dir>
```

## この環境で踏んだ罠（019C と同じ。両方とも真っ白なPNGを作る）

1. **CanvasKit が CDN から取れないと engine が起動しない。**
   build が吐いた `canvaskit/` を指す
2. **既定フォントが取れないと文字が1つも描かれない。**
   しかも engine 初期化が font 取得の時間切れまで終わらないので、
   固定待ちでは間に合わない（`flutter-view` の出現を待つ）

どちらも「撮れてはいるが何も写っていない」形で失敗する。
"""

from __future__ import annotations

import functools
import http.server
import json
import pathlib
import sys
import threading

#: 撮影のためだけのフォント差し替え。**製品の見た目そのものではない。**
#: 見てよいのは配置・重なり・はみ出し・階層であって、字形ではない。
_FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
    "/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf",
)

#: spec §3。mobile / small mobile / tablet / desktop。
VIEWPORTS = (
    ("mobile", 390, 844),
    ("small", 320, 640),
    ("tablet", 834, 1112),
    ("desktop", 1440, 900),
)

PORT = 8615


def _local_font() -> pathlib.Path | None:
    for candidate in _FONT_CANDIDATES:
        path = pathlib.Path(candidate)
        if path.is_file():
            return path
    return None


#: 挿入する設定そのものを印として使う（部分文字列の誤判定を避ける）。
_MARKER = '  config: { canvasKitBaseUrl: "canvaskit/" },'


def _ensure_local_canvaskit(build_dir: pathlib.Path) -> None:
    """CanvasKit を同梱物から読ませる（保険）。

    **本筋は `flutter build web --no-web-resources-cdn` である。**
    そのflagを付けて build すれば engine が最初からローカルを見るので、
    ここは何もしない。付け忘れた build を撮ろうとしたときの保険として
    残してある。
    """
    bootstrap = build_dir / "flutter_bootstrap.js"
    if not bootstrap.is_file():
        return
    text = bootstrap.read_text(encoding="utf-8")
    # **自分が入れた印だけを見る。**
    #
    # 以前は `"canvasKitBaseUrl" in text` で二重挿入を防いでいたが、
    # その名前は**minifyされたengine側にも現れる**（config を読む箇所）。
    # そのため常に「もう入っている」と判断して、実際には1度も挿入されず、
    # engine が CDN を見に行って真っ白なPNGになっていた。
    if _MARKER in text:
        return
    anchor = "_flutter.loader.load({"
    if anchor not in text:
        return
    bootstrap.write_text(text.replace(anchor, anchor + "\n" + _MARKER, 1), encoding="utf-8")


def _app_keys() -> tuple[str, ...]:
    """撮影対象は **manifest が決める**。script に書き写さない。"""
    manifest = (
        pathlib.Path(__file__).resolve().parents[1]
        / "docs" / "evidence" / "quality-gate-v2" / "manifest.json"
    )
    data = json.loads(manifest.read_text(encoding="utf-8"))
    return tuple(n["key"] for n in data["needs"] if n.get("rendered"))



def _chromium_executable() -> str | None:
    """使える Chromium を探す。**見つからなければ Playwright の既定に任せる。**

    この環境の Playwright は headless shell を持っておらず、既定のまま
    `launch()` すると「playwright install を実行しろ」で落ちる。
    勝手に install しない（`AGENTS.md` Agent Execution Policy）ので、
    **既に在るものを指す。**
    """
    import os

    explicit = os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE", "")
    candidates = [explicit] if explicit else []
    candidates += [
        "/opt/pw-browsers/chromium",
        "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
    ]
    for candidate in candidates:
        if candidate and pathlib.Path(candidate).exists():
            return candidate
    return None


def main(build_dir: pathlib.Path, out_dir: pathlib.Path) -> int:
    from playwright.sync_api import sync_playwright

    out_dir.mkdir(parents=True, exist_ok=True)
    _ensure_local_canvaskit(build_dir)
    keys = _app_keys()

    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=str(build_dir),
    )

    class _Quiet(http.server.ThreadingHTTPServer):
        daemon_threads = True

        def log_message(self, *_args: object) -> None:  # noqa: A003
            """撮影ログを HTTP ログで埋めない。"""

    server = _Quiet(("127.0.0.1", PORT), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    font = _local_font()
    if font is None:
        print("[warn] 差し替え用フォントが無い。文字が描かれない可能性がある")

    captured = 0
    with sync_playwright() as pw:
        executable = _chromium_executable()
        browser = pw.chromium.launch(
            headless=True,
            **({"executable_path": executable} if executable else {}),
        )
        for name, width, height in VIEWPORTS:
            page = browser.new_page(
                viewport={"width": width, "height": height}, device_scale_factor=2,
            )
            if font is not None:
                page.route(
                    "https://fonts.gstatic.com/**",
                    lambda route: route.fulfill(
                        status=200, body=font.read_bytes(),
                        headers={"content-type": "font/ttf",
                                 "access-control-allow-origin": "*"},
                    ),
                )
            for key in keys:
                page.goto(
                    f"http://127.0.0.1:{PORT}/index.html?app={key}",
                    wait_until="load",
                )
                page.wait_for_selector("flutter-view", timeout=60_000)
                page.wait_for_timeout(2_500)
                target = out_dir / f"{key}-{name}-{width}x{height}.png"
                page.screenshot(path=str(target))
                captured += 1
                print(f"  {target.name}  ({target.stat().st_size} bytes)")
            page.close()
        browser.close()
    server.shutdown()

    print()
    print(f"  {captured} 枚 ({len(keys)} アプリ × {len(VIEWPORTS)} viewport)")
    print()
    print("  撮っただけでは Gate を通っていない。**全部開いて**")
    print("  hierarchy / typography / spacing / density / contrast /")
    print("  empty-state / long-text / navigation / touch target /")
    print("  visual identity / content fit / accessibility / overflow")
    print("  を評価し、manifest.md へ書くこと。")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        print("usage: python scripts/capture_quality_gate_v2.py <build_dir> <out_dir>")
        raise SystemExit(2)
    raise SystemExit(main(pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])))
