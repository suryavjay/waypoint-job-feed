from .feed import fetch_json_feed
URL='https://raw.githubusercontent.com/ApplyGuy/2027-Internships/main/data/internships.json'
def fetch():return fetch_json_feed('applyguy','ApplyGuy',URL)
