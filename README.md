# Flamenco Server

This is the Flamenco Server component, implemented as a Pillar extension.
Documentation can be found at https://flamenco.io/docs/.

## Development Setup

In order to get Flamenco up and running for development, we need to follow these steps:

- Install requirements with `pip install -r requirements-dev.txt`
- Install Flamenco Server locally with `pip install -e .`
- Add Flamenco as Pillar extension to our project
- Give a user 'subscriber' or 'demo' role to obtain flamenco-use capability, or set up your own
  mapping from role to `flamenco-use` and `flamenco-view` capabilities
- Run `./gulp`
