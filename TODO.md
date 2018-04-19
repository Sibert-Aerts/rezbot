# To Do List

(In no particular order)


* **General:**
    * Read permissions from a file
    * Permission assignment commands
    * Ability to disable specific features (commands, patterns, pipes) in specific channels/servers
    * Logging? lotta work but idk the data would be fun...
    * rewrite `help` to spam less

* **Pipes:**
    * Youtube source

    * Error output!!!

    * >>>? to analyse a pipeline (to learn or debug!)

    * Refactor apply_pipeline a little?

    * native pipes and sources actually put into classes/data structures

    * CTree flags:
        * [?] to produce a single random line instead of all possible lines
            [?] [alpha|beta] [gamma|delta] → alpha delta
        * [-] to produce a minimal number of lines that reach each choice leaf at least once
            [-] [alpha|beta] [gamma|delta] → alpha gamma, beta delta

    * Genericize pipe inputs:
        * {prev *n*} for the nth previous output
        * {that *n*} for the nth previous message in the channel
        * {next *n*} for the nth next message in the channel (for the next message by a certain user in the channel?)

    * new syntax: `{N pipe}` passes N to the pipe as a "desired amount" parameter

    * Automatically `source-eval` all input in commands-from-pipes

    * option to turn pipe/source macros into commands!!!!!!

    * fix indentation/newlines in docstrings in `>pipes` and `>sources` list view

    * in pipe/source arguments, replace \n to newlines

    * Variables in macros: `>define_pipe myPipe translate to=$VAR` is then used like `>>> hello > myPipe var=fr`