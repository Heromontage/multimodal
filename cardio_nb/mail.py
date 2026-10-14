"""Verification email delivery over authenticated TLS SMTP (Gmail by default)."""
from email.message import EmailMessage
import os
import smtplib
import ssl
from urllib.parse import urlsplit


def send_verification_email(recipient: str, token: str):
    username = os.environ.get('SMTP_USERNAME', '').strip()
    password = os.environ.get('SMTP_PASSWORD', '').replace(' ', '')
    base = os.environ.get('APP_BASE_URL', 'http://localhost:3000').rstrip('/')
    url = urlsplit(base)
    if not username or not password:
        raise RuntimeError('Email sender is not configured.')
    if url.scheme not in ('http', 'https') or not url.netloc or url.username or url.query or url.fragment:
        raise RuntimeError('Invalid APP_BASE_URL.')
    if url.scheme != 'https' and url.hostname not in ('localhost', '127.0.0.1', '::1'):
        raise RuntimeError('Public verification links require HTTPS.')
    message = EmailMessage()
    message['Subject'] = 'Verify your email for Coronary Atlas'
    message['From'] = username
    message['To'] = recipient
    # A URL fragment keeps the secret out of HTTP access logs and referrer headers.
    message.set_content(
        'Confirm your email address for Coronary Atlas.\n\n'
        f'{base}/verify-email#token={token}\n\n'
        'This link expires in 30 minutes and can be used once. '
        'Enter your account password on the verification page, then sign in.\n\n'
        'If you did not request this account, ignore this email. '
        'Your address will remain unverified.\n')
    with smtplib.SMTP_SSL(os.environ.get('SMTP_HOST', 'smtp.gmail.com'),
                          int(os.environ.get('SMTP_PORT', '465')),
                          context=ssl.create_default_context(), timeout=10) as smtp:
        smtp.login(username, password)
        if smtp.send_message(message):
            raise RuntimeError('The mail server refused the recipient.')
