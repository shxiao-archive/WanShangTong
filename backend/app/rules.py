from collections import Counter
from statistics import mean

from .models import BusinessData, Merchant, ServiceResource


def build_profile(merchant: Merchant, rows: list[BusinessData]) -> dict:
    recent = sorted(rows, key=lambda row: row.business_date, reverse=True)[:30]
    avg_revenue = mean([row.revenue for row in recent]) if recent else 0
    avg_orders = mean([row.orders for row in recent]) if recent else 0

    if merchant.employee_count >= 15 or merchant.store_area >= 300 or avg_revenue >= 8000:
        scale = "成长型商户"
        scale_basis = "员工、面积或日均营收达到成长型阈值"
    elif merchant.employee_count >= 6 or merchant.store_area >= 100 or avg_revenue >= 2500:
        scale = "稳健经营商户"
        scale_basis = "经营面积、人员与日均营收处于中等水平"
    else:
        scale = "小微活力商户"
        scale_basis = "团队精简、经营体量轻量"

    digital_signals = {"扫码点餐", "线上营销", "短视频推广", "会员系统", "直播带货"}
    signal_count = len(set(merchant.needs) & digital_signals)
    if signal_count >= 3:
        digital = "数字化进阶"
    elif signal_count >= 1:
        digital = "数字化成长"
    else:
        digital = "数字化起步"

    if merchant.bandwidth_mbps >= 500 and merchant.network_environment in {"千兆宽带", "企业专线"}:
        network = "网络基础良好"
    elif merchant.bandwidth_mbps >= 100:
        network = "网络基本可用"
    else:
        network = "网络亟需升级"

    sorted_needs = list(merchant.needs)[:4] or ["稳定网络", "线上获客"]
    return {
        "industry": merchant.industry,
        "business_scale": scale,
        "digital_level": digital,
        "network_status": network,
        "core_needs": sorted_needs,
        "evidence": [
            {"label": "经营规模", "value": f"{merchant.employee_count} 人 / {merchant.store_area}㎡ / 日均 ¥{avg_revenue:,.0f}", "reason": scale_basis},
            {"label": "数字化程度", "value": f"识别到 {signal_count} 项数字化需求", "reason": f"需求标签：{'、'.join(merchant.needs) or '暂无'}"},
            {"label": "网络状况", "value": f"{merchant.network_environment} · {merchant.bandwidth_mbps}Mbps", "reason": "根据接入类型与带宽综合判断"},
            {"label": "经营活跃度", "value": f"近 30 日均单量 {avg_orders:.1f}", "reason": f"基于 {len(recent)} 天有效经营数据"},
        ],
    }


def recommend(merchant: Merchant, resources: list[ServiceResource]) -> list[dict]:
    scored: list[dict] = []
    need_set = set(merchant.needs)
    for resource in resources:
        if resource.status != "enabled":
            continue
        score = 20 if resource.is_universal else 0
        reasons: list[str] = []
        if merchant.industry in resource.target_industries:
            score += 35
            reasons.append(f"适配{merchant.industry}行业经营场景")
        matched = need_set & set(resource.matched_needs)
        if matched:
            score += min(40, len(matched) * 15)
            reasons.append(f"响应“{'、'.join(sorted(matched))}”需求")
        if resource.bandwidth_mbps:
            if merchant.bandwidth_mbps < resource.bandwidth_mbps:
                score += 10
                reasons.append(f"可将当前 {merchant.bandwidth_mbps}Mbps 网络升级至 {resource.bandwidth_mbps}Mbps")
            elif merchant.network_environment in {"无固定宽带", "共享网络"}:
                score += 15
                reasons.append("改善当前不稳定的网络接入")
        if score > 0:
            scored.append(
                {
                    "id": resource.id,
                    "name": resource.name,
                    "category": resource.category,
                    "description": resource.description,
                    "price": resource.price,
                    "unit": resource.unit,
                    "score": min(score, 100),
                    "reasons": reasons or ["通用基础服务，适合中小商户快速启用"],
                    "included_services": resource.included_services,
                }
            )
    scored.sort(key=lambda item: (-item["score"], item["price"]))
    return scored[:3]


def overview(merchants: list[Merchant]) -> dict:
    enabled = [merchant for merchant in merchants if merchant.status == "enabled"]
    return {
        "merchant_count": len(merchants),
        "active_count": len(enabled),
        "industry_distribution": dict(Counter(item.industry for item in enabled)),
        "network_distribution": dict(Counter(item.network_environment for item in enabled)),
        "popular_needs": [
            {"name": name, "count": count}
            for name, count in Counter(need for item in enabled for need in item.needs).most_common(8)
        ],
    }
