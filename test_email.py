"""
Simple Email Test Script - Test Gmail SMTP
Run this to verify email functionality works
"""
from email_sender import send_email_smtp
import os
from dotenv import load_dotenv

load_dotenv()

print("=" * 60)
print("EMAIL TEST - Gmail SMTP")
print("=" * 60)

# Get email config
email_address = os.getenv('EMAIL_ADDRESS')
print(f"\nUsing email: {email_address}")
print(f"SMTP Server: {os.getenv('EMAIL_SMTP_SERVER')}")
print(f"SMTP Port: {os.getenv('EMAIL_SMTP_PORT')}")

# Test email
recipient = input("\nEnter recipient email (or press Enter for vel518496@gmail.com): ").strip()
if not recipient:
    recipient = "vel518496@gmail.com"

print(f"\nSending test email to: {recipient}")
print("Please wait...")

result = send_email_smtp(
    to_email=recipient,
    subject="Test Email from Risk Assessment System",
    body="This is a test email to verify Gmail SMTP is working correctly!\n\nIf you receive this, email functionality is working! 🎉"
)

print("\n" + "=" * 60)
if result:
    print("✅ SUCCESS! Email sent successfully!")
    print(f"Check inbox: {recipient}")
else:
    print("❌ FAILED! Email could not be sent.")
    print("Check your .env file settings:")
    print("  - EMAIL_ADDRESS")
    print("  - EMAIL_PASSWORD (app password)")
    print("  - EMAIL_SMTP_SERVER")
    print("  - EMAIL_SMTP_PORT")
print("=" * 60)
