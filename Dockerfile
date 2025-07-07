FROM entsupml/unison-runner:latest
RUN mkdir /loader
COPY requirements.txt /loader/
RUN cd /loader && pip install --no-cache-dir -r requirements.txt
COPY loader.py /loader
ENTRYPOINT cd /loader; python /loader/loader.py || exit 1; echo "DB loaded"; cd /app; pip install -r requirements.txt; while true; do python main.py; sleep 3; done
