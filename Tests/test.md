# Prior to Pushing to Production Checklist

# Job Scheduler Testing Checklist
## Auth & Mapper Jobs
| Job Type | Book Name      | Active | Stored Successfully |
|----------|----------------|--------|--------------------|
| AUTH     | fourcx         | ✅     | ✅                  |
| AUTH     | fanduel_picks  | ✅     | ✅                  |
| AUTH     | caesars        | ✅     | ✅                  |
| AUTH     | chalkboard     | ✅     | ✅                  |
| AUTH     | kibl           | ✅     | ✅                  |
| AUTH     | onyx           | ❌     | ❌                  |
| AUTH     | ownerbox       | ❌     | ❌                   |
| MAPPER   | betmgm         | ✅     | ✅                   |
| MAPPER   | caesars        | ✅     | ✅                   |
| MAPPER   | fanduel        | ✅     | ✅                   |
| MAPPER   | onyxodds       | ❌     | ❌                   |
| MAPPER   | kibl           | ✅     | ✅                   |

# Celery Tasks / Beat
# Sportsbooks – Storing in Cache
| Book Name      | Type                 | Active | Stored Successfully |
|---------------|----------------------|-------|---------------------|
| underdog      | dfs                  | ✅    | ✅                    |
| betr          | dfs                  | ✅    | ✅                    |
| boom          | dfs                  | ✅    | ✅                    |
| chalkboard    | dfs                  | ✅    | ✅                    |
| dabble        | dfs                  | ✅    | ✅                    |
| drafters      | dfs                  | ❌     | ❌                    |
| pick_6        | dfs                  | ✅    | ✅                    |
| epicks        | dfs                  | ✅    | ✅                    |
| fanduel_picks | dfs                  | ✅    | ✅                    |
| ownerbox      | dfs                  | ❌    | ❌                    |
| parlaye       | dfs                  | ✅    | ✅                    |
| parlayplay    | dfs                  | ✅    | ✅                    |
| prizepicks    | dfs                  | ✅    | ✅                    |
| sleeper       | dfs                  | ✅    | ✅                    |
| splashsports  | dfs                  | ❌    | ❌                    |
| 4cx           | prediction_liquidity | ✅    |                     |
| bet105        | sportsbook           | ✅    |                     |
| stg           | sportsbook           | ✅    |                     |
