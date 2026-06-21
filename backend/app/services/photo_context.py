"""供 AI Prompt 使用的个人照片上下文说明。"""
from app.services.profile_photo import has_session_photo


def photo_context_for_session(session_id: str, profile_photo_ref: str = "") -> str:
    """返回写入各 Prompt 的照片状态块。"""
    if profile_photo_ref and has_session_photo(session_id):
        return """==== 个人照片（已配置）====
- 用户已在知识库「个人自定义模块」上传证件照
- 系统已自动裁剪为 540×790 px（与 PDF 右上角照片框比例一致）
- 简历 Markdown 中保留一行：`![个人照片](...)`，位于联系方式之后、`## 教育经历` 之前
- PDF 导出时照片固定显示在页面右上角（约 2.7cm × 3.95cm），由排版引擎绝对定位，不占用正文流
- **不要**删除、移动或改写照片行；**不要**建议用户「再上传照片」
- 修改姓名/联系方式时控制行宽，为右上角照片预留空间；勿在照片区域堆叠大段文字
==== 照片说明结束 ===="""
    return """==== 个人照片（未上传）====
- 用户尚未上传证件照；可在知识库「个人照片」模块上传
- 定稿导出 PDF 前建议提醒用户上传（上传后系统自动裁剪并注入 Markdown）
- 生成建议时不要虚构照片或添加 `![个人照片]` 行（除非用户明确要求）
==== 照片说明结束 ===="""
