import json


def map_bettorodds(league: str):
    with open("response.json", "r") as f:
        data = json.load(f)
        print(data.keys())

    players = data.get("player")
    teams = data.get("team")
    market = data.get("market")

    with open("players.json", "w") as f:
        json.dump(players, f, indent=2)

    with open("teams.json", "w") as f:
        json.dump(teams, f, indent=2)

    with open("market.json", "w") as f:
        json.dump(market, f, indent=2)

    # for mapped_data in teams.values():
    #     original_team = mapped_data.get("query")
    #     found_team = next(
    #         team
    #         for team in mapped_data.get("teams")
    #         if league == team.get("league")
    #     )










map_bettorodds("NBA")