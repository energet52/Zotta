import json
import boto3
import os

ses = boto3.client("ses", region_name="us-east-1")
TO_EMAIL = os.environ.get("TO_EMAIL", "info@zotta-lms.com")
FROM_EMAIL = os.environ.get("FROM_EMAIL", "info@zotta-lms.com")

def handler(event, context):
    headers = {
        "Access-Control-Allow-Origin": "https://zotta-lms.com",
        "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Allow-Methods": "POST,OPTIONS",
        "Content-Type": "application/json",
    }

    if event.get("requestContext", {}).get("http", {}).get("method") == "OPTIONS":
        return {"statusCode": 200, "headers": headers, "body": ""}

    try:
        body = json.loads(event.get("body", "{}"))
        name = body.get("name", "").strip()
        email = body.get("email", "").strip()
        company = body.get("company", "").strip()
        message = body.get("message", "").strip()

        if not name or not email or not message:
            return {
                "statusCode": 400,
                "headers": headers,
                "body": json.dumps({"error": "Name, email, and message are required"}),
            }

        subject = f"Zotta LMS Inquiry from {name}"
        if company:
            subject += f" ({company})"

        html_body = f"""
        <h2>New Contact Form Submission</h2>
        <table style="border-collapse:collapse;width:100%">
            <tr><td style="padding:8px;font-weight:bold;border-bottom:1px solid #eee">Name</td>
                <td style="padding:8px;border-bottom:1px solid #eee">{name}</td></tr>
            <tr><td style="padding:8px;font-weight:bold;border-bottom:1px solid #eee">Email</td>
                <td style="padding:8px;border-bottom:1px solid #eee"><a href="mailto:{email}">{email}</a></td></tr>
            <tr><td style="padding:8px;font-weight:bold;border-bottom:1px solid #eee">Company</td>
                <td style="padding:8px;border-bottom:1px solid #eee">{company or 'N/A'}</td></tr>
            <tr><td style="padding:8px;font-weight:bold;vertical-align:top">Message</td>
                <td style="padding:8px">{message}</td></tr>
        </table>
        """

        text_body = f"Name: {name}\nEmail: {email}\nCompany: {company or 'N/A'}\n\nMessage:\n{message}"

        ses.send_email(
            Source=FROM_EMAIL,
            Destination={"ToAddresses": [TO_EMAIL]},
            Message={
                "Subject": {"Data": subject},
                "Body": {
                    "Text": {"Data": text_body},
                    "Html": {"Data": html_body},
                },
            },
            ReplyToAddresses=[email],
        )

        return {
            "statusCode": 200,
            "headers": headers,
            "body": json.dumps({"message": "Email sent successfully"}),
        }
    except Exception as e:
        print(f"Error: {e}")
        return {
            "statusCode": 500,
            "headers": headers,
            "body": json.dumps({"error": "Failed to send message"}),
        }
