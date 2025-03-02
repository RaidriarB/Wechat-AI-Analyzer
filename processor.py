#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
微信聊天记录处理模块

该模块用于处理和分析微信聊天记录，提取用户特征和生成分析报告。
"""

import re
import pandas as pd
from collections import Counter
from datetime import datetime


def preprocess_data(df):
    """
    预处理聊天数据
    
    Args:
        df (pandas.DataFrame): 原始聊天记录数据框
        
    Returns:
        pandas.DataFrame: 预处理后的数据框
    """
    # 复制数据框，避免修改原始数据
    processed_df = df.copy()
    
    # 只保留文本消息(Type=1表示文本消息)
    text_messages = processed_df[processed_df['Type'] == 1]
    
    # 去除空消息
    text_messages = text_messages[text_messages['StrContent'].notna() & (text_messages['StrContent'] != '')]
    
    # 过滤XML格式信息（以'<'开头的内容）
    def filter_xml_content(text):
        if not isinstance(text, str):
            return text
        # 使用正则表达式移除所有以'<'开头的XML标签内容
        return re.sub(r'<[^>]*>', '', text)
    
    # 应用XML过滤函数到所有消息内容
    text_messages['StrContent'] = text_messages['StrContent'].apply(filter_xml_content)
    
    # 再次过滤可能变成空字符串的消息
    text_messages = text_messages[text_messages['StrContent'] != '']
    
    # 转换时间格式
    try:
        text_messages['DateTime'] = pd.to_datetime(text_messages['StrTime'])
    except:
        print("时间格式转换失败，将使用原始时间字符串")
    
    # 计算每条消息的字符数量
    text_messages['char_count'] = text_messages['StrContent'].str.len()
    
    print(f"预处理后的文本消息数量: {len(text_messages)}")
    return text_messages


def split_chat_by_chars(df, max_chars=50000):
    """
    将聊天记录按字符数量分割成多个小块
    
    Args:
        df (pandas.DataFrame): 预处理后的聊天记录数据框
        max_chars (int): 每个块的最大字符数量，默认为50000
        
    Returns:
        list: 包含多个DataFrame的列表，每个DataFrame是一个聊天记录块
    """
    chunks = []
    current_chunk = []
    current_chars = 0
    
    # 按时间排序
    sorted_df = df.sort_values(by='DateTime')
    
    for _, row in sorted_df.iterrows():
        # 计算当前消息的字符数量
        msg_chars = len(str(row['StrContent']))
        
        # 如果添加当前消息会超过限制，先保存当前块
        if current_chunk and (current_chars + msg_chars > max_chars):
            chunks.append(pd.DataFrame(current_chunk))
            current_chunk = []
            current_chars = 0
        
        # 将当前消息添加到当前块
        current_chunk.append(row)
        current_chars += msg_chars
        
        # 如果当前块已达到限制，立即保存并重置
        if current_chars >= max_chars:
            chunks.append(pd.DataFrame(current_chunk))
            current_chunk = []
            current_chars = 0
            continue
    
    # 添加最后一个块（如果有）
    if current_chunk:
        chunks.append(pd.DataFrame(current_chunk))
    
    print(f"聊天记录已分割成 {len(chunks)} 个块")
    for i, chunk in enumerate(chunks):
        total_chars = chunk['StrContent'].astype(str).str.len().sum()
        print(f"第 {i+1} 个块的字符数：{total_chars}")
    
    return chunks


def analyze_chat_content(df):
    """
    分析聊天内容，提取关键特征
    
    Args:
        df (pandas.DataFrame): 预处理后的聊天记录数据框
        keywords_count (int): 提取的关键词数量，默认为20
        
    Returns:
        dict: 包含分析结果的字典
    """
    results = {}
    
    # 按用户分组
    user_groups = df.groupby('Sender')
    
    for user, user_data in user_groups:
        # 计算消息频率
        message_count = len(user_data)
        try:
            time_span = (user_data['DateTime'].max() - user_data['DateTime'].min()).days
            msgs_per_day = message_count / max(time_span, 1)
        except:
            msgs_per_day = 0
            print(f"无法计算用户 {user} 的消息频率")
        
        # 分析消息长度
        msg_lengths = user_data['StrContent'].astype(str).apply(len)
        avg_length = msg_lengths.mean()
        max_length = msg_lengths.max()
        
        # 存储结果
        results[user] = {
            'message_count': message_count,
            'messages_per_day': msgs_per_day,
            'avg_message_length': avg_length,
            'max_message_length': max_length
        }
    
    return results


def generate_user_profile(user_id, analysis_results):
    """
    根据分析结果生成用户画像
    
    Args:
        user_id (str): 用户ID
        analysis_results (dict): 分析结果
        
    Returns:
        dict: 用户画像字典
    """
    if user_id not in analysis_results:
        return {"error": f"未找到用户 {user_id} 的分析结果"}
    
    user_data = analysis_results[user_id]
    
    # 根据消息特征推断性格特点
    personality_traits = []
    
    # 根据消息长度判断表达方式
    if user_data['avg_message_length'] > 50:
        personality_traits.append("表达详细")
    else:
        personality_traits.append("简明扼要")
    
    # 根据消息频率判断活跃度
    if user_data['messages_per_day'] > 10:
        personality_traits.append("非常活跃")
    elif user_data['messages_per_day'] > 5:
        personality_traits.append("较为活跃")
    else:
        personality_traits.append("较为安静")
    
    # 生成用户画像
    profile = {
        "user_id": user_id,
        "message_stats": {
            "total_messages": user_data['message_count'],
            "avg_length": round(user_data['avg_message_length'], 2),
            "messages_per_day": round(user_data['messages_per_day'], 2)
        },
        "personality_traits": personality_traits
    }
    
    return profile


def export_merged_chat(df, output_dir):
    """
    将所有聊天记录合并到一个文本文件中，每隔一个月添加一个时间标记
    
    Args:
        df (pandas.DataFrame): 预处理后的聊天记录数据框
        output_dir (str): 输出目录
        
    Returns:
        bool: 是否成功导出聊天记录
    """
    try:
        # 确保DateTime列存在
        if 'DateTime' not in df.columns:
            print("警告: 无法按月份分组，DateTime列不存在")
            return False
            
        # 按时间排序
        sorted_df = df.sort_values(by='DateTime')
        
        # 准备输出内容
        lines = []
        current_month = None
        
        for _, row in sorted_df.iterrows():
            # 获取当前消息的年月
            try:
                msg_date = row['DateTime']
                msg_month = msg_date.strftime('%Y年%m月')
                
                # 如果月份变化，添加时间标记
                if msg_month != current_month:
                    current_month = msg_month
                    lines.append(f"\n===== {current_month} =====\n")
            except:
                # 如果日期处理出错，跳过月份检查
                pass
                
            # 只添加消息内容，不添加时间
            content = row['StrContent']
            lines.append(content)
        
        # 写入文件
        output_file = f"{output_dir}/merged_chat.txt"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        
        print(f"已将所有聊天记录合并到: {output_file}")
        return True
    except Exception as e:
        print(f"合并聊天记录时出错: {e}")
        return False


def generate_report(analysis_results, output_dir):
    """
    生成分析报告并保存到文件
    
    Args:
        analysis_results (dict): 分析结果
        output_dir (str): 输出目录
        
    Returns:
        bool: 是否成功生成报告
    """
    try:
        # 为每个用户生成画像
        for user_id in analysis_results.keys():
            profile = generate_user_profile(user_id, analysis_results)
            
            # 保存为JSON文件
            import json
            output_file = f"{output_dir}/{user_id}_profile.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(profile, f, ensure_ascii=False, indent=2)
            
            print(f"已生成用户 {user_id} 的画像报告: {output_file}")
        
        # 生成汇总报告
        summary = {
            "total_users": len(analysis_results),
            "generated_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "users": list(analysis_results.keys())
        }
        
        with open(f"{output_dir}/summary.json", 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        
        return True
    except Exception as e:
        print(f"生成报告时出错: {e}")
        return False