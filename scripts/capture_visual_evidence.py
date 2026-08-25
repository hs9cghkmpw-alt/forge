"""実描画を撮る（FORGE-019C/020 §37）。

---

## PNGを作ることが目的ではない

`AGENTS.md`:

> 「PNGを生成しただけ」を Visual Review と呼ばない。

この script が作るのは**人が見るための材料**である。撮ったあと必ず

* overlap（重なり）
* overflow / clipping（はみ出し・切れ）
* alignment（そろい）
* spacing（間隔）
* hierarchy（階層）
* primary metric visibility（主指標が主に見えるか）
* mobile usability

を目で確かめ、結果を `docs/visual-evidence/<TASK>/manifest.md` へ書く。

## 使い方

```
python scripts/export_revision_visual_fixture.py       # 本番から After を作る
cd frontend && flutter build web --debug \
    -t lib/forge_019_visual.dart --output=<build_dir>
python scripts/capture_visual_evidence.py <build_dir> <out_dir>
```

## この環境で踏んだ2つの罠（両方とも「真っ白なPNG」を作る）

### 1. CanvasKit が CDN から取れない

Flutter Web は既定で `gstatic.com` から CanvasKit を取る。取れないと
**engine が起動せず、画面は真っ白になる**。build が吐いた
`canvaskit/` を指せば直る（`--canvaskit-base-url` 相当の設定）。

### 2. font が取れないと文字が1つも描かれない

CanvasKit は system font を使わない。既定の Roboto を
`fonts.gstatic.com` から取るので、取れないと**文字が消える**
（背景と枠だけの画像になる）。しかも engine の初期化は
**font 取得が時間切れになるまで終わらない**ので、固定待ちだと
間に合わない。

どちらも「撮れてはいるが何も写っていない」という形で失敗する。
**画像を開いて中身を見ない限り気付けない。**
"""

from __future__ import annotations

import functools
import http.server
import pathlib
import sys
import threading

#: 撮影のためだけのフォント差し替え。
#:
#: **製品の見た目そのものではない。** 字形は差し替えたフォントのもので
#: あり、本番の Roboto / Helvetica とは違う。見てよいのは
#: 配置・重なり・はみ出し・階層であって、字形ではない。
_FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
    "/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf",
)

VIEWPORTS = (("mobile", 390, 844), ("small", 320, 640))
STATES = ("before", "after")
PORT = 8611


def _local_font() -> pathlib.Path | None:
    for candidate in _FONT_CANDIDATES:
        path = pathlib.Path(candidate)
        if path.is_file():
            return path
    return None


def _ensure_local_canvaskit(build_dir: pathlib.Path) -> None:
    """CanvasKit を同梱物から読ませる。**CDNが使えなくても起動する。**"""
    bootstrap = build_dir / "flutter_bootstrap.js"
    if not bootstrap.is_file():
        return
    text = bootstrap.read_text(encoding="utf-8")
    if "canvasKitBaseUrl" in text:
        return
    marker = "_flutter.loader.load({"
    if marker not in text:
        return
    bootstrap.write_text(
        text.replace(
            marker, marker + '\n  config: { canvasKitBaseUrl: "canvaskit/" },', 1,
        ),
        encoding="utf-8",
    )


def main(build_dir: pathlib.Path, out_dir: pathlib.Path) -> int:
    from playwright.sync_api import sync_playwright

    out_dir.mkdir(parents=True, exist_ok=True)
    _ensure_local_canvaskit(build_dir)

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

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        for name, width, height in VIEWPORTS:
            page = browser.new_page(
                viewport={"width": width, "height": height}, device_scale_factor=2,
            )
            if font is not None:
                page.route(
                    "https://fonts.gstatic.com/**",
                    lambda route: route.fulfill(
                        status=200, body=font.read_bytes(),
                        headers={
                            "content-type": "font/ttf",
                            "access-control-allow-origin": "*",
                        },
                    ),
                )
            for state in STATES:
                page.goto(
                    f"http://127.0.0.1:{PORT}/index.html?state={state}",
                    wait_until="load",
                )
                # **固定待ちにしない。** font 取得の時間切れを待つ必要があり、
                # 何秒かかるかは環境で変わる。
                page.wait_for_selector("flutter-view", timeout=60_000)
                page.wait_for_timeout(2_500)
                target = out_dir / f"{state}-{name}-{width}x{height}.png"
                page.screenshot(path=str(target))
                print(f"captured {target} ({target.stat().st_size} bytes)")
            page.close()
        browser.close()
    server.shutdown()

    print()
    print("撮っただけでは Visual Review ではない。画像を開いて")
    print("overlap / overflow / clipping / alignment / spacing / hierarchy /")
    print("primary visibility / mobile usability を確かめ、manifest へ書くこと。")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        print("usage: python scripts/capture_visual_evidence.py <build_dir> <out_dir>")
        raise SystemExit(2)
    raise SystemExit(main(pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])))
