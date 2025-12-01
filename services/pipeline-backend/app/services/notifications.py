import logging
import httpx
from typing import List
from app.core.config import settings
from app.domain.entities import BuildSample

logger = logging.getLogger(__name__)


class NotificationService:
    def send_alert(
        self,
        build: BuildSample,
        risk_factors: List[str],
        risk_score: float = 0.0,
        shadow_mode: bool = False,
    ):
        if not settings.notifications.slack_webhook_url:
            logger.warning("SLACK_WEBHOOK_URL not set, skipping alert")
            return

        if shadow_mode:
            logger.info(
                f"Shadow Mode: Alert suppressed for build {build.id} (Risk Score: {risk_score})"
            )
            return

        # Basic Slack payload
        payload = {
            "text": f"⚠️ High Risk Build Detected: #{build.tr_build_number}",
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "⚠️ High Risk Build Detected",
                        "emoji": True,
                    },
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Repository:*\n{build.repo_id}"},
                        {
                            "type": "mrkdwn",
                            "text": f"*Build Number:*\n#{build.tr_build_number}",
                        },
                    ],
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Risk Score:*\n{risk_score:.2f}"},
                        {"type": "mrkdwn", "text": f"*Status:*\n{build.status}"},
                    ],
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*Risk Factors:*\n"
                        + "\n".join([f"• {f}" for f in risk_factors]),
                    },
                },
            ],
        }

        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.post(
                    settings.notifications.slack_webhook_url, json=payload
                )
                response.raise_for_status()
                logger.info(f"Sent Slack alert for build {build.id}")
        except Exception as e:
            logger.error(f"Failed to send Slack alert: {e}")
