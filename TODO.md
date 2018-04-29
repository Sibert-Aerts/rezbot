# To Do List

(In no particular order)


* **General:**
    * Read permissions from a file
    * Permission assignment commands
    * Ability to disable specific features (commands, patterns, pipes) in specific channels/servers
    * Logging? lotta work but idk the data would be fun...
    * rewrite `help` to spam less
    * post git commits to channel
    * clean out words.txt
    * different txt's for other languages

* **Pipes:**
    * Youtube source
    * Genericize pipe inputs:
        * {prev *n*} for the nth previous output
        * {that *n*} for the nth previous message in the channel
        * {next *n*} for the nth next message in the channel (for the next message by a certain user in the channel?)

    * cowsay complains about shit & shouldn't

    * in pipe/source arguments, replace `\n` to newlines

    * option to turn pipe/source macros into commands!!!!!!
    * Variables in macros: `>define_pipe myPipe translate to=$var$` is then used like `>>> hello > myPipe var=fr`

    * Argument parsing: `format Hello, {}!` should work the same as `format f="Hello, {}!"`

    * **BUGS:**
    * Sources can't contain >'s or ('s (without putting it in quotes which is dumb)

    * **SPECULATIVE:**
    * Option to hide warnings log
    * Command to show most recent warnings log
    * >>>? to analyse a pipeline (to learn or debug!)
    * ChoiceTree flags:
        * [-] to produce a minimal number of lines that reach each choice leaf at least once (is this hard???)
            [-] [alpha|beta] [gamma|delta] → alpha gamma, beta delta