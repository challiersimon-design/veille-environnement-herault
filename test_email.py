
import os
import smtplib
import ssl
from email.message import EmailMessage

message = EmailMessage()
message["Subject"] = "Test veille environnementale Hérault"
message["From"] = os.environ["SMTP_USER"]
message["To"] = os.environ["ALERT_TO"]

message.set_content(
    "Ceci est un test du système de veille environnementale "
    "de l'Hérault. L'envoi des alertes fonctionne."
)

with smtplib.SMTP_SSL(
    os.environ["SMTP_HOST"],
    int(os.environ["SMTP_PORT"]),
    context=ssl.create_default_context()
) as smtp:
    smtp.login(
        os.environ["SMTP_USER"],
        os.environ["SMTP_PASSWORD"]
    )
    smtp.send_message(message)

print("E-mail de test transmis au serveur SMTP.")
