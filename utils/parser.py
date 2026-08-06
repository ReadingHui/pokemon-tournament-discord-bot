import json
import html
import re
from bs4 import BeautifulSoup

class Parser:
    def __init__(self, html_content):
        self.soup = BeautifulSoup(html_content, "html.parser")

    def parse_meta(self, verbose=False):
        html_title = self.soup.find("title").get_text()
        report_type = html_title.split(' - ')[0].strip()
        tournament_name = self.soup.select_one("table.footer tr td:nth-child(1)").get_text(strip=True)
        organizer_name = self.soup.select_one("table.footer tr td:nth-child(2)").get_text(strip=True)
        date_time = self.soup.select_one("table.footer tr td:nth-child(3)").get_text(strip=True)
        if verbose:
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

    def get_player_record(self, td: str):
        text = html.unescape(td)
        text = re.sub(r'\s+', ' ', text).strip()
        text = re.sub(r'★', ' ', text).strip()
        match = re.match(r'^(.*?)\s*(\(.*\))$', text)
        if match:
            name, record = match.groups()
            return name, record
        else:
            raise SyntaxError("[Error] Cannot parse player name and record.")

    def parse_pairing(self):
        round_num = self.soup.find("h3", string=re.compile(r"Round")).get_text().split(' ')[-1]
        round_info = {}
        divs = self.soup.find_all("h3", string=re.compile(r"Division"))
        if not divs:
            divs = self.soup.find("h3", string=re.compile(r"All"))
        for div in divs:
            div_name = div.get_text()
            player_info = {}
            table = div.find_next("table", class_="report")
            rows = table.find_all("tr")
            for row in rows:
                cols = [td.get_text().strip() for td in row.select("td")]
                if not cols:
                    continue
                player, record = self.get_player_record(cols[1])
                if player not in player_info:
                    player_info[player] = {
                        'table': cols[0],
                        'opponent': cols[3].split('\xa0')[0],
                        'record': record
                    }
                else:
                    raise ValueError("Same name for players.")

            round_info[div_name] = player_info
        return {
            round_num: round_info
        }

    def get_player_standing(self, cols):
        rank = int(cols[0].strip())
        name = cols[1].strip()
        drop_rd = int(cols[3].strip()) if cols[3] else "N/A"
        record = cols[4].strip()
        match_pts = int(cols[5].strip())
        opp_win = cols[6].strip()
        opp_opp_win = cols[7].strip()
        return name, {
            "Rank": rank,
            "Drop Round": drop_rd,
            "Record": record,
            "Match Points": match_pts,
            "Opponents' win %": opp_win,
            "Opponents' opponents' win %": opp_opp_win
        }

    def parse_standings(self):
        rounds = [h3.get_text().strip() for h3 in self.soup.find_all("h3", string=re.compile("Standings"))]
        divs = self.soup.find_all("h2", string=re.compile("Division")) 
        player_info = {}
        for i, div in enumerate(divs):
            div_name = div.get_text().strip()
            table = div.find_next("table", class_="report")
            rows = table.find_all("tr")
            for row in rows:
                cols = [td.get_text().strip() for td in row.select("td")]
                if not cols:
                    continue
                player, standing = self.get_player_standing(cols)
                standing['Division'] = div_name
                standing['Rounds'] = rounds[i]
                if player not in player_info:
                    player_info[player] = standing
                else:
                    raise ValueError("Same name for players.")
        return player_info

        


if __name__ == "__main__":
    # Testing case
    with open("config.json", "r", encoding="utf-8") as f:
        config = json.load(f)

    TOM_path = config["TOM_DATA_path"]
    with open("data/testingroster.html", "r", encoding="utf-8") as file:
        html_content = file.read()
    parser = Parser(html_content)
    parser.parse_meta()
    print()

    print("parse_player_list() output:")
    print(parser.parse_player_list())
    print()

    with open("data/testingpairings.html", "r", encoding="utf-8") as file:
        html_content = file.read()
    parser = Parser(html_content)
    print("parse_pairing() output:")
    print(parser.parse_pairing())
    print()

    with open("data/testingstandings.html", "r", encoding="utf-8") as file:
        html_content = file.read()
    parser = Parser(html_content)
    print("parse_standings() output:")
    print(parser.parse_standings())