import json
import os
from bs4 import BeautifulSoup

class Parser:
    def __init__(self, html_content):
        self.soup = BeautifulSoup(html_content, "html.parser")
        headings = self.soup.find_all("h3", string=lambda x: x and "Division" in x)
        self.divs = [heading.get_text().split(' ')[0] for heading in headings]

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

    def parse_roster(self):
        # Extract Divisions        
        divs = self.divs
        roster = {}

        for div in divs:
            target_h3 = self.soup.find("h3", string=lambda x: x and div in x)
            table = target_h3.find_next("table", class_="players_table")
            headers = [col.get_text().replace('\xa0', ' ') for col in table.select("thead tr th")]
            name_idx = headers.index('Name')
            players = [row[name_idx] for row in self.get_rows(table)]
            roster[div] = players

        return roster

if __name__ == "__main__":
    # Testing case
    with open("config.json", "r", encoding="utf-8") as f:
        config = json.load(f)

    TOM_path = config["TOM_DATA_path"]
    with open(os.path.join(TOM_path, "data", "reports", "testingroster.html"), "r", encoding="utf-8") as file:
            html_content = file.read()
    parser = Parser(html_content)
    parser.parse_meta()
    parser.parse_roster()