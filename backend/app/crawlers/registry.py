"""爬虫 Provider 注册表。"""
from app.crawlers.ats_board import AtsBoardProvider
from app.crawlers.browser_discovery import BrowserDiscoveryProvider
from app.crawlers.campus_patrol import CampusPatrolProvider
from app.crawlers.company_campus import CompanyCampusProvider
from app.crawlers.early_batch import EarlyBatchProvider
from app.crawlers.github_joblist import GithubJoblistProvider
from app.crawlers.job_aggregator import JobAggregatorProvider
from app.crawlers.search_discovery import SearchDiscoveryProvider
from app.crawlers.university_html import UniversityHtmlProvider
from app.crawlers.wechat_discovery import WechatDiscoveryProvider
from app.crawlers.wechat_article import WechatArticleProvider

PROVIDERS = {
    "github_joblist": GithubJoblistProvider(),
    "ats_board": AtsBoardProvider(),
    "university_html": UniversityHtmlProvider(),
    "company_campus": CompanyCampusProvider(),
    "job_aggregator": JobAggregatorProvider(),
    "wechat_article": WechatArticleProvider(),
    "early_batch": EarlyBatchProvider(),
    "search_discovery": SearchDiscoveryProvider(),
    "browser_discovery": BrowserDiscoveryProvider(),
    "wechat_discovery": WechatDiscoveryProvider(),
    "campus_patrol": CampusPatrolProvider(),
}
