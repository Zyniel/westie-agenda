import os
import smtplib
import ssl
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from src.python.whatsapp_client import WhatsAppLoginHandler

class WhatsAppGmailLoginHandler(WhatsAppLoginHandler):
    def __init__(self, config):
        super().__init__(config)
        self.sender = None
        self.subject = None
        self.to = None
        self.bcc = None
        self.cc = None

    def set_sender(self, sender: str):
        if not sender:
            raise ValueError('Invalid value for "sender"')
        self.sender = sender

    def set_to(self, to: str):
        if not to:
            raise ValueError('Invalid value for "to"')
        self.to = to

    def set_cc(self, cc: str):
        if not cc:
            raise ValueError('Invalid value for "cc"')
        self.cc = cc

    def set_bcc(self, bcc: str):
        if not bcc:
            raise ValueError('Invalid value for "bcc"')
        self.bcc = bcc

    def set_subject(self, subject: str):
        if not subject:
            raise ValueError('Invalid value for "subject"')
        self.subject = subject

    def notify(self):
        # Send email with QR code image
        msg = MIMEMultipart()
        msg['From'] = self.sender
        msg['To'] = self.to
        #TODO: Implement Bcc, CC
        #msg['Cc'] = self.cc
        #msg['Bcc'] = self.bcc
        msg['Subject'] = self.subject

        # Add a text message
        body = "Here is your QR code:"
        msg.attach(MIMEText(body, 'plain'))

        # Attach the QR code image
        with open(self.qrcode, "rb") as attachment:
            basename = Path(self.qrcode).name
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(attachment.read())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f"attachment; filename= {basename}")
            msg.attach(part)

        # Send email
        with smtplib.SMTP_SSL('smtp.gmail.com', port=465) as server:
            server.login(self.config['mail']['sender'], os.environ['GM_SERVICE_ACCOUNT'])
            server.sendmail(from_addr=self.sender, to_addrs=self.to, msg=msg.as_string())