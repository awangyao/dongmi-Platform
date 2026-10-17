# 政策 HTML 原文链接：从 data/address/address.txt 解析 URL，按文件名 stem（.html 前）建立映射
import os
import re
import pandas as pd
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse

import config

UUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.I,
)

_address_mtime: Optional[float] = None
_stem_to_url: Dict[str, str] = {}

# CSV文件映射
_csv_mtime: Optional[float] = None
_filename_to_policy: Dict[str, Tuple[str, str]] = {}  # 文件名 -> (政策名称, 链接)


def _address_file_path() -> str:
    return os.path.join(os.getcwd(), config.DATA_DIR, "address", "address.txt")


def _csv_file_path() -> str:
    """返回山东省招标平台.csv 的绝对路径。"""
    # 尝试多个可能的路径
    possible_paths = [
        os.path.join(os.getcwd(), config.DATA_DIR, "山东省招标平台.csv"),
        os.path.join(os.path.dirname(__file__), "..", config.DATA_DIR, "山东省招标平台.csv"),
        os.path.join(os.path.dirname(__file__), "..", "data", "山东省招标平台.csv"),
        os.path.join(os.getcwd(), "thinkrag-main", config.DATA_DIR, "山东省招标平台.csv")
    ]
    
    for path in possible_paths:
        if os.path.isfile(path):
            print(f"找到CSV文件: {path}")
            return path
    
    # 如果都找不到，返回默认路径
    default_path = os.path.join(os.getcwd(), config.DATA_DIR, "山东省招标平台.csv")
    print(f"未找到CSV文件，返回默认路径: {default_path}")
    print(f"当前工作目录: {os.getcwd()}")
    print(f"DATA_DIR: {config.DATA_DIR}")
    return default_path


def load_csv_mapping(force: bool = False) -> Dict[str, Tuple[str, str]]:
    """读取山东省招标平台.csv，建立文件名到政策名称和链接的映射。"""
    global _csv_mtime, _filename_to_policy
    path = _csv_file_path()
    if not os.path.isfile(path):
        _filename_to_policy = {}
        return _filename_to_policy
    mtime = os.path.getmtime(path)
    if not force and _filename_to_policy and _csv_mtime == mtime:
        return _filename_to_policy
    out: Dict[str, Tuple[str, str]] = {}
    try:
        # 读取CSV文件，指定编码为utf-8-sig以处理BOM
        df = pd.read_csv(path, encoding='utf-8-sig')
        for _, row in df.iterrows():
            # 检查前三列是否有值
            if pd.notna(row.iloc[0]) and pd.notna(row.iloc[1]) and pd.notna(row.iloc[2]):
                # 构建文件名：序号+政策名（去掉特殊字符）
                serial_number = str(int(row.iloc[0]))
                policy_name = str(row.iloc[1])
                link = str(row.iloc[2])
                # 清理政策名中的特殊字符，用于构建文件名
                clean_name = re.sub(r'[\\/:*?"<>|]', '_', policy_name)
                # 构建文件名格式：序号+政策名.pdf
                filename = f"{serial_number}{clean_name}.pdf"
                out[filename] = (policy_name, link)
    except Exception as e:
        print(f"读取CSV文件失败: {e}")
        _filename_to_policy = {}
        return _filename_to_policy
    _filename_to_policy = out
    _csv_mtime = mtime
    return out


def get_policy_info_by_serial(serial_number: str) -> Optional[Tuple[str, str, str]]:
    """根据序号获取政策信息：(政策名称, 链接, 文件名)"""
    # 直接从CSV文件中读取
    path = _csv_file_path()
    if not os.path.isfile(path):
        return None
    try:
        # 读取CSV文件，指定编码为utf-8-sig以处理BOM
        df = pd.read_csv(path, encoding='utf-8-sig')
        # 遍历每一行
        for _, row in df.iterrows():
            # 检查序号是否匹配
            if pd.notna(row.iloc[0]):
                try:
                    csv_serial = str(int(row.iloc[0]))
                    if csv_serial == serial_number:
                        # 第二列是政策名称
                        policy_name = str(row.iloc[1])
                        # 第三列是链接
                        link = str(row.iloc[2])
                        # 构建文件名
                        clean_name = re.sub(r'[\\/:*?"<>|]', '_', policy_name)
                        filename = f"{serial_number}{clean_name}.pdf"
                        return (policy_name, link, filename)
                except Exception:
                    # 忽略处理行时的错误
                    pass
    except Exception:
        # 忽略读取CSV文件时的错误
        pass
    return None


def load_stem_to_url_map(force: bool = False) -> Dict[str, str]:
    """读取 address.txt，建立 stem（不含 .html）-> 完整 URL。同一 stem 多行时后者覆盖前者。"""
    global _address_mtime, _stem_to_url
    path = _address_file_path()
    if not os.path.isfile(path):
        _stem_to_url = {}
        return _stem_to_url
    mtime = os.path.getmtime(path)
    if not force and _stem_to_url and _address_mtime == mtime:
        return _stem_to_url
    out: Dict[str, str] = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            stem = stem_from_policy_url(line)
            if stem:
                out[stem] = line
    _stem_to_url = out
    _address_mtime = mtime
    return _stem_to_url


def stem_from_policy_url(url: str) -> Optional[str]:
    """从政策页 URL 取路径最后一段去掉 .html 作为 stem。"""
    try:
        path = urlparse(url).path.rstrip("/")
        if not path:
            return None
        name = path.rsplit("/", 1)[-1]
        if name.lower().endswith(".html"):
            return name[:-5]
        return Path(name).stem or None
    except Exception:
        return None


def _stems_from_metadata(metadata: Dict[str, Any]) -> Set[str]:
    stems: Set[str] = set()
    fn = metadata.get("file_name") or metadata.get("filename")
    if fn:
        stems.add(Path(str(fn)).stem)
    for key in ("url_source", "source_url", "document_url", "url"):
        u = metadata.get(key)
        if isinstance(u, str) and u.startswith("http"):
            s = stem_from_policy_url(u)
            if s:
                stems.add(s)
    return stems


def _stems_from_node_text(text: str, max_len: int = 2000) -> Set[str]:
    """从片段正文中匹配 UUID（与政策文件名一致时）。"""
    return set(UUID_RE.findall(text[:max_len]))


def collect_policy_links_from_nodes(nodes: Any) -> List[Tuple[str, str]]:
    """
    根据检索到的节点，在 CSV 映射中查找对应官方链接。
    返回 [(显示名, url), ...] 已按 URL 去重。
    """
    # 加载CSV映射（只加载一次）
    csv_mapping = load_csv_mapping()
    seen_urls: Set[str] = set()
    out: List[Tuple[str, str]] = []

    for nws in nodes:
        node = getattr(nws, "node", nws)
        md = getattr(node, "metadata", None) or {}

        # 获取文件名
        file_name = md.get("file_name", "") or md.get("filename", "")
        
        # 从 CSV 映射中查找
        if file_name:
            policy_name = file_name
            url = ""
            
            # 首先尝试直接从文件名匹配
            if file_name in csv_mapping:
                policy_name, url = csv_mapping[file_name]
            else:
                # 尝试从文件名中提取序号，然后根据序号查找
                # 匹配文件名开头的数字作为序号
                serial_match = re.match(r'^(\d+)', file_name)
                if serial_match:
                    serial_number = serial_match.group(1)
                    # 直接从CSV文件中获取
                    policy_info = get_policy_info_by_serial(serial_number)
                    if policy_info:
                        policy_name, url, _ = policy_info
            
            # 只使用从CSV文件中获取的链接
            if url and url not in seen_urls and "example.com" not in url:
                seen_urls.add(url)
                out.append((policy_name, url))

    return out


def policy_link_appendix_for_prompt(nodes: Any) -> str:
    """
    拼接到用户问题末尾，供大模型在回答中使用 Markdown 超链接。
    """
    # 首先尝试从 collect_policy_links_from_nodes 获取链接
    pairs = collect_policy_links_from_nodes(nodes)
    
    if not pairs:
        # 即使没有找到链接，也尝试从CSV文件中根据序号获取
        new_pairs = []
        seen_urls = set()
        for nws in nodes:
            node = getattr(nws, "node", nws)
            md = getattr(node, "metadata", None) or {}
            file_name = md.get("file_name", "") or md.get("filename", "")
            if file_name:
                # 尝试从文件名中提取序号，然后根据序号查找
                serial_match = re.match(r'^(\d+)', file_name)
                if serial_match:
                    serial_number = serial_match.group(1)
                    # 直接从CSV文件中获取
                    policy_info = get_policy_info_by_serial(serial_number)
                    if policy_info:
                        policy_name, url, _ = policy_info
                        # 过滤掉 example.com 这样的默认链接
                        if url and url not in seen_urls and "example.com" not in url:
                            seen_urls.add(url)
                            new_pairs.append((policy_name, url))
        if new_pairs:
            pairs = new_pairs
    
    if not pairs:
        return ""
    
    # 构建提示词附录
    lines = [
        "",
        "【官方原文链接（与本次检索片段对应，请在推荐政策时附上 Markdown 超链接）】",
        "每条政策在写出名称或要点后，请追加：`[查看原文](URL)`，其中 URL 必须从下列列表选取，勿编造。",
    ]
    for name, url in pairs:
        # 过滤掉 example.com 这样的默认链接
        if "example.com" not in url:
            lines.append(f"- `{name}` → {url}")
    
    return "\n".join(lines)


def markdown_policy_links_block(nodes: Any) -> str:
    """供 Streamlit 展示的 Markdown 区块。"""
    pairs = collect_policy_links_from_nodes(nodes)
    if not pairs:
        return ""
    lines = ["", "**官方原文链接**"]
    for name, url in pairs:
        # 过滤掉 example.com 这样的默认链接
        if "example.com" not in url:
            lines.append(f"- [{name}]({url})")
    return "\n".join(lines)
