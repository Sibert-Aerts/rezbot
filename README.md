# Rezbot
A python-based discord bot using `discord.py` for python 3.6.

## I want to run this bot
* Clone the github repository
* Fill out `src/config.example.ini` and rename it to `src/config.ini`
* Put your own discord user ID (not your name) as an owner in `src/permissions.py`
* Install python modules: `discord.py`, `editdistance`, `parsetools`, `google-cloud-translate` ... (list incomplete)
* Install python module `spacy` and then its English language model via `py -3.6 -m spacy download en_core_web_sm`
* (Optional) Get a Google Cloud Translation API key [here](https://cloud.google.com/translate/docs/quickstart) and set it as an environment variable as described.
* Go to `src/` and run `py -3.6 ./bot.py`

## Contains
* Simple toy commands (`src/botcommands.py`)
* Simple script that checks messages for specific patterns to reply/react to (`src/patterns.py`)
* ~~Downloading, searching through and sampling random captions from youtube videos (`src/resource/youtubecaps`)~~ (currently broken)
* Users can upload txt files, sample quotes from them, generate Markov chains from, apply NLP analysis, etc. via bot commands (`src/resource/upload`)
* A unique scripting language designed to be used via discord messages (codenamed as "pipes" `src/pipes/`)
    * One-time scripts can be quickly written or copy-pasted to generate amusing results
    * Reactive scripts can be made to perform simple toy tasks (e.g. react to every mention of bananas with a banana emoji)  
    but can be used to script more complicated interactions (e.g. fetching a picture from a matching Wikipedia page when a user says "show me xyz"),
    without ever having to leave the discord message box or write a line of python code
    
    (See [PIPESGUIDE.md](./PIPESGUIDE.md) for more information)
