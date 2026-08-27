"""Round 5 の撮影が**操作した証拠**になっていること（020A2 §7 / TD92）。

Round 4 までは「第1タブしか撮れていない」ことが manifest に書かれて
いた。書いただけでは次も同じなので、ここで**落ちる形**にする。

守るのは3つ。

1. **初期タブ以外を撮る state が、撮る app すべてにある。**
   全部 `None`（＝開いたまま撮るだけ）へ戻ったら落ちる。
2. **押す座標が本文の実幅から出ている。** 画面幅で割ると、
   desktop で本文の外（余白）を押す。実際に Round 5 で 4 件外した。
3. **座標の元になる値を Dart から読んでいる。** 写経すると黙ってずれる。
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys
import unittest

_ROOT = pathlib.Path(__file__).resolve().parents[2]


def _load():
    spec = importlib.util.spec_from_file_location(
        "_qg_r5", _ROOT / "scripts" / "capture_quality_gate_r5.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TestRound5ActuallyOperatesTheApp(unittest.TestCase):
    """「開いて撮るだけ」へ戻ったら落ちる。"""

    def setUp(self) -> None:
        self.r5 = _load()

    def test_every_captured_app_has_a_state_behind_a_tab(self) -> None:
        apps = {key for key, _state, _tab in self.r5.STATES}
        operated = {key for key, _state, tab in self.r5.STATES if tab is not None}
        self.assertEqual(
            apps,
            operated,
            "初期タブしか撮らない app がある。"
            " それは Round 4 と同じ『撮れていないだけ』である",
        )

    def test_more_than_one_state_per_app(self) -> None:
        for key in {k for k, _s, _t in self.r5.STATES}:
            states = [s for k, s, _t in self.r5.STATES if k == key]
            self.assertGreater(
                len(states), 1, f"{key} が1画面しか撮っていない",
            )

    def test_the_initial_tab_index_matches_the_renderer(self) -> None:
        """開いた直後に選ばれているタブ。Dart 側と揃っていること。"""
        dart = (
            _ROOT / "frontend" / "lib" / "json_ui" / "widget_registry"
            / "widget_registry_v1_7.dart"
        ).read_text(encoding="utf-8")
        self.assertIn(
            f"int _selectedIndex = {self.r5._INITIAL_TAB_INDEX};",
            dart,
            "初期タブが Renderer と食い違っている。"
            " 経由タブの要否を誤り、押せていないものを撮る",
        )


class TestTabCoordinatesComeFromTheRealLayout(unittest.TestCase):
    """desktop で本文の外を押さないこと。"""

    def setUp(self) -> None:
        self.r5 = _load()
        self.metrics = self.r5.layout_metrics()

    def test_metrics_are_read_from_the_renderer_source(self) -> None:
        max_content, padding = self.metrics
        dart = (
            _ROOT / "frontend" / "lib" / "json_ui" / "renderer"
            / "forge_renderer.dart"
        ).read_text(encoding="utf-8")
        self.assertIn(f"_maxContentWidth = {max_content:g};", dart)
        self.assertIn(f"EdgeInsets.all({padding:g})", dart)

    def test_it_refuses_to_guess_when_the_source_changes(self) -> None:
        """読めなければ**既定値で撮らない**。ずれに気付けなくなる。"""
        with self.assertRaises(RuntimeError):
            self.r5.layout_metrics(source="// no constants here")

    def test_every_tab_center_is_inside_the_content_box(self) -> None:
        max_content, padding = self.metrics
        for width in (320, 390, 834, 1440):
            inner = width - padding * 2
            content = min(inner, max_content)
            left = padding + (inner - content) / 2
            for count in (2, 3, 4):
                for index in range(count):
                    x = self.r5.tab_center_x(width, index, count, self.metrics)
                    self.assertGreater(x, left, f"{width}px の左余白を押している")
                    self.assertLess(
                        x, left + content, f"{width}px の右余白を押している",
                    )

    def test_wide_viewports_do_not_use_the_full_width(self) -> None:
        """**これが Round 5 で実際に外した罠。**

        1440px で画面幅を3等分すると index 0 は x=240 になるが、
        本文は 360 から始まる。押しても何も起きない。
        """
        x = self.r5.tab_center_x(1440, 0, 3, self.metrics)
        naive = 1440 * 0.5 / 3
        self.assertNotAlmostEqual(
            x, naive, msg="画面幅で割っている。desktop で余白を押す",
        )
        self.assertGreater(x, 1440 / 2 - self.metrics[0] / 2)

    def test_narrow_viewports_still_span_the_screen(self) -> None:
        """mobile では本文が上限より狭いので、ほぼ全幅のままであること。"""
        x = self.r5.tab_center_x(390, 0, 3, self.metrics)
        self.assertLess(abs(x - (16 + (390 - 32) * 0.5 / 3)), 0.01)


if __name__ == "__main__":
    unittest.main()
