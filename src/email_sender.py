import smtplib
import os
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)

def send_email(subject, body):
    """
    Sends an email using the credentials from environment variables.
    """
    # Retrieve credentials
    sender_email = os.getenv("EMAIL_SENDER")
    password = os.getenv("EMAIL_PASSWORD")
    recipient_email = os.getenv("EMAIL_RECIPIENT")

    # Validate credentials
    if not all([sender_email, password, recipient_email]):
        logger.error("Missing email environment variables (EMAIL_SENDER, EMAIL_PASSWORD, or EMAIL_RECIPIENT).")
        return False

    # Create the email
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = recipient_email
    msg['Subject'] = subject

    # Attach body (Plain text is usually fine for digests, change to 'html' if needed)
    msg.attach(MIMEText(body, 'plain'))

    try:
        # Connect to Gmail SMTP (Standard port 465 for SSL)
        # If using Outlook/Office365, change to ('smtp.office365.com', 587) and use starttls()
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender_email, password)
            server.send_message(msg)
        
        logger.info(f"Email sent successfully to {recipient_email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return False
