# Rezbot
A python-based discord bot using `discord.py`.

## I want to run this bot
* Clone the github repository
* Fill out `src/config.example.ini` and rename it to `src/config.ini`
* Put your own discord user ID (not your name) as an owner in `src/permissions.py`
* Install python packages: `discord.py`, `editdistance`, `parsetools`, `google-cloud-translate` ... (list incomplete)
* (Optional) Get a Google Cloud Translation API key [here](https://cloud.google.com/translate/docs/quickstart) and set it as an environment variable as described.
* Go to `src/` and run `py -3.6 ./bot.py`

## Features
* Some silly toy commands (`src/botcommands.py`)
* Subsystem that tests messages for regex patterns to reply/react to them (`src/patterns.py`)
* Downloading, searching through and sampling random captions from youtube videos (`src/resource/youtubecaps`)
* Markov and sample random quotes from user-uploaded txt files (`src/resource/upload`)
* A self-designed scripting system that works through discord messages (codenamed as just "pipelines" `src/pipes/`)
    For more information: See [PIPESGUIDE.md](./PIPESGUIDE.md)