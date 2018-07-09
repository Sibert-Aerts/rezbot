# Rezbot
A python-based discord bot using `discord.py`.

## I want to run this bot
* Clone the github repository
* Fill out `src/config.example.ini` and rename it to `src/config.ini`
* Put your own discord user ID (not your name) as an owner in `src/permissions.py`
* Install python packages: `discord.py`, `editdistance`, `parsetools`, `google-cloud-translate` ... (list incomplete)
* (Optional) Get a Google Cloud Translation API key [here](https://cloud.google.com/translate/docs/quickstart) and set it as an environment variable as described.
* Go to `src/` and run `python3 ./bot.py`

## Features
* A couple of silly commands, nothing special (`src/botcommands.py`)
* Subsystem that tests messages for regex patterns and acts on them (`src/patterns.py`)
* Pipes (`src/pipes/`)
* Youtube caption saving and searching (`src/resource/youtubecaps`)
* Txt file saving and searching (`src/resource/upload`)

## Pipes
The killer feature. For more info read PIPESGUIDE.md

### I want to add pipes
(this section may be outdated)
Excellent, jump into `src/pipes/pipes.py`, here you can see the various pipes defined as decorated functions.  
For example, the code for the `sub` pipe looks like this:

```py
@make_pipe({
    'fro': Sig(str, None, 'Pattern to replace (regex)'),
    'to' : Sig(str, None, 'Replacement string'),
})
@as_map
def sub_pipe(text, fro, to):
    '''Substitutes patterns in the input.'''
    return re.sub(fro, to, text)
```

Several things going on here:
* The `@make_pipe` decorator, which takes a dict mapping argument names to `Sig` objects
    * Make a `Sig` using `Sig(type, default=None, desc=None, check=None)`:
        * `type` is what the argument should be parsed as, e.g. `int`
        * `default` is the default value in case the argument is not given, if `None` this marks the argument as required.
        * `desc` is a string describing the argument.
        * `check` is a function that verifies if the parsed value is valid, e.g. `lambda x: x >= 0` if you only want positive values.
* The `@as_map` decorator, an optional decorator for pipes that act on individual strings rather than lists of strings.
* The inner function:
    * The name should be `[pipe name]_pipe`, so that the pipe can be addressed as `[pipe name]`
    * The docstring for this function is shown when you request `>pipes [pipe name]`, so make it informative.
    * The first argument is the input, because of `@as_map`, this is a string, otherwise it would be a list of strings.
    * The following arguments are the arguments that `@make_pipe` parses for you, notice that these variables need to use the argument names that you passed to `@make_pipe`.
    * The return value should also be a string if `@as_map` is used, otherwise it should be a list of strings.

So now you can make your own pipes, feel free to create a pull request if you come up with any good ones, the more the merrier.

For more information on how the decorators work or to extend their functionality (argument parsing is really dumb currently), take a look at `src/pipes/arguments.py`.  
If anything seems particularly mysterious/stupid, or if you have a crazy idea, I would love for you to send me a message.
