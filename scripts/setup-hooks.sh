#!/bin/bash
# Configure git to use the project's .githooks directory.
# Run once after cloning. Also run by `make setup-hooks`.
git config core.hooksPath .githooks
echo "Git hooks configured: .githooks/"
