"""
数据获取模块
包含从财联社、东方财富等数据源获取数据的函数

此模块独立于 main.py，避免循环导入问题
"""

import json
import time
from typing import Dict, List, Any, Optional


def fetch_cls_telegraph(num_items: int = 20) -> str:
    """
    从财联社获取实时电报数据
    
    Args:
        num_items: 获取的电报数量
        
    Returns:
        格式化的电报文本
    """
    import requests
    
    try:
        url = f"https://www.cls.cn/api/sw?app=CailianpressWeb&os=web&sv=8.4.6&sign=sign"
        payload = {
            "app": "CailianpressWeb",
            "os": "web",
            "sv": "8.4.6",
            "sign": "sign",
        }
        
        response = requests.post(url, json=payload, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        if data.get("code") != 200:
            return f"⚠️ 财联社 API 返回错误: {data.get('message', '未知错误')}"
        
        telegraph_list = data.get("data", {}).get("roll_data", [])
        if not telegraph_list:
            return "⚠️ 未能从财联社获取到电报数据。"
        
        formatted_items = []
        count = 0
        for item in telegraph_list:
            if count >= num_items:
                break
            content = item.get("content", "")
            formatted_items.append(f"[{count+1}] {content}")
            count += 1
        
        return "\n".join(formatted_items)
        
    except requests.exceptions.Timeout:
        return "❌ 请求财联社数据超时。请检查网络连接。"
    except requests.exceptions.RequestException as e:
        return f"❌ 请求财联社数据时发生网络错误: {e}"
    except Exception as e:
        return f"❌ 处理财联社数据时发生未知错误: {e}"


def fetch_eastmoney_industry_capital_flow() -> str:
    """
    从东方财富获取行业资金流向数据
    
    Returns:
        格式化的资金流向文本
    """
    import requests
    
    try:
        url = "https://push2.eastmoney.com/api/qt/clist/get"
        params = {
            "pn": 1,
            "pz": 20,
            "po": 1,
            "np": 1,
            "fltt": 2,
            "invt": 2,
            "fid": "f62",
            "fs": "m:90+t:2",
            "fields": "f12,f14,f2,f3,f62",
            "_": int(time.time() * 1000)
        }
        
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        if data.get("data") is None or not data["data"].get("diff"):
            return "⚠️ 未能从东方财富获取到行业资金流向数据。"
        
        items = data["data"]["diff"]
        formatted_lines = ["--- 东方财富行业资金流向排行 ---\n"]
        
        for i, item in enumerate(items[:10]):
            industry_name = item.get("f14", "未知行业")
            change_pct = item.get("f3", 0)
            main_net_inflow = item.get("f62", 0)
            
            change_pct_str = f"+{change_pct}%" if change_pct > 0 else f"{change_pct}%"
            inflow_str = f"+{main_net_inflow/10000:.1f}亿" if main_net_inflow > 0 else f"{main_net_inflow/10000:.1f}亿"
            
            formatted_lines.append(
                f"{i+1}. {industry_name}: 涨跌幅 {change_pct_str}, 主力净流入 {inflow_str}"
            )
        
        return "\n".join(formatted_lines)
        
    except requests.exceptions.Timeout:
        return "❌ 请求东方财富数据超时。请检查网络连接。"
    except requests.exceptions.RequestException as e:
        return f"❌ 请求东方财富数据时发生网络错误: {e}"
    except Exception as e:
        return f"❌ 处理东方财富数据时发生未知错误: {e}"


def fetch_eastmoney_stock_spot() -> str:
    """
    从东方财富获取A股行情快照
    
    Returns:
        格式化的行情文本
    """
    import requests
    
    try:
        url = "https://push2.eastmoney.com/api/qt/clist/get"
        params = {
            "pn": 1,
            "pz": 10,
            "po": 1,
            "np": 1,
            "fltt": 2,
            "invt": 2,
            "fid": "f20",
            "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:204",
            "fields": "f12,f14,f2,f3,f4,f5,f6,f7,f8,f9,f10,f18,f20,f21,f22,f23,f24,f25,f26,f33,f34,f35,f36,f37,f38,f39,f40,f41,f42,f43,f44,f45,f46,f47,f48,f49,f50,f51,f52,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65,f66,f67,f68,f69,f70,f71,f72,f73,f74,f75,f76,f77,f78,f79,f80,f81,f82,f83,f84,f85,f86,f87,f88,f89,f90,f91,f92,f93,f94,f95,f96,f97,f98,f99,f100",
            "_": int(time.time() * 1000)
        }
        
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        if data.get("data") is None or not data["data"].get("diff"):
            return "⚠️ 未能从东方财富获取到A股行情快照。"
        
        items = data["data"]["diff"]
        formatted_lines = ["--- A股行情快照 (Top 10) ---\n"]
        
        for i, item in enumerate(items[:10]):
            stock_name = item.get("f14", "未知")
            stock_code = item.get("f12", "------")
            price = item.get("f2", 0)
            change_pct = item.get("f3", 0)
            volume = item.get("f5", 0)
            
            change_pct_str = f"+{change_pct}%" if change_pct > 0 else f"{change_pct}%"
            
            formatted_lines.append(
                f"{i+1}. {stock_name}({stock_code}): 最新价 {price}, 涨跌幅 {change_pct_str}, 成交量 {volume}"
            )
        
        return "\n".join(formatted_lines)
        
    except requests.exceptions.Timeout:
        return "❌ 请求东方财富数据超时。请检查网络连接。"
    except requests.exceptions.RequestException as e:
        return f"❌ 请求东方财富数据时发生网络错误: {e}"
    except Exception as e:
        return f"❌ 处理东方财富数据时发生未知错误: {e}"
