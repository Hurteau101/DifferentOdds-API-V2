# Configs
## Breakdown
`unique_name` - The unique name assigned to the SGP. (Primary Key)
`league` - The league that the SGP is associated with.

`espn_league` - The league that ESPN uses for that SGP. This is neded when mapping is required.

`sport` - This is the sport that the SGP is associated with. This is used for ESPN mapping.

`stat_type` - This is a list of the stat types. 

`group_fields` - This is used for grouping. Having ['event', 'date', 'team'] will group by event, date, and team. Having teams ensures that the teams all match in the SGP.
Whereas '[event, 'date']' will group by event and date and won't take in account for the team, so the SGP could be markets/players from either team.

`direction` - This is a list of directions. Create all possible direction combinations based on the provided directions and selection odds.

`use_same_player` - This is a boolean that indicates whether to use the same play for all selections. If true, the SGP 
will only use one play for all selections and can't be the same stat_type ((Ex. over 3.5 and over 4.5 for the same player). If false, the SGP will use different plays for each selection.

`validate_players` - This is a boolean that indicates whether to validate players. If using `use_same_play` is true, then this should be True.

`minimum_ev` - This is the minimum EV for the discord alerts. If the SGP has an EV below this threshold, it won't be included.

`number_of_unique_books` - This is the minimum number of unique books required for the SGP. If the SGP doesn't have at least this many unique books, it won't be included.

`movement` - This is currently not used and will be disabled soon.

`active` - This is a boolean that indicates whether the SGP is active. If false, the SGP won't be run for this config.
