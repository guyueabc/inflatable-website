import sys
c = open('app.py', encoding='utf-8').read()

# Find and replace the wrong function
import re
pattern = r'def api_my_models\(\).*?(?=\n@app\.route|\n# ----|\Z)'
match = re.search(pattern, c, re.DOTALL)
if match:
    print(f'Found wrong function: {match.start()} to {match.end()}')
    print('Content:', match.group(0)[:60])
