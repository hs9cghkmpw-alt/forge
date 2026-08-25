"""Web Capability — **調べる力を、命令を受けない形で与える**
(FORGE-020 §16・§17、2026-08-25)。

---

## Model にブラウザを直接持たせない

「Model がブラウザを操作する」形にすると、開く URL も押す場所も
Model が決める。Model の入力には**さっき読んだページ**が混ざるので、
ページが次の行き先を決められることになる。

だから Forge が道具として持つ。

```
web_search(query)          → 出典付きの結果一覧
fetch_url(url)             → HTML → sanitize → 本文抽出 → chunk
browser_open(url)          → 実ブラウザで開く（Playwright）
browser_extract_text()     → 描画後の本文
browser_screenshot()       → 画像（Vision Model 用の Evidence 契約）
browser_click(target)      → **利用者の確認が要る**（購入・送信になりうる）
```

## 取ってきたものは必ず `UntrustedContent`

`fetch_url` は `str` を返さない。`UntrustedContent` を返す。
包みを解かないと本文が取り出せないので、**うっかりプロンプトへ連結
できない**（`untrusted.py`）。

## script / style / nav を落とす

本文抽出は「読むべき文章」だけにする。`<script>` の中身は Model に
とって雑音であるだけでなく、**注入の置き場所**でもある。

## この環境では実ネットワークへ出ていない（正直な申告）

Search Provider も設定していないし、外向きは agent proxy 経由で
多くの host が拒否される。したがって

* `WebSearchTool` は **Provider 未設定なら結果0件を返す**（作り話をしない）
* `fetch_url` の HTTP 往復は **単体テストのみ**（`httpx.MockTransport`）
* `BrowserSession` は Playwright が在るときだけ動く

**UNVERIFIED: 実 Web に対する往復は行っていない。**
"""

from __future__ import annotations

import html
import re
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol

import httpx

from app.ai.agent.untrusted import UntrustedContent

__all__ = [
    "SearchProvider",
    "WebFetchError",
    "WebFetcher",
    "WebSearchResult",
    "WebSearchTool",
    "extract_main_text",
    "chunk_text",
]


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WebSearchResult:
    """検索結果1件。**出典を必ず持つ**（§16）。

    出典の無い「AIが言っていた」を Knowledge へ入れない。
    """

    title: str
    url: str
    snippet: str
    source_domain: str
    retrieved_at: float

    def to_dict(self) -> dict[str, object]:
        return {
            "title": self.title, "url": self.url, "snippet": self.snippet,
            "source_domain": self.source_domain, "retrieved_at": self.retrieved_at,
        }


class SearchProvider(Protocol):
    """検索の実体。**Forge は特定の検索サービスに縛られない。**"""

    name: str

    def search(self, query: str, *, limit: int) -> Sequence[WebSearchResult]: ...


class WebSearchTool:
    """`web_search(query)`。

    **Provider が無ければ0件を返す。** 「たぶんこういうページがある」
    を作らない——作り話は Knowledge の毒である（§27 の poison check が
    拾う前に、そもそも作らない）。
    """

    def __init__(self, provider: SearchProvider | None = None) -> None:
        self._provider = provider

    @property
    def configured(self) -> bool:
        return self._provider is not None

    def search(self, query: str, *, limit: int = 5) -> tuple[WebSearchResult, ...]:
        if self._provider is None:
            return ()
        return tuple(self._provider.search(query, limit=limit))


# ---------------------------------------------------------------------------
# Fetch / sanitize
# ---------------------------------------------------------------------------


class WebFetchError(Exception):
    """取得できなかった。**分類を持つ。**"""

    def __init__(self, kind: str, detail: str) -> None:
        super().__init__(detail)
        self.kind = kind


_DROP_BLOCKS = re.compile(
    r"<(script|style|noscript|template|svg|nav|header|footer|form|iframe)\b[^>]*>"
    r".*?</\1\s*>",
    re.IGNORECASE | re.DOTALL,
)
_COMMENTS = re.compile(r"<!--.*?-->", re.DOTALL)
_TAGS = re.compile(r"<[^>]+>")
_BLANKS = re.compile(r"\n{3,}")


def extract_main_text(markup: str) -> str:
    """HTML から**読むべき文章だけ**を残す。

    `<script>` を落とすのは雑音対策であると同時に**注入対策**でもある
    ——ページ作者が Model へ向けて書いた文を、本文と同じ重みで渡さない。

    完全な本文抽出ではない（Readability 相当の実装は持っていない）。
    **UNVERIFIED: 実サイトでの抽出品質は測っていない。**
    """
    text = _COMMENTS.sub(" ", markup)
    text = _DROP_BLOCKS.sub(" ", text)
    text = re.sub(r"<br\s*/?>|</p>|</div>|</li>|</h[1-6]>", "\n", text, flags=re.IGNORECASE)
    text = _TAGS.sub(" ", text)
    text = html.unescape(text)
    lines = [re.sub(r"[ \t　]+", " ", line).strip() for line in text.splitlines()]
    return _BLANKS.sub("\n\n", "\n".join(line for line in lines if line)).strip()


def chunk_text(text: str, *, size: int = 2000, overlap: int = 200) -> tuple[str, ...]:
    """Model の窓に入る大きさへ割る。**境界で文が切れても捨てない。**"""
    if size <= 0:
        msg = "chunk size must be positive"
        raise ValueError(msg)
    if not text:
        return ()
    step = max(1, size - max(0, overlap))
    chunks: list[str] = []
    for start in range(0, len(text), step):
        piece = text[start : start + size]
        if chunks and len(piece) <= max(0, overlap):
            # 直前の chunk に丸ごと含まれる尻尾を足さない。
            break
        chunks.append(piece)
    return tuple(chunks)


class WebFetcher:
    """`fetch_url(url)`。**戻り値は必ず `UntrustedContent`。**"""

    _MAX_BYTES = 2_000_000
    _ALLOWED_SCHEMES = frozenset({"http", "https"})

    def __init__(
        self,
        *,
        client: httpx.Client | None = None,
        timeout_seconds: float = 15.0,
        max_redirects: int = 5,
        now: object = time.time,
    ) -> None:
        self._client = client
        self._timeout = timeout_seconds
        self._max_redirects = max_redirects
        self._now = now

    def fetch(self, url: str) -> UntrustedContent:
        scheme = url.split(":", 1)[0].lower() if ":" in url else ""
        if scheme not in self._ALLOWED_SCHEMES:
            # `file://` / `data:` を許すと sandbox の外へ手が届く。
            raise WebFetchError("unsupported_scheme", "http/https 以外は取得しない")

        client = self._client or httpx.Client(
            timeout=self._timeout,
            follow_redirects=True,
            max_redirects=self._max_redirects,
        )
        try:
            response = client.get(url)
        except httpx.TooManyRedirects as error:
            raise WebFetchError("redirect_loop", "リダイレクトが多すぎる") from error
        except httpx.TimeoutException as error:
            raise WebFetchError("timeout", "時間内に応答しなかった") from error
        except httpx.HTTPError as error:
            raise WebFetchError("network", "取得できなかった") from error
        finally:
            if self._client is None:
                client.close()

        if response.status_code >= 400:
            raise WebFetchError("http_error", f"HTTP {response.status_code}")

        raw = response.content[: self._MAX_BYTES]
        markup = raw.decode(response.encoding or "utf-8", errors="replace")
        return UntrustedContent.from_web(
            source=url,
            text=extract_main_text(markup),
            retrieved_at=float(self._now()),
        )


# ---------------------------------------------------------------------------
# Browser（Screenshot Evidence 契約）
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScreenshotEvidence:
    """撮った画面の**契約**（§17）。

    **Model 非依存にしてある。** 将来 Vision Model が読むかもしれないし、
    人が見るだけかもしれない。どちらでも同じ形で残る。

    画像そのものはここに入れない——path だけ持つ。Evidence が本文を
    抱えると、Learning / Dataset へ流れたときに止められない。
    """

    url: str
    viewport_width: int
    viewport_height: int
    image_path: str
    captured_at: float
    inspected_by_human: bool = False
    """**人が実際に開いて見たか。**

    `False` のままなら Visual Review ではない（`AGENTS.md`）。
    「PNG を生成した」を「確認した」と数えないための欄である。
    """

    def to_dict(self) -> dict[str, object]:
        return {
            "url": self.url,
            "viewport": [self.viewport_width, self.viewport_height],
            "image_path": self.image_path,
            "captured_at": self.captured_at,
            "inspected_by_human": self.inspected_by_human,
        }


@dataclass
class BrowserSession:
    """`browser_open` / `extract_text` / `screenshot`。

    **Playwright が無ければ何もしない。** 勝手に install しない
    （`AGENTS.md` Agent Execution Policy）。
    """

    headless: bool = True
    viewport_width: int = 390
    viewport_height: int = 844
    _page: object = field(default=None, repr=False)
    _browser: object = field(default=None, repr=False)
    _playwright: object = field(default=None, repr=False)

    @staticmethod
    def available() -> bool:
        try:
            import playwright.sync_api  # noqa: F401, PLC0415
        except ImportError:
            return False
        return True

    def open(self, url: str) -> None:
        from playwright.sync_api import sync_playwright  # noqa: PLC0415

        if self._page is None:
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(headless=self.headless)  # type: ignore[union-attr]
            self._page = self._browser.new_page(  # type: ignore[union-attr]
                viewport={"width": self.viewport_width, "height": self.viewport_height},
            )
        self._page.goto(url, wait_until="networkidle")  # type: ignore[union-attr]

    def extract_text(self, *, source: str = "") -> UntrustedContent:
        """描画後の本文。**これも `UntrustedContent`。**"""
        if self._page is None:
            msg = "browser is not open"
            raise RuntimeError(msg)
        markup = self._page.content()  # type: ignore[union-attr]
        return UntrustedContent.from_web(
            source=source or self._page.url,  # type: ignore[union-attr]
            text=extract_main_text(markup),
            retrieved_at=time.time(),
        )

    def screenshot(self, path: str) -> ScreenshotEvidence:
        if self._page is None:
            msg = "browser is not open"
            raise RuntimeError(msg)
        self._page.screenshot(path=path, full_page=True)  # type: ignore[union-attr]
        return ScreenshotEvidence(
            url=self._page.url,  # type: ignore[union-attr]
            viewport_width=self.viewport_width,
            viewport_height=self.viewport_height,
            image_path=path,
            captured_at=time.time(),
            # **撮っただけでは確認ではない。**
            inspected_by_human=False,
        )

    def close(self) -> None:
        for closer in (self._browser, self._playwright):
            if closer is not None:
                stop = getattr(closer, "close", None) or getattr(closer, "stop", None)
                if stop is not None:
                    stop()
        self._page = self._browser = self._playwright = None


__all__ += ["BrowserSession", "ScreenshotEvidence"]
