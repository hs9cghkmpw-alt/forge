"""生成 Source の **Effect（外界への作用）** を取り出す（SEC-05）。

## なぜ「危険文字列の有無」ではないのか

禁止語 list は、語を避ければ通る。`"sub" + "process"` と書けば抜ける。
ここで取るのは語ではなく **Effect**——「外の世界に何をするか」である。

  Effect が宣言と食い違う → Promotion 拒否
  Effect が読めない       → UNKNOWN → **拒否**（fail closed）

## 言語ごとに仕組みが違ってよい

Python は AST、Dart は構文走査で取る。無理に同じ処理へ寄せない。
**共通なのは Policy（何を重大とみなすか）であって、取り方ではない。**

## この検査が「安全 100%」を意味しないこと

静的検査は書かれたものしか見ない。実行時にしか現れない振る舞いは
Sandbox 側の仕事である。**片方だけでは足りない。**
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import PurePosixPath


class EffectKind(str, Enum):
    """生成物が外界へ及ぼしうる作用。**Permission へ写像できる粒度で切る。**"""

    FILESYSTEM_READ = "filesystem_read"
    FILESYSTEM_WRITE = "filesystem_write"
    DESTRUCTIVE_FILESYSTEM = "destructive_filesystem"
    NETWORK = "network"
    PROCESS_SPAWN = "process_spawn"
    SHELL = "shell"
    DYNAMIC_CODE = "dynamic_code"
    ENVIRONMENT_READ = "environment_read"
    CREDENTIAL_ACCESS = "credential_access"
    NATIVE_LIBRARY = "native_library"
    PERSISTENCE = "persistence"
    PACKAGE_INSTALL = "package_install"
    CODE_DOWNLOAD = "code_download"
    UNKNOWN = "unknown"
    """**読めなかった。** 安全側ではなく危険側へ倒すための値。"""


#: 生成 Capability が持ってよい理由が無い Effect。**宣言があっても通さない。**
#:
#: Tier C を人が承認すれば通る、という筋も考えたが採らない。ここで扱うのは
#: 「AI が書いた Source を Forge 本体へ載せる」経路であり、shell や
#: 動的コード実行を載せてよい正当な理由が現時点で無い。必要になった時点で
#: 個別に議論する——**先に穴を開けておかない。**
PROHIBITED_EFFECTS = frozenset(
    {
        EffectKind.SHELL,
        EffectKind.DYNAMIC_CODE,
        EffectKind.PROCESS_SPAWN,
        EffectKind.CREDENTIAL_ACCESS,
        EffectKind.PACKAGE_INSTALL,
        EffectKind.CODE_DOWNLOAD,
        EffectKind.DESTRUCTIVE_FILESYSTEM,
        EffectKind.PERSISTENCE,
        EffectKind.NATIVE_LIBRARY,
        EffectKind.UNKNOWN,
    }
)


@dataclass(frozen=True, slots=True)
class EffectFinding:
    path: str
    effect: EffectKind
    detail: str
    line: int = 0

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "effect": self.effect.value,
            "detail": self.detail,
            "line": self.line,
        }


@dataclass(frozen=True, slots=True)
class SourceInspectionResult:
    effects: frozenset[EffectKind]
    findings: tuple[EffectFinding, ...]
    files_inspected: int
    imports: frozenset[str] = field(default_factory=frozenset)
    """観測した**外部**依存。**宣言ではなく実際に書かれているもの。**"""

    internal_imports: frozenset[str] = field(default_factory=frozenset)
    """artifact 自身の中を指す import。依存ではないので allowlist へ問わない。

    生成テストが隣の `capability_impl` を import するのはごく普通であり、
    これを「未知の依存」と呼ぶのは検査器の誤りである（2026-09-04 に実際に
    誤検出した）。**ただし「artifact の中にある」ことを確かめてから外す。**
    名前が似ているだけのものを内部扱いしない。
    """

    @property
    def prohibited(self) -> frozenset[EffectKind]:
        return frozenset(self.effects & PROHIBITED_EFFECTS)

    @property
    def clean(self) -> bool:
        return not self.prohibited

    def to_dict(self) -> dict:
        return {
            "effects": sorted(e.value for e in self.effects),
            "prohibited": sorted(e.value for e in self.prohibited),
            "files_inspected": self.files_inspected,
            "imports": sorted(self.imports),
            "internal_imports": sorted(self.internal_imports),
            "findings": [f.to_dict() for f in self.findings],
        }


# --------------------------------------------------------------------------
# Python
# --------------------------------------------------------------------------

_PY_MODULE_EFFECTS = {
    "os": EffectKind.FILESYSTEM_WRITE,
    "sys": EffectKind.ENVIRONMENT_READ,
    "subprocess": EffectKind.PROCESS_SPAWN,
    "socket": EffectKind.NETWORK,
    "ssl": EffectKind.NETWORK,
    "http": EffectKind.NETWORK,
    "urllib": EffectKind.NETWORK,
    "requests": EffectKind.NETWORK,
    "httpx": EffectKind.NETWORK,
    "ftplib": EffectKind.NETWORK,
    "smtplib": EffectKind.NETWORK,
    "asyncio": EffectKind.NETWORK,
    "shutil": EffectKind.DESTRUCTIVE_FILESYSTEM,
    "pathlib": EffectKind.FILESYSTEM_READ,
    "tempfile": EffectKind.FILESYSTEM_WRITE,
    "ctypes": EffectKind.NATIVE_LIBRARY,
    "cffi": EffectKind.NATIVE_LIBRARY,
    "importlib": EffectKind.DYNAMIC_CODE,
    "pickle": EffectKind.DYNAMIC_CODE,
    "marshal": EffectKind.DYNAMIC_CODE,
    "shelve": EffectKind.PERSISTENCE,
    "sqlite3": EffectKind.PERSISTENCE,
    "pip": EffectKind.PACKAGE_INSTALL,
    "setuptools": EffectKind.PACKAGE_INSTALL,
    "keyring": EffectKind.CREDENTIAL_ACCESS,
    "netrc": EffectKind.CREDENTIAL_ACCESS,
    "webbrowser": EffectKind.PROCESS_SPAWN,
    "multiprocessing": EffectKind.PROCESS_SPAWN,
    "threading": EffectKind.PROCESS_SPAWN,
}

_PY_CALL_EFFECTS = {
    "eval": EffectKind.DYNAMIC_CODE,
    "exec": EffectKind.DYNAMIC_CODE,
    "compile": EffectKind.DYNAMIC_CODE,
    "__import__": EffectKind.DYNAMIC_CODE,
    "open": EffectKind.FILESYSTEM_READ,
    "input": EffectKind.ENVIRONMENT_READ,
    "breakpoint": EffectKind.DYNAMIC_CODE,
    # 名前を組み立てて間接的に取りに行く書き方。**禁止語を避けても、
    # 行為としては動的コード解決である**（2026-09-04、自己攻撃で追加）。
    "getattr": EffectKind.DYNAMIC_CODE,
    "setattr": EffectKind.DYNAMIC_CODE,
    "delattr": EffectKind.DYNAMIC_CODE,
    "globals": EffectKind.DYNAMIC_CODE,
    "locals": EffectKind.DYNAMIC_CODE,
    "vars": EffectKind.DYNAMIC_CODE,
}

_PY_ATTRIBUTE_EFFECTS = {
    "system": EffectKind.SHELL,
    "popen": EffectKind.SHELL,
    "spawn": EffectKind.PROCESS_SPAWN,
    "spawnl": EffectKind.PROCESS_SPAWN,
    "spawnv": EffectKind.PROCESS_SPAWN,
    "fork": EffectKind.PROCESS_SPAWN,
    "execv": EffectKind.PROCESS_SPAWN,
    "execve": EffectKind.PROCESS_SPAWN,
    "environ": EffectKind.ENVIRONMENT_READ,
    "getenv": EffectKind.ENVIRONMENT_READ,
    "putenv": EffectKind.ENVIRONMENT_READ,
    "remove": EffectKind.DESTRUCTIVE_FILESYSTEM,
    "unlink": EffectKind.DESTRUCTIVE_FILESYSTEM,
    "rmtree": EffectKind.DESTRUCTIVE_FILESYSTEM,
    "rmdir": EffectKind.DESTRUCTIVE_FILESYSTEM,
    "truncate": EffectKind.DESTRUCTIVE_FILESYSTEM,
    "chmod": EffectKind.DESTRUCTIVE_FILESYSTEM,
    "connect": EffectKind.NETWORK,
    "urlopen": EffectKind.NETWORK,
    "socket": EffectKind.NETWORK,
    "load_module": EffectKind.DYNAMIC_CODE,
    "loads": EffectKind.DYNAMIC_CODE,
}

#: **秘密を探しに行く**書き方。値ではなく「探索する行為」を見る。
#: 実値は決してここへ書かない（CLAUDE.md §4）。
_SECRET_NAME_RE = re.compile(
    r"(?i)\b(api[_-]?key|secret|token|password|passwd|credential|private[_-]?key"
    r"|access[_-]?key|auth[_-]?token|bearer)\b"
)


class _PythonEffectVisitor(ast.NodeVisitor):
    def __init__(self, path: str) -> None:
        self.path = path
        self.findings: list[EffectFinding] = []
        self.imports: set[str] = set()

    def _add(self, effect: EffectKind, detail: str, node: ast.AST) -> None:
        self.findings.append(
            EffectFinding(
                path=self.path,
                effect=effect,
                detail=detail,
                line=getattr(node, "lineno", 0),
            )
        )

    def _module(self, module: str | None, node: ast.AST) -> None:
        if not module:
            return
        root = module.split(".")[0]
        self.imports.add(root)
        effect = _PY_MODULE_EFFECTS.get(root)
        if effect is not None:
            self._add(effect, f"import {module}", node)

    def visit_Import(self, node: ast.Import) -> None:  # noqa: N802
        for alias in node.names:
            self._module(alias.name, node)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:  # noqa: N802
        if node.level:
            # 相対 import。artifact の外へは build_time_sandbox が別途効く。
            self.imports.add(".")
        self._module(node.module, node)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        func = node.func
        if isinstance(func, ast.Name):
            effect = _PY_CALL_EFFECTS.get(func.id)
            if effect is not None:
                self._add(effect, f"call {func.id}()", node)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:  # noqa: N802
        effect = _PY_ATTRIBUTE_EFFECTS.get(node.attr)
        if effect is not None:
            self._add(effect, f"attribute .{node.attr}", node)
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> None:  # noqa: N802
        # `os.environ["OPENAI_API_KEY"]` のような **秘密の名指し**。
        index = node.slice
        if isinstance(index, ast.Constant) and isinstance(index.value, str):
            if _SECRET_NAME_RE.search(index.value):
                self._add(
                    EffectKind.CREDENTIAL_ACCESS,
                    "secret-shaped lookup key",  # **値は書かない**
                    node,
                )
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:  # noqa: N802
        if isinstance(node.value, str) and _SECRET_NAME_RE.search(node.value):
            self._add(
                EffectKind.CREDENTIAL_ACCESS,
                "secret-shaped literal",  # **値は書かない**
                node,
            )
        self.generic_visit(node)


def inspect_python(path: str, content: str) -> tuple[list[EffectFinding], set[str]]:
    try:
        tree = ast.parse(content)
    except SyntaxError as error:
        # **読めないものを安全側へ倒さない。**
        return (
            [
                EffectFinding(
                    path=path,
                    effect=EffectKind.UNKNOWN,
                    detail=f"python source did not parse: {error.msg}",
                    line=error.lineno or 0,
                )
            ],
            set(),
        )
    visitor = _PythonEffectVisitor(path)
    visitor.visit(tree)
    return visitor.findings, visitor.imports


# --------------------------------------------------------------------------
# Dart
# --------------------------------------------------------------------------

_DART_IMPORT_RE = re.compile(
    r"^\s*(?:import|export|part)\s+(?:of\s+)?['\"]([^'\"]+)['\"]", re.MULTILINE
)

_DART_LIBRARY_EFFECTS = {
    "dart:io": EffectKind.FILESYSTEM_WRITE,
    "dart:isolate": EffectKind.PROCESS_SPAWN,
    "dart:ffi": EffectKind.NATIVE_LIBRARY,
    "dart:mirrors": EffectKind.DYNAMIC_CODE,
    "dart:html": EffectKind.NETWORK,
    "dart:js": EffectKind.DYNAMIC_CODE,
    "dart:js_interop": EffectKind.DYNAMIC_CODE,
    "dart:developer": EffectKind.DYNAMIC_CODE,
}

_DART_PACKAGE_EFFECTS = {
    "package:http/": EffectKind.NETWORK,
    "package:dio/": EffectKind.NETWORK,
    "package:web_socket_channel/": EffectKind.NETWORK,
    "package:path_provider/": EffectKind.FILESYSTEM_WRITE,
    "package:shared_preferences/": EffectKind.PERSISTENCE,
    "package:sqflite/": EffectKind.PERSISTENCE,
    "package:hive/": EffectKind.PERSISTENCE,
    "package:flutter_secure_storage/": EffectKind.CREDENTIAL_ACCESS,
    "package:process_run/": EffectKind.PROCESS_SPAWN,
}

#: Dart は AST parser を持ち込めないので token で取る。**import allowlist が
#: 主防御**であり、これは二重化である（片方を抜けてももう片方で落ちる）。
_DART_TOKEN_EFFECTS = (
    ("Process.run", EffectKind.PROCESS_SPAWN),
    ("Process.start", EffectKind.PROCESS_SPAWN),
    ("Process.runSync", EffectKind.PROCESS_SPAWN),
    ("Isolate.spawnUri", EffectKind.PROCESS_SPAWN),
    ("Isolate.spawn", EffectKind.PROCESS_SPAWN),
    ("DynamicLibrary", EffectKind.NATIVE_LIBRARY),
    ("HttpClient", EffectKind.NETWORK),
    ("Socket.connect", EffectKind.NETWORK),
    ("RawSocket", EffectKind.NETWORK),
    ("ServerSocket", EffectKind.NETWORK),
    ("WebSocket", EffectKind.NETWORK),
    ("InternetAddress", EffectKind.NETWORK),
    ("MethodChannel", EffectKind.NATIVE_LIBRARY),
    ("EventChannel", EffectKind.NATIVE_LIBRARY),
    ("BasicMessageChannel", EffectKind.NATIVE_LIBRARY),
    ("Platform.environment", EffectKind.ENVIRONMENT_READ),
    ("String.fromEnvironment", EffectKind.ENVIRONMENT_READ),
    ("int.fromEnvironment", EffectKind.ENVIRONMENT_READ),
    ("bool.fromEnvironment", EffectKind.ENVIRONMENT_READ),
    ("File(", EffectKind.FILESYSTEM_WRITE),
    ("Directory(", EffectKind.FILESYSTEM_WRITE),
    ("Link(", EffectKind.FILESYSTEM_WRITE),
    ("deleteSync", EffectKind.DESTRUCTIVE_FILESYSTEM),
    (".delete(", EffectKind.DESTRUCTIVE_FILESYSTEM),
)


def _strip_dart_comments(content: str) -> str:
    without_block = re.sub(r"/\*.*?\*/", "", content, flags=re.DOTALL)
    return re.sub(r"//.*", "", without_block)


def inspect_dart(path: str, content: str) -> tuple[list[EffectFinding], set[str]]:
    stripped = _strip_dart_comments(content)
    findings: list[EffectFinding] = []
    imports: set[str] = set()

    for uri in _DART_IMPORT_RE.findall(stripped):
        imports.add(uri)
        effect = _DART_LIBRARY_EFFECTS.get(uri)
        if effect is None:
            for prefix, package_effect in _DART_PACKAGE_EFFECTS.items():
                if uri.startswith(prefix):
                    effect = package_effect
                    break
        if effect is not None:
            findings.append(
                EffectFinding(path=path, effect=effect, detail=f"import {uri}")
            )

    for token, effect in _DART_TOKEN_EFFECTS:
        if token in stripped:
            findings.append(
                EffectFinding(path=path, effect=effect, detail=f"token {token}")
            )

    for match in _SECRET_NAME_RE.finditer(stripped):
        findings.append(
            EffectFinding(
                path=path,
                effect=EffectKind.CREDENTIAL_ACCESS,
                # **一致した語そのものを書かない。** 値でなくても出さない。
                detail="secret-shaped identifier",
            )
        )
        break

    return findings, imports


# --------------------------------------------------------------------------
# Dispatch
# --------------------------------------------------------------------------

_INSPECTORS = {
    ".py": inspect_python,
    ".dart": inspect_dart,
}

#: 中身に Effect が無いと分かっている宣言的 metadata。
#: **拡張子だけで安全と決めない**——JSON は実行されないから安全なのであって、
#: 「知らない拡張子」は UNKNOWN のままにする。
_INERT_SUFFIXES = frozenset({".json", ".md", ".txt", ".yaml", ".yml"})


def inspect_generated_sources(
    files: tuple[tuple[str, str], ...],
) -> SourceInspectionResult:
    """`(path, content)` の並びから Effect を取り出す。

    **知らない拡張子は UNKNOWN。** 「たぶん無害」で通さない。
    """
    findings: list[EffectFinding] = []
    imports: set[str] = set()

    # artifact の中に実在する module 名だけを「内部」と認める。
    internal_module_names = {
        PurePosixPath(path).stem
        for path, _ in files
        if PurePosixPath(path).suffix.lower() == ".py"
    }

    for path, content in files:
        suffix = PurePosixPath(path).suffix.lower()
        inspector = _INSPECTORS.get(suffix)
        if inspector is not None:
            file_findings, file_imports = inspector(path, content)
            findings.extend(file_findings)
            imports.update(file_imports)
            continue
        if suffix in _INERT_SUFFIXES:
            continue
        findings.append(
            EffectFinding(
                path=path,
                effect=EffectKind.UNKNOWN,
                detail=f"no inspector for suffix {suffix!r}; refusing to assume it is inert",
            )
        )

    internal = {name for name in imports if name in internal_module_names}
    return SourceInspectionResult(
        effects=frozenset(f.effect for f in findings),
        findings=tuple(findings),
        files_inspected=len(files),
        imports=frozenset(imports - internal),
        internal_imports=frozenset(internal),
    )
