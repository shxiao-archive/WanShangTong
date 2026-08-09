import math
import random
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import BusinessData, Merchant, ServiceResource, User
from .security import hash_password
from .config import get_settings


MERCHANTS = [
    {
        "name": "示例餐饮店 A",
        "industry": "餐饮",
        "phone": "000-0000-0001",
        "address": "示例区示例路 1 号",
        "business_hours": "10:30-23:30",
        "contact_name": "示例联系人 A",
        "scale": "中小",
        "employee_count": 12,
        "store_area": 220,
        "network_environment": "普通宽带",
        "bandwidth_mbps": 100,
        "tags": ["万州味道", "聚餐", "夜宵"],
        "needs": ["高速网络", "扫码点餐", "视频监控", "线上营销"],
        "image_url": "",
        "products": [
            {"name": "万州格格", "price": 36, "category": "招牌菜"},
            {"name": "红汤锅底", "price": 58, "category": "锅底"},
            {"name": "鲜切毛肚", "price": 42, "category": "招牌菜"},
        ],
    },
    {
        "name": "示例零售店 B",
        "industry": "零售",
        "phone": "000-0000-0002",
        "address": "示例区示例路 2 号",
        "business_hours": "08:00-22:00",
        "contact_name": "示例联系人 B",
        "scale": "中型",
        "employee_count": 18,
        "store_area": 480,
        "network_environment": "共享网络",
        "bandwidth_mbps": 80,
        "tags": ["社区生活", "即时零售", "生鲜"],
        "needs": ["收银系统", "会员系统", "视频监控", "稳定网络"],
        "image_url": "",
        "products": [
            {"name": "本地鲜果礼盒", "price": 89, "category": "生鲜"},
            {"name": "三峡特产组合", "price": 128, "category": "特产"},
        ],
    },
    {
        "name": "示例服务店 C",
        "industry": "生活服务",
        "phone": "000-0000-0003",
        "address": "示例区示例路 3 号",
        "business_hours": "09:30-21:30",
        "contact_name": "示例联系人 C",
        "scale": "小微",
        "employee_count": 5,
        "store_area": 85,
        "network_environment": "无固定宽带",
        "bandwidth_mbps": 30,
        "tags": ["预约制", "潮流", "年轻客群"],
        "needs": ["线上预约", "短视频推广", "顾客 Wi-Fi", "线上营销"],
        "image_url": "",
        "products": [
            {"name": "精剪造型", "price": 88, "category": "服务"},
            {"name": "染发套餐", "price": 398, "category": "服务"},
        ],
    },
    {
        "name": "示例餐饮店 D",
        "industry": "餐饮",
        "phone": "000-0000-0004",
        "address": "示例区示例路 4 号",
        "business_hours": "06:30-20:30",
        "contact_name": "示例联系人 D",
        "scale": "小微",
        "employee_count": 6,
        "store_area": 96,
        "network_environment": "千兆宽带",
        "bandwidth_mbps": 1000,
        "tags": ["非遗美食", "早餐", "游客打卡"],
        "needs": ["短视频推广", "直播带货", "线上营销"],
        "image_url": "",
        "products": [
            {"name": "红油小面", "price": 12, "category": "主食"},
            {"name": "牛肉面", "price": 22, "category": "主食"},
        ],
    },
    {
        "name": "示例住宿店 E",
        "industry": "住宿",
        "phone": "000-0000-0005",
        "address": "示例区示例路 5 号",
        "business_hours": "全天",
        "contact_name": "示例联系人 E",
        "scale": "中小",
        "employee_count": 8,
        "store_area": 680,
        "network_environment": "普通宽带",
        "bandwidth_mbps": 200,
        "tags": ["江景", "亲子", "乡村旅游"],
        "needs": ["全屋 Wi-Fi", "视频监控", "线上预约", "稳定网络"],
        "image_url": "",
        "products": [
            {"name": "峡江江景大床房", "price": 328, "category": "住宿"},
            {"name": "亲子家庭套房", "price": 498, "category": "住宿"},
        ],
    },
    {
        "name": "示例农产品店 F",
        "industry": "零售",
        "phone": "000-0000-0006",
        "address": "示例区示例路 6 号",
        "business_hours": "08:30-19:00",
        "contact_name": "示例联系人 F",
        "scale": "小微",
        "employee_count": 4,
        "store_area": 72,
        "network_environment": "移动热点",
        "bandwidth_mbps": 20,
        "tags": ["三峡柑橘", "助农", "产地直发"],
        "needs": ["直播带货", "高速网络", "云存储", "线上营销"],
        "image_url": "",
        "products": [
            {"name": "玫瑰香橙 5kg", "price": 69, "category": "水果"},
            {"name": "脆红李 2.5kg", "price": 88, "category": "水果"},
        ],
    },
]


RESOURCES = [
    {
        "name": "千兆商企宽带",
        "category": "网络",
        "description": "千兆下行、专属装维响应，满足多终端并发与高清视频业务。",
        "price": 199,
        "bandwidth_mbps": 1000,
        "target_industries": ["餐饮", "零售", "住宿", "生活服务"],
        "matched_needs": ["高速网络", "稳定网络", "顾客 Wi-Fi", "直播带货"],
        "included_services": ["千兆光猫", "Wi-Fi 6 路由器", "专属装维"],
    },
    {
        "name": "智慧餐饮轻量套装",
        "category": "数字化",
        "description": "覆盖扫码点餐、后厨出单与经营日报，帮助门店减少高峰期等待。",
        "price": 129,
        "target_industries": ["餐饮"],
        "matched_needs": ["扫码点餐", "收银系统", "会员系统"],
        "included_services": ["扫码点餐", "云端菜单", "经营日报"],
    },
    {
        "name": "云眼安防守护包",
        "category": "安防",
        "description": "门店高清监控、移动端巡店和 7 天云端回看。",
        "price": 89,
        "target_industries": ["餐饮", "零售", "住宿"],
        "matched_needs": ["视频监控", "云存储"],
        "included_services": ["2 路高清摄像头", "7 天云回看", "异常告警"],
    },
    {
        "name": "门店线上增长工具箱",
        "category": "营销",
        "description": "聚合会员运营、短视频内容模板与活动数据复盘。",
        "price": 99,
        "target_industries": ["餐饮", "零售", "生活服务", "住宿"],
        "matched_needs": ["线上营销", "短视频推广", "会员系统"],
        "included_services": ["营销模板", "会员触达", "月度运营诊断"],
    },
    {
        "name": "民宿全屋 Wi-Fi 方案",
        "category": "网络",
        "description": "面向多房间场景的无缝漫游覆盖方案，支持住客网络隔离。",
        "price": 299,
        "bandwidth_mbps": 1000,
        "target_industries": ["住宿"],
        "matched_needs": ["全屋 Wi-Fi", "稳定网络", "顾客 Wi-Fi"],
        "included_services": ["全屋勘测", "3 个无线点位", "住客网络隔离"],
    },
    {
        "name": "直播电商加速包",
        "category": "营销",
        "description": "上行优化网络配合商品素材云盘，适合常态化直播经营。",
        "price": 169,
        "bandwidth_mbps": 500,
        "target_industries": ["零售"],
        "matched_needs": ["直播带货", "高速网络", "云存储"],
        "included_services": ["上行加速", "500GB 云盘", "直播网络检测"],
    },
    {
        "name": "商户基础数字服务包",
        "category": "基础服务",
        "description": "适合数字化起步商户的基础工具组合，可按需扩展。",
        "price": 59,
        "target_industries": [],
        "matched_needs": [],
        "included_services": ["电子名片", "基础客流报表", "在线客服"],
        "is_universal": True,
    },
]


def seed_database(db: Session) -> None:
    if db.scalar(select(User.id).limit(1)):
        return
    settings = get_settings()
    merchant_rows = [Merchant(**item, is_demo=True) for item in MERCHANTS]
    db.add_all(merchant_rows)
    db.flush()
    db.add_all(
        [
            User(
                username="operator",
                password_hash=hash_password(settings.demo_operator_password),
                display_name="平台运营员",
                role="operator",
            ),
            User(
                username="merchant",
                password_hash=hash_password(settings.demo_merchant_password),
                display_name="示例联系人 A",
                role="merchant",
                merchant_id=merchant_rows[0].id,
            ),
        ]
    )
    db.add_all([ServiceResource(**item) for item in RESOURCES])
    db.flush()

    today = date.today()
    randomizer = random.Random(20260726)
    for merchant_index, merchant in enumerate(merchant_rows):
        base_revenue = [4200, 7300, 1750, 2600, 3900, 3100][merchant_index]
        base_orders = [82, 165, 24, 138, 15, 46][merchant_index]
        for offset in range(45):
            business_date = today - timedelta(days=offset)
            weekend_factor = 1.25 if business_date.weekday() >= 5 else 1.0
            season_factor = 1 + math.sin(offset / 4) * 0.08
            noise = randomizer.uniform(0.88, 1.12)
            orders = max(1, round(base_orders * weekend_factor * season_factor * noise))
            visitors = round(orders * randomizer.uniform(1.45, 2.15))
            revenue = round(base_revenue * weekend_factor * season_factor * noise, 2)
            delivery = round(orders * (0.27 if merchant.industry == "餐饮" else 0.1))
            group_buy = round(orders * (0.12 if merchant.industry in {"餐饮", "生活服务"} else 0.05))
            other = round(orders * 0.04)
            dine_in = max(0, orders - delivery - group_buy - other)
            db.add(
                BusinessData(
                    merchant_id=merchant.id,
                    business_date=business_date,
                    visitors=visitors,
                    orders=orders,
                    revenue=revenue,
                    rating=round(randomizer.uniform(4.6, 4.95), 1),
                    dine_in_orders=dine_in,
                    delivery_orders=delivery,
                    group_buy_orders=group_buy,
                    other_orders=other,
                    peak_hour=12 if merchant.industry == "餐饮" else randomizer.choice([10, 15, 19, 20]),
                )
            )
    db.commit()
