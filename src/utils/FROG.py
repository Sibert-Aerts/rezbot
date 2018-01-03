import requests

# PYTHON WRAPPER FOR THE FROG TIPS API
# FOR MORE INFORMATION PLEASE CONSULT HTTPS://FROG.TIPS/API/1/

API_ENDPOINT = 'https://frog.tips/api/1/tips/'

# I DON'T KNOW HOW TO APPLY THE SINGLE INSTANCE PATTERN IN PYTHON SO HERE GOES
class __FROG__:
    def __init__(self):
        self.BUCKET = []

    def FILL_BUCKET(self):
        RESULT = requests.get(API_ENDPOINT)
        if RESULT.status_code != 200: return
        TIPS = RESULT.json()['tips']
        # WHY WOULD THIS API GIVE 0 TIPS
        if len(TIPS) == 0:
            self.FILL_BUCKET()
        else:
            self.BUCKET = TIPS

    def GET_RANDOM(self):
        if not self.BUCKET:
            self.FILL_BUCKET()
        return self.BUCKET.pop()

    def GET_TIP(self, NUMBER=None):
        if NUMBER is None:
            return self.GET_RANDOM()
        RESULT = requests.get(API_ENDPOINT + str(NUMBER))
        if RESULT.status_code != 200:
            return {'number': -1, 'tip': 'FROG not found. Meditate on FROG.'}
        return RESULT.json()

FROG = __FROG__()