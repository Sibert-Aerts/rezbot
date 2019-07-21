# To Do List

(In no particular order)

* **General:**
    * Read permissions from a file
    * Permission assignment commands
    * Ability to disable specific features (commands, patterns, pipes) in specific channels/servers
    * Logging? lotta work but idk the data would be fun...
    * rewrite `help` to spam less
    * post git commits to channel
    * come up with a name for the scripting language
    * unify/clarify parameter names for different pipes (e.g. q/query or whatever)

* **SCRIPTING:**

    * **Pipeline-level:**
        * Refactor pipelines to optimise applying the same one multiple times,
        right now, each time a macro is used the entire thing is parsed/executed/parsecuted PER use

    * **Sources:**
        * Youtube source
        * Recursively parse sources!
            e.g. {source1 arg={source2}} should work always

    * **Pipes:**
        * {prev *n*} for the nth previous output
        * {that *n*} for the nth previous message in the channel
        * {next *n*} for the nth next message in the channel (for the next message by a certain user in the channel?)

    * **Uploaded files:**
        * "Append to file" pipe (+ make new file if file doesn't exist yet)
        * "replace specified line" pipe
        * download file command

    * option to turn macros into commands
    * namespaces/categories for macros, like: funny.item or random.word or whatever....

    * **SPOUTS:**
        * look more smarter at the list of "spout callbacks" and what it should actually be doing
        * implement `print` as a spout
        * option for a pipeline to print nothing to console, e.g. so that events can silently cause side-effects

    * **EVENTS:**
        * bot saves & loads Events from a file
        * more types of triggers: MESSAGE CONTAINS (regex), USER IS (username/id), TIME IS (?), logical operations?? ????

    * **GROUP MODES:**
        * #a..b;c..d;e..f [pipe1|pipe2|pipe3]           should work as is obvious
        * *#a..b [pipe1|pipe2]              should work as          #a..b ( *[pipe1|pipe2] )
        * (1;2;3) [pipe1|pipe2|pipe3]       should kinda work as    (6) (#0..1;1..3;3..6 [pipe1|pipe2|pipe3])
        * (same for others???)

    * **CONDITIONS:**
        * Add logical operations: NOT/AND/OR/XOR
        * Different base conditions:
            * x = y         checks the variables (get, set) x and y
            * count < 10    checks if the number of items is less than 10

    * **BUGS:**
        * make all sources addressable as both singular and plural in ALL CONTEXTS
        * (check if all pipes don't accidentally change `input` in place, because it is passed by reference and this breaks the flow)
    
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
        * Flow control? conditional `return` pipes so loops are easier?
        * pipes have an associated "complexity" cost function based on args/input values that makes sure a user doesn't request absurdly much work...?

    * **??????**
        * Actually execute parallel pipes "in parallel" using asyncio????