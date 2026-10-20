import smtplib
from email.message import EmailMessage

from app.core.config import settings

from app.core.logger import logger


def send_verification_email(
    *,
    recipient: str,
    verification_url: str,
) -> None:
    subject = "Verify your account"

    body = (
        "Hello,\n\n"
        "Please verify your email address using the link below:\n\n"
        f"{verification_url}\n\n"
        "This link expires in "
        f"{settings.email_verification_expire_hours} hours.\n\n"
        "If you did not create this account, you can ignore this email."
    )

    if settings.email_backend == "console":
        if settings.app_env.lower() != "development":
            raise RuntimeError(
                "The console email backend is only permitted in development."
            )

        logger.info(
            f"Development verification email for {recipient}:\n{verification_url}"
        )
        return

    if settings.email_backend != "smtp":
        raise RuntimeError("Unsupported email backend.")

    if not settings.smtp_host or not settings.smtp_from_email:
        raise RuntimeError("SMTP configuration is incomplete.")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.smtp_from_email
    message["To"] = recipient
    message.set_content(body)

    try:
        with smtplib.SMTP(
            settings.smtp_host,
            settings.smtp_port,
            timeout=15,
        ) as server:
            if settings.smtp_starttls:
                server.starttls()

            if settings.smtp_username:
                server.login(
                    settings.smtp_username,
                    settings.smtp_password or "",
                )

            server.send_message(message)

    except Exception:
        logger.exception("Failed to send verification email.")
        raise