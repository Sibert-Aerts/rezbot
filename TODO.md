# To Do List

(In no particular order)

* **General:**
    * Ability to disable specific features (commands, patterns, pipes) in specific channels/servers
    * rewrite `help` to spam less
    * come up with a name for the scripting language

* **SCRIPTING:**

    * **Script analysis:**
        * Warn if certain parallel pipes are unreachable for the given groupmode
        * Same, but with even more 

    * **Signatures:**
        * options can be smarter (e.g. "nick" works to match "nickname" if it's the only option starting with "nick")
        * ability to mark a Sig as "The One" even if it has a default value
        * Possibly warn about unused pieces of argstring

    * **Sources:**
        * Recursively parse sources, e.g. `{source1 arg={source2}}`

    * **Pipes:**
        * Nothing

    * **Uploaded files:**
        * "Append to file" spout (which creates a new file if it doesn't exist yet)
        * "replace specified line" spout

    * Way of easily turning macros into commands
    * Namespaces/Categories for user-made scripts (macros/events)
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

    * **GROUP MODES:**
        * #a..b;c..d;e..f [pipe1|pipe2|pipe3]           should work as is obvious
        * (1;2;3) [pipe1|pipe2|pipe3]       should kinda work as    (6) (#0..1;1..3;3..6 [pipe1|pipe2|pipe3])
        * (same for others???)

    * **CONDITIONS:**
        * Different syntax, {}'s already mean a kind of specific thing!
        * Add logical operations: NOT/AND/OR/XOR
        * Evaluating pipes or sources inside condition expressions?
    
    * **PARSING BUGS:**
        * `>> foo > bar x=( > baz` doesn't understand the ( should be a character and not a parenthesis (circumventable by writing `x="("`)
        * `>> foo > bar x='"' > baz` similarly, the " is interpreted as opening a string that is never closed, circumvented by adding a closing " afterwards but that's stupid
        * `>> """choice-escaped source"""` is not possible right now

    * **SPECULATIVE:**
        * Option to hide warnings log
        * Command to show most recent warnings log
        * Special mode to analyse how a pipeline is parsed for debugging or learning purposes
        * ChoiceTree flags:
            * [-] to produce a minimal number of lines that reach each choice leaf at least once (is this hard???)
                [-] [alpha|beta] [gamma|delta] → alpha gamma, beta delta
        * in pipe/source arguments, replace `\n` to newlines
        * conditional `return` pipes so loops are easier?
        * pipes have an associated "complexity" cost function based on args/input values that makes sure a user doesn't request absurdly much work...?

    * **??????**
        * Actually execute parallel pipes "in parallel" using asyncio????