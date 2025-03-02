#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
微信聊天记录分析工具

该工具用于分析微信聊天记录，生成用户的性格特点、兴趣爱好、个人简介等信息。
"""

import os
import pandas as pd
import argparse
from datetime import datetime
import json
from openai import OpenAI
from processor import *
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


def load_data_from_xls(file_path):
    """
    从XLS文件中读取聊天记录数据
    
    Args:
        file_path (str): XLS文件路径
        
    Returns:
        pandas.DataFrame: 包含聊天记录的数据框
    """
    try:
        # 尝试读取XLS文件
        print(f"正在读取文件: {file_path}")
        df = pd.read_excel(file_path)
        
        # 显示数据基本信息
        print(f"成功读取数据，共 {len(df)} 条记录")
        print("数据列名:", df.columns.tolist())
        print("数据预览:")
        print(df.head())
        
        return df
    except Exception as e:
        print(f"读取文件时出错: {e}")
        return None


def call_deepseek_api(text, api_key, prompt):
    """
    调用DeepSeek API进行文本处理
    
    Args:
        text (str): 要处理的文本
        api_key (str): DeepSeek API密钥
        prompt (str): 提示词
        
    Returns:
        str: API返回的处理结果
    """
    try:
        # 创建OpenAI客户端，设置base_url为DeepSeek API地址
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        
        # 发送请求
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": text}
            ],
            max_tokens=8000,
            temperature=0.7,
            stream=False
        )
        
        # 返回生成的内容
        return response.choices[0].message.content
    except Exception as e:
        print(f"调用API时出错: {e}")
        return None


def process_chat_chunks(chunks, api_key, prompt, output_dir, max_workers=10):
    """
    处理分割后的聊天记录块
    
    Args:
        chunks (list): 包含多个DataFrame的列表，每个DataFrame是一个聊天记录块
        api_key (str): DeepSeek API密钥
        prompt (str): 提示词
        output_dir (str): 输出目录
        max_workers (int): 最大线程数，默认为10
        
    Returns:
        list: 每个块的处理结果
    """
    results = [None] * len(chunks)  # 预分配结果列表以保持顺序
    
    # 创建分块结果目录
    chunks_dir = f"{output_dir}/chunks"
    if not os.path.exists(chunks_dir):
        os.makedirs(chunks_dir)
    
    def process_chunk(chunk_info):
        i, chunk = chunk_info
        print(f"\n处理第 {i+1}/{len(chunks)} 个块...")
        
        # 将块中的消息合并成文本
        chunk_text = "\n".join(chunk["StrContent"].astype(str))
        
        # 保存块文本到文件
        chunk_file = f"{chunks_dir}/chunk_{i+1}.txt"
        with open(chunk_file, "w", encoding="utf-8") as f:
            f.write(chunk_text)
        
        # 调用API处理块文本
        if api_key:
            print(f"调用DeepSeek API处理第 {i+1} 个块...")
            result = call_deepseek_api(chunk_text, api_key, prompt)
            
            if result:
                # 保存API处理结果
                result_file = f"{chunks_dir}/result_{i+1}.txt"
                with open(result_file, "w", encoding="utf-8") as f:
                    f.write(result)
                
                print(f"第 {i+1} 个块处理完成，结果已保存到: {result_file}")
                return i, result
            else:
                print(f"第 {i+1} 个块处理失败")
                return i, None
        else:
            print(f"未提供API密钥，跳过API处理，已保存块文本到: {chunk_file}")
            return i, None
    
    # 使用线程池并行处理
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有任务
        future_to_chunk = {executor.submit(process_chunk, (i, chunk)): i 
                         for i, chunk in enumerate(chunks)}
        
        # 收集结果
        for future in as_completed(future_to_chunk):
            try:
                i, result = future.result()
                if result:
                    results[i] = result
            except Exception as e:
                print(f"处理块时出错: {e}")
    
    # 过滤掉None值并合并结果
    results = [r for r in results if r is not None]
    
    # 如果有处理结果，合并所有结果
    if results and api_key:
        merged_result = "\n\n=== 分块处理结果汇总 ===\n\n" + "\n\n---\n\n".join(results)
        merged_file = f"{output_dir}/merged_results.txt"
        
        with open(merged_file, "w", encoding="utf-8") as f:
            f.write(merged_result)
        
        print(f"\n所有块的处理结果已合并到: {merged_file}")
    
    return results


def load_config():
    """加载配置文件"""
    config_path = Path(__file__).parent / 'config.json'
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"加载配置文件失败: {e}")
        return {}

def main():
    # 加载配置
    config = load_config()
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="微信聊天记录分析工具")
    parser.add_argument(
        "--input", "-i", 
        required=True, 
        help="输入的XLS文件路径"
    )
    parser.add_argument(
        "--max-chars", "-m",
        type=int,
        default=50000,
        help="分割聊天记录的最大字符数量，默认为50000"
    )
    parser.add_argument(
        "--summarize", "-S",
        action="store_true",
        help="是否生成汇总报告"
    )
    parser.add_argument(
        "--top-n", "-t",
        type=int,
        default=None,
        help="选取的话题数量，默认为全部话题"
    )

    args = parser.parse_args()
    
    # 检查输入文件是否存在
    if not os.path.exists(args.input):
        print(f"错误: 输入文件 '{args.input}' 不存在")
        return
    
    # 设置输出目录
    base_output_dir = config.get('output_dir', 'output')
    input_filename = os.path.splitext(os.path.basename(args.input))[0]
    output_dir = os.path.join(base_output_dir, input_filename)
    
    # 创建输出目录（如果不存在）
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"创建输出目录: {output_dir}")
    
    # 创建分块结果目录
    chunks_dir = os.path.join(output_dir, 'chunks')
    if not os.path.exists(chunks_dir):
        os.makedirs(chunks_dir)
        print(f"创建分块目录: {chunks_dir}")
    
    # 设置API密钥
    api_key = config.get('api_key')
    
    # 设置提示词文件路径
    prompts_dir = Path(config.get('prompts_dir', 'prompts'))
    prompt_file = prompts_dir / 'prompts.txt'
    sum_prompt_file = prompts_dir / 'sum-prompts.txt'
    
    # 读取数据
    chat_data = load_data_from_xls(args.input)
    
    if chat_data is not None:
        print("数据加载成功，准备进行后续分析...")
        
        # 预处理数据
        print("\n开始预处理数据...")
        processed_data = preprocess_data(chat_data)
        
        # 如果需要分割聊天记录
        if args.max_chars > 0:
            print(f"\n开始按最大字符数量 {args.max_chars} 分割聊天记录...")
            chunks = split_chat_by_chars(processed_data, max_chars=args.max_chars)
            
            # 调用API处理分割后的聊天记录
            if api_key:
                # 读取提示词
                prompt = ""
                if os.path.exists(prompt_file):
                    with open(prompt_file, "r", encoding="utf-8") as f:
                        prompt = f.read()
                else:
                    print(f"警告: 提示词文件 '{prompt_file}' 不存在，将使用空提示词")
                
                # 处理分割后的聊天记录
                print("\n开始处理分割后的聊天记录...")
                # 从配置文件中读取max_workers
                max_workers = config.get('max_workers', 10)
                process_results = process_chat_chunks(chunks, api_key, prompt, output_dir, max_workers=max_workers)
                
                if process_results:
                    print("\n分割处理完成！")
                    
                    # 如果需要生成汇总报告
                    if args.summarize:
                        print("\n开始生成汇总报告...")
                        from summarizer import summarize_chat
                        if summarize_chat(chunks_dir, output_dir, api_key, sum_prompt_file, args.top_n):
                            print("汇总报告生成成功！")
                        else:
                            print("汇总报告生成失败")
                else:
                    print("\n分割处理未完成或未生成结果")
            else:
                print("\n已完成聊天记录分割，跳过API处理")
        
        # 分析聊天内容
        print("\n开始分析聊天内容...")
        analysis_results = analyze_chat_content(processed_data)
        
        # 生成报告
        print("\n开始生成分析报告...")
        report_success = generate_report(analysis_results, output_dir)
        
        # 合并聊天记录到一个文件
        print("\n开始合并聊天记录...")
        merge_success = export_merged_chat(processed_data, output_dir)
        
        if report_success and merge_success:
            print(f"\n分析完成！报告和合并聊天记录已保存到 {output_dir} 目录")
        elif report_success:
            print(f"\n分析完成！报告已保存到 {output_dir} 目录，但合并聊天记录失败")
        elif merge_success:
            print(f"\n合并聊天记录已保存到 {output_dir} 目录，但报告生成失败")
        else:
            print("\n报告生成和合并聊天记录均失败")
    else:
        print("数据加载失败，程序终止")


if __name__ == "__main__":
    main()