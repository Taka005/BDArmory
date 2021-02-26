# Standard library imports
import argparse
import json
from collections import Counter
from pathlib import Path

parser = argparse.ArgumentParser(description="Tournament log parser", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument('tournament', type=str, nargs='?', help="Tournament folder to parse.")
parser.add_argument('-q', '--quiet', action='store_true', help="Don't print results summary to console.")
parser.add_argument('-n', '--no-files', action='store_true', help="Don't create summary files.")
args = parser.parse_args()
tournamentDir = Path(args.tournament) if args.tournament is not None else Path('')
tournamentData = {}


def CalculateAccuracy(hits, shots): return 100 * hits / shots if shots > 0 else 0


for round in sorted(roundDir for roundDir in tournamentDir.iterdir() if roundDir.is_dir()) if args.tournament is not None else (tournamentDir,):
	tournamentData[round.name] = {}
	for heat in sorted(round.glob("*.log")):
		with open(heat, "r") as logFile:
			tournamentData[round.name][heat.name] = {'result': None, 'duration': 0, 'craft': {}}
			for line in logFile:
				line = line.strip()
				if 'BDArmoryCompetition' not in line:
					continue  # Ignore irrelevant lines
				_, field = line.split(' ', 1)
				if field.startswith('Dumping Results'):
					tournamentData[round.name][heat.name]['duration'] = float(field[field.find('(') + 4:field.find(')') - 1])
				elif field.startswith('ALIVE:'):
					state, craft = field.split(':', 1)
					tournamentData[round.name][heat.name]['craft'][craft] = {'state': state}
				elif field.startswith('DEAD:'):
					state, order, time, craft = field.split(':', 3)
					tournamentData[round.name][heat.name]['craft'][craft] = {'state': state, 'deathOrder': int(order), 'deathTime': float(time)}
				elif field.startswith('MIA:'):
					state, craft = field.split(':', 1)
					tournamentData[round.name][heat.name]['craft'][craft] = {'state': state}
				elif field.startswith('WHOSHOTWHO:'):
					_, craft, shooters = field.split(':', 2)
					data = shooters.split(':')
					tournamentData[round.name][heat.name]['craft'][craft].update({'hitsBy': {player: int(hits) for player, hits in zip(data[1::2], data[::2])}})
				elif field.startswith('WHODAMAGEDWHOWITHBULLETS:'):
					_, craft, shooters = field.split(':', 2)
					data = shooters.split(':')
					tournamentData[round.name][heat.name]['craft'][craft].update({'bulletDamageBy': {player: float(damage) for player, damage in zip(data[1::2], data[::2])}})
				elif field.startswith('WHOSHOTWHOWITHMISSILES:'):
					_, craft, shooters = field.split(':', 2)
					data = shooters.split(':')
					tournamentData[round.name][heat.name]['craft'][craft].update({'missileHitsBy': {player: int(hits) for player, hits in zip(data[1::2], data[::2])}})
				elif field.startswith('WHODAMAGEDWHOWITHMISSILES:'):
					_, craft, shooters = field.split(':', 2)
					data = shooters.split(':')
					tournamentData[round.name][heat.name]['craft'][craft].update({'missileDamageBy': {player: float(damage) for player, damage in zip(data[1::2], data[::2])}})
				elif field.startswith('WHORAMMEDWHO:'):
					_, craft, rammers = field.split(':', 2)
					data = rammers.split(':')
					tournamentData[round.name][heat.name]['craft'][craft].update({'rammedPartsLostBy': {player: int(partsLost) for player, partsLost in zip(data[1::2], data[::2])}})
				elif field.startswith('CLEANKILL:'):
					_, craft, killer = field.split(':', 2)
					tournamentData[round.name][heat.name]['craft'][craft].update({'cleanKillBy': killer})
				elif field.startswith('CLEANMISSILEKILL:'):
					_, craft, killer = field.split(':', 2)
					tournamentData[round.name][heat.name]['craft'][craft].update({'cleanMissileKillBy': killer})
				elif field.startswith('CLEANRAM:'):
					_, craft, killer = field.split(':', 2)
					tournamentData[round.name][heat.name]['craft'][craft].update({'cleanRamKillBy': killer})
				elif field.startswith('OTHERKILL'):
					_, craft, reason = field.split(':', 2)
					tournamentData[round.name][heat.name]['craft'][craft].update({'otherKillReason': reason})
				elif field.startswith('ACCURACY:'):
					_, craft, accuracy = field.split(':', 2)
					hits, shots = accuracy.split('/')
					accuracy = CalculateAccuracy(int(hits), int(shots))
					tournamentData[round.name][heat.name]['craft'][craft].update({'accuracy': accuracy, 'hits': int(hits), 'shots': int(shots)})
				elif field.startswith('RESULT:'):
					heat_result = field.split(':', 2)
					result_type = heat_result[1]
					if (len(heat_result) > 2):
						teams = json.loads(heat_result[2])
						if isinstance(teams, dict):  # Win, single team
							tournamentData[round.name][heat.name]['result'] = {'result': result_type, 'teams': {teams['team']: ', '.join(teams['members'])}}
						elif isinstance(teams, list):  # Draw, multiple teams
							tournamentData[round.name][heat.name]['result'] = {'result': result_type, 'teams': {team['team']: ', '.join(team['members']) for team in teams}}
					else:  # Mutual Annihilation
						tournamentData[round.name][heat.name]['result'] = {'result': result_type}
				# Ignore Tag mode for now.

if not args.no_files:
	with open(tournamentDir / 'results.json', 'w') as outFile:
		json.dump(tournamentData, outFile, indent=2)


craftNames = sorted(list(set(craft for round in tournamentData.values() for heat in round.values() for craft in heat['craft'].keys())))
teamWins = Counter([team for round in tournamentData.values() for heat in round.values() if heat['result']['result'] == "Win" for team in heat['result']['teams']])
teamDraws = Counter([team for round in tournamentData.values() for heat in round.values() if heat['result']['result'] == "Draw" for team in heat['result']['teams']])
teams = {team: members for round in tournamentData.values() for heat in round.values() if 'teams' in heat['result'] for team, members in heat['result']['teams'].items()}
summary = {
	'craft': {
		craft: {
			'survivedCount': len([1 for round in tournamentData.values() for heat in round.values() if craft in heat['craft'] and heat['craft'][craft]['state'] == 'ALIVE']),
			'deathCount': (
				len([1 for round in tournamentData.values() for heat in round.values() if craft in heat['craft'] and heat['craft'][craft]['state'] == 'DEAD']),  # Total
				len([1 for round in tournamentData.values() for heat in round.values() if craft in heat['craft'] and heat['craft'][craft]['state'] == 'DEAD' and 'cleanKillBy' in heat['craft'][craft]]),  # Bullets
				len([1 for round in tournamentData.values() for heat in round.values() if craft in heat['craft'] and heat['craft'][craft]['state'] == 'DEAD' and 'cleanMissileKillBy' in heat['craft'][craft]]),  # Missiles
				len([1 for round in tournamentData.values() for heat in round.values() if craft in heat['craft'] and heat['craft'][craft]['state'] == 'DEAD' and 'cleanRamKillBy' in heat['craft'][craft]]),  # Rams
				len([1 for round in tournamentData.values() for heat in round.values() if craft in heat['craft'] and heat['craft'][craft]['state'] == 'DEAD' and not any(field in heat['craft'][craft] for field in ('cleanKillBy', 'cleanMissileKillBy', 'cleanRamKillBy')) and any(field in heat['craft'][craft] for field in ('hitsBy', 'missileHitsBy', 'rammedPartsLostBy'))]),  # Dirty kill
				len([1 for round in tournamentData.values() for heat in round.values() if craft in heat['craft'] and heat['craft'][craft]['state'] == 'DEAD' and not any(field in heat['craft'][craft] for field in ('hitsBy', 'missileHitsBy', 'rammedPartsLostBy')) and not any('rammedPartsLostBy' in data and craft in data['rammedPartsLostBy'] for data in heat['craft'].values())]),  # Suicide (died without being hit or ramming anyone).
			),
			'deathOrder': sum([heat['craft'][craft]['deathOrder'] / len(heat['craft']) if 'deathOrder' in heat['craft'][craft] else 1 for round in tournamentData.values() for heat in round.values() if craft in heat['craft']]),
			'deathTime': sum([heat['craft'][craft]['deathTime'] if 'deathTime' in heat['craft'][craft] else heat['duration'] for round in tournamentData.values() for heat in round.values() if craft in heat['craft']]),
			'cleanKills': (
				len([1 for round in tournamentData.values() for heat in round.values() for data in heat['craft'].values() if any((field in data and data[field] == craft) for field in ('cleanKillBy', 'cleanMissileKillBy', 'cleanRamKillBy'))]),  # Total
				len([1 for round in tournamentData.values() for heat in round.values() for data in heat['craft'].values() if 'cleanKillBy' in data and data['cleanKillBy'] == craft]),  # Bullets
				len([1 for round in tournamentData.values() for heat in round.values() for data in heat['craft'].values() if 'cleanMissileKillBy' in data and data['cleanMissileKillBy'] == craft]),  # Missiles
				len([1 for round in tournamentData.values() for heat in round.values() for data in heat['craft'].values() if 'cleanRamKillBy' in data and data['cleanRamKillBy'] == craft]),  # Rams
			),
			'assists': len([1 for round in tournamentData.values() for heat in round.values() for data in heat['craft'].values() if data['state'] == 'DEAD' and any(field in data and craft in data[field] for field in ('hitsBy', 'missileHitsBy', 'rammedPartsLostBy')) and not any((field in data and data[field] == craft) for field in ('cleanKillBy', 'cleanMissileKillBy', 'cleanRamKillBy'))]),
			'hits': sum([heat['craft'][craft]['hits'] for round in tournamentData.values() for heat in round.values() if craft in heat['craft'] and 'hits' in heat['craft'][craft]]),
			'bulletDamage': sum([data[field][craft] for round in tournamentData.values() for heat in round.values() for data in heat['craft'].values() for field in ('bulletDamageBy',) if field in data and craft in data[field]]),
			'missileHits': sum([data[field][craft] for round in tournamentData.values() for heat in round.values() for data in heat['craft'].values() for field in ('missileHitsBy',) if field in data and craft in data[field]]),
			'missileDamage': sum([data[field][craft] for round in tournamentData.values() for heat in round.values() for data in heat['craft'].values() for field in ('missileDamageBy',) if field in data and craft in data[field]]),
			'ramScore': sum([data[field][craft] for round in tournamentData.values() for heat in round.values() for data in heat['craft'].values() for field in ('rammedPartsLostBy',) if field in data and craft in data[field]]),
			'accuracy': CalculateAccuracy(sum([heat['craft'][craft]['hits'] for round in tournamentData.values() for heat in round.values() if craft in heat['craft'] and 'hits' in heat['craft'][craft]]), sum([heat['craft'][craft]['shots'] for round in tournamentData.values() for heat in round.values() if craft in heat['craft'] and 'shots' in heat['craft'][craft]])),
		}
		for craft in craftNames
	},
	'team results': {
		'wins': teamWins,
		'draws': teamDraws
	},
	'teams': teams
}

for craft in summary['craft'].values():
	spawns = craft['survivedCount'] + craft['deathCount'][0]
	craft.update({
		'damage/hit': craft['bulletDamage'] / craft['hits'] if craft['hits'] > 0 else 0,
		'hits/spawn': craft['hits'] / spawns if spawns > 0 else 0,
		'damage/spawn': craft['bulletDamage'] / spawns if spawns > 0 else 0,
	})

if not args.no_files:
	with open(tournamentDir / 'summary.json', 'w') as outFile:
		json.dump(summary, outFile, indent=2)

if len(summary['craft']) > 0:
	if not args.no_files:
		csv_summary = "craft," + ",".join(
			",".join(('deathCount', 'dcB', 'dcM', 'dcR', 'dcA', 'dcS')) if k == 'deathCount' else
			",".join(('cleanKills', 'ckB', 'ckM', 'ckR')) if k == 'cleanKills' else
			k for k in next(iter(summary['craft'].values())).keys()) + "\n"
		csv_summary += "\n".join(craft + "," + ",".join(str(int(100 * v) / 100) if not isinstance(v, tuple) else ",".join(str(int(100 * sf) / 100) for sf in v) for v in scores.values()) for craft, scores in summary['craft'].items())
		with open(tournamentDir / 'summary.csv', 'w') as outFile:
			outFile.write(csv_summary)

	if not args.quiet:
		# Write results to console
		strings = []
		headers = ['Name', 'Survive', 'Deaths (BMRAS)', 'D.Order', 'D.Time', 'Kills (BMR)', 'Assists', 'Hits', 'Damage', 'MisHits', 'MisDmg', 'Ram', 'Acc%', 'Dmg/Hit', 'Hits/Sp', 'Dmg/Sp']
		summary_strings = {'header': {field: field for field in headers}}
		for craft in sorted(summary['craft']):
			tmp = summary['craft'][craft]
			spawns = tmp['survivedCount'] + tmp['deathCount'][0]
			summary_strings.update({
				craft: {
					'Name': craft,
					'Survive': f"{tmp['survivedCount']}",
					'Deaths (BMRAS)': f"{tmp['deathCount'][0]} ({' '.join(str(s) for s in tmp['deathCount'][1:])})",
					'D.Order': f"{tmp['deathOrder']:.3f}",
					'D.Time': f"{tmp['deathTime']:.1f}",
					'Kills (BMR)': f"{tmp['cleanKills'][0]} ({' '.join(str(s) for s in tmp['cleanKills'][1:])})",
					'Assists': f"{tmp['assists']}",
					'Hits': f"{tmp['hits']}",
					'Damage': f"{tmp['bulletDamage']:.0f}",
					'MisHits': f"{tmp['missileHits']}",
					'MisDmg': f"{tmp['missileDamage']:.0f}",
					'Ram': f"{tmp['ramScore']}",
					'Acc%': f"{tmp['accuracy']:.2f}",
					'Dmg/Hit': f"{tmp['damage/hit']:.1f}",
					'Hits/Sp': f"{tmp['hits/spawn']:.1f}",
					'Dmg/Sp': f"{tmp['damage/spawn']:.1f}"
				}
			})
		column_widths = {column: max(len(craft[column]) + 2 for craft in summary_strings.values()) for column in headers}
		strings.append(''.join(f"{header:{column_widths[header]}s}" for header in headers))
		for craft in sorted(summary['craft']):
			strings.append(''.join(f"{summary_strings[craft][header]:{column_widths[header]}s}" for header in headers))

		teamNames = sorted(list(set([team for result_type in summary['team results'].values() for team in result_type])))
		default_team_names = [chr(k) for k in range(ord('A'), ord('A') + len(summary['craft']))]
		if len(teamNames) > 0 and not all(name in default_team_names for name in teamNames):  # Don't do teams if they're assigned as 'A', 'B', ... as they won't be consistent between rounds.
			name_length = max([len(team) for team in teamNames])
			strings.append(f"\nTeam{' '*(name_length-4)}\tWins\tDraws\tVessels")
			for team in teamNames:
				strings.append(f"{team}{' '*(name_length-len(team))}\t{teamWins[team]}\t{teamDraws[team]}\t{summary['teams'][team]}")
		for string in strings:
			print(string)
else:
	print("No valid log files found.")
