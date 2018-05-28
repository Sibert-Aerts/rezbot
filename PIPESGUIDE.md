# Guide to using pipes

## Introduction

Pipes are a text manipulation scripting toy that I slowly developed over time.
The concept is that you start with some piece(s) of text as a **source** (e.g. chat messages, tweets, random dictionary words...)
and you modify them using **pipes** that perform some simple task (e.g. turn everything uppercase, swap random letters, translate...)
and by chaining together multiple pipes in sequence you create a **pipeline**.

You can use this to set up a bizarre game of telephone by chaining translation pipes, create bizarre word-art or unicode monstrosities,
automatically produce memes, generate randomized lyrics, ...

## Contents
1. [Introduction](#introduction)
2. [Basic Features](#basic-features)
    * [Sources](#sources) 
    * [Pipes](#pipes) 
    * [Arguments](#arguments)
    * [Print](#print) 
3. [Advanced Features](#advanced-features)
    * [Multiple lines](#multiple-lines) 
    * [Multi-line start](#multi-line-start) 
    * [Group modes](#group-modes) 
    * [Parallel pipes](#parallel-pipes)

## Basic features

The basic structure of a pipeline is as follows:
    `>>>[start] > [pipe] > [pipe] > ...`

### Sources
**[start]** can just be literal text, e.g. `Hello world!` or `Shited on Ya Doo Doo Ass`.  
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

Pipes and sources may take arguments, previously presented as **[args]**, this is a sequence of zero or more assignments of the form:  
`name=value` or `name="value that allows spaces and 'single quotes' in it"` or `name='value with "double quotes" in it!'`
If a pipe or source only has a single **required** argument, the `name=` part and quote marks may even be omitted entirely.

<details>
  <summary>Examples</summary>

  `>>>{word pattern=ass}` might produce `grasshopper`  
  `>>>family > format f="The most important thing is {}!"` produces `The most important thing is family!`  
  `>>>friends > format But {} also matter!` produces `But friends also matter!`  
  `>>>{simpsons q=superintendent multiline=false} > translate to=fr` might produce `Pense que Skinner, pense.`  
  </details>
<br>

To see information on a source or pipe's arguments, use `>source sourceName` or `>pipe pipeName`

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
We can see the `print` pipe treats multiple inputs by dividing the output into different lines and columns. The `case` and `convert` pipes simply apply to each individual input, one at a time.

Not all pipes are this simple, `split` for example, can be used to turn one line of input into multiple lines of output.  
`>>>Hello, world! > split on=,` produces:
```
Hello
 world!
```
One line of input "Hello, world!" is turned into two lines of output, "Hello" and " world!" by splitting on the character ",".

Conversely, there are also pipes that may expect multiple inputs. The pipe `join` for example takes any number of lines of input, and produces a single line of output:  
`>>>{3 words} > join s=" and "` might produce `rioters and intercepted and orbit`

### Multi-line start
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
