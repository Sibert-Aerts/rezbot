# Guide to using pipelines

## Introduction

Pipelines are a text-based scripting toy inspired by functional programming and shell scripts, with users able to post scripts directly to a Discord chatroom where the bot runs the scripts and posts the results in the chatroom.  
This way a group of discord users can easily use and compose unique bot features without needing much scripting experience or access to scripting tools.

The concept is that you start with a text **source** (e.g. chat messages, tweets, random dictionary words...)
and you modify them using **pipes** that perform some simple task on text (e.g. turning everything uppercase, swapping random letters, translating it...) and you can chain together multiple pipes in a row to create a **pipeline** which combines to perform a more complex task.

You can use this to set up a "game of telephone" by chaining translation pipes, construct ASCII/emoji-art, generate all kinds of random phrases, automatically respond to messages, compose poetry...

Over time, as the number of features grew, the language became more powerful and complex. However, a primary design goal has always been to make the basic scripting features as simple to use as possible, to be accessible to people with little to no scripting experience.  
At the same time, the more complex features are intended to invite an almost puzzle-solving approach from experienced programmers as they try to figure out the shortest/simplest/most elegant way of implementing an idea.

## Contents
1. [Introduction](#introduction)
2. [Basic Features](#basic-features)
    * [Sources](#sources) 
    * [Pipes](#pipes) 
    * [Arguments](#arguments)
    * [Print](#print) 
3. [Advanced Features](#advanced-features)
    * [Multiple lines](#multiple-lines) 
    * [Multi-line Start](#multi-line-start) 
    * [Group modes](#group-modes) 
    * [Parallel pipes](#parallel-pipes)

## Basic features

A basic pipeline has the following form:  
    `>>>[start] > [pipe] > [pipe] > ...`  
e.g.  
    `>>> Hello! > translate to=fr > convert to=fullwidth`  
Is a pipeline which takes "Hello!", translates it to French, and then converts it to fullwidth characters.  
This gives as output: `ｓａｌｕｔ！`
   

### Sources
**[start]** can just be literal text, e.g. `Hello world!`.  
But it can also contain **sources**, special elements that find/produce text, of the form `{name [args]}`  
    e.g. `{word}`, `Here's a simpsons quote: {simpsons}`, `dril once said "{dril q="my ass"}"`.
    
<details>
  <summary>Examples</summary>

  `>>>Hello, world!` produces `Hello, world!`  
  `>>>{word}` might produce `flops`  
  `>>>I told you, no {word} in the kitchen!` might produce `I told you, no descendents in the kitchen!`  
  `>>>My father once told me "{dril}"` might produce `My father once told me "thinking of becoming a "Pipes" dipshit"`  
  `>>>He yelled: {simpsons q=aurora}` might produce `He yelled: Good Lord! What is happening in there?`    
  </details>
<br>

The list of native sources can be seen using the `>sources` command.

### Pipes

In a pipeline, **[pipe]** is an item of the form `name [args]`.  
    e.g. `print`, `letterize p=0.3`, `translate from=en to=fr`
    
<details>
  <summary>Examples</summary>

  `>>>Hello, world! > letterize` might produce `Hebdo, wornd!`  
  `>>>Hello, world! > case A` produces `HELLO, WORLD!`  
  `>>>Hello, world! > convert fraktur` produces `ℌ𝔢𝔩𝔩𝔬, 𝔴𝔬𝔯𝔩𝔡!`  
  `>>>Hello, world! > translate to=fr > convert smallcaps` produces `ʙᴏɴᴊᴏᴜʀ ʟᴇ ᴍᴏɴᴅᴇ!`  
  </details>
<br>

The list of native pipes can be seen using the `>pipes` command.

### Arguments

Pipes and sources may take arguments (presented as **[args]** in the previous sections) this is a sequence of zero or more assignments of the form:  
`name=value` or `name="value that allows spaces and 'single quotes' in it"` or `name='value with "double quotes" in it!'`
If a pipe or source only has a single **required** argument, the `name=` part and quote marks may even be omitted entirely.
For pipes, arguments are also allowed to contain *sources*. 

<details>
  <summary>Examples</summary>

  `>>>{word pattern=ass}` might produce `grasshopper`  
  `>>>family > format f="The most important thing is {0}!"` produces `The most important thing is family!`  
  `>>>friends > format But {0} also matter!` produces `But friends also matter!`  
  `>>>money > format But {word} matters most of all!` might produce `But intonation matters most of all!`  
  `>>>{simpsons q=superintendent multiline=false} > translate to=fr` might produce `Pense que Skinner, pense.`  
  </details>
<br>

To see information on a source or pipe's possible arguments, use `>source sourceName` or `>pipe pipeName`

### Print

In a pipeline it can sometimes be fun or useful to know what the output was at a certain step of the process.
The `print` pipe records intermediate output to be included in the message the bot sends once the pipeline has completed running.
(The final output of the pipeline is automatically included in the message, so you don't need to put a `print` at the end of every pipeline.)
Also, as a shorthand, `->` may be used in place of `> print >`.


<details>
  <summary>Examples</summary>

  `>>>Hello, world!` produces `Hello, world!`  
  `>>>Hello, world! > print` produces `Hello, world! → Hello, world!`  
  `>>>Hello, world! > print > convert fraktur` produces `Hello, world! → ℌ𝔢𝔩𝔩𝔬, 𝔴𝔬𝔯𝔩𝔡!`  
  `>>>Hello, world! -> convert fraktur` also produces `Hello, world! → ℌ𝔢𝔩𝔩𝔬, 𝔴𝔬𝔯𝔩𝔡!`  
  </details>
<br>

## Advanced features
Various advanced features that allow for more interesting use of pipelines.

### Multiple lines
So far we've only seen pipelines where each *start* produced only a single line of output, but it's possible for a pipe(line) to apply on multiple lines of input at once.  
For example: `>>>{2 words}` might produce:
```
reciprocates
gamuts
```
Unlike all previous examples, the bot produces two lines of output instead of one. Let's try adding pipes and prints to the command.  
`>>>{2 words} -> case A -> convert fullwidth` might produce:  
```
captor       → CAPTOR       → ＣＡＰＴＯＲ
deprogrammed → DEPROGRAMMED → ＤＥＰＲＯＧＲＡＭＭＥＤ
```
We see that `print` nicely formats the intermediate lines of output as different columns, and that the `case` and `convert` pipes simply apply to each individual input as one would expect.

Not all pipes are this simple, `split` for example, can be used to turn one line of input into multiple lines of output.  
`>>>Hello, world! > split on=,` produces:
```
Hello
 world!
```
One line of input "Hello, world!" is turned into two lines of output, "Hello" and " world!" by splitting on the character ",".

Conversely, there are also pipes that may expect multiple inputs. The pipe `join` for example takes any number of lines of input, and produces a single line of output:  
`>>>{3 words} > join s=" and "` might produce `rioters and intercepted and orbit`

### Multi-line Start
Some sources can produce multiple lines of output, as previously seen by the use of `{2 words}` and similar sources. This behaviour is sadly suppressed in the cases where a source is used inside a literal string, so `>>>I like {2 words}!` is identical to simply `>>>I like {word}!`, and will produce only a single line of output.

A different way of having the *start* produce multiple lines of output is the following notation:  
`>>> [Hi|hello], my name is J[im|ohn]` produces:
```
Hi, my name is Jim
hello, my name is Jim
Hi, my name is John
hello, my name is John
```
Brackets are allowed to be nested, and options are allowed to be empty, so the following is also possible:  
`>>> My name is J[im[|my|bo]|ohn[|son]]` produces:
```
My name is Jim
My name is Jimmy
My name is Jimbo
My name is John
My name is Johnson
```
But more simply, this allows for an easy way to write multiple lines of input:  
`>>>first|second|third!` produces:
```
first
second
third!
```
As three individual lines of input!

Additionally, a special "[?]" flag at the start will only result in a single *random* possible output to be picked:  
`>>>[?]My name is J[im[|my|bo]|ohn[|son]]` may produce `My name is John`.

### Group modes
Group modes are syntax that allow you to decide how inputs are grouped together when a pipe processes them. 

As we previously saw, the `join` pipe takes all input it is given and turns them into a single output. By default the pipeline will feed *all* lines into a pipe as a single group, but by using group modes we can change that.

#### Normal grouping
`>>>one|two|three|four > (2) join s=" and "` produces:
```
one and two
three and four
```
The `(2)` after the `>` and before `join`, tells the pipe to process the inputs in groups of 2.

#### Divide grouping
`>>>one|two|three|four|five > /2 join s=" and "` produces:
```
one and two and three
four and five
```
The `/2` splits the input into 2 groups of roughly equal size.

#### Modulo grouping

`>>>one|two|three|four|five|six > %2 join s=" and "` produces:
```
one and three and five
two and four and six
```
The `%2` splits the input into 2 groups, determined by the line numbers beind identical modulo 2.

#### Index grouping
`>>>zero|one|two > #1 convert fullwidth` produces:
```
zero
ｏｎｅ
two
```
The `#1` says to only apply the pipe to the line index 1 (the second line), leaving the other lines unchanged.

#### Interval grouping
`>>>zero|one|two|three > #1..3 convert fullwidth` produces:
```
zero
ｏｎｅ
ｔｗｏ
three
```
The `#1..3` says to only apply the pipe to the lines index 1 through (but not including) 3, leaving the other lines unchanged.

For more precise documentation of group mode workings, please read the huge comment at the start of [groupmodes.py](src/pipes/groupmodes.py).


### Parallel pipes
Now that we know how to produce multiple rows of input and how to control their grouping, we can start applying different pipes in parallel.

In a normal pipeline pipes are applied in sequence. Using parallel pipes we can branch the flow to have different parts of the flow go through different pipes. This system also re-uses the multi-line syntax from earlier. Let's start with an example:  
`>>>one|two|three|four > (2)[convert fullwidth | convert fraktur]` produces:
```
ｏｎｅ
ｔｗｏ
𝔱𝔥𝔯𝔢𝔢
𝔣𝔬𝔲𝔯
```
Two pipes are written in parallel: `convert fullwidth` and `convert fraktur`. The group mode `(2)` takes the input in groups of 2, sends the **first** group to the **first** parallel pipe, the **second** group to the **second** parallel pipe. Each line of input only goes through a *single* pipe on its way to the end of the pipeline. 

The group mode is key, as illustrated in this example:  
`>>>one|two|three > [convert fullwidth | convert fraktur]` just produces:
```
ｏｎｅ
ｔｗｏ
ｔｈｒｅｅ
```
`convert fraktur` is not applied to any input. This is because by default all input is considered as a single group (equivalent to `/1`), and this single group is only fed into the first of the parallel pipes, making the other parallel pipes useless.

Notation is also not very rigid, following the same logic as multi-line starts discussed above:
`>>>one|two|three|four > (1) convert [fullwidth|smallcaps]` produces:
```
ｏｎｅ
ᴛᴡᴏ
ｔｈｒｅｅ
ꜰᴏᴜʀ
```
If there are more input groups than there are parallel pipes it simply cycles through them.

#### Multiply mode
Another desirable feature is to apply a group of inputs to *every* pipe in a sequence.  
`>>> Hello > * convert [fraktur|fullwidth|smallcaps]` produces:
```
ℌ𝔢𝔩𝔩𝔬
Ｈｅｌｌｏ
ʜᴇʟʟᴏ
```
The `*` makes it apply each group of input to each of the parallel pipes. Watch out as this can easily produce a large number of output rows. If you want to specify a group mode, write it after the asterisk, like so: `*(1) convert` or `*/2 join`.


### Input as arguments
As previously seen, arguments are usually hard-coded values (ignoring *sources* in the arguments which are re-evaluated each time the pipe is executed). An advanced feature is the ability to take a line of input to a pipe and use it as an *argument* instead of as input.

For example: `>>> Hello|fr > translate to={1}` produces `Bonjour`  
This is what happens internally when executing that script.
* The pipe `translate to={1}` receives the input items `Hello` and `fr`
* When parsing the arguments, it replaces `{1}` with the "1th" input item: `fr`, so the argument string becomes `to=fr`
* `fr` is **discarded** because it was inserted into the argument string
* `Hello` is passed as input to `translate` with arguments `to=fr`, producing `Bonjour`

Note the second-to-last bullet: By default, all input items that are inserted into the argument string are discarded, this way the item is *only* used as an argument. If you don't want this behaviour (for example, you want to use it as an argument for multiple pipes in a row), putting an exclamation mark `!` at the end of the index causes a different behaviour:

For example: `>>> Hello|fr > translate to={1!}` produces two line of output: `fr` and `Bonjour`  
The same set of steps happens here, except the second-to-last bullet is replaced by:
* `fr` is **ignored** as input to `translate`, and is instead directly **prepended** to the output.

In a general case where multiple items are inserted this way, they are prepended to the output in their original order.

e.g. `>>>Bonjour|es|fr > translate from={2!} to={1!}` produces the output `es`, `fr`, `Buenos dias` in that order.


### Conditional branching (WIP)
A WIP feature that directs input to one of multiple given pipe(line)s based on conditions on the input.

Example: Consider a pipe macro named `example` defined as  
`{0 = "yes" | 0 = "no" }[ format Heck yeah! | format Oh no! | format Ah jeez! ]`  
Then: `>>> yes > example` produces `Heck yeah!`  
`>>> no > example` produces `Oh no!`  
and any other input just produces `Ah jeez!`
