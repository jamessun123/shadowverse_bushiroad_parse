from flask import Flask, request, jsonify
import os
import uuid

# IMPORT your functions from existing files
from decklog_parser import parse_deck_page, load_bp_mappings
from build_deck_site import render_html, extract_en_image_url

# Google Drive
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2 import service_account

app = Flask(__name__)

FOLDER_ID = "1-zgElUGMt6nxqX5jin1rc1Tk-qJlduE5"

def upload_file(file_path):
    creds = service_account.Credentials.from_service_account_file(
        "service-account.json",
        scopes=["https://www.googleapis.com/auth/drive"]
    )

    service = build("drive", "v3", credentials=creds)

    file_metadata = {
        "name": os.path.basename(file_path),
        "parents": [FOLDER_ID]
    }

    media = MediaFileUpload(file_path, mimetype="text/html")

    file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id"
    ).execute()

    return f"https://drive.google.com/file/d/{file['id']}/view"

@app.route("/", methods=["POST"])
def run():
    data = request.json
    deck_code = data.get("deck_code")
    output_name = data.get("output_name", str(uuid.uuid4()))

    if not deck_code:
        return jsonify({"error": "Missing deck_code"}), 400

    try:
        load_bp_mappings()

        # Step 1: scrape
        deck_data = {
            "deck_code": deck_code,
            "cards": parse_deck_page(deck_code)
        }

        # Step 2: enrich cards (⚠️ potential cost hotspot)
        for card in deck_data["cards"]:
            en_link = card.get("en_cards_link", "")
            card["en_image_url"] = extract_en_image_url(en_link, "")

        # Step 3: render HTML
        html = render_html(deck_data, deck_data["cards"])

        # Step 4: save temp file
        file_path = f"/tmp/{output_name}.html"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(html)

        # Step 5: upload
        drive_link = upload_file(file_path)

        return jsonify({
            "status": "success",
            "drive_link": drive_link
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)