from pathlib import Path

from docx import Document as DocxDocument
from PyPDF2 import PdfReader


def parse_document(file_path: str) -> str:
    """
    解析文档内容为纯文本。

    为了让项目更贴近课程设计场景，这里支持 txt、md、pdf、docx 四类文档。
    如果后续需要扩展 pptx、html，只需要继续补充分支即可。
    """

    suffix = Path(file_path).suffix.lower()
    if suffix in {".txt", ".md"}:
        return _read_text_file(file_path)
    if suffix == ".pdf":
        return _read_pdf(file_path)
    if suffix == ".docx":
        return _read_docx(file_path)
    raise ValueError(f"暂不支持解析的文件类型：{suffix}")


def _read_text_file(file_path: str) -> str:
    """读取普通文本文件。"""

    encodings = ["utf-8", "gb18030", "gbk", "latin-1"]
    for encoding in encodings:
        try:
            with open(file_path, "r", encoding=encoding) as file:
                return file.read()
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("text", b"", 0, 1, "无法识别文本编码")


def _read_pdf(file_path: str) -> str:
    """提取 PDF 文本。"""

    reader = PdfReader(file_path)
    texts = []
    for page in reader.pages:
        texts.append(page.extract_text() or "")
    return "\n".join(texts)


def _read_docx(file_path: str) -> str:
    """提取 DOCX 文本。"""

    document = DocxDocument(file_path)
    texts = [paragraph.text for paragraph in document.paragraphs]
    return "\n".join(texts)
