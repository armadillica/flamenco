#!/bin/bash -e

GID=$(id --group)

# Use Docker to get Go in a way that allows overwriting the
# standard library with statically linked versions.
docker run -i --rm \
    -v $(pwd):/docker \
    -v "${GOPATH}:/go-local" \
    --env GOPATH=/go-local \
     golang /bin/bash -e << EOT
go version
cd \${GOPATH}/src/flamenco-manager
CGO_ENABLED=0 go get -a -ldflags '-s'
cp \${GOPATH}/bin/flamenco-manager /docker
chown $UID:$GID /docker/flamenco-manager
EOT
