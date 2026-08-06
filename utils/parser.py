import json
import os
from bs4 import BeautifulSoup

class Parser:
    def __init__(self, html_content):
        self.soup = BeautifulSoup(html_content, "html.parser")

    def parse_meta(self):
        html_title = self.soup.find("title").get_text()
        report_type, tournament_name, date_time = [t.strip() for t in html_title.split('-')]
        organizer_name = self.soup.select_one("table.footer tr td:nth-child(2)").get_text(strip=True)
        print()
        print(f"Report type:            {report_type}")
        print(f"Tournament name:        {tournament_name}")
        print(f"Organizer name:         {organizer_name}")
        print(f"Report date and time:   {date_time}")
        return report_type, tournament_name, organizer_name, date_time


    def get_rows(self, table):
        all_rows = table.select("tbody tr")
        rows = []
        for row in all_rows:
            cols = [td.get_text(strip=True) for td in row.find_all("td")]
            rows.append(cols)
        return rows

    def parse_player_list(self):
        headers = [col.get_text().replace('\xa0', ' ') for col in self.soup.select_one("table.players_table thead tr").find_all("th")]
        name_idx = headers.index('Name')
        age_division_idx = headers.index("Age Division")
        static_seat_idx = headers.index("Static Seat")

        players = {}
        rows = self.soup.select(".players_table tbody tr")
        for row in rows:
            cols = [s.get_text().strip() for s in row.find_all('td')]
            name = cols[name_idx]
            age_division = cols[age_division_idx]
            static_seat = int(cols[static_seat_idx]) if cols[static_seat_idx] else 0
            player_info = {
                'discord_id': None,
                'age_division': age_division,
                'static_seat': static_seat
            }
            players[name] = player_info
        
        return players

    def parse_pairing(self):
        pass


if __name__ == "__main__":
    # Testing case
    with open("config.json", "r", encoding="utf-8") as f:
        config = json.load(f)

    TOM_path = config["TOM_DATA_path"]
    with open(os.path.join(TOM_path, "data", "reports", "testingroster.html"), "r", encoding="utf-8") as file:
        html_content = file.read()
    parser = Parser(html_content)
    parser.parse_meta()
    print()

    print("parse_player_list() output:")
    print(parser.parse_player_list())
    print()

    with open(os.path.join(TOM_path, "data", "reports", "testingpairings.html"), "r", encoding="utf-8") as file:
        html_content = file.read()
    parser = Parser(html_content)
    print("parse_pairing() output:")
    print(parser.parse_pairing())