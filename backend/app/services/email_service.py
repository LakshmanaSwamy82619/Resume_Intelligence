"""
Branded multipart email templates and SMTP delivery.

Every message includes both an accessible plain-text alternative and a
responsive HTML version for mail clients that support formatted email.
"""
from __future__ import annotations

import html
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

from app.core.config import get_settings

logger = logging.getLogger("app.services.email")
settings = get_settings()


class BrandedEmail(str):
    """Plain-text compatible body carrying an HTML alternative for delivery."""

    def __new__(cls, text_body: str, html_body: str):
        instance = super().__new__(cls, text_body)
        instance.html_body = html_body
        return instance


def _layout(title: str, preheader: str, content: str) -> str:
    safe_title = html.escape(title)
    safe_preheader = html.escape(preheader)
    return f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#eef2f7;font-family:Arial,Helvetica,sans-serif;color:#172033;">
  <div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;">{safe_preheader}</div>
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:#eef2f7;padding:32px 12px;">
    <tr><td align="center">
      <table role="presentation" width="600" cellspacing="0" cellpadding="0" border="0" style="width:100%;max-width:600px;background:#ffffff;border:1px solid #dce4ee;border-radius:16px;overflow:hidden;">
        <tr><td style="padding:24px 32px;background:#111b2b;">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0"><tr>
            <td><div style="font-size:18px;font-weight:700;letter-spacing:-.3px;color:#ffffff;">signal<span style="color:#67e8c3;">hire</span></div><div style="margin-top:5px;font-size:10px;letter-spacing:1.6px;color:#9baac0;">RESUME INTELLIGENCE</div></td>
            <td align="right"><span style="display:inline-block;padding:7px 10px;border:1px solid #34445b;border-radius:20px;color:#b8c6d9;font-size:10px;">SECURE WORKSPACE</span></td>
          </tr></table>
        </td></tr>
        <tr><td style="padding:34px 32px 30px;">
          <div style="margin-bottom:10px;color:#68788e;font-size:10px;font-weight:700;letter-spacing:1.5px;">{safe_title.upper()}</div>
          {content}
        </td></tr>
        <tr><td style="padding:18px 32px;background:#f7f9fc;border-top:1px solid #e7edf4;color:#7b8798;font-size:11px;line-height:1.6;">
          This is an automated message from Resume Intelligence. If you did not expect it, contact your workspace administrator.
        </td></tr>
      </table>
      <div style="padding:16px 8px;color:#8a96a6;font-size:10px;">Evidence-led recruiting, in context.</div>
    </td></tr>
  </table>
</body>
</html>"""


def _email(text_body: str, title: str, heading: str, intro: str, detail_html: str, preheader: str) -> BrandedEmail:
    content = f"""<h1 style="margin:0 0 12px;color:#172033;font-size:25px;line-height:1.25;letter-spacing:-.5px;">{html.escape(heading)}</h1>
          <p style="margin:0 0 22px;color:#65738a;font-size:14px;line-height:1.7;">{html.escape(intro)}</p>
          {detail_html}"""
    return BrandedEmail(text_body, _layout(title, preheader, content))


def _generic_html(subject: str, text_body: str) -> str:
    paragraphs = "".join(
        f'<p style="margin:0 0 14px;color:#526177;font-size:14px;line-height:1.7;">{html.escape(line)}</p>'
        for line in text_body.splitlines()
        if line.strip()
    )
    return _layout(subject, subject, paragraphs)


def send_email(to_email: str, subject: str, body: str, cc_email: str | None = None) -> bool:
    if settings.EMAIL_PROVIDER == "console":
        # Never write account passwords, OTPs, or message bodies to application logs.
        logger.info("email_console_send", extra={"extra_fields": {"to": to_email, "subject": subject}})
        return True

    if not settings.SMTP_HOST:
        logger.warning("email_smtp_not_configured", extra={"extra_fields": {"to": to_email}})
        return False

    try:
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = formataddr(("Resume Intelligence", settings.SMTP_FROM_EMAIL))
        message["To"] = to_email
        if cc_email:
            message["Cc"] = cc_email
        message.attach(MIMEText(str(body), "plain", "utf-8"))
        html_body = getattr(body, "html_body", _generic_html(subject, str(body)))
        message.attach(MIMEText(html_body, "html", "utf-8"))

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
            if settings.SMTP_USE_TLS:
                server.starttls()
            if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            recipients = [to_email] + ([cc_email] if cc_email and cc_email.casefold() != to_email.casefold() else [])
            server.sendmail(settings.SMTP_FROM_EMAIL, recipients, message.as_string())
        return True
    except Exception as exc:
        # SMTP exception strings can contain server response data. Log only the
        # exception type so credentials or one-time codes cannot leak to logs.
        logger.error(
            "email_send_failed",
            extra={"extra_fields": {"to": to_email, "error_type": type(exc).__name__}},
        )
        return False


def candidate_stage_email(full_name: str, stage: str) -> tuple[str, BrandedEmail]:
    name = full_name.strip() or "there"
    messages = {
        "screening": (
            "Next step: screening",
            "Your application is moving to screening",
            "Thank you for your interest. We would like to move your application to the screening stage.",
            "Our recruiting team will be in touch with next steps.",
        ),
        "accepted": (
            "Your application has been accepted",
            "You have been selected to continue",
            "Thank you for speaking with our team. We are pleased to move you forward in the hiring process.",
            "Our recruiting team will contact you with the next steps.",
        ),
        "offer": (
            "We are pleased to make you an offer",
            "An offer is waiting for you",
            "We are pleased to share an offer for you to join our team.",
            "Please reply to this email or contact your recruiter to discuss the details.",
        ),
        "hired": (
            "Welcome to the team",
            "Congratulations, and welcome aboard",
            "We are delighted that you have accepted and will be joining our team.",
            "Your recruiter will share onboarding details with you shortly.",
        ),
        "rejected": (
            "Update on your application",
            "Thank you for your time",
            "After careful consideration, we will not be moving forward with your application at this time.",
            "We appreciate your interest and wish you success in your search.",
        ),
    }
    subject, heading, intro, detail = messages[stage]
    safe_name, safe_detail = html.escape(name), html.escape(detail)
    text = f"Hi {name},\n\n{intro}\n\n{detail}\n\nRegards,\nRecruiting team"
    body = _email(text, subject, heading, intro, f'<p style="margin:0 0 12px;color:#526177;font-size:14px;line-height:1.7;">Hi {safe_name},</p><p style="margin:0;color:#526177;font-size:14px;line-height:1.7;">{safe_detail}</p>', subject)
    return subject, body


def account_created_email_body(full_name: str, email: str, temporary_password: str) -> str:
    safe_name, safe_email, safe_password = map(html.escape, (full_name, email, temporary_password))
    text_body = (
        f"Hi {full_name},\n\n"
        "Welcome to Resume Intelligence. Your HR account is ready.\n\n"
        f"Login email: {email}\n"
        f"Temporary password: {temporary_password}\n\n"
        "Sign in with these details and choose a new password before accessing your HR workspace.\n"
        "For your security, do not share this temporary password.\n"
    )
    detail = f"""<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin:22px 0;background:#f6f9fc;border:1px solid #e2e9f1;border-radius:12px;">
            <tr><td style="padding:16px 18px;border-bottom:1px solid #e2e9f1;color:#6e7b8f;font-size:11px;">LOGIN EMAIL</td></tr>
            <tr><td style="padding:0 18px 16px;color:#172033;font-size:14px;font-weight:700;word-break:break-word;">{safe_email}</td></tr>
            <tr><td style="padding:15px 18px 7px;border-top:1px solid #e2e9f1;color:#6e7b8f;font-size:11px;">TEMPORARY PASSWORD</td></tr>
            <tr><td style="padding:0 18px 17px;color:#172033;font-family:Consolas,monospace;font-size:16px;font-weight:700;word-break:break-all;">{safe_password}</td></tr>
          </table>
          <div style="padding:14px 16px;background:#effaf6;border-left:3px solid #35b991;border-radius:7px;color:#42665b;font-size:12px;line-height:1.65;">Sign in with these details, then create a new password. Your HR workspace will be available after the password change.</div>"""
    return _email(
        text_body,
        "Welcome",
        f"Welcome, {full_name}",
        "Your administrator has created your HR account. Use the sign-in details below to get started.",
        detail,
        "Your HR account is ready. Sign in and set your new password.",
    )


def otp_email_body(full_name: str, otp_code: str, purpose: str) -> str:
    purpose_label = purpose.replace("_", " ")
    text_body = (
        f"Hi {full_name},\n\n"
        f"Your one-time verification code for {purpose_label} is: {otp_code}\n"
        "This code expires shortly. If you did not request this, please ignore this email.\n"
    )
    detail = f"""<div style="margin:22px 0;padding:22px;text-align:center;background:#f6f9fc;border:1px solid #e2e9f1;border-radius:12px;">
            <div style="margin-bottom:8px;color:#718096;font-size:10px;font-weight:700;letter-spacing:1.3px;">VERIFICATION CODE</div>
            <div style="color:#172033;font-family:Consolas,monospace;font-size:30px;font-weight:700;letter-spacing:7px;">{html.escape(otp_code)}</div>
          </div>
          <p style="margin:0;color:#738096;font-size:12px;line-height:1.65;">This code expires shortly and can only be used once. If you did not request it, you can safely ignore this message.</p>"""
    return _email(text_body, "Verification code", "Confirm it’s you", f"Use this code to continue with {purpose_label}.", detail, "Your one-time verification code is inside.")


def password_reset_confirmation_body(full_name: str) -> str:
    text_body = f"Hi {full_name},\n\nYour password was just changed. If this wasn't you, contact your administrator immediately.\n"
    detail = """<div style="padding:16px;background:#effaf6;border:1px solid #d5f0e5;border-radius:10px;color:#42665b;font-size:13px;line-height:1.7;">Your password has been updated successfully. If you did not make this change, contact your workspace administrator right away.</div>"""
    return _email(text_body, "Password updated", "Your password was changed", "This is a confirmation that your account password has been updated.", detail, "Your account password was changed.")


def processing_completed_body(full_name: str, total: int, processed: int, failed: int) -> str:
    text_body = (
        f"Hi {full_name},\n\n"
        "Your bulk resume upload has finished processing.\n"
        f"Total: {total}, Processed: {processed}, Failed: {failed}\n"
    )
    detail = f"""<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin:22px 0;">
            <tr>
              <td align="center" style="padding:15px 8px;background:#f6f9fc;border:1px solid #e2e9f1;border-radius:10px;"><div style="color:#718096;font-size:10px;">TOTAL</div><div style="margin-top:6px;color:#172033;font-size:23px;font-weight:700;">{int(total)}</div></td>
              <td width="8"></td>
              <td align="center" style="padding:15px 8px;background:#effaf6;border:1px solid #d5f0e5;border-radius:10px;"><div style="color:#4d8170;font-size:10px;">PROCESSED</div><div style="margin-top:6px;color:#167957;font-size:23px;font-weight:700;">{int(processed)}</div></td>
              <td width="8"></td>
              <td align="center" style="padding:15px 8px;background:#fff7ed;border:1px solid #f5e6ce;border-radius:10px;"><div style="color:#92754d;font-size:10px;">FAILED</div><div style="margin-top:6px;color:#ad6c1d;font-size:23px;font-weight:700;">{int(failed)}</div></td>
            </tr>
          </table>"""
    return _email(text_body, "Upload complete", "Resume processing is complete", "Your bulk upload has finished. Here’s the processing summary.", detail, "Your bulk resume upload has finished processing.")
