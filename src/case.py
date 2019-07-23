import re

CASE_RE = re.compile(r'^([^()]*)(?:\(([^()]+)\)([^()]*))?$')

CASE_UPP = object()
CASE_LOW = object()
CASE_XOR = object()
CASE_NOP = object()

def case_parse(s):
    out = []
    for c in s:
        if c.isupper(): out.append(CASE_UPP)
        elif c.islower(): out.append(CASE_LOW)
        elif c == '^': out.append(CASE_XOR)
        else: out.append(CASE_NOP)
    return out

def apply_case(c, i):
    if c is CASE_UPP: return i.upper()
    if c is CASE_LOW: return i.lower()
    if c is CASE_XOR: return (i.upper() if i.islower() else i.lower())
    if c is CASE_NOP: return i

def case(pattern, inputs):
    m = re.match(CASE_RE, pattern)
    if m is None:
        raise ValueError('Invalid case pattern "%s"' % pattern)
    
    head, body, tail = m.groups()
    outputs = []
    
    if body is None:
        for input in inputs:
            output = []
            for i, c in zip(input, case_parse(head)):
                output.append(apply_case(c, i))
            output.append(input[len(head):])
            outputs.append(''.join(output))

    else:
        lh, lb, lt = len(head), len(body), len(tail)
        head, body, tail = case_parse(head), case_parse(body), case_parse(tail)

        for input in inputs:
            output = []
            li = len(input)

            for i, c in zip(input, head):
                output.append(apply_case(c, i))

            if li > lh:
                if li - lh < lt:
                    for i, c in zip(input[lh:], tail):
                        output.append(apply_case(c, i))
                else:
                    b = li - lh - lt
                    for i in range(b):
                        output.append(apply_case(body[i%lb], input[lh+i]))
                    if lt:
                        for i, c in zip(input[-lt:], tail):
                            output.append(apply_case(c, i))
            outputs.append(''.join(output))

    return outputs

inputs = ['hello', 'aaaaaaaaa', 'AaAaAaAaAaAa']
patterns = ['AAAAA', 'aa(AA)aa', 'XX(yy)', '(xx)YY', 'AAA(---)AAA', 'AAA(^^^)AAA']
for pattern in patterns:
    print(pattern)
    print('\n'.join('\t' + o for o in case(pattern, inputs)))
    print()