from flask import Flask, request, jsonify
import json
import logging
import os
import uuid

# IMPORT your functions from existing files
from decklog_parser import parse_deck_page, load_bp_mappings
from build_deck_site import render_html, extract_en_image_url

# Google Drive
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google.cloud import secretmanager

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)

FOLDER_ID = "1-zgElUGMt6nxqX5jin1rc1Tk-qJlduE5"
TOKEN_SECRET_NAME = os.environ.get(
    "GOOGLE_OAUTH_TOKEN_SECRET_RESOURCE",
    "projects/shadowverse-494623/secrets/drive-oauth-token/versions/latest"
)

def load_token():
    logger.debug("Loading OAuth token from Secret Manager: %s", TOKEN_SECRET_NAME)
    client = secretmanager.SecretManagerServiceClient()
    response = client.access_secret_version(request={"name": TOKEN_SECRET_NAME})
    token_data = response.payload.data.decode("utf-8")
    logger.debug("Loaded token payload (%d bytes)", len(token_data))
    return json.loads(token_data)


def get_drive_service():
    SCOPES = ["https://www.googleapis.com/auth/drive"]
    logger.debug("Initializing Drive service with scopes: %s", SCOPES)

    token_info = load_token()
    creds = Credentials.from_authorized_user_info(token_info, SCOPES)
    logger.debug("Loaded credentials, expired=%s refresh_token=%s", creds.expired, bool(creds.refresh_token))

    if creds.expired and creds.refresh_token:
        logger.debug("Refreshing expired credentials")
        creds.refresh(Request())
        logger.debug("Credentials refreshed")

    service = build("drive", "v3", credentials=creds)
    logger.debug("Drive service built successfully")
    return service

def upload_file(file_path):
    logger.debug("Preparing to upload file: %s", file_path)
    service = get_drive_service()

    file_metadata = {
        "name": os.path.basename(file_path),
        "parents": [FOLDER_ID]
    }
    logger.debug("Uploading to folder: %s", FOLDER_ID)

    media = MediaFileUpload(file_path, mimetype="text/html")
    file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id"
    ).execute()
    logger.debug("Upload complete; file id=%s", file.get("id"))

    return f"https://drive.google.com/file/d/{file['id']}/view"

@app.route("/", methods=["POST"])
def run():
    data = request.json
    deck_code = data.get("deck_code")
    output_name = data.get("output_name", str(uuid.uuid4()))
    logger.debug("Received request: deck_code=%s output_name=%s", deck_code, output_name)

    if not deck_code:
        logger.debug("Request missing deck_code")
        return jsonify({"error": "Missing deck_code"}), 400

    try:
        logger.debug("Loading BP mappings")
        load_bp_mappings()

        logger.debug("Parsing deck page for deck_code: %s", deck_code)
        deck_data = {
            "deck_code": deck_code,
            "cards": parse_deck_page(deck_code)
        }

        logger.debug("Enriching card data with English image URLs")
        for card in deck_data["cards"]:
            en_link = card.get("en_cards_link", "")
            card["en_image_url"] = extract_en_image_url(en_link, "")

        logger.debug("Rendering HTML output")
        html = render_html(deck_data, deck_data["cards"])

        file_path = f"/tmp/{output_name}.html"
        logger.debug("Saving rendered HTML to temporary file: %s", file_path)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(html)

        logger.debug("Uploading generated file to Google Drive")
        drive_link = upload_file(file_path)
        logger.debug("Upload finished; drive_link=%s", drive_link)

        return jsonify({
            "status": "success",
            "drive_link": drive_link
        })

    except Exception as e:
        logger.exception("Unhandled exception during request processing")
        return jsonify({"error": str(e)}), 500
    
if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)