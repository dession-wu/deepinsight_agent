"""
数据获取模块
包含从财联社、东方财富等数据源获取数据的函数

此模块独立于 main.py，避免循环导入问题。

实现说明：
- 财联社采用 nodeapi/telegraphList 接口（原 /api/sw + 假 sign 的实现已废弃，
  该接口必失败，现统一为原 main.py 中验证可用的版本）。
- 东方财富采用 push2 隐式 API，与主链路使用中的版本一致。
"""

from datetime import datetime

import requests


def fetch_cls_telegraph(num_items: int = 20) -> str:
    """
    从财联社（CLS）电报接口获取最新的财经快讯。

    Args:
        num_items: 获取的新闻条数，默认 20 条，最大建议 50 条。

    Returns:
        格式化后的新闻字符串，适合直接输入给大模型。
    """
    url = "https://www.cls.cn/nodeapi/telegraphList"
    params = {
        "app": "CailianpressWeb",
        "os": "web",
        "refresh_type": "1",
        "order": "1",
        "rn": min(num_items, 50),
        "sv": "8.4.6",
        "sign": "8bc6630fbf8b4a195cd99b4da66ed07b"
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Referer": "https://www.cls.cn/telegraph"
    }

    try:
        response = requests.get(url, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()

        if data.get("error") != 0:
            return f"❌ 财联社接口返回错误: {data}"

        roll_data = data.get("data", {}).get("roll_data", [])
        if not roll_data:
            return "⚠️ 未从财联社获取到任何数据。"

        formatted_news = []
        for item in roll_data:
            ctime = item.get("ctime")
            time_str = datetime.fromtimestamp(ctime).strftime("%m-%d %H:%M") if ctime else "未知时间"
            content = item.get("content", "")
            # 财联社 content 通常已经包含标题，如果 content 为空则使用 brief
            if not content:
                content = item.get("brief", "")
            formatted_news.append(f"[{time_str}] {content}")

        return "\n\n".join(formatted_news)

    except requests.exceptions.Timeout:
        return "❌ 请求财联社数据超时。请检查网络连接。"
    except requests.exceptions.RequestException as e:
        return f"❌ 网络请求失败，无法连接财联社: {e}"
    except Exception as e:
        return f"❌ 处理财联社数据时发生错误: {e}"


def fetch_eastmoney_industry_capital_flow() -> str:
    """
    从东方财富网获取行业板块资金流向排行数据。
    通过调用其内部 push2 接口（隐式 API）获取实时 JSON 数据。

    Returns:
        格式化后的行业资金流向字符串，适合直接输入给大模型。
    """
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": "1",           # 页码
        "pz": "20",          # 每页条数
        "po": "1",           # 排序方向：1降序
        "np": "1",
        "fltt": "2",         # 浮点精度
        "invt": "2",
        "fid": "f62",        # 按主力净流入排序
        "fs": "m:90+t:2",    # 行业板块筛选条件
        "fields": "f12,f14,f2,f3,f62,f128,f140,f136,f141,f207,f208",
        "_": str(int(datetime.now().timestamp() * 1000))
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Referer": "https://data.eastmoney.com/bkzj/hy.html"
    }

    try:
        response = requests.get(url, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()

        if data.get("data") is None:
            return "⚠️ 东方财富接口未返回数据，可能受反爬限制。"

        diff = data.get("data", {}).get("diff", [])
        if not diff:
            return "⚠️ 未从东方财富获取到任何行业资金流向数据。"

        # 字段映射说明（f开头为东方财富内部字段编码）
        # f12: 板块代码, f14: 板块名称, f2: 最新价, f3: 涨跌幅
        # f62: 主力净流入(元), f128: 主力净流入占比, f140: 超大单净流入
        # f136: 超大单净流入占比, f141: 大单净流入, f207: 大单净流入占比
        formatted_lines = ["【行业板块资金流向排行】\n"]

        for item in diff:
            name = item.get("f14", "未知板块")
            change_pct = item.get("f3", "-")
            main_inflow = item.get("f62", "-")
            main_inflow_pct = item.get("f128", "-")

            change_str = f"{change_pct:.2f}%" if isinstance(change_pct, (int, float)) else "-"
            inflow_str = f"{main_inflow/10000:.2f}万" if isinstance(main_inflow, (int, float)) else "-"
            inflow_pct_str = f"{main_inflow_pct:.2f}%" if isinstance(main_inflow_pct, (int, float)) else "-"

            formatted_lines.append(
                f"• {name}: 涨跌幅 {change_str}, 主力净流入 {inflow_str} ({inflow_pct_str})"
            )

        return "\n".join(formatted_lines)

    except requests.exceptions.Timeout:
        return "❌ 请求东方财富数据超时。请检查网络连接。"
    except requests.exceptions.RequestException as e:
        return f"❌ 网络请求失败，无法连接东方财富: {e}"
    except Exception as e:
        return f"❌ 处理东方财富数据时发生错误: {e}"


def fetch_eastmoney_stock_spot() -> str:
    """
    从东方财富网获取 A 股实时行情快照（全市场涨跌幅前20）。

    Returns:
        格式化后的股票行情字符串。
    """
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": "1",
        "pz": "20",
        "po": "1",
        "np": "1",
        "fltt": "2",
        "invt": "2",
        "fid": "f12",
        "fs": "m:0+t:6,m:0+t:13,m:1+t:2,m:1+t:23",  # 沪深A股
        "fields": "f12,f14,f2,f3,f4,f5,f6,f7,f8,f9,f10,f18,f20,f21,f23,f24,f25,f22,f11,f62,f128,f136,f115,f152",
        "_": str(int(datetime.now().timestamp() * 1000))
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Referer": "https://quote.eastmoney.com/"
    }

    try:
        response = requests.get(url, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()

        if data.get("data") is None:
            return "⚠️ 东方财富行情接口未返回数据。"

        diff = data.get("data", {}).get("diff", [])
        if not diff:
            return "⚠️ 未获取到股票行情数据。"

        formatted_lines = ["【A股实时行情快照】\n"]

        for item in diff[:10]:  # 只展示前10条避免过长
            code = item.get("f12", "-")
            name = item.get("f14", "-")
            price = item.get("f2", "-")
            change_pct = item.get("f3", "-")
            change_amt = item.get("f4", "-")

            price_str = f"{price:.2f}" if isinstance(price, (int, float)) else "-"
            change_str = f"{change_pct:.2f}%" if isinstance(change_pct, (int, float)) else "-"
            amt_str = f"{change_amt:.2f}" if isinstance(change_amt, (int, float)) else "-"

            formatted_lines.append(
                f"• {name}({code}): 最新价 {price_str}, 涨跌幅 {change_str}, 涨跌额 {amt_str}"
            )

        return "\n".join(formatted_lines)

    except requests.exceptions.Timeout:
        return "❌ 请求东方财富数据超时。请检查网络连接。"
    except requests.exceptions.RequestException as e:
        return f"❌ 网络请求失败: {e}"
    except Exception as e:
        return f"❌ 处理行情数据时发生错误: {e}"