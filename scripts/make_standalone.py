# usage: make_standalone.py  -- submission.html (artifact source, no <head>) -> 2026-SaintCon-Badge-Hack-Teardown.html (opens anywhere)
import os
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
src = open(os.path.join(ROOT, 'submission.html')).read()
src = src.replace('<meta name="claude:viewport-fit-sides" content="cover">\n', '', 1)
i = src.index('<div class="band band--hero">')
out = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
       '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
       + src[:i] + '</head>\n<body style="margin:0">\n' + src[i:] + '\n</body>\n</html>\n')
open(os.path.join(ROOT, '2026-SaintCon-Badge-Hack-Teardown.html'), 'w').write(out)
print('wrote 2026-SaintCon-Badge-Hack-Teardown.html')
