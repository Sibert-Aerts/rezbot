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
        * {rand} for a random word (?)
        *

    * Format pipe that combines one or more inputs into a single output:
      `a | b | c > format %1 + %2 = %3` produces `a + b = c`

    * Kana to romaji pipe

    * Ability to assign custom pipes:
        * idk like `>>> telephone <- translate -> translate to=en`
        and then `>>> something something > telephone` works
        * allow for variables too: `>>> myPipe > translate to={var}` is then used like `>>> hello > myPipe var=fr` ?
        * These should then also save to a file, and have functions to see/edit/describe/delete them