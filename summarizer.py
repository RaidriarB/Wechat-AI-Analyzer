#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
聊天记录汇总模块

该模块用于读取分块处理的结果文件，进行汇总分析并生成最终报告。
"""

import os
import json
from openai import OpenAI
from typing import List, Dict, Any


def read_result_files(chunks_dir: str) -> List[Dict[str, Any]]:
    """
    读取所有result_*.txt文件并解析其中的JSON数据
    
    Args:
        chunks_dir (str): 包含结果文件的目录路径
        
    Returns:
        List[Dict[str, Any]]: 解析后的JSON数据列表
    """
    results = []
    
    # 获取所有result_*.txt文件
    result_files = [f for f in os.listdir(chunks_dir) if f.startswith('result_') and f.endswith('.txt')]
    
    for file_name in sorted(result_files):
        file_path = os.path.join(chunks_dir, file_name)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                # 移除可能的Markdown代码块标记
                content = content.replace('```json', '').replace('```', '')
                data = json.loads(content)
                results.append(data)
        except Exception as e:
            print(f"读取文件 {file_name} 时出错: {e}")
    
    return results


def merge_topics(results: List[Dict[str, Any]], top_n: int = None) -> List[Dict[str, Any]]:
    """
    合并所有话题并按message_count排序
    
    Args:
        results (List[Dict[str, Any]]): 解析后的JSON数据列表
        top_n (int, optional): 选取的话题数量，默认为None表示选取所有话题
        
    Returns:
        List[Dict[str, Any]]: 排序后的话题列表
    """
    all_topics = []
    
    # 收集所有话题
    for result in results:
        if 'topics' in result:
            all_topics.extend(result['topics'])
    
    # 按message_count排序
    sorted_topics = sorted(all_topics, key=lambda x: x.get('message_count', 0), reverse=True)
    
    # 如果指定了top_n，只返回前N个话题
    if top_n is not None:
        return sorted_topics[:top_n]
    
    return sorted_topics


def generate_final_report(topics: List[Dict[str, Any]], api_key: str, prompt_file: str) -> str:
    """
    使用DeepSeek API生成最终报告
    
    Args:
        topics (List[Dict[str, Any]]): 排序后的话题列表
        api_key (str): DeepSeek API密钥
        prompt_file (str): 提示词文件路径
        
    Returns:
        str: 生成的报告内容
    """
    try:
        # 读取提示词
        with open(prompt_file, 'r', encoding='utf-8') as f:
            prompt = f.read()
        
        # 将话题列表转换为JSON字符串
        topics_json = json.dumps(topics, ensure_ascii=False, indent=2)
        
        # 创建OpenAI客户端
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        
        # 发送请求
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": topics_json}
            ],
            max_tokens=8000,
            temperature=0.7,
            stream=False
        )
        
        # 返回生成的报告
        return response.choices[0].message.content
    except Exception as e:
        print(f"生成报告时出错: {e}")
        return None


def save_report(report: str, output_dir: str) -> bool:
    """
    保存生成的报告
    
    Args:
        report (str): 报告内容
        output_dir (str): 输出目录路径
        
    Returns:
        bool: 是否成功保存报告
    """
    try:
        report_file = os.path.join(output_dir, 'final_report.txt')
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"报告已保存到: {report_file}")
        return True
    except Exception as e:
        print(f"保存报告时出错: {e}")
        return False


def summarize_chat(chunks_dir: str, output_dir: str, api_key: str, prompt_file: str, top_n: int = None) -> bool:
    """
    汇总聊天记录并生成最终报告
    
    Args:
        chunks_dir (str): 包含结果文件的目录路径
        output_dir (str): 输出目录路径
        api_key (str): DeepSeek API密钥
        prompt_file (str): 提示词文件路径
        top_n (int, optional): 选取的话题数量，默认为None
        
    Returns:
        bool: 是否成功生成报告
    """
    # 读取所有结果文件
    results = read_result_files(chunks_dir)
    if not results:
        print("未找到任何结果文件")
        return False
    
    # 合并并排序话题
    sorted_topics = merge_topics(results, top_n)
    if not sorted_topics:
        print("未找到任何有效话题")
        return False
    
    # 生成最终报告
    report = generate_final_report(sorted_topics, api_key, prompt_file)
    if not report:
        print("生成报告失败")
        return False
    
    # 保存报告
    return save_report(report, output_dir)