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

    * Refactor apply_pipeline a little?
    * native pipes and sources actually put into classes/data structures

    * in pipe/source arguments, replace `\n` to newlines

    * option to turn pipe/source macros into commands!!!!!!
    * new syntax: `{N pipe}` passes N to the pipe as a "desired amount" parameter
    * Variables in macros: `>define_pipe myPipe translate to=$VAR` is then used like `>>> hello > myPipe var=fr`
    * CTree flags:
        * [?] to produce a single random line instead of all possible lines
            [?] [alpha|beta] [gamma|delta] → alpha delta

    * **SPECULATIVE:**
    * Option to hide warnings log
    * Command to show most recent warnings log
    * >>>? to analyse a pipeline (to learn or debug!)
    * CTree flags:
        * [-] to produce a minimal number of lines that reach each choice leaf at least once (is this hard???)
            [-] [alpha|beta] [gamma|delta] → alpha gamma, beta delta