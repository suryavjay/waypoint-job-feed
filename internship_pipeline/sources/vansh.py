from .feed import fetch_json_feed
URL='https://raw.githubusercontent.com/vanshb03/Summer2027-Internships/dev/.github/scripts/listings.json'
def fetch():return fetch_json_feed('vansh','Vansh',URL,summer_scope=True)
