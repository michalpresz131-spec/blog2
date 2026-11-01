import logging

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def send_notification(subject, body, recipients):
    """Send configured notifications without making email outages lose a submission."""
    recipients = [address for address in recipients if address]
    if not recipients:
        logger.error(
            "Blog notification not sent: configure NOTIFY_EMAIL or "
            "MODERATION_NOTIFICATION_EMAILS."
        )
        return
    if not settings.DEBUG and settings.EMAIL_BACKEND.endswith(".console.EmailBackend"):
        logger.error(
            "Blog notification not sent: production is using Django's console "
            "email backend. Configure an email delivery backend."
        )
        return
    try:
        sent = send_mail(
            subject,
            body,
            settings.DEFAULT_FROM_EMAIL,
            recipients,
            fail_silently=False,
        )
    except Exception:
        logger.exception("Could not send blog notification")
    else:
        if sent:
            logger.info(
                "Blog notification accepted by %s (%s message(s)).",
                settings.EMAIL_BACKEND,
                sent,
            )
        else:
            logger.warning(
                "Blog notification backend %s did not send a message.",
                settings.EMAIL_BACKEND,
            )


def notify_moderators(kind, item):
    author = getattr(item, "author_name", "A visitor")
    subject = f"New {kind} awaiting AllManiac moderation"
    send_notification(
        subject,
        f"{author} submitted a {kind} for review.\n\n"
        f"Open the Django admin to review it: /admin/blog/{kind}/",
        settings.MODERATION_NOTIFICATION_EMAILS,
    )


def notify_submitter(item, status_label):
    if not item.author_email:
        return
    send_notification(
        f"Your AllManiac {item._meta.verbose_name} was {status_label}",
        f"Hello {item.author_name},\n\n"
        f"Your submission “{getattr(item, 'title', 'comment')}” was {status_label} by a moderator.",
        [item.author_email],
    )
