#!/bin/bash -e

GID=$(id --group)
if [ ! -e flamenco-manager.yaml ]; then
    echo "Create a flamenco-manager.yaml for Docker in $(pwd), then run this command again." >&2
    exit 1
fi

HASH=$(git show-ref --head --hash HEAD | head -n 1)
EXPORT_TO=flamenco-manager-${HASH}.docker.tgz

# Use Docker to get Go in a way that allows overwriting the
# standard library with statically linked versions.
docker run -i --rm \
    -v $(pwd):/docker \
    -v "${GOPATH}:/go-local" \
    --env GOPATH=/go-local \
     golang /bin/bash -ex << EOT
go version
cd \${GOPATH}/src/flamenco-manager
CGO_ENABLED=0 go get -a -ldflags '-s'
cp \${GOPATH}/bin/flamenco-manager /docker
chown $UID:$GID /docker/flamenco-manager
EOT

# Use the statically linked executable to build our final Docker image.
docker build -t armadillica/flamenco-manager:${HASH} .

if docker ps -a --no-trunc --filter "name=flamenco-manager" | grep -q flamenco-manager; then
    echo
    echo '==> Docker container "flamenco-manager" already exists, press ENTER to remove and recreate.'
    read dummy
    docker stop flamenco-manager
    docker rm flamenco-manager
fi

docker save armadillica/flamenco-manager:${HASH} | gzip > ${EXPORT_TO}
echo Docker container created and exported to ${EXPORT_TO}

cat > flamenco-manager-install-${HASH}.sh << EOT
#!/bin/sh
gunzip < flamenco-manager-${HASH}.docker.tgz | docker load
echo
echo Image installed, create container with:
echo docker create --name flamenco-manager --net host  armadillica/flamenco-manager:${HASH}
EOT
chmod +x flamenco-manager-install-${HASH}.sh
