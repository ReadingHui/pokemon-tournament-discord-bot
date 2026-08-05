import requests
import json
import os

from parser import Parser
from embed import Embedder

with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

TOM_path = config["TOM_DATA_path"]
webhook_url = config["webhook_url"]

def send_to_webhook(webhook_url: str, content: str, title:str=None, embed=True):
    # Discord message payload
    payload = {
        "title": title,
        "description": content,
        # "username": "Pokemon Tournament Bot",  # Optional custom bot display name
    }

    if embed:
        payload = {
            "embeds": [
                {
                    "title": title,
                    "description": content,
                    # "username": "Pokemon Tournament Bot",  # Optional custom bot display name
                }
            ]
        }

    else:
        payload = {
            "content": content
        }

    response = requests.post(webhook_url, json=payload)

    if response.status_code == 204:
        print("Successfully sent message to Discord!")
    else:
        print(
            f"Failed to send message: {response.status_code} - {response.text}"
        )

def send_roster(name):
    roster_name = name + "roster.html"
    roster_path = os.path.join(TOM_path, "data", "reports", roster_name)
    with open(roster_path, "r", encoding="utf-8") as file:
        html_content = file.read()

    parser = Parser(html_content)
    report_type, tournament_name, organizer_name, date_time = parser.parse_meta()
    roster_content = parser.parse_roster()
    roster_embedder = Embedder('roster')
    messages = roster_embedder.build(roster_content)
    send_to_webhook(webhook_url, "# 📝 Player Roster:", embed=False)
    for div, message in messages.items():
        for chunk in message['content']:
            send_to_webhook(webhook_url, chunk, message['title'])

def send_pairing(name):
    pass

def main():
    # name = input("Tournament Name: ")
    name = "testing" # For testing
    send_roster(name)
    send_pairing(name)
    


if __name__ == "__main__":
    main()
    