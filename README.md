This repository helps to run Unison Runner on top of your CSV files

## To run:
1. Register workspace https://app.hyperunison.com/settings/company/biobanks/create
2. After workspace registration Runner will be created and you will see Runner token
3. Place token to the .env file
4. Copy your CSV files to the csv/ folder. Note, only CSV files are acceptable. TSV will not work
5. run `docker compose up`
6. Open your workspace in app.hyperunison.com and see source tables and data. You may start mapping

## What will happen?
1. You CSV files will be uploaded to the PostgreSQL service
2. Runner will start, connect to Unison, connect to PostgreSQL and start scanning DB
3. You may start structural mapping immediately or wait until DB scanning to be finished


## To changes CSV files
1. Upload another CSV files
2. Run `docker compose restart`
3. Go to the runner data repositories tab: https://app.hyperunison.com/settings/company/biobanks
4. Open `RUNNERS` of the workspace and click `RESCAN DATA SOURCE`
5. Wait until runner will rescan files 
