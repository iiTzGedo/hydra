"""Email utilities for sending emails via SMTP."""

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from hydra_api.core.config import Settings

logger = structlog.get_logger(__name__)


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
            raise EmailError("aiosmtplib is not installed. Run: pip install aiosmtplib")

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
        <p>Hello <strong>{username}</strong>,</p>
        <p>You requested a password reset for your Hydra account.</p>
        <p>Click the button below to reset your password:</p>
        <a href="{reset_link}" class="button">Reset Password</a>
        <p>Or copy this link: <a href="{reset_link}">{reset_link}</a></p>
        <p class="footer">
            This link will expire in {expires_hours} hours.<br>
            If you did not request this password reset, please ignore this email.
        </p>
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
