# 统一加载 data 目录：政策/说明类 PDF、文本，以及企业等 JSON 档案
import glob
import os
from typing import List

from llama_index.core import Document, SimpleDirectoryReader

from server.readers.json_enterprise import load_json_documents

# 与政策库、企业档案相关的常见扩展名（JSON 单独解析，不交给 SimpleDirectoryReader）
_TEXT_LIKE_EXTS = [".pdf", ".txt", ".docx", ".doc", ".md", ".markdown", ".html", ".htm"]


def _has_text_like_files(input_dir: str) -> bool:
    for ext in _TEXT_LIKE_EXTS:
        if glob.glob(os.path.join(input_dir, "**", f"*{ext}"), recursive=True):
            return True
    return False


def load_all_data_documents(input_dir: str) -> List[Document]:
    """
    合并目录中的 PDF/Office/文本 与 全部 JSON（企业信息等）。
    """
    input_dir = os.path.abspath(input_dir)
    if not os.path.isdir(input_dir):
        print(f"数据目录不存在: {input_dir}")
        return []

    documents: List[Document] = []

    if _has_text_like_files(input_dir):
        try:
            reader = SimpleDirectoryReader(
                input_dir=input_dir,
                recursive=True,
                required_exts=_TEXT_LIKE_EXTS,
                filename_as_id=True,
            )
            part = reader.load_data()
            documents.extend(part)
            print(f"SimpleDirectoryReader 加载 {len(part)} 个文件类文档")
        except Exception as e:
            print(f"SimpleDirectoryReader 加载失败: {e}")

    json_docs = load_json_documents(input_dir)
    documents.extend(json_docs)

    print(f"data 目录合计 {len(documents)} 个 Document 待入库")
    return documents
