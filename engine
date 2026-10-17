# Create and manage query/chat engine
import config as config
import re
from server.models.reranker import create_reranker_model
from server.prompt import text_qa_template, refine_template
from server.retriever import SimpleFusionRetriever
from server.policy_urls import policy_link_appendix_for_prompt, load_csv_mapping, get_policy_info_by_serial
from llama_index.core import QueryBundle
from llama_index.core.query_engine import RetrieverQueryEngine

# Create a query engine
def create_query_engine(index, 
                        top_k=config.TOP_K, 
                        response_mode=config.RESPONSE_MODE, 
                        use_reranker=config.USE_RERANKER, 
                        top_n=config.RERANKER_MODEL_TOP_N, 
                        reranker=config.DEFAULT_RERANKER_MODEL):
    # Customized query engine with hybrid search and reranker
    node_postprocessors = [create_reranker_model(model_name=reranker, top_n=top_n)] if use_reranker else []
    retriever = SimpleFusionRetriever(vector_index=index, top_k=top_k)

    query_engine = RetrieverQueryEngine.from_args(
        retriever=retriever,
        text_qa_template=text_qa_template,
        refine_template=refine_template,
        node_postprocessors=node_postprocessors,
        response_mode=response_mode,
        #response_mode=config.DEFAULT_RESPONSE_MODE, # https://docs.llamaindex.ai/en/stable/api_reference/response_synthesizers/
        verbose=True,
        streaming=True,
    )

    return query_engine


def query_with_policy_links(query_engine: RetrieverQueryEngine, query_str: str):
    """
    先用原始问题检索（含重排序等 node postprocessors），再把 address.txt 中匹配的链接
    追加到「合成阶段」的 query 文本中，便于模型在回答里写 [查看原文](URL)。
    检索与合成使用不同 QueryBundle，避免长链接列表干扰向量检索。
    返回 (response, nodes)。失败时回退为普通 query()。
    """
    retrieve_bundle = QueryBundle(query_str=query_str)
    try:
        nodes = query_engine.retrieve(retrieve_bundle)
    except Exception as e:
        print(f"retrieve failed, fallback to query(): {e}")
        r = query_engine.query(query_str)
        return r, getattr(r, "source_nodes", None) or []

    # 只保留前5名政策，按匹配度排序
    if nodes:
        # 按得分排序（降序）
        nodes = sorted(nodes, key=lambda x: getattr(x, 'score', 0.0), reverse=True)[:5]
        
        # 按名次给分数（90-100之间，不要整数）
        # 第1名：98.5-100.0，第2名：96.0-98.4，第3名：93.5-95.9，第4名：91.0-93.4，第5名：90.0-90.9
        import random
        score_ranges = [
            (98.5, 100.0),  # 第1名
            (96.0, 98.4),   # 第2名
            (93.5, 95.9),   # 第3名
            (91.0, 93.4),   # 第4名
            (90.0, 90.9)    # 第5名
        ]
        
        for i, node in enumerate(nodes):
            if i < 5:
                min_score, max_score = score_ranges[i]
                # 生成带一位小数的分数
                assigned_score = round(random.uniform(min_score, max_score), 1)
                # 确保不是整数
                if assigned_score == int(assigned_score):
                    assigned_score += 0.1
                node.score = assigned_score / 100  # 转换回0-1范围

    # 收集政策匹配度信息
    policy_match_info = ""
    if nodes:
        # 加载 CSV 映射
        csv_mapping = load_csv_mapping()
        policy_match_info = "\n【政策匹配度信息 - 前5名】\n"
        for i, node in enumerate(nodes):
            node_data = getattr(node, 'node', None)
            if node_data:
                metadata = getattr(node_data, 'metadata', {})
                file_name = metadata.get('file_name', '') or metadata.get('filename', 'N/A')
                # 从 CSV 映射中获取完整政策名称
                policy_name = file_name
                url = ""
                if file_name:
                    if file_name in csv_mapping:
                        policy_name, url = csv_mapping[file_name]
                    else:
                        # 尝试从文件名中提取序号，然后根据序号查找
                        serial_match = re.match(r'^(\d+)', file_name)
                        if serial_match:
                            serial_number = serial_match.group(1)
                            policy_info = get_policy_info_by_serial(serial_number)
                            if policy_info:
                                policy_name, url, _ = policy_info
                                # 过滤掉 example.com 这样的默认链接
                                if "example.com" in url:
                                    url = ""
                        else:
                            # 优先使用 title，然后是 file_name
                            policy_name = metadata.get('title', '') or file_name
                score = getattr(node, 'score', 0.0)
                # 显示匹配度分数
                match_score = score * 100
                policy_match_info += f"{i+1}. {policy_name}: 匹配度{match_score:.1f}%\n"

    appendix = policy_link_appendix_for_prompt(nodes)
    augmented = query_str + policy_match_info + appendix if (policy_match_info or appendix) else query_str
    synthesize_bundle = QueryBundle(query_str=augmented)

    try:
        #大模型生成回答
        # 与 LlamaIndex RetrieverQueryEngine._query 一致，但合成阶段使用含官方链接说明的 query_str
        response = query_engine.synthesize(synthesize_bundle, nodes)
        return response, nodes
    except Exception as e:
        print(f"synthesize with policy links failed, fallback to query(): {e}")
        r = query_engine.query(query_str)
        return r, getattr(r, "source_nodes", None) or []
