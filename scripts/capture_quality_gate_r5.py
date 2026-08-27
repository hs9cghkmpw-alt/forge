"""Quality Gate v2 **Round 5** — 操作して撮る（TD92 / 020A2 §7、2026-08-26）。

---

## Round 4 までの限界

`capture_quality_gate_v2.py` は**第1タブしか撮れなかった**。

`analytics.json` には `bar_chart` と `metric_view(aggregate=sum)` が
**実在する**のに、一覧タブにあるので静止画に写らない。

> **「撮れていない」と「無い」は違う。**
> Round 4 の manifest はそう書いたが、書いただけでは次も同じである。

この script は Playwright で**実際にタブを押してから**撮る。

## 撮る state

app ごとに「その道具の要点が見える画面」を指定する。
**app ごとの UI を作るのではない**——同じ Renderer の同じ画面を、
違うタブで撮るだけである。

## 操作の手順

```
app を開く
  → flutter-view の出現を待つ
  → **タブを座標で押す**
  → 落ち着くまで待つ
  → 押す前と絵が変わったことを確かめる
  → 撮る
  → **画像を開いて人が見る**
```

### なぜ座標なのか（実際に試して分かったこと）

最初 `page.get_by_text("一覧")` で押そうとしたが、**全部 timeout した**。

Flutter Web の CanvasKit は**画面を canvas へ描く**ので、
「一覧」という DOM のテキストは存在しない。Playwright から見えるのは
`<flutter-view>` と `<canvas>` だけである。

`flt-semantics-placeholder` を押して semantics tree を有効にする道も
試した。node は 13 個できたが `aria-label` は空で、タブを名前で
指せなかった。

残るのは**実際の利用者と同じ操作**——画面のその位置を押すことである。
`page.mouse.click()` は本物のマウスイベントを送るので、
Flutter の hit test を素通りしない。

### 本文は画面いっぱいではない（Round 5 で実際に外した）

最初 `x = width * (index + 0.5) / len(tabs)` で押したところ、
**desktop(1440) だけ 4 件が押せなかった。**

`forge_renderer.dart` は本文を `Center` +
`maxWidth: _maxContentWidth` で包んでいる。つまり 1440px でも
タブ列があるのは **360〜1080** で、その外は余白である。
上の式だと index 0 は x=240（余白）、index 2 は x=1200（余白）へ
落ちる。**index 1 だけが偶然 x=720＝中央で当たっていた。**

なので座標は Dart 側の値から出す。値は写経せず
**`forge_renderer.dart` から読む**——写すと黙ってずれる。

### 押せたことを絵で確かめる

座標を押すと「押したつもり」になりやすい。**押す前と後の絵を比べ、
1バイトも変わっていなければ失敗として扱う。**

ただしこの比較には**2つの穴がある**。両方とも実際に踏んだ。

1. **カーソルが乗っただけでも絵は変わる。** `InkWell` の hover が
   出るので、タブが切り替わらなくても差分が出る。
   → 撮る前に**カーソルをタブ列から外す**。
2. **もともと選ばれているタブは押しても変わらない。** 一覧が先頭に
   来る app（`summary_first` / `comparison_first`）では
   「一覧タブを押す」が no-op になる。
   → その場合は**別のタブを経由してから戻る**。
   往きと帰りの両方で絵が変わることを要求する。

## 撮っただけでは Gate を通っていない

`AGENTS.md`:

> 「PNGを生成しただけ」を Visual Review と呼ばない。
"""

from __future__ import annotations

import functools
import http.server
import json
import pathlib
import re
import sys
import threading



def _v2():
    """Round 4 の撮影基盤を読み込む。**同じ罠を2度書かない。**

    `scripts/` は package ではないので、ファイルから直接読む。
    CanvasKit / フォント / Chromium の扱いは v2 が既に解いている
    （どれも「撮れてはいるが何も写っていない」形で失敗する罠）。
    """
    import importlib.util

    path = pathlib.Path(__file__).resolve().parent / "capture_quality_gate_v2.py"
    spec = importlib.util.spec_from_file_location("_qg_v2", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_V2 = _v2()
VIEWPORTS = _V2.VIEWPORTS
_chromium_executable = _V2._chromium_executable
_ensure_local_canvaskit = _V2._ensure_local_canvaskit
_local_font = _V2._local_font

PORT = 8616

#: **撮る state。** `(app key, state 名, 押すタブの語)`。
#:
#: タブの語は Entity 名から作られるので、**部分一致**で押す
#: （「一覧」「を追加」）。app 名を script に書き写さない。
STATES: tuple[tuple[str, str, str | None], ...] = (
    ("finance", "initial", None),
    ("finance", "input", "を追加"),
    ("finance", "summary", "一覧"),

    ("analytics", "initial", None),
    ("analytics", "input", "を追加"),
    ("analytics", "comparison", "一覧"),

    ("study", "initial", None),
    ("study", "input", "を追加"),
    ("study", "trend", "一覧"),

    ("photo", "initial", None),
    ("photo", "input", "を追加"),
    ("photo", "list", "一覧"),

    # ゲームは「いま作れる範囲」しか無い。**それを撮る。**
    ("game", "initial", None),
    ("game", "supported_only", "一覧"),
)


#: タブ列の縦位置（CSS px）。`AppBar` は `toolbarHeight: 72` 固定なので
#: viewport によらない。
_TAB_ROW_Y = 116

#: 開いた直後に選ばれているタブ（`_TabViewSwitcher._selectedIndex`）。
_INITIAL_TAB_INDEX = 0

#: 本文の描画に関わる Dart 側の値を**そこから読む**ための場所。
_RENDERER_DART = (
    pathlib.Path(__file__).resolve().parents[1]
    / "frontend" / "lib" / "json_ui" / "renderer" / "forge_renderer.dart"
)


def layout_metrics(source: str | None = None) -> tuple[float, float]:
    """本文の `(最大幅, 左右 padding)` を `forge_renderer.dart` から読む。

    **写経しない。** 片方でも読めなければ例外にする——
    「読めなかったので既定値」は、ずれたことに気付けない形である。
    """
    text = source if source is not None else _RENDERER_DART.read_text(encoding="utf-8")
    width = re.search(r"_maxContentWidth\s*=\s*([0-9.]+)\s*;", text)
    padding = re.search(r"padding:\s*const EdgeInsets\.all\(([0-9.]+)\)", text)
    if width is None or padding is None:
        raise RuntimeError(
            "forge_renderer.dart から _maxContentWidth / padding を読めない。"
            " 撮影座標が出せないので撮らない。",
        )
    return float(width.group(1)), float(padding.group(1))


def tab_center_x(
    viewport_width: float, index: int, count: int, metrics: tuple[float, float],
) -> float:
    """`index` 番目のタブの中心 x（CSS px）。

    本文は `SingleChildScrollView(padding)` の内側で `Center` +
    `ConstrainedBox(maxWidth)` に入っている。**広い画面では本文は
    画面幅ではない。**
    """
    max_content, padding = metrics
    inner = viewport_width - padding * 2
    content = min(inner, max_content)
    left = padding + (inner - content) / 2
    return left + content * (index + 0.5) / count


def _app_keys() -> tuple[str, ...]:
    manifest = (
        pathlib.Path(__file__).resolve().parents[1]
        / "docs" / "evidence" / "quality-gate-v2" / "manifest.json"
    )
    data = json.loads(manifest.read_text(encoding="utf-8"))
    return tuple(n["key"] for n in data["needs"] if n.get("rendered"))


def _tab_titles() -> dict[str, tuple[str, ...]]:
    """app ごとのタブ名を**生成物から**読む。script に書き写さない。

    タブ名は Entity 名から作られる（「売上記録一覧」）。ここへ写すと、
    名前が変わったときに黙ってずれる。
    """
    evidence = (
        pathlib.Path(__file__).resolve().parents[1]
        / "docs" / "evidence" / "quality-gate-v2"
    )

    def find(node: object) -> tuple[str, ...] | None:
        if isinstance(node, dict):
            if node.get("type") == "tab_view":
                titles = node.get("tab_titles")
                if isinstance(titles, list):
                    return tuple(str(x) for x in titles)
            for value in node.values():
                found = find(value)
                if found:
                    return found
        elif isinstance(node, list):
            for value in node:
                found = find(value)
                if found:
                    return found
        return None

    titles: dict[str, tuple[str, ...]] = {}
    for path in sorted(evidence.glob("*.json")):
        if path.name == "manifest.json":
            continue
        found = find(json.loads(path.read_text(encoding="utf-8")))
        if found:
            titles[path.stem] = found
    return titles


def main(build_dir: pathlib.Path, out_dir: pathlib.Path) -> int:
    from playwright.sync_api import sync_playwright

    out_dir.mkdir(parents=True, exist_ok=True)
    _ensure_local_canvaskit(build_dir)

    available = set(_app_keys())
    tab_titles = _tab_titles()
    states = [s for s in STATES if s[0] in available]
    skipped = {s[0] for s in STATES} - available
    if skipped:
        # **撮れなかったものを黙って落とさない。**
        print(f"[warn] 生成されていない app を飛ばした: {sorted(skipped)}")

    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=str(build_dir),
    )

    class _Quiet(http.server.ThreadingHTTPServer):
        daemon_threads = True

        def log_message(self, *_args: object) -> None:
            """撮影ログを HTTP ログで埋めない。"""

    server = _Quiet(("127.0.0.1", PORT), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    font = _local_font()
    if font is None:
        print("[warn] 差し替え用フォントが無い。文字が描かれない可能性がある")

    metrics = layout_metrics()
    print(f"  本文 maxWidth={metrics[0]:g} padding={metrics[1]:g}"
          "（forge_renderer.dart から読んだ）")

    captured = 0
    failed: list[str] = []
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
            for key, state, tab in states:
                page.goto(
                    f"http://127.0.0.1:{PORT}/index.html?app={key}",
                    wait_until="load",
                )
                page.wait_for_selector("flutter-view", timeout=60_000)
                page.wait_for_timeout(2_500)

                def settled() -> bytes:
                    """カーソルをタブ列から外してから撮る。

                    `InkWell` の hover は**タブが変わらなくても**絵を
                    変える。外さないと「押せた」の判定がその hover で
                    通ってしまう（実際に mobile で通っていた）。
                    """
                    page.mouse.move(width - 2, height - 2)
                    page.wait_for_timeout(400)
                    return page.screenshot()

                def press(index: int, count: int) -> None:
                    # **利用者と同じ操作。** CanvasKit は canvas へ描くので
                    # DOM のテキストが無い（実際に試して分かった）。
                    page.mouse.click(
                        tab_center_x(width, index, count, metrics), _TAB_ROW_Y,
                    )
                    page.wait_for_timeout(1_200)

                if tab is not None:
                    titles = tab_titles.get(key, ())
                    index = next(
                        (i for i, title in enumerate(titles) if tab in title), None,
                    )
                    if index is None:
                        failed.append(f"{key}-{state}-{name}: タブ『{tab}』が無い")
                        print(f"  [FAIL] {key}-{state}-{name} タブ『{tab}』が無い"
                              f"（実際: {list(titles)}）")
                        continue

                    before = settled()
                    if index == _INITIAL_TAB_INDEX:
                        # **もともと選ばれているタブは押しても変わらない。**
                        # 押せることを示すために、別のタブを経由して戻る。
                        detour = (index + 1) % len(titles)
                        press(detour, len(titles))
                        midway = settled()
                        if midway == before:
                            failed.append(
                                f"{key}-{state}-{name}: 経由タブが押せない")
                            print(f"  [FAIL] {key}-{state}-{name} "
                                  f"経由タブ（{titles[detour]}）を押しても絵が変わらない")
                            continue
                        press(index, len(titles))
                        if settled() == midway:
                            failed.append(f"{key}-{state}-{name}: 戻れない")
                            print(f"  [FAIL] {key}-{state}-{name} "
                                  f"『{titles[index]}』へ戻れない")
                            continue
                    else:
                        press(index, len(titles))
                        if settled() == before:
                            # **押したつもりを撮らない。**
                            failed.append(f"{key}-{state}-{name}: 絵が変わらない")
                            print(f"  [FAIL] {key}-{state}-{name} "
                                  "タブを押したが絵が変わらない")
                            continue

                target = out_dir / f"{key}-{state}-{name}-{width}x{height}.png"
                page.screenshot(path=str(target))
                captured += 1
                print(f"  {target.name}  ({target.stat().st_size} bytes)")
            page.close()
        browser.close()
    server.shutdown()

    print()
    print(f"  {captured} 枚 / {len(states)} state × {len(VIEWPORTS)} viewport")
    if failed:
        print()
        print(f"  **押せなかった操作が {len(failed)} 件ある。**")
        for line in failed:
            print(f"    - {line}")
        print("  撮れた枚数だけを見て PASS にしない。")
    print()
    print("  撮っただけでは Gate を通っていない。**全部開いて**評価し、")
    print("  round-5/manifest.md へ書くこと。")
    # 押せなかった操作があるなら、**それは失敗である。**
    return 1 if failed else 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        print("usage: python scripts/capture_quality_gate_r5.py <build_dir> <out_dir>")
        raise SystemExit(2)
    raise SystemExit(main(pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])))
