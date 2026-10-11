"""通用打包导出：把模块结果装配为 zip bytes（README 索引 + 数据文件）。

skill_seekers 的 docs 专用打包在自身模块内；这里放跨模块通用的装配器，
供 bilibili_crawler / bilibili_tools / mediacrawler 的 archive 端点复用。
"""
from typing import Any

import zipfile
from io import BytesIO


def zip_bytes(files: dict[str, str | bytes]) -> bytes:
    """{归档路径: 文本或字节} → zip bytes（DEFLATED，UTF-8）。"""
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            data = content.encode("utf-8") if isinstance(content, str) else content
            zf.writestr(name, data)
    return buf.getvalue()


def readme_index(title: str, meta: list[tuple[str, Any]], toc: list[tuple[str, str]]) -> str:
    """归档 README.md：标题 + 键值元信息 + 文件目录表。"""
    lines = [f"# {title}", ""]
    for k, v in meta:
        lines.append(f"- {k}: {v}")
    lines += ["", "| file | 说明 |", "|---|---|"]
    for path, desc in toc:
        lines.append(f"| [{path}]({path}) | {desc} |")
    return "\n".join(lines).rstrip() + "\n"


def md_table(headers: list[str], rows: list[list[Any]]) -> str:
    """简单 markdown 表格（None → 空串，竖线转义）。"""
    def cell(v: Any) -> str:
        return str(v if v is not None else "").replace("|", "\\|").replace("\n", " ")

    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        out.append("| " + " | ".join(cell(v) for v in row) + " |")
    return "\n".join(out) + "\n"
