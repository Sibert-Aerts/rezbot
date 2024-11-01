# To Do List

(In no particular order)


* **WIP features**

    * Ability to create/modify events and macros en-masse by uploading a JSON file
        * Allow uploading JSON to merge with existing file
        * Allow uploading JSON to replace existing file

    * Finish Conditions (see below)


* **NEW HOTNESS: VIEWS/BUTTONS**

    * Probably useful to have some kind of generic RezbotView base class
        * When bot dies (through >die or otherwise?) close (ie. call ontimeout) ALL UI Views

    * View/Button/Slash command interfaces for browsing/managing uploaded files

    * Slash command autocomplete is nice, but make it *try* interpreting a non-autocompleted input too, so you don't have to wait for it if you're certain


* **General:**
    * Ability to disable specific features (commands, patterns, pipes) in specific channels/servers
    * rewrite `help` to spam less
    * come up with a name for the scripting language
    * Global "existing name directory" so you can never have overlapping source/pipe/spout/event/macro names, even if they're unique within their category?

* **SCRIPTING:**

    * Objects need a ".display_name" or something e.g. `Pipe: convert`, `Pipe Macro: smoog`, `OnMessage Event: spinkus`

    * **Script analysis:**
        * Warn if certain parallel pipes are unreachable for the given groupmode

    * **Parameters:**
        * Possibly warn about unused pieces of argstring (e.g. `{txt file=heck hell}` warns about `hell` being there for no reason)

    * **Sources:**
        * `creates_min: int` and `creates_max: int|None` attributes, idk, would be fun
            * `creates: int` which sets both at once

    * **Pipes:**
        * (Nothing)

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

    * **EVENTS:**
        * Thing where being enabled/disabled is a layered structure with "yes/unset/no" flags per Channel/Server/Global
            * ie. for a message in a channel it looks up through the chain for the first definite "yes" or "no"
        * Validate/static analysis on code changed by the Edit Event box widget
        * Now that they're not Pickled anymore, they can be holding on to the PipelineWithOrigin of their respective script, instead of the LRU thing?
        * more types of event triggers: MESSAGE CONTAINS (regex), USER IS (username/id), TIME IS (?), logical operations?? ????
            * `ON CONDITION ({message} ILIKE /^hello/ AND {get {me id}_evil} IS TRUE)`
        * `ON COMMAND !praise name` would allow acces to argument `name` by using `{arg name}`?

    * **GROUP MODES:**
        * #a:b,c:d,e:f [pipe1|pipe2|pipe3]           should work as is obvious
        * (1,2,3) [pipe1|pipe2|pipe3]       should kinda work as    (6) (#0:1,1:3,3:6 [pipe1|pipe2|pipe3])
        * (same for others???)

    * **CONDITIONS:**
        * WIP: Errors in applying are not properly caught/conveyed.
            * e.g. Evaluation: Warnings that aren't terminal aren't conveyed
            * e.g. Evaluation: `foo > 10` raises an uncaught ValueError
        * More aggregate conditions
            * "ALL ARE WHITE/EMPTY/BOOL/TRUE/FALSE/INT/FLOAT"
            * "COUNT > 10"
        * WIP: How does implicit `{}` tracking work? It should probably just refuse it entirely, right?

    * **PARSING BUGS:**
        * `>> foo > bar x=( > baz` doesn't understand the ( should be a character and not a parenthesis (circumventable by writing `x="("`)

    * **SPECULATIVE:**
        * Allow pipe(line)s as arguments, somehow?
            * e.g. `sub_func from=\b(\w) to=( convert fraktur )`
        * Option to post minimal warnings logs + command to show most recent warnings log
            * Per Channel/per Event?
        * Special mode to analyse how a pipeline is parsed for debugging or learning purposes
        * conditional `return` pipes so loops are easier?
        * pipes have an associated "complexity" cost function based on args/input values that makes sure a user doesn't request absurdly much work...?