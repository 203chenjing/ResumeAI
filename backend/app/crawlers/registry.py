"""爬虫 Provider 注册表。"""
from app.crawlers.company_campus import CompanyCampusProvider
from app.crawlers.feishu_bitable import FeishuBitableProvider
from app.crawlers.job_aggregator import JobAggregatorProvider
from app.crawlers.university_html import UniversityHtmlProvider
from app.crawlers.wechat_article import WechatArticleProvider

PROVIDERS = {
    "university_html": UniversityHtmlProvider(),
    "company_campus": CompanyCampusProvider(),
    "job_aggregator": JobAggregatorProvider(),
    "wechat_article": WechatArticleProvider(),
    "feishu_bitable": FeishuBitableProvider(),
}
