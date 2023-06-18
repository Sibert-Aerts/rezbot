# To Do List

(In no particular order)




* **NEW HOTNESS: VIEWS/BUTTONS**

    * Probably useful to have some kind of generic RezbotView base class
        * When bot dies (through >die or otherwise?) close (= run ontimeout) ALL UI Views

    * Multiple text inputs on a single modal?
        * label1, label2, label3, ...?
        * input_label1, input_label2, input_label3, ...?

    * View/Button/Slash command interfaces for browsing/managing uploaded files

    * Slash command autocomplete is nice, but make it *try* interpreting a non-autocompleted input too, so you don't have to wait for it if you're certain

* **General:**
    * Ability to disable specific features (commands, patterns, pipes) in specific channels/servers
    * rewrite `help` to spam less
    * come up with a name for the scripting language
    * Global "existing name directory" so you can never have overlapping source/pipe/spout/event/macro names, even if they're unique within their category?

* **SCRIPTING:**

    * Objects need a ".full_name" or something e.g. `Pipe: convert`, `Pipe Macro: smoog`, `OnMessage Event: spinkus`

    * **Script analysis:**
        * Warn if certain parallel pipes are unreachable for the given groupmode

    * **Parameters:**
        * Option-parameters can be smarter (e.g. "nick" counts as "nickname" if it's the unique option starting with "nick")
        * Possibly warn about unused pieces of argstring (e.g. `{txt file=heck hell}` warns about `hell` being there for no reason)

    * **Sources:**
        * `creates_min: int` and `creates_max: int|None` attributes, idk, would be fun
            * `creates: int` which sets both at once

    * **Pipes:**
        * (Nothing)

    * **TemplatedString:**
        * Implicit item indexing doesn't work for combination implicit and explicit args
            * `param={} {}` gives `param={1} {0}` instead of `param={0} {1}` (because internally it's all the same as `implicitparam={0} param={1}`
        * Implicit item indexing doesn't work exactly as expected with nested sources
            * `{} {word pattern={}} {}` gives `{0} {word pattern={0}} {1}` instead of `{0} {word pattern={1}} {2}`

    * **Uploaded files:**
        * "Append to file" spout (which creates a new file if it doesn't exist yet)
        * "replace specified line" spout
        * Allow structured files (json)

    * **Macros:**
        * Way of easily turning macros into commands
        * Custom namespaces for macros and events
            * Decreases clutter of the global macros/events lists
            * Can easily see related macros/events in one place
            * Easily enable/disable all events in a namespace at the same time

    * **SPOUTS:**
        * Split Spouts into (at least) 2 functions:
            * collect( discord_ctx, spout_state, values, args ) → spout_state
                Called each time the spout is encountered in a script, spout_state replaces SPOUT_CALLBACKS
                and is a (spout-specific?) state object that the spout adds its own information to if it needs to

                e.g. in the current model they just add a callback to spout_state

            * callback( spout_state )
                called (on each addressed spout? on EACH spout???) when the Script reaches its end, allowing each spout to sort out its collected state

                e.g. in the current model they just execute each of their callbacks in spout_state

    * **EVENTS:**
        * more types of conditions: MESSAGE CONTAINS (regex), USER IS (username/id), TIME IS (?), logical operations?? ????
        * `ON COMMAND !praise name` would allow acces to argument `name` by using `{arg name}`?

    * **GROUP MODES:**
        * #a:b,c:d,e:f [pipe1|pipe2|pipe3]           should work as is obvious
        * (1,2,3) [pipe1|pipe2|pipe3]       should kinda work as    (6) (#0:1,1:3,3:6 [pipe1|pipe2|pipe3])
        * (same for others???)

    * **CONDITIONS:**
        * Phase out usage of the old syntax `{ }` vs. new `IF(( ))` and `SWITCH(( ))`
        * Furthermore, don't reference items as 0 or 1, but as {0} or {1} for uniformity, and maybe just full-on obey Context ignore/remove logic
        * Allow logical operations and clauses
        * Evaluating sources or even pipes inside condition expressions? e.g. instead of `*[count|] > {0="1"} [...]` something like `{count="1"} [...]`

    * **PARSING BUGS:**
        * `>> foo > bar x=( > baz` doesn't understand the ( should be a character and not a parenthesis (circumventable by writing `x="("`)
        * `>> foo > bar x='"' > baz` similarly, the " is interpreted as opening a string that is never closed, circumvented by adding a closing " afterwards but that's stupid

    * **SPECULATIVE:**
        * Allow pipe(line)s as arguments, somehow
            * e.g. `sub_func from=\b(\w) to=( convert fraktur )`

        * Option to hide warnings log
        * Command to show most recent warnings log
        * Special mode to analyse how a pipeline is parsed for debugging or learning purposes
        * ChoiceTree flags:
            * [-] to produce a minimal number of lines that reach each choice leaf at least once (is this hard???)
                [-] [alpha|beta] [gamma|delta] → alpha gamma, beta delta
        * in pipe/source arguments, replace `\n` to newlines
        * conditional `return` pipes so loops are easier?
        * pipes have an associated "complexity" cost function based on args/input values that makes sure a user doesn't request absurdly much work...?