#!/usr/bin/env python

from pillar import PillarServer
from flamenco import FlamencoExtension

app = PillarServer('.')
app.load_extension(FlamencoExtension(), '/flamenco')
app.process_extensions()

if __name__ == '__main__':
    app.run('::0', 5000, debug=True)
