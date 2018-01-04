import xml.etree.ElementTree as ET
import random
import os
import re

from fuzzywuzzy import fuzz, process

def HERE(FILENAME):
    return os.path.join(os.path.dirname(__file__), FILENAME)

class ISSUE:
    def __init__(self, ISSUE):
        self.NUM = ISSUE.attrib['num']
        self.TITLE = ISSUE[0].text
        self.DATE = ISSUE[1].text
        self.DIALOG = ISSUE[2].text

    def URL(self):
        return f'https://jerkcity.com/jerkcity{self.NUM}.html'

    def IMAGE_URL(self):
        return f'https://jerkcity.com/jerkcity{self.NUM}.gif'

class __JERKCITY__:
    def __init__(self):
        ROOT = ET.parse(HERE('dialog.xml')).getroot()
        self.ISSUES = [ISSUE(I) for I in ROOT]

    def GET_RANDOM(self, AMOUNT=0):
        if AMOUNT <= 0:
            return random.choice(self.ISSUES)
        else:
            return random.sample(self.ISSUES, AMOUNT)

    def GET(self, NUM):
        return self.ISSUES[NUM-1]

    # I CAN'T BELIEVE THIS IS WHAT FUZZYWUZZY ASKS OF ME
    class __QUERY__:
        def __init__(self, QUERY):
            self.TITLE = ''
            self.DIALOG = QUERY

    def SEARCH(self, QUERY, AMOUNT=0):
        QUERY = __JERKCITY__.__QUERY__(QUERY)
        # PARTIAL_RATIO FEELS RIGHT
        RESULTS = process.extract(QUERY, self.ISSUES, processor=lambda X: X.TITLE+'\n'+X.DIALOG, scorer= fuzz.partial_ratio, limit=max(5, AMOUNT))

        # RESULTS IS A LIST OF (ISSUE_XML, SCORE) TUPLES
        if AMOUNT == 0:
            # CHECK IF THE TOP RESULT'S SCORE IS MUCH (TEN) BIGGER THAN THE RUNNER UP
            if RESULTS[0][1] > RESULTS[1][1] + 10:
                return RESULTS[0][0]
            else:
                return random.choice(RESULTS)[0]
        else:
            return [RESULT[0] for RESULT in random.sample(RESULTS, AMOUNT)]

JERKCITY = __JERKCITY__()