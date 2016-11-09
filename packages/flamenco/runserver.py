#!/usr/bin/env python

from pillar import PillarServer
from attract import AttractExtension

app = PillarServer('.')
app.load_extension(AttractExtension(), '/attract')
app.process_extensions()

if __name__ == '__main__':
    app.run('::0', 5000, debug=True)
