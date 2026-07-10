"""邮件发送 Service — 阿里云 Direct Mail"""

import json
import logging

from aliyunsdkcore.client import AcsClient
from aliyunsdkcore.request import CommonRequest

from backend.config import (
    ALIYUN_ACCESS_KEY_ID,
    ALIYUN_ACCESS_KEY_SECRET,
    ALIYUN_ACCOUNT_NAME,
    ALIYUN_REGION,
)

logger = logging.getLogger("email_service")


def send_email(to_address: str, subject: str, html_body: str) -> bool:
    """通过阿里云 Direct Mail 发送邮件。

    Args:
        to_address: 收件人邮箱
        subject: 邮件主题
        html_body: HTML 邮件正文

    Returns:
        True 发送成功，False 失败
    """
    if not ALIYUN_ACCESS_KEY_ID or not ALIYUN_ACCESS_KEY_SECRET:
        logger.error("ALIYUN_ACCESS_KEY 未配置，无法发送邮件")
        return False

    client = AcsClient(ALIYUN_ACCESS_KEY_ID, ALIYUN_ACCESS_KEY_SECRET, ALIYUN_REGION)
    request = CommonRequest()
    request.set_domain("dm.aliyuncs.com")
    request.set_version("2015-11-23")
    request.set_action_name("SingleSendMail")
    request.set_method("POST")

    request.add_query_param("AccountName", ALIYUN_ACCOUNT_NAME)
    request.add_query_param("AddressType", "1")
    request.add_query_param("ReplyToAddress", "false")
    request.add_query_param("ToAddress", to_address)
    request.add_query_param("Subject", subject)
    request.add_query_param("HtmlBody", html_body)

    try:
        response = client.do_action_with_exception(request)
        result = json.loads(response)
        logger.info("邮件发送成功 -> %s, RequestId=%s", to_address, result.get("RequestId", "N/A"))
        return True
    except Exception as e:
        logger.error("邮件发送失败 -> %s: %s", to_address, e)
        return False
