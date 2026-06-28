"""爬虫 Provider 注册表。"""
from app.crawlers.ats_board import AtsBoardProvider
from app.crawlers.company_campus import CompanyCampusProvider
from app.crawlers.github_joblist import GithubJoblistProvider
from app.crawlers.job_aggregator import JobAggregatorProvider
from app.crawlers.university_html import UniversityHtmlProvider
from app.crawlers.wechat_article import WechatArticleProvider

PROVIDERS = {
    "github_joblist": GithubJoblistProvider(),
    "ats_board": AtsBoardProvider(),
    "university_html": UniversityHtmlProvider(),
    "company_campus": CompanyCampusProvider(),
    "job_aggregator": JobAggregatorProvider(),
    "wechat_article": WechatArticleProvider(),
}
