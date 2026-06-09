import re
with open(r'D:\code\a_js\proj\rt\public\algos\rotate-list.toml', 'r', encoding='utf-8') as f:
    text = f.read()
blocks = re.findall(r'code = """(.*?)"""', text, re.DOTALL)
print(f'Found {len(blocks)} code blocks')
all_ok = True
for i in range(len(blocks)-1):
    prev = blocks[i]
    curr = blocks[i+1]
    prev_lines = prev.split('\n')
    curr_lines = curr.split('\n')

    # Check common prefix (line-based)
    pfx = 0
    while pfx < min(len(prev_lines), len(curr_lines)) and prev_lines[pfx] == curr_lines[pfx]:
        pfx += 1
    # Check common suffix (line-based)
    sfx = 0
    while (sfx < min(len(prev_lines), len(curr_lines) - pfx) and
           prev_lines[-1 - sfx] == curr_lines[-1 - sfx]):
        sfx += 1

    if pfx + sfx >= min(len(prev_lines), len(curr_lines)):
        added = curr_lines[pfx:len(curr_lines) - sfx if sfx else len(curr_lines)]
        print(f'Step {i} -> Step {i+1}: PASS (pfx={pfx}, sfx={sfx}, added {len(added)} lines)')
    else:
        all_ok = False
        print(f'Step {i} -> Step {i+1}: FAIL (pfx={pfx}, sfx={sfx})')
        print(f'  prev last pfx line: {prev_lines[pfx-1] if pfx else "<none>"!r}')
        print(f'  curr diverge line:   {curr_lines[pfx]!r}')
        print(f'  prev diverge line:   {prev_lines[pfx]!r}')

print('Line counts:', [len(b.split('\n')) for b in blocks])
print('OVERALL:', 'PASS' if all_ok else 'FAIL')