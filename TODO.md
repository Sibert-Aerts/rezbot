# To Do List

(In no particular order)


* **General:**
    * Read permissions from a file
    * Permission assignment commands
    * Ability to disable specific features (commands, patterns, pipes) in specific channels/servers
    * Logging? lotta work but idk the data would be fun...

* **Pipes:**
    * Genericize pipe inputs:
        * {prev *n*} for the nth previous output
        * {that *n*} for the nth previous message in the channel
        * {next *n*} for the nth next message in the channel (for the next message by a certain user in the channel?)

    * new syntax: {n pipe} passes n to the pipe indicating the number of desired outputs

    * Automatically `source-eval` all input in commands-from-pipes

    * in pipe/source arguments, replace \n to newlines

    * Custom pipes with replacement rules:
        * allow for variables too: `>define_pipe myPipe translate to={var}` is then used like `>>> hello > myPipe var=fr`