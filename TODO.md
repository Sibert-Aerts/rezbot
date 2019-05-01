# To Do List

(In no particular order)

* **CRITICAL:**
    * pipes/sources as commands doesn't work as of discord.py v1.0!!!!

* **General:**
    * Read permissions from a file
    * Permission assignment commands
    * Ability to disable specific features (commands, patterns, pipes) in specific channels/servers
    * Logging? lotta work but idk the data would be fun...
    * rewrite `help` to spam less
    * post git commits to channel
    * different txt's for other languages
    * come up with a name for the scripting language
    * unify/clarify parameter names for different pipes (e.g. q/query or whatever)

* **SCRIPTING:**

    * **Pipeline-level:**
        * Refactor pipelines to optimise applying the same one multiple times,
        right now, each time a macro is used the entire thing is parsed/executed/parsecuted PER use

    * **Sources:**
        * Youtube source

    * **Pipes:**
        * {prev *n*} for the nth previous output
        * {that *n*} for the nth previous message in the channel
        * {next *n*} for the nth next message in the channel (for the next message by a certain user in the channel?)

    * TXT uploads:
        * figure out more things to do with them

    * option to turn macros into commands!!!!!!
    * parse sources inside of ARGS
    * ways to use FLOW ITEMS as/in ARGS
    * namespaces/categories for macros, like: funny.item or random.word or whatever....

    * **SPOUTS:**
        * output to new txt file
        * append to existing txt file
        * (output to image??)
        * spout callback is a list of every callback encountered?
        * spout just straight up ends the pipeline then and there??
        * implement `print` as a spout

    * **EVENTS:**
        * ability to define/edit/delete Events by name
        * ability to enable/disable specific Events in a channel
        * bot saves & loads Events from a file
        * more types of triggers: MESSAGE CONTAINS (regex), USER IS (username/id), TIME IS (?), logical operations?? ????

    * **BUGS:**
        * make all sources addressable as both singular and plural in ALL CONTEXTS
        * check if all pipes don't accidentally change `input` in place, because it is passed by reference and this breaks the flow
    
    * **PARSING BUGS:**
        * `>>> foo > bar x=( > baz` doesn't understand the ( should be a character and not a parenthesis (circumventable by writing `x="("`)
        * `>>> foo > bar x='"' > baz` similarly, the " is interpreted as opening a string that is never closed, circumvented by adding a closing " afterwards but that's stupid
        * `x="""some"thing"""` turns into `x="some"thing"`, so x only gets "some" as an argument, probably should be much smarter
        * `>>> """choice-escaped source"""` is not possible right now

    * **SPECULATIVE:**
        * Option to hide warnings log
        * Command to show most recent warnings log
        * >>>? to analyse a pipeline (to learn or debug!)
        * ChoiceTree flags:
            * [-] to produce a minimal number of lines that reach each choice leaf at least once (is this hard???)
                [-] [alpha|beta] [gamma|delta] → alpha gamma, beta delta
        * in pipe/source arguments, replace `\n` to newlines
        * Flow control? conditional `return` pipes so recursive yet halting pipelines are possible?
        * pipes have an associated "complexity" cost function based on args/input values that makes sure a user doesn't request absurdly much work...?

    * **??????**
        * Actually execute parallel pipes in parallel using asyncio????