# Guide to using pipes

## Introduction

Pipes are a text manipulation scripting toy that I slowly developed over time.
The concept is that you start with some piece(s) of text as a **source** (e.g. chat messages, tweets, random dictionary words...)
and you modify them using **pipes** that perform some simple task (e.g. turn everything uppercase, swap random letters, translate...)
and by chaining together multiple pipes in sequence you create a **pipeline**.

You can use this to set up a bizarre game of telephone by chaining translation pipes, create bizarre word-art or unicode monstrosities,
automatically produce memes, generate randomized lyrics, ...

## The basics

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
