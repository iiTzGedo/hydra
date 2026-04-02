"""Email utilities for sending emails via SMTP."""

import html as html_lib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from hydra.core.config import Settings

logger = structlog.get_logger(__name__)


def _stringify(value: object | None) -> str:
    """Coerce email template values to text safely."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def _escape_html(value: object | None) -> str:
    """Escape arbitrary values for HTML output."""
    return html_lib.escape(_stringify(value))


class EmailError(Exception):
    """Exception raised when email sending fails."""

    pass


class EmailService:
    """Service for sending emails via SMTP."""

    def __init__(self, settings: "Settings"):
        """Initialize email service with settings."""
        self.settings = settings
        self._client = None

    @property
    def is_configured(self) -> bool:
        """Check if email service is properly configured."""
        return self.settings.has_smtp

    async def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        html: str | None = None,
    ) -> bool:
        """
        Send an email.

        Args:
            to: Recipient email address
            subject: Email subject line
            body: Plain text email body
            html: Optional HTML email body

        Returns:
            True if email was sent successfully

        Raises:
            EmailError: If email sending fails
        """
        if not self.is_configured:
            logger.warning(
                "email_not_configured",
                message="SMTP is not configured, email not sent",
                to=to,
                subject=subject,
            )
            return False

        try:
            import aiosmtplib

            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = (
                f"{self.settings.smtp_from_name} <{self.settings.smtp_from_address}>"
            )
            msg["To"] = to

            # Add plain text part
            msg.attach(MIMEText(body, "plain", "utf-8"))

            # Add HTML part if provided
            if html:
                msg.attach(MIMEText(html, "html", "utf-8"))

            # Determine TLS settings
            use_tls = self.settings.smtp_use_tls and not self.settings.smtp_starttls
            start_tls = self.settings.smtp_starttls

            # Send email
            await aiosmtplib.send(
                msg,
                hostname=self.settings.smtp_host,
                port=self.settings.smtp_port,
                username=self.settings.smtp_username,
                password=self.settings.smtp_password,
                use_tls=use_tls,
                start_tls=start_tls,
                timeout=self.settings.smtp_timeout,
            )

            logger.info(
                "email_sent",
                to=to,
                subject=subject,
            )
            return True

        except ImportError:
            logger.error(
                "email_dependency_missing",
                message="aiosmtplib is not installed",
            )
            raise EmailError("aiosmtplib is not installed. Run `uv sync` to install project dependencies.")

        except Exception as e:
            logger.error(
                "email_send_failed",
                to=to,
                subject=subject,
                error=str(e),
            )
            raise EmailError(f"Failed to send email: {e}") from e

    async def send_password_reset_email(
        self,
        to: str,
        username: str,
        reset_token: str,
        expires_hours: int = 24,
    ) -> bool:
        """
        Send a password reset email.

        Args:
            to: Recipient email address
            username: User's username
            reset_token: The password reset token
            expires_hours: Hours until token expires

        Returns:
            True if email was sent successfully
        """
        base_url = (
            self.settings.password_reset_base_url
            or f"http://localhost:{self.settings.api_port}"
        )
        reset_link = f"{base_url}/reset-password?token={reset_token}"

        subject = "Hydra - Password Reset Request"

        body = f"""Hello {username},

You requested a password reset for your Hydra account.

Click the link below to reset your password:
{reset_link}

This link will expire in {expires_hours} hours.

If you did not request this password reset, please ignore this email.

- The Hydra Team
"""

        safe_username = html_lib.escape(username)
        safe_reset_link = html_lib.escape(reset_link)
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .button {{ display: inline-block; padding: 12px 24px; background-color: #2563eb; color: white; text-decoration: none; border-radius: 6px; margin: 20px 0; }}
        .footer {{ color: #6b7280; font-size: 14px; margin-top: 30px; }}
    </style>
</head>
<body>
    <div class="container">
        <h2>Password Reset Request</h2>
        <p>Hello <strong>{safe_username}</strong>,</p>
        <p>You requested a password reset for your Hydra account.</p>
        <p>Click the button below to reset your password:</p>
        <a href="{safe_reset_link}" class="button">Reset Password</a>
        <p>Or copy this link: <a href="{safe_reset_link}">{safe_reset_link}</a></p>
        <p class="footer">
            This link will expire in {expires_hours} hours.<br>
            If you did not request this password reset, please ignore this email.
        </p>
    </div>
</body>
</html>
"""

        return await self.send_email(to, subject, body, html)

    async def send_notification_email(
        self,
        to: str,
        notification: dict,
    ) -> bool:
        """Send a notification email.

        Args:
            to: Recipient email address
            notification: Notification document or summary

        Returns:
            True if email was sent successfully
        """
        title_text = _stringify(notification.get("title") or "Notification")
        message_text = _stringify(notification.get("message"))
        tier_text = _stringify(notification.get("tier"))
        tier_label_text = _stringify(notification.get("tierLabel"))
        created_at = notification.get("createdAt", "")
        try:
            from datetime import datetime as _dt
            if isinstance(created_at, _dt):
                created_at = created_at.isoformat()
        except Exception:
            pass
        created_at_text = _stringify(created_at)
        notif_type_text = _stringify(notification.get("type"))
        links = notification.get("links") or []

        subject = f"Hydra Notification: {title_text}"

        link_lines = ""
        if links:
            link_lines = "\nLinks:\n" + "\n".join(
                f"- {_stringify(l.get('label') or l.get('href'))}: {_stringify(l.get('href'))}"
                for l in links
                if _stringify(l.get("href"))
            )

        body = f"""Hydra Notification

Title: {title_text}
Message: {message_text}
Type: {notif_type_text}
Tier: {tier_label_text or tier_text}
Time: {created_at_text}
{link_lines}
"""

        title = _escape_html(title_text)
        message = _escape_html(message_text)
        tier = _escape_html(tier_text)
        tier_label = _escape_html(tier_label_text)
        created_at_html = _escape_html(created_at_text)
        notif_type = _escape_html(notif_type_text)

        html_links = ""
        if links:
            safe_links = []
            for l in links:
                href = _stringify(l.get("href"))
                if href and (
                    href.startswith("/")
                    or href.startswith("http://")
                    or href.startswith("https://")
                ):
                    safe_href = _escape_html(href)
                    safe_label = _escape_html(l.get("label") or href)
                    safe_links.append(f"<li><a href=\"{safe_href}\">{safe_label}</a></li>")
            if safe_links:
                html_links = f"<ul>{''.join(safe_links)}</ul>"

        html = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
    .meta {{ color: #6b7280; font-size: 13px; }}
  </style>
</head>
<body>
  <div class="container">
    <h2>{title}</h2>
    <p>{message}</p>
    <p class="meta">
      <strong>Type:</strong> {notif_type}<br/>
      <strong>Tier:</strong> {tier_label or tier}<br/>
      <strong>Time:</strong> {created_at_html}
    </p>
    {html_links}
  </div>
</body>
</html>
"""

        return await self.send_email(to, subject, body, html)


# Module-level instance for convenience
_email_service: EmailService | None = None


def get_email_service(settings: "Settings") -> EmailService:
    """Get or create the email service instance."""
    global _email_service
    if _email_service is None:
        _email_service = EmailService(settings)
    return _email_service


async def send_email(
    settings: "Settings",
    to: str,
    subject: str,
    body: str,
    html: str | None = None,
) -> bool:
    """
    Convenience function to send an email.

    Args:
        settings: Application settings
        to: Recipient email address
        subject: Email subject line
        body: Plain text email body
        html: Optional HTML email body

    Returns:
        True if email was sent successfully
    """
    service = get_email_service(settings)
    return await service.send_email(to, subject, body, html)


async def send_notification_email(
    settings: "Settings",
    to: str,
    notification: dict,
) -> bool:
    """Convenience function to send notification emails."""
    service = get_email_service(settings)
    return await service.send_notification_email(to, notification)
