import re

class WordleInfo:
    SPLITTER = re.compile(r'[a-zA-Z][?!]?')

    def __init__(self, line: str):
        letters = WordleInfo.SPLITTER.findall(line)
        self.n = n = len(letters)
        self.raw = line

        self.green = [None] * n
        self.yellow = [None] * n
        pseudogrey = []
        self.max = {}
        self.grey = []

        self.emoji = ''

        for i in range(n):
            letter = letters[i]
            if letter[-1] == '!':
                self.green[i] = letter[0]
                self.emoji += '🟩'
            elif letter[-1] == '?':
                self.yellow[i] = letter[0]
                self.emoji += '🟨'
            else:
                pseudogrey.append(letter[0])
                self.emoji += '⬛'

        ## Special case: Letters grayed out for already being sufficiently present in green/yellow
        for c in pseudogrey:
            if c not in self.green and c not in self.yellow:
                self.grey.append(c)
            else:
                self.max[c] = self.green.count(c) + self.yellow.count(c)

        self.solved = (None not in self.green)

    def test(self, word: str):
        if len(word) != self.n:
            return False

        if any( c in word for c in self.grey ):
            return False
        if any( word.count(c) > self.max[c] for c in self.max ):
            return False
        if any( c and (c not in word) for c in self.yellow ):
            return False
        for i in range(self.n):
            if self.yellow[i] and word[i] == self.yellow[i]:
                return False
            if self.green[i] and word[i] != self.green[i]:
                return False
        return True


def create_info(word: str, guess: str):
    n = len(word)
    if n != len(guess): raise ValueError('Bad guess length!')

    freq = {}
    for c in word:
        if c not in freq: freq[c] = 1
        else: freq[c] += 1

    infostr = ''
    # Green letters take precedence on depleting the letter frequency
    for i in range(n):
        if word[i] == guess[i]:
            freq[guess[i]] -= 1

    for i in range(n):
        if word[i] == guess[i]:
            infostr += guess[i] + '!'
        elif guess[i] in word and freq[guess[i]] > 0:
            infostr += guess[i] + '?'
            freq[guess[i]] -= 1
        else:
            infostr += guess[i]

    return WordleInfo(infostr)





if __name__ == '__main__':
    info = WordleInfo('a?b!cde?')
    print(info.emoji)
    print(info.test('abcde'))
    print(info.test('xbaxe'))
    print(info.test('xbaex'))

    print()
    create_info('apple', 'banan')
    print()
    create_info('apple', 'ample')
    print()
    create_info('apple', 'apppe')
    print()
    create_info('apple', 'rocks')