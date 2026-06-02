
import json
import re
from pathlib import Path

# Define paths relative to the script's execution
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "Site Data"
OUTPUT_FILE = DATA_DIR / "mlb_rosters.json"
ROSTER_FILES_DIR = Path("/opt/data/cache/documents")

def parse_roster_markdown(filepath):
    content = filepath.read_text(encoding='utf-8')
    
    # Extract metadata from front matter
    metadata_match = re.search(r'---\\nteam: (.+)\\nleague: (.+)\\ndivision: (.+)\\nupdated: (.+)\\ntags: \\[(.+)\\]\\n---', content, re.DOTALL)
    if not metadata_match:
        print(f"Could not parse metadata for {filepath.name}")
        return None

    team_name = metadata_match.group(1).strip()
    league = metadata_match.group(2).strip()
    division = metadata_match.group(3).strip()
    updated = metadata_match.group(4).strip()

    # Extract table data
    table_match = re.search(r'\| # \| Name \| Pos \| Bats \| Throws \| Age \| Height \| Weight \|\\n\|---|------|-----|------|--------|-----|--------|--------|\\n((?:\\|[^\\n]+\\|\\n?)+)', content)
    if not table_match:
        print(f"Could not parse roster table for {team_name}")
        return None

    player_lines = table_match.group(1).strip().split('\\n')
    players = []
    for line in player_lines:
        cells = [c.strip() for c in line.split('|') if c.strip()]
        if len(cells) == 8: # Ensure all columns are present
            players.append({
                'number': cells[0],
                'name': cells[1],
                'pos': cells[2],
                'bats': cells[3],
                'throws': cells[4],
                'age': int(cells[5]),
                'height': cells[6],
                'weight': cells[7],
            })
    
    return {
        'team': team_name,
        'league': league,
        'division': division,
        'updated': updated,
        'players': players
    }

def main():
    all_rosters = {'American League': [], 'National League': []}
    
    # List of provided roster files
    roster_files = [
        ROSTER_FILES_DIR / 'Kansas City Royals.md',
        ROSTER_FILES_DIR / 'Detroit Tigers.md',
        ROSTER_FILES_DIR / 'Cleveland Guardians.md',
        ROSTER_FILES_DIR / 'Chicago White Sox.md',
    ]

    for roster_file in roster_files:
        if roster_file.exists():
            roster_data = parse_roster_markdown(roster_file)
            if roster_data:
                if roster_data['league'] == 'American League':
                    all_rosters['American League'].append(roster_data)
                elif roster_data['league'] == 'National League':
                    all_rosters['National League'].append(roster_data)
                print(f"Parsed roster for {roster_data['team']} ({roster_data['league']})")
            else:
                print(f"Skipping {roster_file.name} due to parsing error.")
        else:
            print(f"Roster file not found: {roster_file.name}")

    # Ensure output directory exists
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    # Write to JSON file
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_rosters, f, indent=2, ensure_ascii=False)
    
    print(f"Successfully wrote MLB rosters to {OUTPUT_FILE}")

if __name__ == '__main__':
    main()
