import logging
from email.utils import parseaddr

import boto3
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)


class SesEmailBackend(BaseEmailBackend):
    """Deliver Django email messages with the AWS SES HTTPS API."""

    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently)
        if not settings.AWS_SES_REGION_NAME:
            raise ImproperlyConfigured("Set AWS_SES_REGION_NAME to use AWS SES email.")
        if not settings.AWS_SES_FROM_EMAIL:
            raise ImproperlyConfigured("Set AWS_SES_FROM_EMAIL to use AWS SES email.")
        self.client = boto3.client("ses", region_name=settings.AWS_SES_REGION_NAME)

    def send_messages(self, email_messages):
        sent = 0
        for message in email_messages:
            sender = parseaddr(message.from_email or settings.AWS_SES_FROM_EMAIL)[1]
            destinations = list(dict.fromkeys(message.to + message.cc + message.bcc))
            if not sender or not destinations:
                continue
            try:
                self.client.send_raw_email(
                    Source=sender,
                    Destinations=destinations,
                    RawMessage={"Data": message.message().as_bytes()},
                )
            except Exception:
                if not self.fail_silently:
                    raise
                logger.exception("Could not send email through AWS SES")
            else:
                sent += 1
        return sent
