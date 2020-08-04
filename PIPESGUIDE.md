# Guide to using pipelines

## Introduction

Pipelines are a text-based scripting toy inspired by functional programming and shell scripts, with users able to post scripts directly to a Discord chatroom where the bot runs the scripts and posts the results in the chatroom. This way a group of discord users can easily use and create unique bot features without needing much experience, access to scripting tools or without having to leave the Discord window.

The language's basic premise is that you start with a text **source** (e.g. chat messages, tweets, random dictionary words...)
and you modify them using **pipes** that perform some simple task on text (e.g. turning everything uppercase, swapping random letters, translating it...) and you can chain together multiple pipes in a row to create a **pipeline** which combines to perform a more complex task.

Examples of what you can do in the language include chaining different translation pipes together to achieve a "game of telephone" effect, constructing ASCII/emoji-art, generating new phrases by randomly combining existing phrases, automatically responding to messages, composing poetry...

Over time, as the number of features grew, the language became more complex, but a primary design goal has always been to make the most basic scripting features as accessible as possible, as to be usable by people with relatively little experience with programming languages.
On the other hand, some of the more complex features may invite a puzzle-solving approach from more experienced programmers to try to figure out the shortest, simplest or most elegant solution to a scripting problem.

## Contents
1. [Introduction](#introduction)
2. [Basic Features](#basic-features)
    * [Sources](#sources)
    * [Pipes](#pipes)
    * [Spouts](#spouts)
    * [Parameters](#parameters)
    * [Print](#print)
3. [Advanced Features](#advanced-features)
    * [Multiple items](#multiple-items) 
    * [Multi-item Start](#multi-item-start) 
    * [Group modes](#group-modes) 
    * [Parallel pipes](#parallel-pipes)
    * [Input as arguments](#input-as-arguments)
    * [Conditional branching (WIP)](#conditional-branching-wip)

## Basic features

![A diagram showing a simple pipeline](https://i.imgur.com/gWzqpQc.png)

A basic script has the following form:  
    `>> [start] > [pipe] > [pipe] > ...`  
For example:  
    `>> Hello! > translate to=fr > convert to=fraktur`  
is a script which takes the text "Hello!", translates it to French, and then converts it to fraktur lettering.  
If you copy the above code (including the starting `>>`) and paste it in a chatroom where a Rezbot is active, it should reply: `𝔰𝔞𝔩𝔲𝔱!`

Sending a message in a chatroom with a Rezbot present is the only way to directly run scripts, and all example scripts in the rest of this document can be tried out in this same way. If you want access to a server where you can try out Rezbot, send me (Rezuaq#0736) a message on Discord.

### Sources
The **[start]** part of a script can be literal text, e.g. `Hello world!`,
but it can also contain **sources**, which are special elements that produce various kinds of text.  
A source is used by writing `{ [sourceName] [arguments] }`, for example `{word}` or `{simpsons q=steam}`.
Sources can be used on their own, for example `>>{word}` is a script that will fetch a single random dictionary word,
but sources may also be mixed in with a piece of text, for example `>> I love {word}, but I hate {word}!` is a script that may produce "I love fronts, but I hate newspapermen!"
    
<details>
  <summary>Examples</summary>

  `>> Hello, world!` produces `Hello, world!`  
  `>> {word}` might produce `flops`  
  `>> I told you, no {word} in the kitchen!` might produce `I told you, no descendents in the kitchen!`  
  `>> My father once told me "{dril}"` might produce `My father once told me "pyramid was the first haunted hous.e Fact."`  
  `>> He yelled: {simpsons q=aurora}` might produce `He yelled: Good Lord! What is happening in there?`    
  </details>
<br>

Use the `>sources` command to see a list of sources.

### Pipes

A **pipe** is a scripting element that takes some input text, applies some transformation to it, and outputs some other text.  
A pipe is used by writing `[pipeName] [arguments]`, for example `strip` or `translate from=en to=de`.
A sequence of pipes should be separated using greater than signs (`>`), and will result in the different pipes being applied in sequence from left to right, with each pipe receiving the output from the previous pipe as input. For example `translate to=de > case (A)` first translates text to German, and then turns the translated text entirely uppercase.  
From a programming perspective, a pipe is a function that takes strings (and possibly some arguments) and returns strings. From a functional perspective, most pipes are *pure*: deterministic and without side-effects.
    
<details>
  <summary>Examples</summary>

  `>> Hello, world! > letterize` might produce `Hebdo, wornd!`  
  `>> Hello, world! > case (A)` produces `HELLO, WORLD!`  
  `>> Hello, world! > convert fraktur` produces `ℌ𝔢𝔩𝔩𝔬, 𝔴𝔬𝔯𝔩𝔡!`  
  `>> Hello, world! > translate to=fr > convert smallcaps` produces `ʙᴏɴᴊᴏᴜʀ ʟᴇ ᴍᴏɴᴅᴇ!`  
  </details>
<br>

Use the `>pipes` command to see a list of pipes.

### Spouts

A **spout** is a variation of pipe that has the special attribute that it does not transform its inputs whatsoever.
Instead, a spout will perform some kind of *side effect*, for example: posting a message, writing inputs to a file, storing inputs as a variable, etc.  
From a functional perspective, spouts are the opposite of pure: they *only* have side-effects.  

(As of writing, a minor quirk with spouts: When a script is ran, the default behaviour is to post the final output of the script as a Discord message, if however any kind of spout is encountered during the script's execution, this quietly prevents that default behaviour. If you instead want to make sure script output is posted as a message, use the `send_message` spout.)
    
<details>
  <summary>Examples</summary>

  `>> Hello, world! > react 😂` will cause a 😂 reaction to your message, but produces no other output  
  `>> Hello, world! > embed` produces `Hello, world!` displayed inside a Discord embed  
  `>> Hello, world! > set myVar` produces no output, but `>>{get myVar}` will now produce `Hello, world!`
  </details>
<br>

Use the `>spouts` command to see the list of spouts.

### Parameters

Sources, pipes and spouts may have **parameters**, which are listed by using the commands `>source sourceName`, `>pipe pipeName` or `>spout spoutName` respectively.  
A parameter will be listed as:
* <ins>param</ins>: Description of the parameter. (*paramType*, default: *paramDefault*)

This indicates that the parameter is called `param`, its type is *paramType* (usually `str` for "string", `int` for "integer" or `parse_bool` for "true or false"), and that if it isn't passed an argument, it will use the default value *paramDefault*.

Arguments may be passed to a parameter using the notation `param=argWithoutSpaces` or `param="argument with spaces and 'single' quotes"` or `param='argument with spaces and "double" quotes'`, with different assignments separated by spaces.  
In the case of an element only having a single parameter, or only a single *required* parameter, the `param=` and enclosing quotation marks may be omitted. For example, `join s="+"`, `join s=+` and `join +` all do the same thing.  
For pipes and spouts, arguments are also allowed to use sources. 

<details>
  <summary>Examples</summary>

  `>> {word pattern=ass}` might produce `grasshopper`  
  `>> family > format f="The most important thing is {0}!"` produces `The most important thing is family!`  
  `>> friends > format But {0} also matter!` produces `But friends also matter!`  
  `>> money > format But {word} matters most of all!` might produce `But intonation matters most of all!`  
  `>> {simpsons q=superintendent multiline=false} > translate to=fr` might produce `Pense que Skinner, pense.`  
  </details>
<br>

To see information on a source or pipe's possible arguments, use `>source sourceName` or `>pipe pipeName`

### Print

`print` is a unique spout that allows you to see a script's intermediate output alongside the final output.
By default, the final output of each script is automatically `print`ed, so you never have to put a `print` at the end of a script.
For ease of use, the *print arrow* `->` may be used, which is equivalent to writing `> print >`.


<details>
  <summary>Examples</summary>

  `>> Hello, world!` produces `Hello, world!`  
  `>> Hello, world! > print` produces `Hello, world! → Hello, world!`  
  `>> Hello, world! > print > convert fraktur` produces `Hello, world! → ℌ𝔢𝔩𝔩𝔬, 𝔴𝔬𝔯𝔩𝔡!`  
  `>> Hello, world! -> convert fraktur` also produces `Hello, world! → ℌ𝔢𝔩𝔩𝔬, 𝔴𝔬𝔯𝔩𝔡!`  
  </details>
<br>



## Advanced features
Various advanced features that allow for more interesting use of pipelines.

### Multiple items
So far we've only seen examples where **[start]** only evaluated to a single piece of text (which we will refer to as an **item**). It is however possible for a script to handle more than one item at a time, for example: `>> {2 words}` might produce:
```
environment
precipitant
```
Not how, when a bot runs this script, the output message is now wrapped in a *code block* instead of the normal case where the bot posts script output unformatted. This is to indicate that the output of this very simple script contains *more than one* item, namely the two items `environment` and `precipitant`. In intuitive terms: two different *snippets* of text, in programming terms: two different *strings*.

`>> {2 words} -> case (A) -> convert fullwidth` might produce:  
```
cocktail → COCKTAIL → ＣＯＣＫＴＡＩＬ
gamuts   → GAMUTS   → ＧＡＭＵＴＳ
```
We see that `print` nicely formats the intermediate lines of output as different columns, and that the `case` and `convert` pipes seem to apply to each individual item as one would expect. You can visualise a script as a sort of flowchart:

![a diagram of the multi-item example](https://i.imgur.com/ayUZBgk.png)

(I left out the implicit `print` pipes since, being spouts, they do not affect the flow of the script)
<br><br>

Not all pipes are this simple, `split` for example, can be used to turn one line of input into multiple lines of output.  
`>> Hello, world! > split on=","` produces:
```
Hello
 world!
```
One line of input "Hello, world!" is turned into two lines of output, "Hello" and " world!" by splitting on the character ",". Note how " world!" starts with a space!

<img src=https://i.imgur.com/rKLMepZ.png width=50%><br><br>

Conversely, there are also pipes that may expect multiple inputs. The pipe `join` for example takes any number of lines of input, and produces a single line of output:  
`>> {3 words} > join s=" and "` might produce `rioters and intercepted and orbit`

<img src=https://i.imgur.com/2aTmGCD.png width=80%><br><br>

### Multi-item Start
Some sources can evaluate to multiple items, as previously seen when using `{2 words}` and similar sources. This behaviour is sadly suppressed in the cases where a source is used inside a literal string, so `>> I like {2 words}!` is identical to simply writing `>> I like {word}!`, and will evaluate to only a single item.

A different way of having the *[start]* evaluate to multiple items is the following notation:  
`>> one|two|three` produces three output items:
```
one
two
three
```
So you can simply use bars (`|`) to separate the different items that you want to use as your starting input, if you want to actually type a bar you have to escape it with a `\` backslash.  
The notation also allows for more complex constructions by using square brackets (`[]`):
`>> [Hi|Hello], my name is J[im|ohn]` produces:
```
Hi, my name is Jim
Hello, my name is Jim
Hi, my name is John
Hello, my name is John
```
i.e. square brackets allow you to describe a piece of text as being a *choice* of multiple different pieces of text separated by bars. The bot then expands these choices by picking every possible combination the different options that can be made, by going through every possible choice from left-to-right.  
Choices can even be nested: `>> My name is J[im[|my|bo]|ohn[|son]]` produces:
```
My name is Jim
My name is Jimmy
My name is Jimbo
My name is John
My name is Johnson
```
Try to look at that example and really see why it produces those outputs.  
Because nested choices creates a "tree" structure, this process is called "choice tree expansion". Square brackets can also be escaped using backslashes in case you want to use actual square brackets.

A different use: a "[?]" flag at the start will result in a single *random* possible combination to be picked:  
`>> [?]My name is J[im[|my|bo]|ohn[|son]]` may produce `My name is John` as its single output.  
This mode gives equal weight to each possible combination, e.g. for `[?][Tom|Will[|iam]]` is equally likely to evaluate as `Tom`, as `Will`, or as `William`.


### Group modes
Group modes are syntax that allow you to decide how inputs are grouped together when a pipe processes them. 

As we previously saw, the `join` pipe takes all input it is given and turns them into a single output. By default the pipeline will feed *all* items into a pipe "at once", as a single group, which is not always what we want. Group modes let us change that.

#### Row grouping
`>> one|two|three|four > (2) join s=" and "` produces two outputs:
```
one and two
three and four
```
The `(2)` after the `>` and before `join`, tells the bot to split the inputs into groups of 2, and to feed each group into the `split` pipe individually.  
Consider the following visualisation, with bundles of arrows represent how items are grouped:

<img src=https://i.imgur.com/BIjTOvI.png width=50%><br><br>

(The green arrows in the diagram indicate arrows affected by the group mode. A second "phantom" `join` pipe was added to more clearly visualise the fact the two groups of items are handled totally independently, as if there were two different `join` pipes at play. )

#### Divide grouping
`>> one|two|three|four|five > /2 join s=" and "` produces two outputs:
```
one and two and three
four and five
```
The `/2` splits the input into 2 groups of roughly equal size.

<img src=https://i.imgur.com/WSvnkem.png width=55%><br><br>

#### Modulo grouping

`>> one|two|three|four|five|six > %2 join s=" and "` produces two outputs:
```
one and three and five
two and four and six
```
The `%2` splits the input into 2 groups, determined by the line numbers beind identical modulo 2 (i.e. having the same remainder after division by 2; whether the number is even or odd).

<img src=https://i.imgur.com/TIPIE2m.png width=55%><br><br>

#### Column grouping

`>> one|two|three|four|five|six > \2 join s=" and "` produces three outputs:
```
one and four
two and five
three and six
```
This one is the least intuitive of them all, but the name "column" suggests considering the items as table: `\2` says to consider the list of items as a row-first matrix consisting of two rows (or equivalently: columns of height 2), and to take the resulting columns as the groups, going left to right. (Diagram to be added.)  
If that doesn't make any sense, don't worry, you'll never have to use this one.

<img src=https://i.imgur.com/D4jclVH.png width=55%><br><br>

#### Index grouping
`>> zero|one|two > #1 convert fraktur` produces:
```
zero
ｏｎｅ
two
```
The `#1` says to only apply the pipe to the item index 1 (the second item, since we start counting at 0), leaving the other items unchanged.

<img src=https://i.imgur.com/n6WC1hW.png width=50%><br><br>

(That is not a typo, "1th" ("oneth") is playful notation meant to distinguish it from "1st"; we're not actually selecting the *first* item.)

#### Interval grouping
`>> zero|one|two|three > #1:3 convert fullwidth` produces:
```
zero
ｏｎｅ
ｔｗｏ
three
```
The `#1:3` says to only apply the pipe to the items index 1 through (but not including) 3, leaving the other items unchanged.

<img src=https://i.imgur.com/qR5ckHV.png width=50%><br><br><br>

For more precise documentation of group mode workings and special cases, feel free to consult read the huge, meticulously formatted comment at the head of [groupmodes.py](src/pipes/groupmodes.py).


### Parallel pipes
Now that we know how to produce multiple rows of input and how to control their grouping, we can start applying different pipes in parallel.

In a normal pipeline pipes are applied in sequence. Using parallel pipes we can branch the flow to have different parts of the flow go through different pipes. This system also re-uses the multi-line syntax from earlier. Let's start with an example:  
`>> one|two|three|four > (2)[convert fullwidth | convert fraktur]` produces:
```
ｏｎｅ
ｔｗｏ
𝔱𝔥𝔯𝔢𝔢
𝔣𝔬𝔲𝔯
```
Two pipes are written in parallel: `convert fullwidth` and `convert fraktur`. The group mode `(2)` takes the input in groups of 2, sends the **first** group to the **first** parallel pipe, the **second** group to the **second** parallel pipe. Each line of input only goes through a *single* pipe on its way to the end of the pipeline. 

The group mode is key, as illustrated in this example:  
`>> one|two|three > [convert fullwidth | convert fraktur]` just produces:
```
ｏｎｅ
ｔｗｏ
ｔｈｒｅｅ
```
`convert fraktur` is not applied to any input. This is because by default all input is considered as a single group (equivalent to `/1`), and this single group is only fed into the first of the parallel pipes, making the other parallel pipes useless.

Notation is also not very rigid, following the same logic as multi-line starts discussed above:
`>> one|two|three|four > (1) convert [fullwidth|smallcaps]` produces:
```
ｏｎｅ
ᴛᴡᴏ
ｔｈｒｅｅ
ꜰᴏᴜʀ
```
If there are more input groups than there are parallel pipes it simply cycles through them.

#### Multiply mode
Another desirable feature is to apply a group of inputs to *every* pipe in a sequence.  
`>> Hello > * convert [fraktur|fullwidth|smallcaps]` produces:
```
ℌ𝔢𝔩𝔩𝔬
Ｈｅｌｌｏ
ʜᴇʟʟᴏ
```
The `*` makes it apply each group of input to each of the parallel pipes. Watch out as this can easily produce a large number of output rows. If you want to specify a group mode, write it after the asterisk, like so: `*(1) convert` or `*/2 join`.


### Input as arguments
As previously seen, arguments are usually hard-coded values (ignoring *sources* in the arguments which are re-evaluated each time the pipe is executed). An advanced feature is the ability to take a line of input to a pipe and use it as an *argument* instead of as input.

For example: `>> Hello|fr > translate to={1}` produces `Bonjour`  
This is what happens internally when executing that script.
* The pipe `translate to={1}` receives the input items `Hello` and `fr`
* When parsing the arguments, it replaces `{1}` with the "1th" input item: `fr`, so the argument string becomes `to=fr`
* `fr` is **discarded** because it was inserted into the argument string
* `Hello` is passed as input to `translate` with arguments `to=fr`, producing `Bonjour`

Note the second-to-last bullet: By default, all input items that are inserted into the argument string are discarded, this way the item is *only* used as an argument. If you don't want this behaviour (for example, you want to use it as an argument for multiple pipes in a row), putting an exclamation mark `!` at the end of the index causes a different behaviour:

For example: `>> Hello|fr > translate to={1!}` produces two line of output: `fr` and `Bonjour`  
The same set of steps happens here, except the second-to-last bullet is replaced by:
* `fr` is **ignored** as input to `translate`, and is instead directly **prepended** to the output.

In a general case where multiple items are inserted this way, they are prepended to the output in their original order.

e.g. `>> Bonjour|es|fr > translate from={2!} to={1!}` produces the output `es`, `fr`, `Buenos dias` in that order.


### Conditional branching (WIP)
A WIP feature that directs input to one of multiple given pipe(line)s based on conditions on the input.

Example: Consider a pipe macro named `example` defined as  
`{0 = "yes" | 0 = "no" }[ format Heck yeah! | format Oh no! | format Ah jeez! ]`  
Then: `>> yes > example` produces `Heck yeah!`  
`>> no > example` produces `Oh no!`  
and any other input just produces `Ah jeez!`
